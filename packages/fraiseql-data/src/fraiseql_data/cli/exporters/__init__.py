"""Data exporters for fraiseql-data CLI.

This module provides exporters for different output formats:
- JSON: Machine-readable, widely supported
- CSV: Spreadsheet-friendly, simple
- SQL: Database-ready INSERT statements
- YAML: Human-readable configuration format
"""

from __future__ import annotations

from .base import BaseExporter
from .csv_exporter import CSVExporter
from .json_exporter import JSONExporter
from .sql_exporter import SQLExporter
from .yaml_exporter import YAMLExporter

# Export these names when someone does: from exporters import *
__all__ = [
    "BaseExporter",
    "CSVExporter",
    "JSONExporter",
    "SQLExporter",
    "YAMLExporter",
    "get_exporter",
]


def get_exporter(format: str, **kwargs) -> BaseExporter:
    """Get exporter instance for specified format.

    This is a factory function - it creates the right exporter
    based on the format string.

    Args:
        format: Export format name ("json", "csv", "sql", "yaml")
        **kwargs: Format-specific options (passed to exporter __init__)

    Returns:
        Exporter instance ready to use

    Raises:
        ValueError: If format is not supported

    Example:
        # Get a JSON exporter with metadata
        exporter = get_exporter("json", include_metadata=True)
        output = exporter.export_table("users", rows)

        # Get a CSV exporter without header
        exporter = get_exporter("csv", include_header=False)
        output = exporter.export_table("users", rows)
    """
    # Map format names to exporter classes
    exporters = {
        "json": JSONExporter,
        "csv": CSVExporter,
        "sql": SQLExporter,
        "yaml": YAMLExporter,
    }

    # Check if format is valid
    if format not in exporters:
        raise ValueError(
            f"Unsupported export format: {format}. Supported formats: {', '.join(exporters.keys())}"
        )

    # Create and return exporter instance
    # **kwargs unpacks keyword arguments to the __init__ method
    return exporters[format](**kwargs)
