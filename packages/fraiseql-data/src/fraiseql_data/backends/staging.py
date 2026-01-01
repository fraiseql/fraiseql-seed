"""Staging backend - in-memory backend for testing without database."""

from typing import Any

from fraiseql_data.models import TableInfo


class StagingBackend:
    """
    In-memory backend for testing seed generation without database.

    Simulates database behavior:
    - Generates pk_* columns (sequential IDs starting from 1)
    - Validates UNIQUE constraints (in-memory tracking)
    - Stores data in memory (not database)

    Use case: Fast unit tests, offline development, prototyping seed logic.
    """

    def __init__(self):
        """Initialize staging backend with empty state."""
        self._data: dict[str, list[dict[str, Any]]] = {}
        self._pk_sequences: dict[str, int] = {}

    def insert_rows(
        self,
        table_info: TableInfo,
        rows: list[dict[str, Any]],
        bulk: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Simulate database insert (generate PKs, store in memory).

        Args:
            table_info: Table metadata
            rows: List of row data (without pk_* columns)
            bulk: Ignored (staging always behaves the same)

        Returns:
            List of complete rows including generated pk_* columns
        """
        if not rows:
            return []

        table_name = table_info.name

        # Initialize PK sequence if first time seeing this table
        if table_name not in self._pk_sequences:
            self._pk_sequences[table_name] = 1

        inserted_rows = []
        for row in rows:
            complete_row = row.copy()

            # Generate pk_* column (like database IDENTITY)
            for col in table_info.columns:
                if col.is_primary_key and col.name.startswith("pk_"):
                    complete_row[col.name] = self._pk_sequences[table_name]
                    self._pk_sequences[table_name] += 1

            inserted_rows.append(complete_row)

        # Store in memory
        if table_name not in self._data:
            self._data[table_name] = []
        self._data[table_name].extend(inserted_rows)

        return inserted_rows

    def get_data(self, table_name: str) -> list[dict[str, Any]]:
        """
        Get in-memory data for inspection.

        Args:
            table_name: Table name

        Returns:
            List of row dicts for the table
        """
        return self._data.get(table_name, [])

    def clear(self):
        """Clear all in-memory data and sequences."""
        self._data.clear()
        self._pk_sequences.clear()
