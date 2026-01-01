"""CLI command handlers - business logic separated from CLI layer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console

from .errors import DataGenerationError, SchemaInspectionError

if TYPE_CHECKING:
    from psycopg import Connection

    from fraiseql_data import Seeds

console = Console()


class GenerateHandler:
    """Handler for generate command - staging backend data generation."""

    def __init__(self, quiet: bool = False):
        """Initialize generate handler.

        Args:
            quiet: Whether to suppress output
        """
        self.quiet = quiet

    def execute(
        self, tables: list[str], count: int, auto_deps: bool, schema: str = "test"
    ) -> Seeds:
        """Execute data generation without database connection.

        Args:
            tables: List of table names to generate data for
            count: Number of rows per table
            auto_deps: Whether to auto-generate dependencies
            schema: Schema name (default: "test")

        Returns:
            Seeds object with generated data

        Raises:
            DataGenerationError: If generation fails
        """
        if not self.quiet:
            console.print(f"[bold blue]Generating data for {len(tables)} table(s)...[/bold blue]")

        try:
            from fraiseql_data import SeedBuilder

            # Use staging backend (no database required)
            builder = SeedBuilder(conn=None, schema=schema, backend="staging")

            # Add tables
            for table in tables:
                if auto_deps:
                    builder.add(table, count=count, auto_deps=True)
                else:
                    builder.add(table, count=count)

            # Generate data
            seeds = builder.execute()

            if not self.quiet:
                self._print_summary(tables, seeds)

            return seeds

        except Exception as e:
            # Determine which table caused the error if possible
            table_name = tables[0] if tables else "unknown"
            raise DataGenerationError(table_name, e) from e

    def _print_summary(self, tables: list[str], seeds: Seeds) -> None:
        """Print generation summary.

        Args:
            tables: List of table names
            seeds: Generated seeds
        """
        console.print("📊 [bold green]Generated Data Summary:[/bold green]")
        total_rows = 0
        for table_name in tables:
            if hasattr(seeds, table_name):
                row_count = len(getattr(seeds, table_name))
                console.print(f"  • {table_name}: {row_count} rows")
                total_rows += row_count

        console.print(f"\n✅ [green]Total: {total_rows} rows generated[/green]")


class SeedHandler:
    """Handler for seed command - database seeding with generated data."""

    def __init__(self, quiet: bool = False):
        """Initialize seed handler.

        Args:
            quiet: Whether to suppress output
        """
        self.quiet = quiet

    def execute(
        self,
        conn: Connection,
        tables: list[str],
        count: int,
        auto_deps: bool,
        schema: str = "public",
    ) -> Seeds:
        """Execute database seeding.

        Args:
            conn: Database connection
            tables: List of table names to seed
            count: Number of rows per table
            auto_deps: Whether to auto-generate dependencies
            schema: Database schema (default: "public")

        Returns:
            Seeds object with seeded data

        Raises:
            DataGenerationError: If seeding fails
        """
        if not self.quiet:
            console.print(
                f"[bold blue]🌱 Seeding database with {len(tables)} table(s)...[/bold blue]"
            )

        try:
            from fraiseql_data import SeedBuilder

            # Initialize builder
            builder = SeedBuilder(conn=conn, schema=schema)

            # Add tables
            for table in tables:
                if auto_deps:
                    builder.add(table, count=count, auto_deps=True)
                else:
                    builder.add(table, count=count)

            # Execute seeding
            seeds = builder.execute()

            if not self.quiet:
                self._print_summary(tables, seeds)

            return seeds

        except Exception as e:
            # Determine which table caused the error if possible
            table_name = tables[0] if tables else "unknown"
            raise DataGenerationError(table_name, e) from e

    def _print_summary(self, tables: list[str], seeds: Seeds) -> None:
        """Print seeding summary.

        Args:
            tables: List of table names
            seeds: Seeded data
        """
        console.print("📊 [bold green]Seeding Summary:[/bold green]")
        total_rows = 0
        for table_name in tables:
            if hasattr(seeds, table_name):
                row_count = len(getattr(seeds, table_name))
                console.print(f"  • {table_name}: {row_count} rows inserted")
                total_rows += row_count

        console.print(f"\n✅ [green]Successfully seeded {total_rows} total rows![/green]")


class InspectHandler:
    """Handler for inspect command - database schema inspection."""

    def __init__(self, quiet: bool = False):
        """Initialize inspect handler.

        Args:
            quiet: Whether to suppress output
        """
        self.quiet = quiet

    def execute(self, conn: Connection, schema: str = "public") -> dict[str, dict]:
        """Execute schema inspection.

        Args:
            conn: Database connection
            schema: Database schema (default: "public")

        Returns:
            Dictionary mapping table names to their info

        Raises:
            SchemaInspectionError: If inspection fails
        """
        console.print(f"[bold blue]🔍 Inspecting schema: {schema}[/bold blue]")

        try:
            from fraiseql_data import SeedBuilder

            builder = SeedBuilder(conn, schema)

            # Get all tables
            tables = builder.introspector.get_tables()

            if not self.quiet:
                console.print(f"\n📋 [green]Found {len(tables)} tables:[/green]")

            # Collect table information
            table_info_map = {}
            for table_name in sorted(tables):
                table_info = builder.introspector.get_table_info(table_name)
                col_count = len(table_info.columns)

                # Count FKs
                fk_count = sum(1 for col in table_info.columns if col.foreign_key)

                table_info_map[table_name] = {
                    "columns": col_count,
                    "foreign_keys": fk_count,
                    "info": table_info,
                }

                if not self.quiet:
                    console.print(f"  • {table_name}: {col_count} columns, {fk_count} FKs")

            if not self.quiet:
                console.print("\n✅ [green]Schema inspection complete![/green]")

            return table_info_map

        except Exception as e:
            raise SchemaInspectionError(schema, e) from e
