"""Data models and type definitions."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ColumnInfo:
    """Column metadata from database introspection."""

    name: str
    pg_type: str
    is_nullable: bool
    is_primary_key: bool = False
    default_value: str | None = None


@dataclass
class ForeignKeyInfo:
    """Foreign key relationship metadata."""

    column: str
    referenced_table: str
    referenced_column: str


@dataclass
class TableInfo:
    """Table metadata with Trinity pattern detection."""

    name: str
    columns: list[ColumnInfo]
    foreign_keys: list[ForeignKeyInfo] = field(default_factory=list)

    @property
    def is_trinity(self) -> bool:
        """Check if table follows Trinity pattern (pk_*, id, identifier)."""
        col_names = {c.name for c in self.columns}
        has_pk = any(c.name.startswith("pk_") and c.is_primary_key for c in self.columns)
        has_id = "id" in col_names
        has_identifier = "identifier" in col_names
        return has_pk and has_id and has_identifier

    @property
    def pk_column(self) -> str | None:
        """Get primary key column name."""
        for col in self.columns:
            if col.is_primary_key:
                return col.name
        return None

    @property
    def id_column(self) -> str | None:
        """Get UUID id column name (Trinity pattern)."""
        if "id" in {c.name for c in self.columns}:
            return "id"
        return None

    @property
    def identifier_column(self) -> str | None:
        """Get identifier column name (Trinity pattern)."""
        if "identifier" in {c.name for c in self.columns}:
            return "identifier"
        return None


@dataclass
class SeedRow:
    """A single row of seed data."""

    _data: dict[str, Any]

    def __getattr__(self, name: str) -> Any:
        """Allow attribute access to column values."""
        if name.startswith("_"):
            raise AttributeError(f"No attribute '{name}'")
        if name in self._data:
            return self._data[name]
        raise AttributeError(f"No column '{name}' in seed data")


class Seeds:
    """Container for generated seed data."""

    def __init__(self):
        self._tables: dict[str, list[SeedRow]] = {}

    def add_table(self, table_name: str, rows: list[dict[str, Any]]) -> None:
        """Add seed data for a table."""
        self._tables[table_name] = [SeedRow(_data=row) for row in rows]

    def __getattr__(self, name: str) -> list[SeedRow]:
        """Allow attribute access to tables."""
        if name.startswith("_"):
            raise AttributeError(f"No attribute '{name}'")
        if name in self._tables:
            return self._tables[name]
        raise AttributeError(f"No table '{name}' in seeds")


@dataclass
class SeedPlan:
    """Plan for generating seed data for a single table."""

    table: str
    count: int
    strategy: str = "faker"
    overrides: dict[str, Any] = field(default_factory=dict)
