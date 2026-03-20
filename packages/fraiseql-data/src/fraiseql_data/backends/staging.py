"""Staging backend - in-memory backend for testing without database."""

from typing import Any

from fraiseql_data.models import TableInfo


class StagingBackend:
    """
    In-memory backend for testing seed generation without database.

    Simulates database behavior:
    - Generates pk_* columns (sequential IDs starting from 1)
    - Optionally simulates Trinity's deterministic PK allocation (UUID→PK mapping)
    - Validates UNIQUE constraints (in-memory tracking)
    - Stores data in memory (not database)

    Use case: Fast unit tests, offline development, prototyping seed logic.
    """

    def __init__(self):
        """Initialize staging backend with empty state."""
        self._data: dict[str, list[dict[str, Any]]] = {}
        self._pk_sequences: dict[str, int] = {}
        self._trinity_simulation_enabled = False
        # Simulate Trinity's uuid_allocation_log: (table_name, uuid_value, tenant_id) → pk_value
        self._uuid_allocation_log: dict[tuple[str, str, Any], int] = {}

    def enable_trinity_simulation(self, tenant_id: Any = None) -> None:
        """
        Enable Trinity extension simulation for deterministic PK allocation.

        When enabled, the backend simulates Trinity's UUID→PK mapping:
        - Same UUID always generates same PK within the same test run
        - Deterministic across multiple StagingBackend instances
        - Supports multi-tenant isolation via tenant_id

        Args:
            tenant_id: Optional tenant ID for multi-tenant simulation
        """
        self._trinity_simulation_enabled = True
        self._trinity_tenant_id = tenant_id

    def allocate_uuid_pk(self, table_name: str, uuid_value: Any, tenant_id: Any = None) -> int:
        """
        Simulate Trinity's allocate_uuid_pk function.

        Args:
            table_name: Table name
            uuid_value: UUID value to allocate PK for
            tenant_id: Optional tenant ID (overrides constructor value if provided)

        Returns:
            Deterministically allocated PK value
        """
        # Use provided tenant_id or fall back to simulation-wide value
        if tenant_id is None:
            tenant_id = self._trinity_tenant_id

        # Convert UUID to string for consistent hashing
        uuid_str = str(uuid_value)
        allocation_key = (table_name, uuid_str, tenant_id)

        # Check if already allocated
        if allocation_key in self._uuid_allocation_log:
            return self._uuid_allocation_log[allocation_key]

        # Allocate new PK: next available for this table
        table_name_key = (table_name, tenant_id)
        if table_name_key not in self._pk_sequences:
            self._pk_sequences[table_name_key] = 1

        pk = self._pk_sequences[table_name_key]
        self._pk_sequences[table_name_key] += 1

        # Record allocation
        self._uuid_allocation_log[allocation_key] = pk
        return pk

    def insert_rows(
        self,
        table_info: TableInfo,
        rows: list[dict[str, Any]],
        bulk: bool = True,  # noqa: ARG002
    ) -> list[dict[str, Any]]:
        """
        Simulate database insert (generate PKs, store in memory).

        Args:
            table_info: Table metadata
            rows: List of row data (without pk_* columns, unless Trinity allocated)
            bulk: Ignored (staging always behaves the same)

        Returns:
            List of complete rows including generated pk_* columns
        """
        if not rows:
            return []

        table_name = table_info.name

        # Initialize PK sequence if first time seeing this table (non-Trinity mode)
        if table_name not in self._pk_sequences and not self._trinity_simulation_enabled:
            self._pk_sequences[table_name] = 1

        inserted_rows = []
        for row in rows:
            complete_row = row.copy()

            # Find pk_* column
            pk_column = None
            for col in table_info.columns:
                if col.is_primary_key and col.name.startswith("pk_"):
                    pk_column = col.name
                    break

            if pk_column and (pk_column not in complete_row or complete_row[pk_column] is None):
                if self._trinity_simulation_enabled:
                    # Trinity simulation: use UUID to allocate PK deterministically
                    uuid_value = complete_row.get("id")
                    if uuid_value is not None:
                        pk = self.allocate_uuid_pk(table_name, uuid_value, self._trinity_tenant_id)
                        complete_row[pk_column] = pk
                    else:
                        # Fallback: sequential (shouldn't happen with Trinity generator)
                        table_key = (table_name, self._trinity_tenant_id)
                        if table_key not in self._pk_sequences:
                            self._pk_sequences[table_key] = 1
                        pk = self._pk_sequences[table_key]
                        self._pk_sequences[table_key] += 1
                        complete_row[pk_column] = pk
                else:
                    # Standard mode: sequential allocation
                    complete_row[pk_column] = self._pk_sequences[table_name]
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
