"""CLI commands for fraiseql-data - presentation layer only."""

from __future__ import annotations

import sys

import click
from psycopg import connect
from rich.console import Console

from .config import load_config
from .errors import CLIError, DatabaseConnectionError
from .formatters import format_output, get_available_formats
from .handlers import GenerateHandler, InspectHandler, SeedHandler
from .logging import get_logger, setup_logging
from .utils import display_error, get_database_url, mask_database_url, sanitize_error_message

console = Console()


@click.group()
@click.version_option(package_name="fraiseql-data")
@click.option("--debug", is_flag=True, help="Enable debug mode with verbose logging")
@click.pass_context
def cli(ctx: click.Context, debug: bool) -> None:
    """fraiseql-data - Smart PostgreSQL test data generation."""
    # Set up logging
    setup_logging(debug=debug)

    # Load configuration
    config = load_config()

    # Store in context for commands
    ctx.ensure_object(dict)
    ctx.obj["config"] = config
    ctx.obj["debug"] = debug


@cli.command()
@click.argument("tables", nargs=-1, required=True)
@click.option("--count", type=int, default=None, help="Number of rows per table")
@click.option("--auto-deps", is_flag=True, help="Auto-generate dependencies")
@click.option("--quiet", "-q", is_flag=True, help="Quiet mode")
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(get_available_formats()),
    default=None,
    help="Output format",
)
@click.pass_context
def generate(
    ctx: click.Context,
    tables: list[str],
    count: int | None,
    auto_deps: bool,
    quiet: bool,
    output_format: str | None,
) -> None:
    """Generate test data without database connection."""
    config = ctx.obj["config"]
    logger = get_logger(debug=ctx.obj["debug"])

    # Apply config defaults
    if count is None:
        count = config.get_default_count()
    if output_format is None:
        output_format = config.get_output_format()
    if not quiet:
        quiet = config.get_quiet()

    logger.log_command("generate", {"tables": list(tables), "count": count, "auto_deps": auto_deps})

    try:
        handler = GenerateHandler(quiet=quiet)
        seeds = handler.execute(tables=list(tables), count=count, auto_deps=auto_deps)

        # Format output
        output = format_output(seeds, output_format)
        click.echo(output)

    except CLIError as e:
        logger.log_error(e, {"command": "generate", "tables": list(tables)})
        display_error(e)
        sys.exit(e.exit_code)
    except Exception as e:
        logger.log_error(e, {"command": "generate", "tables": list(tables)})
        sanitized_message = sanitize_error_message(e)
        console.print(f"[red]❌ Error:[/red] {sanitized_message}")
        sys.exit(1)


@cli.command()
@click.argument("tables", nargs=-1, required=True)
@click.option(
    "--database", default=None, help="Database connection string (or set DATABASE_URL env var)"
)
@click.option("--count", type=int, default=None, help="Number of rows per table")
@click.option("--auto-deps", is_flag=True, help="Auto-generate dependencies")
@click.option("--dry-run", is_flag=True, help="Show what would be done without executing")
@click.option("--quiet", "-q", is_flag=True, help="Quiet mode")
@click.option("--schema", default=None, help="Database schema")
@click.pass_context
def seed(
    ctx: click.Context,
    tables: list[str],
    database: str | None,
    count: int | None,
    auto_deps: bool,
    dry_run: bool,
    quiet: bool,
    schema: str | None,
) -> None:
    """Seed database with generated data.

    Database connection can be provided via:
    - --database option
    - DATABASE_URL environment variable
    - Configuration file
    """
    config = ctx.obj["config"]
    logger = get_logger(debug=ctx.obj["debug"])

    # Apply config defaults
    if database is None:
        database = config.get_database_url()
    if count is None:
        count = config.get_default_count()
    if schema is None:
        schema = config.get_default_schema()
    if not quiet:
        quiet = config.get_quiet()

    try:
        database_url = get_database_url(database)

        logger.log_command("seed", {"tables": list(tables), "count": count, "schema": schema})

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
                logger.log_database_connection(mask_database_url(database_url), True)
                handler = SeedHandler(quiet=quiet)
                handler.execute(
                    conn=conn, tables=list(tables), count=count, auto_deps=auto_deps, schema=schema
                )
        except Exception as e:
            logger.log_database_connection(mask_database_url(database_url), False)
            raise DatabaseConnectionError(mask_database_url(database_url), e) from e

    except CLIError as e:
        logger.log_error(e, {"command": "seed", "tables": list(tables)})
        display_error(e)
        sys.exit(e.exit_code)
    except Exception as e:
        logger.log_error(e, {"command": "seed", "tables": list(tables)})
        sanitized_message = sanitize_error_message(e, database_url)
        console.print(f"[red]❌ Error:[/red] {sanitized_message}")
        sys.exit(1)


@cli.command()
@click.option(
    "--database", default=None, help="Database connection string (or set DATABASE_URL env var)"
)
@click.option("--schema", default=None, help="Database schema")
@click.pass_context
def inspect(ctx: click.Context, database: str | None, schema: str | None) -> None:
    """Inspect database schema.

    Database connection can be provided via:
    - --database option
    - DATABASE_URL environment variable
    - Configuration file
    """
    config = ctx.obj["config"]
    logger = get_logger(debug=ctx.obj["debug"])

    # Apply config defaults
    if database is None:
        database = config.get_database_url()
    if schema is None:
        schema = config.get_default_schema()

    try:
        database_url = get_database_url(database)

        logger.log_command("inspect", {"schema": schema})

        console.print(f"[dim]Connecting to: {mask_database_url(database_url)}[/dim]")

        # Connect to database with context manager
        try:
            with connect(database_url) as conn:
                logger.log_database_connection(mask_database_url(database_url), True)
                handler = InspectHandler(quiet=False)
                handler.execute(conn=conn, schema=schema)
        except Exception as e:
            logger.log_database_connection(mask_database_url(database_url), False)
            raise DatabaseConnectionError(mask_database_url(database_url), e) from e

    except CLIError as e:
        logger.log_error(e, {"command": "inspect"})
        display_error(e)
        sys.exit(e.exit_code)
    except Exception as e:
        logger.log_error(e, {"command": "inspect"})
        sanitized_message = sanitize_error_message(e, database_url)
        console.print(f"[red]❌ Error:[/red] {sanitized_message}")
        sys.exit(1)


if __name__ == "__main__":
    cli()
