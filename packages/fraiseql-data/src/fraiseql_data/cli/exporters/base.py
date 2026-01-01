"""Base exporter interface.

This file defines what ALL exporters must implement.
Think of it as a template or contract.
"""

from __future__ import annotations

from abc import ABC, abstractmethod  # ABC = Abstract Base Class
from typing import Any


class BaseExporter(ABC):
    """Abstract base class for data exporters.

    All exporters (JSON, CSV, SQL) must inherit from this class
    and implement the required methods.
    """

    @abstractmethod
    def export_table(
        self,
        table_name: str,
        rows: list[dict[str, Any]],
        schema: str | None = None,
    ) -> str:
        """Export table data to format-specific output.

        This method MUST be implemented by every exporter.
        It takes raw data (list of dictionaries) and converts it
        to the specific format (JSON, CSV, etc.).

        Args:
            table_name: Name of the table being exported (e.g., "users")
            rows: List of row dictionaries
                  Example: [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
            schema: Optional schema name (e.g., "public")

        Returns:
            Formatted export string (the actual JSON, CSV, etc. text)

        Example:
            exporter = JSONExporter()
            output = exporter.export_table(
                "users",
                [{"id": 1, "name": "Alice"}],
                schema="public"
            )
            # output = '{"users": [{"id": 1, "name": "Alice"}]}'
        """
        pass  # Subclasses MUST implement this

    @abstractmethod
    def get_file_extension(self) -> str:
        """Get recommended file extension for this format.

        Returns:
            File extension with leading dot (e.g., ".json", ".csv")

        Example:
            exporter = JSONExporter()
            ext = exporter.get_file_extension()  # Returns ".json"
        """
        pass

    @abstractmethod
    def supports_multi_table(self) -> bool:
        """Whether this exporter can handle multiple tables in one file.

        Some formats (like JSON) can export multiple tables in one file:
        {
            "users": [...],
            "products": [...]
        }

        Others (like CSV) can only handle one table per file.

        Returns:
            True if multi-table export is supported, False otherwise
        """
        pass
