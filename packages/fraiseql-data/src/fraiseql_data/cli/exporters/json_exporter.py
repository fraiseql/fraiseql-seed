"""JSON exporter implementation.

This exporter converts database rows to JSON format.
"""

from __future__ import annotations

import json
from datetime import date, datetime  # For date serialization
from decimal import Decimal  # For numeric types
from typing import Any
from uuid import UUID  # For UUID serialization

from .base import BaseExporter


class JSONExporter(BaseExporter):
    """Export data as JSON.

    Example output:
    {
        "users": [
            {"id": 1, "name": "Alice", "email": "alice@example.com"},
            {"id": 2, "name": "Bob", "email": "bob@example.com"}
        ]
    }
    """

    def __init__(self, pretty: bool = True, include_metadata: bool = False):
        """Initialize JSON exporter.

        Args:
            pretty: If True, format JSON with indentation (human-readable)
                    If False, compact JSON (machine-readable)
            include_metadata: If True, include metadata like row count, timestamp
        """
        self.pretty = pretty
        self.include_metadata = include_metadata

    def export_table(
        self,
        table_name: str,
        rows: list[dict[str, Any]],
        schema: str | None = None,
    ) -> str:
        """Export table as JSON."""
        # Build the output structure
        data: dict[str, Any] = {table_name: rows}

        # Optionally add metadata
        if self.include_metadata:
            data["_metadata"] = {
                "table": table_name,
                "schema": schema,
                "row_count": len(rows),
                "exported_at": datetime.now().isoformat(),
            }

        # Convert to JSON string
        indent = 2 if self.pretty else None
        return json.dumps(data, indent=indent, default=self._json_serializer)

    def get_file_extension(self) -> str:
        """Get file extension for JSON files."""
        return ".json"

    def supports_multi_table(self) -> bool:
        """JSON can handle multiple tables in one file."""
        return True

    @staticmethod
    def _json_serializer(obj: Any) -> Any:
        """Custom JSON serializer for special types.

        Python's json.dumps() doesn't know how to serialize certain types
        like datetime, UUID, Decimal. This function teaches it how.

        Args:
            obj: Object that json.dumps() doesn't know how to serialize

        Returns:
            Serializable version of the object

        Raises:
            TypeError: If we don't know how to serialize this type
        """
        # Convert datetime/date to ISO format string
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()  # "2025-01-01T12:00:00"

        # Convert UUID to string
        if isinstance(obj, UUID):
            return str(obj)  # "550e8400-e29b-41d4-a716-446655440000"

        # Convert Decimal to float
        if isinstance(obj, Decimal):
            return float(obj)  # 99.99

        # Unknown type - raise error
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
