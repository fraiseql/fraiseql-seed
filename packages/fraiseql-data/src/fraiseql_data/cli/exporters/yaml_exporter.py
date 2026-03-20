"""YAML exporter implementation.

YAML is like JSON but more human-readable. It's often used for
configuration files and seed data.
"""

from __future__ import annotations

from typing import Any

import yaml  # Requires PyYAML package

from .base import BaseExporter


class YAMLExporter(BaseExporter):
    """Export data as YAML.

    Example output:
    users:
      - id: 1
        name: Alice
        email: alice@example.com
      - id: 2
        name: Bob
        email: bob@example.com
    """

    def __init__(self, pretty: bool = True):
        """Initialize YAML exporter.

        Args:
            pretty: If True, use default flow style (readable)
                    If False, use compact format
        """
        self.pretty = pretty

    def export_table(
        self,
        table_name: str,
        rows: list[dict[str, Any]],
        schema: str | None = None,  # noqa: ARG002
    ) -> str:
        """Export table as YAML."""
        # Build the output structure
        data = {table_name: rows}

        # Convert to YAML string
        return yaml.dump(
            data,
            default_flow_style=not self.pretty,  # False = pretty, True = compact
            sort_keys=False,  # Keep original order
        )

    def get_file_extension(self) -> str:
        """Get file extension for YAML files."""
        return ".yaml"

    def supports_multi_table(self) -> bool:
        """YAML can handle multiple tables."""
        return True
