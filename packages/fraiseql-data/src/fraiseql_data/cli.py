"""CLI commands for fraiseql-data."""

import os
import re
import sys

import click
from rich.console import Console

console = Console()


def _get_database_url(database: str | None) -> str:
    """Get database URL from option or environment variable.

    Priority:
    1. --database option
    2. DATABASE_URL environment variable
    3. Error if neither provided
    """
    if database:
        return database

    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        return env_url

    console.print("[red]❌ Error: No database connection provided[/red]")
    console.print(
        "[blue]💡 Provide --database option or set DATABASE_URL environment variable[/blue]"
    )
    sys.exit(1)


def _mask_database_url(url: str) -> str:
    """Mask password in database URL for safe display."""
    # Pattern: postgresql://user:password@host:port/database
    return re.sub(
        r'(postgresql://[^:]+:)([^@]+)(@.+)',
        r'\1***\3',
        url
    )


def _sanitize_error_message(error: Exception, database_url: str | None = None) -> str:
    """Sanitize error message to remove any credentials."""
    message = str(error)

    # If we have a database URL, mask it in the error
    if database_url:
        message = message.replace(database_url, _mask_database_url(database_url))

    # Also catch common password patterns
    message = re.sub(r'password=[^\s&]+', 'password=***', message, flags=re.IGNORECASE)
    message = re.sub(r':[^:@]+@', ':***@', message)

    return message


@click.group()
@click.version_option(package_name="fraiseql-data")
def cli() -> None:
    """fraiseql-data - Smart PostgreSQL test data generation."""
    pass


@cli.command()
@click.argument("tables", nargs=-1, required=True)
@click.option("--count", type=int, default=10, help="Number of rows per table (default: 10)")
@click.option("--auto-deps", is_flag=True, help="Auto-generate dependencies")
@click.option("--quiet", "-q", is_flag=True, help="Quiet mode")
def generate(tables: list[str], count: int, auto_deps: bool, quiet: bool) -> None:
    """Generate test data without database connection."""
    if not quiet:
        console.print(f"[bold blue]Generating data for {len(tables)} table(s)...[/bold blue]")

    try:
        from fraiseql_data import SeedBuilder

        # Use staging backend (no database required)
        builder = SeedBuilder(conn=None, schema="test", backend="staging")

        # Add tables
        for table in tables:
            if auto_deps:
                builder.add(table, count=count, auto_deps=True)
            else:
                builder.add(table, count=count)

        # Generate data
        seeds = builder.execute()

        if not quiet:
            # Show summary
            console.print("📊 [bold green]Generated Data Summary:[/bold green]")
            total_rows = 0
            for table_name in tables:
                if hasattr(seeds, table_name):
                    row_count = len(getattr(seeds, table_name))
                    console.print(f"  • {table_name}: {row_count} rows")
                    total_rows += row_count

            console.print(f"\n✅ [green]Total: {total_rows} rows generated[/green]")

        # Output JSON data
        output = seeds.to_json()
        click.echo(output)

    except Exception as e:
        sanitized_message = _sanitize_error_message(e)
        console.print(f"[red]❌ Error: {sanitized_message}[/red]")
        sys.exit(1)


@cli.command()
@click.argument("tables", nargs=-1, required=True)
@click.option(
    "--database", default=None, help="Database connection string (or set DATABASE_URL env var)"
)
@click.option("--count", type=int, default=10, help="Number of rows per table (default: 10)")
@click.option("--auto-deps", is_flag=True, help="Auto-generate dependencies")
@click.option("--dry-run", is_flag=True, help="Show what would be done without executing")
@click.option("--quiet", "-q", is_flag=True, help="Quiet mode")
def seed(
    tables: list[str],
    database: str | None,
    count: int,
    auto_deps: bool,
    dry_run: bool,
    quiet: bool,
) -> None:
    """Seed database with generated data.

    Database connection can be provided via:
    - --database option
    - DATABASE_URL environment variable
    """
    database_url = _get_database_url(database)

    if not quiet:
        console.print(f"[bold blue]🌱 Seeding database with {len(tables)} table(s)...[/bold blue]")
        if dry_run:
            console.print("[yellow]🧪 DRY RUN MODE - No data will be inserted[/yellow]")
        else:
            console.print(f"[dim]Connecting to: {_mask_database_url(database_url)}[/dim]")

    try:
        from psycopg import connect

        from fraiseql_data import SeedBuilder

        if dry_run:
            # Show what would be done (no connection needed)
            console.print("[cyan]📋 Would generate data for tables:[/cyan]")
            for table in tables:
                console.print(f"  • {table}: {count} rows")
            if auto_deps:
                console.print("[cyan]🔗 Would auto-generate dependencies[/cyan]")
            return

        # Connect to database with context manager
        with connect(database_url) as conn:
            # Initialize builder
            builder = SeedBuilder(conn=conn, schema="public")

            # Add tables
            for table in tables:
                if auto_deps:
                    builder.add(table, count=count, auto_deps=True)
                else:
                    builder.add(table, count=count)

            # Execute seeding
            seeds = builder.execute()

            if not quiet:
                # Show summary
                console.print("📊 [bold green]Seeding Summary:[/bold green]")
                total_rows = 0
                for table_name in tables:
                    if hasattr(seeds, table_name):
                        row_count = len(getattr(seeds, table_name))
                        console.print(f"  • {table_name}: {row_count} rows inserted")
                        total_rows += row_count

                console.print(f"\n✅ [green]Successfully seeded {total_rows} total rows![/green]")

    except Exception as e:
        sanitized_message = _sanitize_error_message(e, database_url)
        console.print(f"[red]❌ Error: {sanitized_message}[/red]")
        sys.exit(1)


@cli.command()
@click.option(
    "--database", default=None, help="Database connection string (or set DATABASE_URL env var)"
)
@click.option("--schema", default="public", help="Database schema (default: public)")
def inspect(database: str | None, schema: str) -> None:
    """Inspect database schema.

    Database connection can be provided via:
    - --database option
    - DATABASE_URL environment variable
    """
    database_url = _get_database_url(database)

    console.print(f"[bold blue]🔍 Inspecting schema: {schema}[/bold blue]")
    console.print(f"[dim]Connecting to: {_mask_database_url(database_url)}[/dim]")

    try:
        from psycopg import connect

        from fraiseql_data import SeedBuilder

        # Connect to database with context manager
        with connect(database_url) as conn:
            builder = SeedBuilder(conn, schema)

            # Get all tables
            tables = builder.introspector.get_tables()
            console.print(f"\n📋 [green]Found {len(tables)} tables:[/green]")

            for table_name in sorted(tables):
                table_info = builder.introspector.get_table_info(table_name)
                col_count = len(table_info.columns)

                # Count FKs
                fk_count = sum(1 for col in table_info.columns if col.foreign_key)

                console.print(f"  • {table_name}: {col_count} columns, {fk_count} FKs")

            console.print("\n✅ [green]Schema inspection complete![/green]")

    except Exception as e:
        sanitized_message = _sanitize_error_message(e, database_url)
        console.print(f"[red]❌ Error: {sanitized_message}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    cli()
