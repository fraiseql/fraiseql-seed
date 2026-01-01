"""SeedBuilder API for declarative seed generation."""

from typing import Any

from fraiseql_uuid import Pattern
from psycopg import Connection

# Note: Backend and introspector imports moved to __init__ for lazy loading
from fraiseql_data.exceptions import (
    ColumnGenerationError,
    ForeignKeyResolutionError,
    SelfReferenceError,
    UniqueConstraintError,
)
from fraiseql_data.generators import FakerGenerator, TrinityGenerator
from fraiseql_data.models import SeedPlan, Seeds, TableInfo

# Constants for generation logic
MAX_UNIQUE_RETRIES = 10  # Maximum attempts to generate unique value


class BatchContext:
    """Context manager for batch seed operations with fluent API."""

    def __init__(self, builder: "SeedBuilder"):
        """
        Initialize batch context.

        Args:
            builder: SeedBuilder instance
        """
        self.builder = builder
        self._operations: list[SeedPlan] = []

    def add(
        self,
        table: str,
        count: int | Any,  # Allow callable
        strategy: str = "faker",
        overrides: dict[str, Any] | None = None,
    ) -> "BatchContext":
        """
        Add table to batch (chainable).

        Args:
            table: Table name
            count: Number of rows or callable returning count
            strategy: Generation strategy (default: "faker")
            overrides: Column overrides

        Returns:
            Self for chaining
        """
        # Resolve callable count immediately
        if callable(count):
            count = count()

        self._operations.append(
            SeedPlan(
                table=table,
                count=count,
                strategy=strategy,
                overrides=overrides or {},
            )
        )
        return self

    def when(self, condition: bool) -> "ConditionalContext":
        """
        Create conditional context for conditional operations.

        Args:
            condition: Whether to execute subsequent operations

        Returns:
            ConditionalContext for conditional chaining

        Example:
            >>> with builder.batch() as batch:
            >>>     batch.add("tb_manufacturer", count=10)
            >>>     batch.when(include_models).add("tb_model", count=50)
        """
        return ConditionalContext(self, condition)

    def execute(self) -> Seeds:
        """
        Execute all batched operations.

        Returns:
            Seeds object with generated data
        """
        # Add all operations to builder's plan
        for operation in self._operations:
            self.builder._plan.append(operation)

        # Execute builder
        return self.builder.execute()

    def __enter__(self) -> "BatchContext":
        """Enter context manager."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager - auto-execute if no exception."""
        if exc_type is None:
            self.execute()


class ConditionalContext:
    """Conditional operations for batch context."""

    def __init__(self, batch: BatchContext, condition: bool):
        """
        Initialize conditional context.

        Args:
            batch: Parent BatchContext
            condition: Whether to execute operations
        """
        self.batch = batch
        self.condition = condition

    def add(
        self,
        table: str,
        count: int | Any,  # Allow callable
        strategy: str = "faker",
        overrides: dict[str, Any] | None = None,
    ) -> BatchContext:
        """
        Add table only if condition is true.

        Args:
            table: Table name
            count: Number of rows or callable returning count
            strategy: Generation strategy
            overrides: Column overrides

        Returns:
            Parent BatchContext for continued chaining
        """
        if self.condition:
            # Resolve callable count if needed
            if callable(count):
                count = count()

            self.batch._operations.append(
                SeedPlan(
                    table=table,
                    count=count,
                    strategy=strategy,
                    overrides=overrides or {},
                )
            )

        return self.batch


class SeedBuilder:
    """Declarative API for building and executing seed data plans."""

    def __init__(
        self,
        conn: Connection | None,
        schema: str,
        backend: str = "direct",
    ):
        """
        Initialize SeedBuilder.

        Args:
            conn: PostgreSQL connection (None for staging backend)
            schema: Schema name
            backend: Backend type - "direct" (database) or "staging" (in-memory)

        Raises:
            SchemaNotFoundError: If schema doesn't exist (direct backend only)

        Example:
            >>> # Database backend (default)
            >>> builder = SeedBuilder(conn, schema="test")
            >>>
            >>> # Staging backend (no database)
            >>> builder = SeedBuilder(None, schema="test", backend="staging")
        """
        self.conn = conn
        self.schema = schema
        self.pattern = Pattern()
        self._plan: list[SeedPlan] = []

        if backend == "staging":
            # Staging backend - no database required
            from fraiseql_data.backends.staging import StagingBackend
            from fraiseql_data.introspection import MockIntrospector

            self.backend = StagingBackend()
            self.introspector = MockIntrospector()
        else:
            # Direct backend - requires database connection
            if conn is None:
                raise ValueError(
                    "Database connection required for direct backend. "
                    "Use backend='staging' for in-memory testing without database."
                )

            from fraiseql_data.backends.direct import DirectBackend
            from fraiseql_data.introspection import SchemaIntrospector

            self.backend = DirectBackend(conn, schema)
            self.introspector = SchemaIntrospector(conn, schema)

    def add(
        self,
        table: str,
        count: int | Any,  # Allow callable for dynamic count
        strategy: str = "faker",
        overrides: dict[str, Any] | None = None,
    ) -> "SeedBuilder":
        """
        Add a table to the seed plan.

        Args:
            table: Table name
            count: Number of rows to generate (int or callable returning int)
            strategy: Generation strategy (default: "faker")
            overrides: Column overrides (callable or value)

        Returns:
            Self for chaining

        Raises:
            TableNotFoundError: If table doesn't exist in schema

        Example:
            >>> # Static count
            >>> builder.add("users", count=10)
            >>> # Dynamic count via callable
            >>> builder.add("users", count=lambda: random.randint(5, 15))
        """
        # Validate table exists (raises TableNotFoundError if not)
        self.introspector.get_table_info(table)

        # Resolve callable count
        if callable(count):
            count = count()

        self._plan.append(
            SeedPlan(
                table=table,
                count=count,
                strategy=strategy,
                overrides=overrides or {},
            )
        )
        return self

    def execute(self) -> Seeds:
        """
        Execute the seed plan and return generated data.

        Returns:
            Seeds object with generated data accessible by table name

        Raises:
            CircularDependencyError: If circular dependencies detected
            MissingDependencyError: If dependency not in seed plan
            ForeignKeyResolutionError: If FK reference cannot be resolved
            ColumnGenerationError: If column data cannot be generated
        """
        # Validate all dependencies are included in plan
        graph = self.introspector.get_dependency_graph()
        graph.validate_plan([p.table for p in self._plan])

        # Sort plan by dependencies
        sorted_tables = self.introspector.topological_sort()
        plan_by_table = {p.table: p for p in self._plan}

        # Filter to only tables in plan, but in dependency order
        sorted_plan = [
            plan_by_table[table] for table in sorted_tables if table in plan_by_table
        ]

        seeds = Seeds()
        generated_data: dict[str, list[dict[str, Any]]] = {}

        for plan in sorted_plan:
            table_info = self.introspector.get_table_info(plan.table)

            # Check if table has self-referencing FKs
            has_self_ref = len(table_info.get_self_referencing_fks()) > 0

            if has_self_ref:
                # For self-referencing tables, insert one-by-one and track
                inserted_rows = []
                for instance in range(1, plan.count + 1):
                    # Create single-row plan with correct instance number
                    single_plan = SeedPlan(
                        table=plan.table,
                        count=1,
                        strategy=plan.strategy,
                        overrides=plan.overrides,
                    )
                    # Generate single row, passing instance number
                    rows = self._generate_rows(
                        table_info,
                        single_plan,
                        generated_data,
                        inserted_rows,
                        instance_start=instance,
                    )
                    # Insert the single row (use bulk=False for single row)
                    new_rows = self.backend.insert_rows(table_info, rows, bulk=False)
                    inserted_rows.extend(new_rows)
            else:
                # Regular table: generate all rows at once
                rows = self._generate_rows(table_info, plan, generated_data)
                inserted_rows = self.backend.insert_rows(table_info, rows)

            # Store for reference by dependent tables
            generated_data[plan.table] = inserted_rows
            seeds.add_table(plan.table, inserted_rows)

        return seeds

    def insert_seeds(self, seeds: Seeds) -> Seeds:
        """
        Insert pre-loaded seed data into database.

        This method is used to insert seed data that was previously exported
        or loaded from JSON/CSV files. It bypasses generation and directly
        inserts the provided data into the database.

        Args:
            seeds: Seeds object containing pre-loaded data

        Returns:
            Seeds object with database-generated values (pk_*, timestamps)

        Raises:
            TableNotFoundError: If table in seeds doesn't exist in schema

        Example:
            >>> # Load from JSON
            >>> imported = Seeds.from_json("fixtures.json")
            >>> # Insert into database
            >>> builder = SeedBuilder(conn, schema="test")
            >>> result = builder.insert_seeds(imported)
            >>> # result now has database-generated PKs
        """
        result = Seeds()

        for table_name, rows in seeds._tables.items():
            # Validate table exists
            table_info = self.introspector.get_table_info(table_name)

            # Convert SeedRow objects to dicts
            row_dicts = [row._data for row in rows]

            # Insert via backend (gets database-generated values)
            inserted_rows = self.backend.insert_rows(table_info, row_dicts, bulk=True)

            # Store in result Seeds object
            result.add_table(table_name, inserted_rows)

        return result

    def batch(self) -> BatchContext:
        """
        Create a batch context manager for fluent multi-table seeding.

        Returns:
            BatchContext for chaining operations

        Example:
            >>> # Auto-execute on context exit
            >>> with builder.batch() as batch:
            >>>     batch.add("tb_manufacturer", count=10)
            >>>     batch.add("tb_product", count=100)
            >>>
            >>> # Conditional operations
            >>> with builder.batch() as batch:
            >>>     batch.add("tb_manufacturer", count=10)
            >>>     batch.when(include_models).add("tb_model", count=50)
            >>>
            >>> # Manual execution
            >>> batch = builder.batch()
            >>> batch.add("users", count=10)
            >>> seeds = batch.execute()
        """
        return BatchContext(self)

    def set_table_schema(self, table_name: str, table_info: TableInfo) -> None:
        """
        Set table schema manually (for staging backend only).

        Args:
            table_name: Table name
            table_info: Table metadata

        Raises:
            ValueError: If not using staging backend

        Example:
            >>> builder = SeedBuilder(None, schema="test", backend="staging")
            >>> table_info = TableInfo(name="users", columns=[...])
            >>> builder.set_table_schema("users", table_info)
        """
        from fraiseql_data.introspection import MockIntrospector

        if isinstance(self.introspector, MockIntrospector):
            self.introspector.set_table_schema(table_name, table_info)
        else:
            raise ValueError(
                "set_table_schema() only available with staging backend. "
                "Use backend='staging' when initializing SeedBuilder."
            )

    def _generate_rows(
        self,
        table_info: TableInfo,
        plan: SeedPlan,
        generated_data: dict[str, list[dict[str, Any]]],
        current_table_rows: list[dict[str, Any]] | None = None,
        instance_start: int = 1,
    ) -> list[dict[str, Any]]:
        """
        Generate rows for a table.

        Args:
            table_info: Table metadata
            plan: Seed plan for this table
            generated_data: Previously generated data for FK references
            current_table_rows: Previously inserted rows for self-referencing tables
            instance_start: Starting instance number for Trinity pattern UUIDs

        Returns:
            List of row dicts (before database insertion)

        Raises:
            ForeignKeyResolutionError: If FK reference cannot be resolved
            ColumnGenerationError: If column data cannot be auto-generated
            SelfReferenceError: If self-referencing FK is non-nullable
            UniqueConstraintError: If cannot generate unique value
        """
        import random

        faker_gen = FakerGenerator()
        trinity_gen = TrinityGenerator(self.pattern, table_info.name)

        # Parse CHECK constraints and build rules
        check_rules: dict[str, Any] = {}
        if table_info.check_constraints:
            import logging

            from fraiseql_data.constraint_parser import CheckConstraintParser

            logger = logging.getLogger("fraiseql_data.builder")
            parser = CheckConstraintParser()

            for constraint in table_info.check_constraints:
                rule = parser.parse(constraint.check_clause)
                if rule:
                    # Successfully parsed - can auto-satisfy
                    check_rules[rule.column] = rule
                    logger.info(
                        f"Auto-satisfying CHECK constraint on '{rule.column}': "
                        f"{constraint.check_clause}"
                    )
                else:
                    # Too complex - emit warning
                    logger.warning(
                        f"Table '{table_info.name}' has complex CHECK constraint "
                        f"'{constraint.constraint_name}': {constraint.check_clause}. "
                        f"Auto-generated data may violate this constraint. "
                        f"Consider providing overrides for affected columns."
                    )

        # Track UNIQUE column values to avoid duplicates
        unique_values: dict[str, set[Any]] = {}

        # Track multi-column UNIQUE tuples to avoid duplicates
        multi_unique_tuples: dict[str, set[tuple[Any, ...]]] = {}
        for constraint in table_info.multi_unique_constraints:
            # Use constraint name as key
            multi_unique_tuples[constraint.constraint_name] = set()

        # Initialize current_table_rows if None
        if current_table_rows is None:
            current_table_rows = []

        rows = []
        for i in range(instance_start, instance_start + plan.count):
            row: dict[str, Any] = {}

            # Generate data for each column
            for col in table_info.columns:
                # Skip pk_* IDENTITY columns (database generates)
                if col.is_primary_key and col.name.startswith("pk_"):
                    continue

                # Skip Trinity columns for now (will add later)
                if col.name in ("id", "identifier"):
                    continue

                # Handle foreign keys
                if any(fk.column == col.name for fk in table_info.foreign_keys):
                    fk = next(fk for fk in table_info.foreign_keys if fk.column == col.name)

                    # Handle self-referencing FK
                    if fk.is_self_referencing:
                        if not col.is_nullable:
                            raise SelfReferenceError(
                                col.name,
                                table_info.name,
                                "Non-nullable self-reference requires override",
                            )
                        # First row gets NULL, others pick from current table
                        if len(current_table_rows) == 0:
                            row[col.name] = None
                        else:
                            parent_row = random.choice(current_table_rows)
                            row[col.name] = parent_row[fk.referenced_column]
                        continue

                    # Regular FK: validate parent data exists
                    if fk.referenced_table not in generated_data:
                        raise ForeignKeyResolutionError(fk.column, fk.referenced_table)
                    # Pick random from generated parent data
                    parent_row = random.choice(generated_data[fk.referenced_table])
                    row[col.name] = parent_row[fk.referenced_column]
                    continue

                # Check for override
                if col.name in plan.overrides:
                    override = plan.overrides[col.name]
                    if callable(override):
                        # Check if callable expects instance argument
                        import inspect
                        sig = inspect.signature(override)
                        if len(sig.parameters) > 0:
                            row[col.name] = override(i)
                        else:
                            row[col.name] = override()
                    else:
                        row[col.name] = override
                    continue

                # Check if column has auto-satisfiable CHECK constraint
                if col.name in check_rules:
                    rule = check_rules[col.name]
                    row[col.name] = rule.generate()
                    continue

                # Generate using strategy
                if plan.strategy == "faker":
                    value = faker_gen.generate(col.name, col.pg_type)
                else:
                    # Try custom generator from registry
                    from fraiseql_data.generators.registry import get_generator

                    generator_class = get_generator(plan.strategy)
                    if generator_class is None:
                        raise ValueError(
                            f"Unknown strategy '{plan.strategy}'. "
                            f"Available: 'faker', or custom registered generators. "
                            f"Register custom generator with register_generator()."
                        )
                    custom_gen = generator_class()
                    value = custom_gen.generate(
                        col.name,
                        col.pg_type,
                        instance=i,
                        row_data=row,
                        table_info=table_info,
                    )

                # Handle UNIQUE constraint (for both faker and custom generators)
                if col.is_unique and value is not None:
                    if col.name not in unique_values:
                        unique_values[col.name] = set()

                    # Retry if collision
                    retries = 0
                    while value in unique_values[col.name] and retries < MAX_UNIQUE_RETRIES:
                        value = faker_gen.generate(col.name, col.pg_type)
                        retries += 1

                    if retries == MAX_UNIQUE_RETRIES:
                        raise UniqueConstraintError(
                            col.name,
                            table_info.name,
                            f"Could not generate unique value "
                            f"after {MAX_UNIQUE_RETRIES} attempts",
                        )

                    unique_values[col.name].add(value)

                if value is None and not col.is_nullable and col.default_value is None:
                    # Could not auto-generate required column
                    raise ColumnGenerationError(col.name, col.pg_type, table_info.name)
                row[col.name] = value

            # Add Trinity columns if table follows pattern
            if table_info.is_trinity:
                trinity_data = trinity_gen.generate(i, **row)
                row.update(trinity_data)

            # Validate multi-column UNIQUE constraints
            for constraint in table_info.multi_unique_constraints:
                # Extract tuple of values for this constraint
                tuple_values = tuple(row.get(col) for col in constraint.columns)

                # Check if tuple already exists
                if tuple_values in multi_unique_tuples[constraint.constraint_name]:
                    # Collision detected
                    from fraiseql_data.exceptions import MultiColumnUniqueConstraintError

                    raise MultiColumnUniqueConstraintError(
                        constraint.columns,
                        table_info.name,
                        f"Generated duplicate tuple {tuple_values} for "
                        f"UNIQUE{constraint.columns}. Consider providing overrides "
                        f"for one or more columns in this constraint.",
                    )

                # Track this tuple
                multi_unique_tuples[constraint.constraint_name].add(tuple_values)

            rows.append(row)

        return rows
