"""CLI commands for fraiseql-data - presentation layer only."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from psycopg import connect
from rich.console import Console

from .config import load_config
from .errors import CLIError, DatabaseConnectionError
from .formatters import format_output, get_available_formats
from .handlers import GenerateHandler, InspectHandler, SeedHandler
from .interactive import InteractiveSession
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
@click.argument("tables", nargs=-1, required=False)
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
@click.option("--interactive", "-i", is_flag=True, help="Interactive mode")
@click.pass_context
def generate(
    ctx: click.Context,
    tables: list[str],
    count: int | None,
    auto_deps: bool,
    quiet: bool,
    output_format: str | None,
    interactive: bool,
) -> None:
    """Generate test data without database connection.

    Use --interactive for a guided wizard.
    """
    config = ctx.obj["config"]
    logger = get_logger(debug=ctx.obj["debug"])

    # Interactive mode
    if interactive or not tables:
        session = InteractiveSession()
        options = session.run_generate()
        tables = options["tables"]
        count = options["count"]
        auto_deps = options["auto_deps"]
        output_format = options["format"]

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
@click.argument("tables", nargs=-1, required=False)
@click.option(
    "--database", default=None, help="Database connection string (or set DATABASE_URL env var)"
)
@click.option("--count", type=int, default=None, help="Number of rows per table")
@click.option("--auto-deps", is_flag=True, help="Auto-generate dependencies")
@click.option("--dry-run", is_flag=True, help="Show what would be done without executing")
@click.option("--quiet", "-q", is_flag=True, help="Quiet mode")
@click.option("--schema", default=None, help="Database schema")
@click.option("--interactive", "-i", is_flag=True, help="Interactive mode")
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
    interactive: bool,
) -> None:
    """Seed database with generated data.

    Database connection can be provided via:
    - --database option
    - DATABASE_URL environment variable
    - Configuration file

    Use --interactive for a guided wizard.
    """
    config = ctx.obj["config"]
    logger = get_logger(debug=ctx.obj["debug"])

    # Interactive mode
    if interactive or not tables:
        session = InteractiveSession()
        options = session.run_seed()
        tables = options["tables"]
        if options["database"]:
            database = options["database"]
        schema = options["schema"]
        count = options["count"]
        auto_deps = options["auto_deps"]
        dry_run = options["dry_run"]

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


@cli.command()
@click.argument("tables", nargs=-1, required=True)
@click.option(
    "--database", default=None, help="Database connection string (or set DATABASE_URL env var)"
)
@click.option("--schema", default=None, help="Database schema")
@click.option("--where", "where_clause", default=None, help="SQL WHERE clause for filtering")
@click.option("--limit", type=int, default=None, help="Maximum rows per table")
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["json", "csv", "sql", "yaml"]),
    default="json",
    help="Output format",
)
@click.option(
    "--output", "-o", type=click.Path(), default=None, help="Output file path (defaults to stdout)"
)
@click.option("--quiet", "-q", is_flag=True, help="Quiet mode (no progress messages)")
@click.option(
    "--batch-size",
    type=int,
    default=10000,
    help="Number of rows to fetch at once (affects memory usage)",
)
@click.pass_context
def export(
    ctx: click.Context,
    tables: tuple[str, ...],  # Click gives us a tuple
    database: str | None,
    schema: str | None,
    where_clause: str | None,
    limit: int | None,
    output_format: str,
    output: str | None,
    quiet: bool,
    batch_size: int,
) -> None:
    """Export existing database data.

    Examples:

        \b
        # Export single table to JSON
        fraiseql-data export users --database "postgresql://localhost/mydb"

        \b
        # Export multiple tables to CSV
        fraiseql-data export users products --format csv

        \b
        # Export with WHERE clause (safe for SELECT conditions only)
        fraiseql-data export users --where "status = 'active'" --format sql

        \b
        # Export with limit and save to file
        fraiseql-data export logs --limit 1000 --format json -o logs.json
    """
    # Import at function level to avoid circular imports
    import sys

    from .errors import CLIError
    from .handlers import ExportHandler
    from .logging import get_logger
    from .utils import display_error, get_database_url, sanitize_error_message

    # Get configuration and logger
    config = ctx.obj["config"]
    logger = get_logger(debug=ctx.obj["debug"])

    # Get database URL from:
    # 1. --database option
    # 2. DATABASE_URL environment variable
    database_url = get_database_url(database)

    # Apply config defaults
    if schema is None:
        schema = config.get_database_schema()
    if not quiet:
        quiet = config.get_quiet()

    # Log command execution
    logger.log_command(
        "export",
        {
            "tables": list(tables),
            "schema": schema,
            "format": output_format,
        },
    )

    try:
        # Execute export operation
        handler = ExportHandler(quiet=quiet, batch_size=batch_size)
        exported_data = handler.execute(
            database_url=database_url,
            tables=list(tables),  # Convert tuple to list
            schema=schema,
            where_clause=where_clause,
            limit=limit,
        )

        # Import exporter factory
        from .exporters import get_exporter

        # Get the appropriate exporter
        exporter = get_exporter(output_format)

        # Handle output formatting
        if output_format == "json" and len(exported_data) > 1:
            # For JSON with multiple tables, combine into single JSON object
            combined_data = {}
            for table_name, data in exported_data.items():
                combined_data[table_name] = data["rows"]
            # Use JSON exporter's custom serializer
            import json

            from .exporters import JSONExporter

            output_text = json.dumps(combined_data, indent=2, default=JSONExporter._json_serializer)
        elif not exporter.supports_multi_table():
            # CSV can only handle one table - use first one
            table_name, data = next(iter(exported_data.items()))
            output_text = exporter.export_table(
                table_name,
                data["rows"],
                schema=schema,
            )
        else:
            # Multi-table formats (JSON single table, SQL, YAML)
            output_parts = []
            for table_name, data in exported_data.items():
                table_output = exporter.export_table(
                    table_name,
                    data["rows"],
                    schema=schema,
                )
                output_parts.append(table_output)

            if len(output_parts) > 1:
                output_text = "\n\n".join(output_parts)
            else:
                output_text = output_parts[0] if output_parts else ""

        # Write to file or stdout
        if output:
            # Write to file
            with Path(output).open("w") as f:
                f.write(output_text)
            if not quiet:
                console.print(f"[green]✓[/green] Exported to {output}")
        else:
            # Write to stdout
            click.echo(output_text)

    except CLIError as e:
        # Known error with exit code
        logger.log_error(e, {"command": "export", "tables": list(tables)})
        display_error(e)
        sys.exit(e.exit_code)
    except Exception as e:
        # Unexpected error
        logger.log_error(e, {"command": "export", "tables": list(tables)})
        sanitized_message = sanitize_error_message(e)
        console.print(f"[red]❌ Error:[/red] {sanitized_message}")
        sys.exit(1)


if __name__ == "__main__":
    cli()
