"""Interactive mode for guided command building."""

from __future__ import annotations

from typing import Any

import click
from rich.console import Console
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

console = Console()


class InteractiveSession:
    """Interactive session for building CLI commands."""

    def __init__(self):
        """Initialize interactive session."""
        self.console = console

    def run_generate(self) -> dict[str, Any]:
        """Run interactive data generation wizard.

        Returns:
            Dictionary of command options
        """
        self.console.print("\n[bold cyan]🔧 Interactive Data Generation Wizard[/bold cyan]\n")

        # Step 1: Select tables
        tables_input = Prompt.ask(
            "[bold]Tables to generate[/bold] (comma-separated)",
            default="users",
        )
        tables = [t.strip() for t in tables_input.split(",")]

        # Step 2: Row count
        count = IntPrompt.ask(
            "[bold]Number of rows per table[/bold]",
            default=10,
        )

        # Step 3: Auto-dependencies
        auto_deps = Confirm.ask(
            "[bold]Auto-generate dependencies?[/bold]",
            default=True,
        )

        # Step 4: Output format
        self.console.print("\n[bold]Available output formats:[/bold]")
        formats = ["json", "csv", "yaml", "table"]
        for i, fmt in enumerate(formats, 1):
            self.console.print(f"  {i}. {fmt}")

        format_choice = Prompt.ask(
            "\n[bold]Output format[/bold]",
            choices=formats,
            default="json",
        )

        # Summary
        self.console.print("\n[bold green]Summary:[/bold green]")
        summary_table = Table(show_header=False, box=None)
        summary_table.add_row("Tables:", ", ".join(tables))
        summary_table.add_row("Count:", str(count))
        summary_table.add_row("Auto-deps:", "Yes" if auto_deps else "No")
        summary_table.add_row("Format:", format_choice)
        self.console.print(summary_table)

        # Confirm
        if not Confirm.ask("\n[bold]Proceed?[/bold]", default=True):
            self.console.print("[yellow]Cancelled[/yellow]")
            raise click.Abort()

        return {
            "tables": tables,
            "count": count,
            "auto_deps": auto_deps,
            "format": format_choice,
        }

    def run_seed(self) -> dict[str, Any]:
        """Run interactive database seeding wizard.

        Returns:
            Dictionary of command options
        """
        self.console.print("\n[bold cyan]🌱 Interactive Database Seeding Wizard[/bold cyan]\n")

        # Step 1: Database URL
        database = Prompt.ask(
            "[bold]Database URL[/bold] (or press Enter to use DATABASE_URL env var)",
            default="",
        )
        if not database:
            database = None  # Will use env var or config

        # Step 2: Schema
        schema = Prompt.ask(
            "[bold]Database schema[/bold]",
            default="public",
        )

        # Step 3: Select tables
        tables_input = Prompt.ask(
            "[bold]Tables to seed[/bold] (comma-separated)",
            default="users",
        )
        tables = [t.strip() for t in tables_input.split(",")]

        # Step 4: Row count
        count = IntPrompt.ask(
            "[bold]Number of rows per table[/bold]",
            default=10,
        )

        # Step 5: Auto-dependencies
        auto_deps = Confirm.ask(
            "[bold]Auto-generate dependencies?[/bold]",
            default=True,
        )

        # Step 6: Dry run
        dry_run = Confirm.ask(
            "[bold]Dry run (preview without executing)?[/bold]",
            default=False,
        )

        # Summary
        self.console.print("\n[bold green]Summary:[/bold green]")
        summary_table = Table(show_header=False, box=None)
        if database:
            db_display = database[:50] + "..." if len(database) > 50 else database
            summary_table.add_row("Database:", db_display)
        else:
            summary_table.add_row("Database:", "From DATABASE_URL or config")
        summary_table.add_row("Schema:", schema)
        summary_table.add_row("Tables:", ", ".join(tables))
        summary_table.add_row("Count:", str(count))
        summary_table.add_row("Auto-deps:", "Yes" if auto_deps else "No")
        summary_table.add_row("Dry run:", "Yes" if dry_run else "No")
        self.console.print(summary_table)

        # Confirm
        if not Confirm.ask("\n[bold]Proceed?[/bold]", default=True):
            self.console.print("[yellow]Cancelled[/yellow]")
            raise click.Abort()

        return {
            "tables": tables,
            "database": database,
            "schema": schema,
            "count": count,
            "auto_deps": auto_deps,
            "dry_run": dry_run,
        }

    def run_inspect(self) -> dict[str, Any]:
        """Run interactive schema inspection wizard.

        Returns:
            Dictionary of command options
        """
        self.console.print("\n[bold cyan]🔍 Interactive Schema Inspection Wizard[/bold cyan]\n")

        # Step 1: Database URL
        database = Prompt.ask(
            "[bold]Database URL[/bold] (or press Enter to use DATABASE_URL env var)",
            default="",
        )
        if not database:
            database = None  # Will use env var or config

        # Step 2: Schema
        schema = Prompt.ask(
            "[bold]Database schema[/bold]",
            default="public",
        )

        # Summary
        self.console.print("\n[bold green]Summary:[/bold green]")
        summary_table = Table(show_header=False, box=None)
        if database:
            db_display = database[:50] + "..." if len(database) > 50 else database
            summary_table.add_row("Database:", db_display)
        else:
            summary_table.add_row("Database:", "From DATABASE_URL or config")
        summary_table.add_row("Schema:", schema)
        self.console.print(summary_table)

        # Confirm
        if not Confirm.ask("\n[bold]Proceed?[/bold]", default=True):
            self.console.print("[yellow]Cancelled[/yellow]")
            raise click.Abort()

        return {
            "database": database,
            "schema": schema,
        }
