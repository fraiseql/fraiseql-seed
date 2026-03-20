"""CLI error types with context-aware messaging."""

from __future__ import annotations


class CLIError(Exception):
    """Base CLI error with user-friendly messaging."""

    def __init__(self, message: str, suggestion: str | None = None, exit_code: int = 1):
        """Initialize CLI error.

        Args:
            message: Error message to display
            suggestion: Optional suggestion for fixing the error
            exit_code: Exit code to use when terminating
        """
        self.message = message
        self.suggestion = suggestion
        self.exit_code = exit_code
        super().__init__(message)


class DatabaseConnectionError(CLIError):
    """Database connection failed."""

    def __init__(self, masked_url: str, original_error: Exception):
        """Initialize database connection error.

        Args:
            masked_url: Database URL with password masked
            original_error: Original exception from connection attempt
        """
        super().__init__(
            f"Cannot connect to database: {masked_url}",
            f"Check your DATABASE_URL or use --database option. Error: {original_error}",
            exit_code=2,
        )
        self.masked_url = masked_url
        self.original_error = original_error


class DatabaseURLNotProvidedError(CLIError):
    """Database URL not provided via CLI or environment."""

    def __init__(self):
        """Initialize database URL not provided error."""
        super().__init__(
            "No database connection provided",
            "Provide --database option or set DATABASE_URL environment variable",
            exit_code=2,
        )


class TableNotFoundError(CLIError):
    """Requested table does not exist in database schema."""

    def __init__(self, table_name: str, schema: str, available_tables: list[str] | None = None):
        """Initialize table not found error.

        Args:
            table_name: Name of table that wasn't found
            schema: Schema that was searched
            available_tables: List of available tables (for suggestions)
        """
        suggestion = f"Table '{table_name}' not found in schema '{schema}'"
        if available_tables:
            # Find similar table names
            similar = [t for t in available_tables if table_name.lower() in t.lower()]
            if similar:
                suggestion += f". Did you mean: {', '.join(similar[:3])}?"
            else:
                suggestion += f". Available tables: {', '.join(available_tables[:5])}"
                if len(available_tables) > 5:  # noqa: PLR2004
                    suggestion += f" (and {len(available_tables) - 5} more)"

        super().__init__(
            f"Table not found: {table_name}",
            suggestion,
            exit_code=3,
        )
        self.table_name = table_name
        self.schema = schema
        self.available_tables = available_tables


class DataGenerationError(CLIError):
    """Error during data generation."""

    def __init__(self, table_name: str, original_error: Exception):
        """Initialize data generation error.

        Args:
            table_name: Table for which generation failed
            original_error: Original exception from generation
        """
        super().__init__(
            f"Failed to generate data for table '{table_name}'",
            f"Error: {original_error}",
            exit_code=4,
        )
        self.table_name = table_name
        self.original_error = original_error


class SchemaInspectionError(CLIError):
    """Error during schema inspection."""

    def __init__(self, schema: str, original_error: Exception):
        """Initialize schema inspection error.

        Args:
            schema: Schema that failed to inspect
            original_error: Original exception from inspection
        """
        super().__init__(
            f"Failed to inspect schema '{schema}'",
            f"Check schema name and permissions. Error: {original_error}",
            exit_code=5,
        )
        self.schema = schema
        self.original_error = original_error
