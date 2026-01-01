"""SQL INSERT statement exporter.

This exporter converts database rows to SQL INSERT statements.
Useful for backups or transferring data between databases.
"""

from __future__ import annotations

from typing import Any

from .base import BaseExporter


class SQLExporter(BaseExporter):
    """Export data as SQL INSERT statements.

    Example output:
    -- Exported data for public.users
    -- Row count: 2

    INSERT INTO public.users (id, name, email)
    VALUES
      (1, 'Alice', 'alice@example.com'),
      (2, 'Bob', 'bob@example.com');
    """

    def __init__(self, batch_size: int = 100):
        """Initialize SQL exporter.

        Args:
            batch_size: Number of rows per INSERT statement
                        Large batches are more efficient but harder to read
        """
        self.batch_size = batch_size

    def export_table(
        self,
        table_name: str,
        rows: list[dict[str, Any]],
        schema: str | None = None,
    ) -> str:
        """Export table as SQL INSERT statements."""
        # Handle empty table
        if not rows:
            return f"-- No data to export for {table_name}\n"

        # Determine full table name (with schema if provided)
        full_table_name = f"{schema}.{table_name}" if schema else table_name

        statements: list[str] = []

        # Add header comments
        statements.append(f"-- Exported data for {full_table_name}")
        statements.append(f"-- Row count: {len(rows)}")
        statements.append("")

        # Get column names from first row
        columns = list(rows[0].keys())
        col_list = ", ".join(columns)  # "id, name, email"

        # Generate INSERT statements in batches
        # Why batches? INSERT INTO ... VALUES (...), (...), (...) is faster
        # than multiple separate INSERT statements
        for i in range(0, len(rows), self.batch_size):
            batch = rows[i : i + self.batch_size]
            values_list = []

            # Build VALUES clause for each row
            for row in batch:
                values = []
                for col in columns:
                    value = row[col]
                    values.append(self._format_value(value))
                values_list.append(f"({', '.join(values)})")

            # Build complete INSERT statement
            values_clause = ",\n  ".join(values_list)
            insert_stmt = f"INSERT INTO {full_table_name} ({col_list})\nVALUES\n  {values_clause};"
            statements.append(insert_stmt)
            statements.append("")

        return "\n".join(statements)

    def get_file_extension(self) -> str:
        """Get file extension for SQL files."""
        return ".sql"

    def supports_multi_table(self) -> bool:
        """SQL can handle multiple tables (separate INSERT statements)."""
        return True

    @staticmethod
    def _format_value(value: Any) -> str:
        """Format value for SQL INSERT statement.

        This function converts Python values to SQL literals.

        Examples:
            None → NULL
            True → TRUE
            42 → 42
            "hello" → 'hello'
            "it's" → 'it''s' (escaped single quote)

        Args:
            value: Python value to format

        Returns:
            SQL literal as string
        """
        # NULL values
        if value is None:
            return "NULL"

        # Boolean values
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"

        # Numeric values (int, float)
        if isinstance(value, (int, float)):
            return str(value)

        # String values (need escaping and quoting)
        if isinstance(value, str):
            # Escape single quotes: "it's" → "it''s"
            escaped = value.replace("'", "''")
            return f"'{escaped}'"

        # Default: convert to string and quote
        # This handles datetime, UUID, etc.
        return f"'{str(value)}'"
