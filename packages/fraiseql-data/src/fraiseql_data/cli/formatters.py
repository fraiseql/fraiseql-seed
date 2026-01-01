"""Output format plugins for CLI data export."""

from __future__ import annotations

import csv
import io
import json
from abc import ABC, abstractmethod
from typing import Any

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


class OutputFormatter(ABC):
    """Base class for output formatters."""

    @abstractmethod
    def format(self, data: Any) -> str:
        """Format data to string.

        Args:
            data: Data to format

        Returns:
            Formatted string
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Get formatter name.

        Returns:
            Formatter name (e.g., "json", "csv")
        """
        pass


class JsonFormatter(OutputFormatter):
    """JSON output formatter."""

    def format(self, data: Any) -> str:
        """Format data as JSON.

        Args:
            data: Data to format (dict, list, or Seeds object)

        Returns:
            JSON string
        """
        # Handle Seeds object
        if hasattr(data, "to_json"):
            return data.to_json()

        # Handle dict/list
        return json.dumps(data, indent=2, default=str)

    def get_name(self) -> str:
        """Get formatter name."""
        return "json"


class CsvFormatter(OutputFormatter):
    """CSV output formatter."""

    def format(self, data: Any) -> str:
        """Format data as CSV.

        Args:
            data: Data to format (dict of lists)

        Returns:
            CSV string
        """
        output = io.StringIO()

        # Convert Seeds object to dict
        if hasattr(data, "to_dict"):
            data = data.to_dict()

        if isinstance(data, dict):
            # Multiple tables - write each table
            for table_name, rows in data.items():
                if not rows:
                    continue

                output.write(f"# Table: {table_name}\n")

                # Get column names from first row
                if isinstance(rows, list) and rows:
                    first_row = rows[0]
                    if isinstance(first_row, dict):
                        columns = list(first_row.keys())
                    else:
                        # Assume it's a tuple/list
                        columns = [f"col_{i}" for i in range(len(first_row))]

                    writer = csv.DictWriter(output, fieldnames=columns)
                    writer.writeheader()

                    for row in rows:
                        if isinstance(row, dict):
                            writer.writerow(row)
                        else:
                            # Convert tuple/list to dict
                            row_dict = dict(zip(columns, row, strict=False))
                            writer.writerow(row_dict)

                output.write("\n")

        return output.getvalue()

    def get_name(self) -> str:
        """Get formatter name."""
        return "csv"


class YamlFormatter(OutputFormatter):
    """YAML output formatter."""

    def format(self, data: Any) -> str:
        """Format data as YAML.

        Args:
            data: Data to format

        Returns:
            YAML string
        """
        if not YAML_AVAILABLE:
            raise RuntimeError("YAML support not available. Install PyYAML: pip install pyyaml")

        # Convert Seeds object to dict
        if hasattr(data, "to_dict"):
            data = data.to_dict()

        return yaml.dump(data, default_flow_style=False, sort_keys=False)

    def get_name(self) -> str:
        """Get formatter name."""
        return "yaml"


class TableFormatter(OutputFormatter):
    """Rich table output formatter (human-readable)."""

    def format(self, data: Any) -> str:
        """Format data as rich table.

        Args:
            data: Data to format

        Returns:
            Table string (markdown-style)
        """
        # Convert Seeds object to dict
        if hasattr(data, "to_dict"):
            data = data.to_dict()

        output = []

        if isinstance(data, dict):
            for table_name, rows in data.items():
                if not rows:
                    continue

                output.append(f"## {table_name}")
                output.append("")

                # Get column names from first row
                if isinstance(rows, list) and rows:
                    first_row = rows[0]
                    if isinstance(first_row, dict):
                        columns = list(first_row.keys())
                    else:
                        columns = [f"col_{i}" for i in range(len(first_row))]

                    # Header
                    output.append("| " + " | ".join(columns) + " |")
                    output.append("|" + "|".join(["---" for _ in columns]) + "|")

                    # Rows (limit to 10 for preview)
                    for row in rows[:10]:
                        if isinstance(row, dict):
                            values = [str(row.get(col, "")) for col in columns]
                        else:
                            values = [str(v) for v in row]
                        output.append("| " + " | ".join(values) + " |")

                    if len(rows) > 10:
                        output.append(f"\n... and {len(rows) - 10} more rows")

                output.append("")

        return "\n".join(output)

    def get_name(self) -> str:
        """Get formatter name."""
        return "table"


class FormatterRegistry:
    """Registry for output formatters."""

    def __init__(self):
        """Initialize formatter registry."""
        self._formatters: dict[str, OutputFormatter] = {}
        self._register_builtin_formatters()

    def _register_builtin_formatters(self):
        """Register built-in formatters."""
        self.register(JsonFormatter())
        self.register(CsvFormatter())
        self.register(TableFormatter())

        if YAML_AVAILABLE:
            self.register(YamlFormatter())

    def register(self, formatter: OutputFormatter):
        """Register a formatter.

        Args:
            formatter: Formatter instance to register
        """
        self._formatters[formatter.get_name()] = formatter

    def get(self, name: str) -> OutputFormatter:
        """Get formatter by name.

        Args:
            name: Formatter name

        Returns:
            Formatter instance

        Raises:
            ValueError: If formatter not found
        """
        if name not in self._formatters:
            available = ", ".join(self._formatters.keys())
            raise ValueError(f"Unknown format: {name}. Available formats: {available}")

        return self._formatters[name]

    def get_available_formats(self) -> list[str]:
        """Get list of available format names.

        Returns:
            List of format names
        """
        return list(self._formatters.keys())


# Global registry instance
_registry = FormatterRegistry()


def get_formatter(name: str) -> OutputFormatter:
    """Get formatter by name.

    Args:
        name: Formatter name

    Returns:
        Formatter instance
    """
    return _registry.get(name)


def get_available_formats() -> list[str]:
    """Get list of available format names.

    Returns:
        List of format names
    """
    return _registry.get_available_formats()


def format_output(data: Any, format_name: str = "json") -> str:
    """Format data using specified formatter.

    Args:
        data: Data to format
        format_name: Formatter name (default: "json")

    Returns:
        Formatted string
    """
    formatter = get_formatter(format_name)
    return formatter.format(data)
