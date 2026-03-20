"""CSV exporter implementation.

This exporter converts database rows to CSV (Comma-Separated Values) format.
"""

from __future__ import annotations

import csv  # Python's built-in CSV module
import io  # For in-memory string buffer
from typing import Any

from .base import BaseExporter


class CSVExporter(BaseExporter):
    """Export data as CSV.

    Example output:
    id,name,email
    1,Alice,alice@example.com
    2,Bob,bob@example.com
    """

    def __init__(self, include_header: bool = True, delimiter: str = ","):
        """Initialize CSV exporter.

        Args:
            include_header: If True, include column names as first row
            delimiter: Character to separate values (usually comma)
        """
        self.include_header = include_header
        self.delimiter = delimiter

    def export_table(
        self,
        _table_name: str,
        rows: list[dict[str, Any]],
        _schema: str | None = None,
    ) -> str:
        """Export table as CSV."""
        # Handle empty table
        if not rows:
            return ""

        # Create an in-memory text buffer (like a file, but in memory)
        output = io.StringIO()

        # Get column names from first row
        fieldnames = list(rows[0].keys())

        # Create CSV writer
        writer = csv.DictWriter(
            output,
            fieldnames=fieldnames,
            delimiter=self.delimiter,
        )

        # Write header row (column names)
        if self.include_header:
            writer.writeheader()  # Writes: id,name,email

        # Write data rows
        writer.writerows(rows)  # Writes: 1,Alice,alice@example.com

        # Get the CSV string from the buffer
        return output.getvalue()

    def get_file_extension(self) -> str:
        """Get file extension for CSV files."""
        return ".csv"

    def supports_multi_table(self) -> bool:
        """CSV can only handle one table per file."""
        return False  # You can't put multiple tables in one CSV file
