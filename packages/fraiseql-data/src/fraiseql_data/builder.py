"""SeedBuilder API for declarative seed generation."""

from typing import Any

from fraiseql_uuid import Pattern
from psycopg import Connection

from fraiseql_data.backends.direct import DirectBackend
from fraiseql_data.exceptions import (
    ColumnGenerationError,
    ForeignKeyResolutionError,
    SelfReferenceError,
    UniqueConstraintError,
)
from fraiseql_data.generators import FakerGenerator, TrinityGenerator
from fraiseql_data.introspection import SchemaIntrospector
from fraiseql_data.models import SeedPlan, Seeds, TableInfo

# Constants for generation logic
MAX_UNIQUE_RETRIES = 10  # Maximum attempts to generate unique value


class SeedBuilder:
    """Declarative API for building and executing seed data plans."""

    def __init__(self, conn: Connection, schema: str):
        """
        Initialize SeedBuilder.

        Args:
            conn: PostgreSQL connection
            schema: Schema name

        Raises:
            SchemaNotFoundError: If schema doesn't exist
        """
        self.conn = conn
        self.schema = schema
        self.introspector = SchemaIntrospector(conn, schema)
        self.backend = DirectBackend(conn, schema)
        self.pattern = Pattern()
        self._plan: list[SeedPlan] = []

    def add(
        self,
        table: str,
        count: int,
        strategy: str = "faker",
        overrides: dict[str, Any] | None = None,
    ) -> "SeedBuilder":
        """
        Add a table to the seed plan.

        Args:
            table: Table name
            count: Number of rows to generate
            strategy: Generation strategy (default: "faker")
            overrides: Column overrides (callable or value)

        Returns:
            Self for chaining

        Raises:
            TableNotFoundError: If table doesn't exist in schema
        """
        # Validate table exists (raises TableNotFoundError if not)
        self.introspector.get_table_info(table)

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

        # Warn about CHECK constraints
        if table_info.check_constraints:
            import logging

            logger = logging.getLogger("fraiseql_data.builder")
            for constraint in table_info.check_constraints:
                logger.warning(
                    f"Table '{table_info.name}' has CHECK constraint "
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
