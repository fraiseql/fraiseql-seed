"""SeedBuilder API for declarative seed generation."""

import inspect
import logging
from pathlib import Path
from typing import Any

from fraiseql_uuid import Pattern
from psycopg import Connection

# Note: Backend and introspector imports moved to __init__ for lazy loading
from fraiseql_data.auto_deps import AutoDependencyResolver
from fraiseql_data.exceptions import (
    ColumnGenerationError,
    ForeignKeyResolutionError,
    MultiColumnUniqueConstraintError,
    SelfReferenceError,
    UniqueConstraintError,
)
from fraiseql_data.generators import FakerGenerator, TrinityGenerator
from fraiseql_data.generators.groups import GroupRegistry
from fraiseql_data.models import SeedPlan, Seeds, TableInfo

logger = logging.getLogger(__name__)

_seed_common_warned = False

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
        auto_deps: bool | dict[str, int | dict[str, Any]] = False,
        groups: list | None = None,
    ) -> "BatchContext":
        """
        Add table to batch (chainable).

        Args:
            table: Table name
            count: Number of rows or callable returning count
            strategy: Generation strategy (default: "faker")
            overrides: Column overrides
            auto_deps: Auto-generate FK dependencies
            groups: Column groups (None=auto-detect, []=disable, list=custom)

        Returns:
            Self for chaining
        """
        # Resolve callable count immediately
        if callable(count):
            count = count()

        # Auto-generate dependencies if requested
        if auto_deps:
            # Resolve auto-dependencies and add to builder's plan
            dep_plans = self.builder._auto_deps_resolver.resolve_dependencies(
                table, auto_deps, self.builder._plan, count
            )
            self.builder._plan.extend(dep_plans)

        self._operations.append(
            SeedPlan(
                table=table,
                count=count,
                strategy=strategy,
                overrides=overrides or {},
                groups=groups,
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
        auto_deps: bool | dict[str, int | dict[str, Any]] = False,
        groups: list | None = None,
    ) -> BatchContext:
        """
        Add table only if condition is true.

        Args:
            table: Table name
            count: Number of rows or callable returning count
            strategy: Generation strategy
            overrides: Column overrides
            auto_deps: Auto-generate FK dependencies
            groups: Column groups (None=auto-detect, []=disable, list=custom)

        Returns:
            Parent BatchContext for continued chaining
        """
        if self.condition:
            # Resolve callable count if needed
            if callable(count):
                count = count()

            # Auto-generate dependencies if requested
            if auto_deps:
                # Resolve auto-dependencies and add to builder's plan
                dep_plans = self.batch.builder._auto_deps_resolver.resolve_dependencies(
                    table, auto_deps, self.batch.builder._plan, count
                )
                self.batch.builder._plan.extend(dep_plans)

            self.batch._operations.append(
                SeedPlan(
                    table=table,
                    count=count,
                    strategy=strategy,
                    overrides=overrides or {},
                    groups=groups,
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
        seed_common: str | Path | Any | None = None,
        validate_seed_common: bool = True,
        trinity_enabled: bool = False,
        trinity_tenant_id: Any = None,
    ):
        """
        Initialize SeedBuilder.

        Args:
            conn: PostgreSQL connection (None for staging backend)
            schema: Schema name
            backend: Backend type - "direct" (database) or "staging" (in-memory)
            seed_common: Seed common baseline (file/directory/instance or None)
                - Path to YAML/JSON file
                - Path to directory (auto-detects format and environment)
                - SeedCommon instance
                - None (shows warning, not recommended)
            validate_seed_common: Validate FK references (default: True)
            trinity_enabled: Enable Trinity extension for deterministic
                PK allocation (default: False)
            trinity_tenant_id: Tenant ID for multi-tenant Trinity
                allocation (optional)

        Raises:
            SchemaNotFoundError: If schema doesn't exist (direct backend only)

        Example:
            >>> # With seed common (recommended)
            >>> builder = SeedBuilder(conn, schema="test", seed_common="db/")
            >>>
            >>> # With Trinity extension enabled
            >>> builder = SeedBuilder(
            ...     conn, schema="test", trinity_enabled=True, trinity_tenant_id=1
            ... )
            >>>
            >>> # Staging backend (no database)
            >>> builder = SeedBuilder(None, schema="test", backend="staging")
        """
        self.conn = conn
        self.schema = schema
        self.pattern = Pattern()
        self._plan: list[SeedPlan] = []
        self.trinity_enabled = trinity_enabled
        self.trinity_tenant_id = trinity_tenant_id

        if backend == "staging":
            # Staging backend - no database required
            from fraiseql_data.backends.staging import StagingBackend
            from fraiseql_data.introspection import MockIntrospector

            self.backend = StagingBackend()
            # Enable Trinity simulation in staging backend if requested
            if trinity_enabled:
                self.backend.enable_trinity_simulation(tenant_id=trinity_tenant_id)
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

        # Load seed common baseline
        from fraiseql_data.seed_common import SeedCommon, SeedCommonValidationError

        if seed_common is None:
            global _seed_common_warned  # noqa: PLW0603
            if validate_seed_common and not _seed_common_warned:
                _seed_common_warned = True
                logger.warning(
                    "No seed common defined. UUID collisions may occur when "
                    "creating multiple SeedBuilder instances.\n"
                    "Recommendation: Define seed common baseline:\n"
                    "  SeedBuilder(..., seed_common='db/')\n"
                    "This warning will become an error in v2.0."
                )
            self._seed_common = SeedCommon(instance_offsets={}, data=None)
        elif isinstance(seed_common, SeedCommon):
            self._seed_common = seed_common
        else:
            # Load from file/directory
            path = Path(seed_common)

            if path.is_dir():
                # Directory: auto-detect format and environment
                self._seed_common = SeedCommon.from_directory(path)
            elif path.suffix in (".yaml", ".yml"):
                self._seed_common = SeedCommon.from_yaml(path)
            elif path.suffix == ".json":
                self._seed_common = SeedCommon.from_json(path)
            else:
                raise ValueError(f"Unsupported seed common format: {path}")

            # Validate if enabled
            if validate_seed_common and backend != "staging":
                errors = self._seed_common.validate(self.introspector)
                if errors:
                    error_msg = "Seed common validation failed:\n" + "\n".join(
                        f"  {i + 1}. {err}" for i, err in enumerate(errors)
                    )
                    raise SeedCommonValidationError(error_msg)

        logger.debug(f"Seed common loaded: {self._seed_common.get_instance_offsets()}")

        # Initialize auto-dependency resolver with seed common
        self._auto_deps_resolver = AutoDependencyResolver(self.introspector, self._seed_common)

    def add(
        self,
        table: str,
        count: int | Any,  # Allow callable for dynamic count
        strategy: str = "faker",
        overrides: dict[str, Any] | None = None,
        auto_deps: bool | dict[str, int | dict[str, Any]] = False,
        groups: list | None = None,
    ) -> "SeedBuilder":
        """
        Add a table to the seed plan.

        Args:
            table: Table name
            count: Number of rows to generate (int or callable returning int)
            strategy: Generation strategy (default: "faker")
            overrides: Column overrides (callable or value)
            auto_deps: Auto-generate FK dependencies
                - False: No auto-deps (default)
                - True: Generate 1 of each dependency (minimal)
                - dict: Explicit counts per dependency table

        Returns:
            Self for chaining

        Raises:
            TableNotFoundError: If table doesn't exist in schema

        Example:
            >>> # Static count
            >>> builder.add("users", count=10)
            >>> # Dynamic count via callable
            >>> builder.add("users", count=lambda: random.randint(5, 15))
            >>> # Auto-generate dependencies (minimal)
            >>> builder.add("tb_allocation", count=10, auto_deps=True)
            >>> # Auto-generate with explicit counts
            >>> builder.add(
            ...     "tb_allocation",
            ...     count=100,
            ...     auto_deps={"tb_organization": 2, "tb_machine": 10}
            ... )
        """
        # Validate table exists (raises TableNotFoundError if not)
        self.introspector.get_table_info(table)

        # Resolve callable count
        if callable(count):
            count = count()

        # Auto-generate dependencies if requested
        if auto_deps:
            # Resolve auto-dependencies and add to plan
            dep_plans = self._auto_deps_resolver.resolve_dependencies(
                table, auto_deps, self._plan, count
            )
            self._plan.extend(dep_plans)

        self._plan.append(
            SeedPlan(
                table=table,
                count=count,
                strategy=strategy,
                overrides=overrides or {},
                groups=groups,
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
        # Build overridden FK map: table -> set of FK column names with overrides
        overridden_fks: dict[str, set[str]] = {}
        for plan in self._plan:
            if plan.overrides:
                table_info = self.introspector.get_table_info(plan.table)
                fk_cols_with_override = {
                    fk.column for fk in table_info.foreign_keys if fk.column in plan.overrides
                }
                if fk_cols_with_override:
                    overridden_fks[plan.table] = fk_cols_with_override

        # Validate all dependencies are included in plan
        graph = self.introspector.get_dependency_graph()
        graph.validate_plan([p.table for p in self._plan], overridden_fks)

        # Sort plan by dependencies
        sorted_tables = self.introspector.topological_sort()
        plan_by_table = {p.table: p for p in self._plan}

        # Filter to only tables in plan, but in dependency order
        sorted_plan = [plan_by_table[table] for table in sorted_tables if table in plan_by_table]

        seeds = Seeds()
        generated_data: dict[str, list[dict[str, Any]]] = {}

        for plan in sorted_plan:
            table_info = self.introspector.get_table_info(plan.table)

            # Skip generation if count=0 (dependency satisfied by seed common)
            if plan.count == 0:
                # Seed common data already exists in database, no generation needed
                # Add empty list to maintain dependency tracking
                generated_data[plan.table] = []
                seeds.add_table(plan.table, [])
                continue

            # Check if table has self-referencing FKs
            has_self_ref = len(table_info.get_self_referencing_fks()) > 0

            if has_self_ref:
                # For self-referencing tables, insert one-by-one and track
                # Start instance counter after seed common range
                instance_start = self._seed_common.get_instance_start(plan.table)
                inserted_rows = []
                for i in range(plan.count):
                    instance = instance_start + i
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
                # Start instance counter after seed common range
                instance_start = self._seed_common.get_instance_start(plan.table)

                rows = self._generate_rows(
                    table_info, plan, generated_data, instance_start=instance_start
                )
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

    @staticmethod
    def _apply_override(override: Any, counter: int) -> Any:
        """Apply an override value, calling it if callable."""
        if callable(override):
            sig = inspect.signature(override)
            if len(sig.parameters) > 0:
                return override(counter)
            return override()
        return override

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

        # Build Trinity context if enabled
        trinity_context = None
        if self.trinity_enabled and self.conn is not None:
            trinity_context = {
                "conn": self.conn,
                "tenant_id": self.trinity_tenant_id,
            }

        trinity_gen = TrinityGenerator(
            self.pattern, table_info.name, trinity_context=trinity_context
        )

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

        # Detect active groups
        column_names = {col.name for col in table_info.columns}
        if plan.groups is not None:
            # Explicit groups: use as-is (empty list disables groups)
            active_groups = plan.groups
        else:
            # Auto-detect from built-in registry
            registry = GroupRegistry()
            active_groups = registry.detect_groups(column_names)

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
        for counter, instance in enumerate(
            range(instance_start, instance_start + plan.count), start=1
        ):
            row: dict[str, Any] = {}

            # Generate group values for this row
            group_values: dict[str, Any] = {}
            if active_groups:
                for group in active_groups:
                    # Build context: overrides for this group + prior group outputs
                    context: dict[str, Any] = {
                        col_name: self._apply_override(val, counter)
                        for col_name, val in plan.overrides.items()
                        if col_name in group.fields
                    }
                    context.update(group_values)
                    values = group.generator(context)
                    group_values.update(
                        {
                            k: v
                            for k, v in values.items()
                            if k not in plan.overrides
                            and k not in check_rules
                            and (k in column_names or k.startswith("_"))
                        }
                    )

            # Generate data for each column
            for col in table_info.columns:
                # Skip identity columns (GENERATED ALWAYS/BY DEFAULT AS IDENTITY)
                if col.is_identity:
                    continue

                # Skip serial columns (nextval default on PK)
                if col.is_primary_key and col.default_value and "nextval(" in col.default_value:
                    continue

                # Skip pk_* columns (database generates via sequence/identity)
                if col.is_primary_key and col.name.startswith("pk_"):
                    continue

                # Skip Trinity columns for now (will add later)
                if col.name in ("id", "identifier"):
                    continue

                # Check for override (before FK resolution so overrides take priority)
                if col.name in plan.overrides:
                    row[col.name] = self._apply_override(plan.overrides[col.name], counter)
                    continue

                # Use group-generated value if available
                if col.name in group_values:
                    value = group_values[col.name]

                    # Handle UNIQUE constraint on group columns
                    if col.is_unique and value is not None:
                        if col.name not in unique_values:
                            unique_values[col.name] = set()

                        if value in unique_values[col.name]:
                            # Find the group that owns this column
                            owning_group = next(g for g in active_groups if col.name in g.fields)
                            for attempt in range(MAX_UNIQUE_RETRIES):
                                ctx: dict[str, Any] = {
                                    c: self._apply_override(v, counter)
                                    for c, v in plan.overrides.items()
                                    if c in owning_group.fields
                                }
                                # Email suffix fallback after half retries
                                if col.name == "email" and attempt >= MAX_UNIQUE_RETRIES // 2:
                                    ctx["_email_suffix"] = attempt
                                new_values = owning_group.generator(ctx)
                                value = new_values[col.name]
                                if value not in unique_values[col.name]:
                                    # Update group_values for coherence
                                    group_values.update(
                                        {
                                            k: v
                                            for k, v in new_values.items()
                                            if k not in plan.overrides
                                            and k not in check_rules
                                            and (k in column_names or k.startswith("_"))
                                        }
                                    )
                                    break
                            else:
                                raise UniqueConstraintError(
                                    col.name,
                                    table_info.name,
                                    f"Could not generate unique group value "
                                    f"after {MAX_UNIQUE_RETRIES} attempts",
                                )

                        unique_values[col.name].add(value)

                    row[col.name] = value
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
                        instance=instance,
                        counter=counter,
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
                            f"Could not generate unique value after {MAX_UNIQUE_RETRIES} attempts",
                        )

                    unique_values[col.name].add(value)

                if value is None and not col.is_nullable and col.default_value is None:
                    # Could not auto-generate required column
                    raise ColumnGenerationError(col.name, col.pg_type, table_info.name)
                row[col.name] = value

            # Add Trinity columns if table follows pattern
            if table_info.is_trinity:
                trinity_data = trinity_gen.generate(instance, **row)
                row.update(trinity_data)

            # Validate multi-column UNIQUE constraints
            for constraint in table_info.multi_unique_constraints:
                # Extract tuple of values for this constraint
                tuple_values = tuple(row.get(col) for col in constraint.columns)

                # Check if tuple already exists
                if tuple_values in multi_unique_tuples[constraint.constraint_name]:
                    # Collision detected
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
