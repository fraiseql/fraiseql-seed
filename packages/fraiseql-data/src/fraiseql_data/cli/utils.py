"""CLI utility functions - security and helpers."""

from __future__ import annotations

import os
import re

from rich.console import Console

from .errors import DatabaseURLNotProvidedError

console = Console()


def get_database_url(database: str | None) -> str:
    """Get database URL from option or environment variable.

    Priority:
    1. --database option
    2. DATABASE_URL environment variable
    3. Error if neither provided

    Args:
        database: Database URL from CLI option (or None)

    Returns:
        Database URL string

    Raises:
        DatabaseURLNotProvidedError: If no URL provided
    """
    if database:
        return database

    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        return env_url

    raise DatabaseURLNotProvidedError()


def mask_database_url(url: str) -> str:
    """Mask password in database URL for safe display.

    Args:
        url: Database URL (e.g., postgresql://user:pass@host/db)

    Returns:
        Masked URL (e.g., postgresql://user:***@host/db)
    """
    # Pattern: postgresql://user:password@host:port/database
    return re.sub(r"(postgresql://[^:]+:)([^@]+)(@.+)", r"\1***\3", url)


def sanitize_error_message(error: Exception, database_url: str | None = None) -> str:
    """Sanitize error message to remove any credentials.

    Args:
        error: Exception to sanitize
        database_url: Optional database URL to mask in error

    Returns:
        Sanitized error message
    """
    message = str(error)

    # If we have a database URL, mask it in the error
    if database_url:
        message = message.replace(database_url, mask_database_url(database_url))

    # Also catch common password patterns
    message = re.sub(r"password=[^\s&]+", "password=***", message, flags=re.IGNORECASE)
    message = re.sub(r":[^:@]+@", ":***@", message)

    return message


def display_error(error: Exception, exit_code: int = 1) -> None:
    """Display error message with optional suggestion.

    Args:
        error: Error to display
        exit_code: Exit code (default: 1)
    """
    from .errors import CLIError

    if isinstance(error, CLIError):
        console.print(f"[red]❌ Error:[/red] {error.message}")
        if error.suggestion:
            console.print(f"[blue]💡 Suggestion:[/blue] {error.suggestion}")
    else:
        console.print(f"[red]❌ Error:[/red] {error}")
