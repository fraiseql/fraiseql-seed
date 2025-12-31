"""SeedBuilder API for declarative seed generation."""

from typing import Any

from fraiseql_uuid import Pattern
from psycopg import Connection

from fraiseql_data.backends.direct import DirectBackend
from fraiseql_data.exceptions import ColumnGenerationError, ForeignKeyResolutionError
from fraiseql_data.generators import FakerGenerator, TrinityGenerator
from fraiseql_data.introspection import SchemaIntrospector
from fraiseql_data.models import SeedPlan, Seeds, TableInfo


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
    ) -> list[dict[str, Any]]:
        """
        Generate rows for a table.

        Args:
            table_info: Table metadata
            plan: Seed plan for this table
            generated_data: Previously generated data for FK references

        Returns:
            List of row dicts (before database insertion)

        Raises:
            ForeignKeyResolutionError: If FK reference cannot be resolved
            ColumnGenerationError: If column data cannot be auto-generated
        """
        faker_gen = FakerGenerator()
        trinity_gen = TrinityGenerator(self.pattern, table_info.name)

        rows = []
        for i in range(1, plan.count + 1):
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
                    # Validate parent data exists
                    if fk.referenced_table not in generated_data:
                        raise ForeignKeyResolutionError(fk.column, fk.referenced_table)
                    # Pick random from generated parent data
                    import random
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

                # Generate using Faker
                if plan.strategy == "faker":
                    value = faker_gen.generate(col.name, col.pg_type)
                    if value is None and not col.is_nullable and col.default_value is None:
                        # Could not auto-generate required column
                        raise ColumnGenerationError(col.name, col.pg_type, table_info.name)
                    row[col.name] = value

            # Add Trinity columns if table follows pattern
            if table_info.is_trinity:
                trinity_data = trinity_gen.generate(i, **row)
                row.update(trinity_data)

            rows.append(row)

        return rows
