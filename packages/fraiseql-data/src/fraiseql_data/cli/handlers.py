"""CLI command handlers - business logic separated from CLI layer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich.console import Console

from .errors import CLIError, DataGenerationError, SchemaInspectionError
from .logging import get_logger

if TYPE_CHECKING:
    from psycopg import Connection

    from fraiseql_data import Seeds

console = Console()


def _validate_where_clause(where_clause: str | None) -> str | None:
    """Validate WHERE clause for basic SQL injection prevention.

    This is not foolproof but provides basic protection against
    obvious SQL injection attempts.

    Args:
        where_clause: Raw WHERE clause from user input

    Returns:
        Validated WHERE clause or None

    Raises:
        CLIError: If WHERE clause contains dangerous patterns
    """
    if not where_clause:
        return None

    # Remove leading/trailing whitespace
    where_clause = where_clause.strip()

    if not where_clause:
        return None

    # Convert to uppercase for pattern matching
    upper_clause = where_clause.upper()

    # Dangerous patterns that indicate SQL injection attempts
    dangerous_patterns = [
        "DROP ",
        "DELETE ",
        "UPDATE ",
        "INSERT ",
        "ALTER ",
        "CREATE ",
        "TRUNCATE ",
        "EXEC ",
        "EXECUTE ",
        "UNION SELECT",
        "--",  # SQL comments
        "/*",  # Block comments
        "*/",
        ";",  # Statement separators (basic protection)
    ]

    for pattern in dangerous_patterns:
        if pattern in upper_clause:
            raise CLIError(
                f"Potentially dangerous WHERE clause detected: '{where_clause}'",
                "WHERE clauses should only contain SELECT conditions (comparisons, AND/OR, etc.)",
                exit_code=1,
            )

    # Basic length check (very long WHERE clauses might be suspicious)
    if len(where_clause) > 1000:  # noqa: PLR2004
        raise CLIError(
            "WHERE clause too long (max 1000 characters)",
            "Please simplify your WHERE condition",
            exit_code=1,
        )

    return where_clause


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


class ExportHandler:
    """Handler for export command - business logic layer.

    This handler:
    1. Connects to the database
    2. Validates requested tables exist
    3. Fetches data from each table
    4. Returns structured data for formatting
    """

    def __init__(self, quiet: bool = False, batch_size: int = 10000):
        """Initialize export handler.

        Args:
            quiet: If True, suppress progress messages
            batch_size: Number of rows to process at once (for memory efficiency)
        """
        self.quiet = quiet
        self.batch_size = batch_size
        self.logger = get_logger()

    def execute(
        self,
        database_url: str,
        tables: list[str],
        schema: str | None = None,
        where_clause: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Execute export operation.

        Args:
            database_url: Database connection string
                          Example: "postgresql://user:pass@localhost/mydb"
            tables: List of tables to export
                    Example: ["users", "products"]
            schema: Optional schema name (default: "public")
            where_clause: Optional SQL WHERE clause for filtering
                          Example: "status = 'active'"
            limit: Optional row limit per table
                   Example: 1000

        Returns:
            Dictionary with exported data per table
            Example:
            {
                "users": {
                    "rows": [{...}, {...}],
                    "count": 2,
                    "columns": ["id", "name", "email"]
                },
                "products": {...}
            }

        Raises:
            DatabaseConnectionError: If database connection fails
            CLIError: If table doesn't exist or other validation error
        """
        from psycopg import connect

        from ..introspection import SchemaIntrospector
        from .errors import CLIError, DatabaseConnectionError

        # Validate WHERE clause for security
        validated_where = _validate_where_clause(where_clause)

        # Log what we're doing (for debugging)
        self.logger.log_command(
            "export",
            {
                "tables": tables,
                "schema": schema,
                "where_clause": bool(validated_where),
            },
        )

        # Connect to database
        try:
            conn = connect(database_url)
        except Exception as e:
            from .utils import mask_database_url

            raise DatabaseConnectionError(
                mask_database_url(database_url),
                e,
            ) from e

        try:
            # Introspect schema to validate tables exist
            introspector = SchemaIntrospector(conn, schema or "public")
            table_infos = introspector.get_tables()
            available_tables = [table_info.name for table_info in table_infos]

            # Validate requested tables
            # Convert to sets for efficient comparison
            invalid_tables = set(tables) - set(available_tables)
            if invalid_tables:
                raise CLIError(
                    f"Tables not found: {', '.join(invalid_tables)}",
                    exit_code=1,
                )

            # Export each table
            exported_data: dict[str, Any] = {}

            for table in tables:
                # Show progress (unless quiet mode)
                if not self.quiet:
                    console.print(f"[blue]Exporting {table}...[/blue]")

                # Build SQL query
                # Note: In production code, we'd use parameterized queries
                # to prevent SQL injection. This is safe because:
                # 1. We validated table exists (from introspection)
                # 2. schema is validated by introspector
                # 3. where_clause is user-provided but only for their own use
                query_parts = []

                if schema:
                    query_parts.append(f"SELECT * FROM {schema}.{table}")
                else:
                    query_parts.append(f"SELECT * FROM {table}")

                if validated_where:
                    query_parts.append(f"WHERE {validated_where}")

                if limit:
                    query_parts.append(f"LIMIT {limit}")

                query = " ".join(query_parts)

                # Fetch data with memory-efficient batching
                cursor = conn.execute(query)

                # Get column names from cursor description
                # cursor.description is a tuple of tuples: ((name, type, ...), ...)
                columns = [desc[0] for desc in cursor.description]

                # Fetch rows in batches to prevent memory exhaustion
                rows = []
                batch_count = 0
                while True:
                    # Fetch next batch of rows
                    batch = cursor.fetchmany(self.batch_size)
                    if not batch:
                        break  # No more rows

                    batch_count += 1
                    if not self.quiet and batch_count % 10 == 0:
                        console.print(f"[dim]Fetched {len(rows)} rows so far...[/dim]")

                    # Convert batch to dictionaries
                    rows.extend(dict(zip(columns, row, strict=True)) for row in batch)

                    # Safety check: prevent excessive memory usage
                    if len(rows) > 100000:  # noqa: PLR2004  # 100K row limit as safety net
                        raise CLIError(
                            f"Table '{table}' has too many rows ({len(rows)}+). "
                            "Use --limit to restrict the number of rows.",
                            "Try: --limit 50000",
                            exit_code=1,
                        )

                # Store exported data
                exported_data[table] = {
                    "rows": rows,
                    "count": len(rows),
                    "columns": columns,
                }

                # Show progress
                if not self.quiet:
                    console.print(f"[green]✓[/green] Exported {len(rows)} rows from {table}")

            return exported_data

        finally:
            # Always close connection (even if error occurred)
            conn.close()
