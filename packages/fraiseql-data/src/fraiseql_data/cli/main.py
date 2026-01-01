"""CLI commands for fraiseql-data - presentation layer only."""

from __future__ import annotations

import sys

import click
from psycopg import connect
from rich.console import Console

from .errors import CLIError, DatabaseConnectionError
from .handlers import GenerateHandler, InspectHandler, SeedHandler
from .utils import display_error, get_database_url, mask_database_url, sanitize_error_message

console = Console()


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
    try:
        handler = GenerateHandler(quiet=quiet)
        seeds = handler.execute(tables=list(tables), count=count, auto_deps=auto_deps)

        # Output JSON data
        output = seeds.to_json()
        click.echo(output)

    except CLIError as e:
        display_error(e)
        sys.exit(e.exit_code)
    except Exception as e:
        sanitized_message = sanitize_error_message(e)
        console.print(f"[red]❌ Error:[/red] {sanitized_message}")
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
    try:
        database_url = get_database_url(database)

        if not quiet:
            if dry_run:
                console.print("[yellow]🧪 DRY RUN MODE - No data will be inserted[/yellow]")
            else:
                console.print(f"[dim]Connecting to: {mask_database_url(database_url)}[/dim]")

        if dry_run:
            # Show what would be done (no connection needed)
            console.print("[cyan]📋 Would generate data for tables:[/cyan]")
            for table in tables:
                console.print(f"  • {table}: {count} rows")
            if auto_deps:
                console.print("[cyan]🔗 Would auto-generate dependencies[/cyan]")
            return

        # Connect to database with context manager
        try:
            with connect(database_url) as conn:
                handler = SeedHandler(quiet=quiet)
                handler.execute(
                    conn=conn, tables=list(tables), count=count, auto_deps=auto_deps
                )
        except Exception as e:
            raise DatabaseConnectionError(mask_database_url(database_url), e) from e

    except CLIError as e:
        display_error(e)
        sys.exit(e.exit_code)
    except Exception as e:
        sanitized_message = sanitize_error_message(e, database_url)
        console.print(f"[red]❌ Error:[/red] {sanitized_message}")
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
    try:
        database_url = get_database_url(database)

        console.print(f"[dim]Connecting to: {mask_database_url(database_url)}[/dim]")

        # Connect to database with context manager
        try:
            with connect(database_url) as conn:
                handler = InspectHandler(quiet=False)
                handler.execute(conn=conn, schema=schema)
        except Exception as e:
            raise DatabaseConnectionError(mask_database_url(database_url), e) from e

    except CLIError as e:
        display_error(e)
        sys.exit(e.exit_code)
    except Exception as e:
        sanitized_message = sanitize_error_message(e, database_url)
        console.print(f"[red]❌ Error:[/red] {sanitized_message}")
        sys.exit(1)


if __name__ == "__main__":
    cli()
