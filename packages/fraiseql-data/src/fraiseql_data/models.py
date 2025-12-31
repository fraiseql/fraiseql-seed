"""Data models and type definitions."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ColumnInfo:
    """
    Column metadata from database introspection.

    Attributes:
        name: Column name
        pg_type: PostgreSQL data type
        is_nullable: Whether column allows NULL values
        is_primary_key: Whether column is primary key
        default_value: Database default value expression (if any)
        is_unique: Whether column has UNIQUE constraint
    """

    name: str
    pg_type: str
    is_nullable: bool
    is_primary_key: bool = False
    default_value: str | None = None
    is_unique: bool = False


@dataclass
class ForeignKeyInfo:
    """
    Foreign key relationship metadata.

    Attributes:
        column: Foreign key column name in this table
        referenced_table: Parent table being referenced
        referenced_column: Column in parent table (usually PK)
        is_self_referencing: Whether this FK references the same table
    """

    column: str
    referenced_table: str
    referenced_column: str
    is_self_referencing: bool = False


@dataclass
class TableInfo:
    """
    Table metadata with Trinity pattern detection.

    Attributes:
        name: Table name
        columns: List of column metadata
        foreign_keys: List of foreign key relationships
    """

    name: str
    columns: list[ColumnInfo]
    foreign_keys: list[ForeignKeyInfo] = field(default_factory=list)

    @property
    def is_trinity(self) -> bool:
        """
        Check if table follows Trinity pattern.

        Returns:
            True if table has pk_* (INTEGER IDENTITY), id (UUID), identifier (TEXT)
        """
        col_names = {c.name for c in self.columns}
        has_pk = any(c.name.startswith("pk_") and c.is_primary_key for c in self.columns)
        has_id = "id" in col_names
        has_identifier = "identifier" in col_names
        return has_pk and has_id and has_identifier

    @property
    def pk_column(self) -> str | None:
        """
        Get primary key column name.

        Returns:
            Primary key column name or None if no PK found
        """
        for col in self.columns:
            if col.is_primary_key:
                return col.name
        return None

    @property
    def id_column(self) -> str | None:
        """
        Get UUID id column name (Trinity pattern).

        Returns:
            'id' if exists, None otherwise
        """
        if "id" in {c.name for c in self.columns}:
            return "id"
        return None

    @property
    def identifier_column(self) -> str | None:
        """
        Get identifier column name (Trinity pattern).

        Returns:
            'identifier' if exists, None otherwise
        """
        if "identifier" in {c.name for c in self.columns}:
            return "identifier"
        return None

    def get_self_referencing_fks(self) -> list[ForeignKeyInfo]:
        """
        Get all self-referencing foreign keys.

        Returns:
            List of ForeignKeyInfo objects where is_self_referencing is True
        """
        return [fk for fk in self.foreign_keys if fk.is_self_referencing]


@dataclass
class SeedRow:
    """
    A single row of seed data with attribute access.

    Allows accessing column values as attributes:
        row.pk_manufacturer  # Access column value
        row.id              # Access UUID
        row.name            # Access name column

    Attributes:
        _data: Raw column data dict
    """

    _data: dict[str, Any]

    def __getattr__(self, name: str) -> Any:
        """
        Allow attribute access to column values.

        Args:
            name: Column name

        Returns:
            Column value

        Raises:
            AttributeError: If column doesn't exist
        """
        if name.startswith("_"):
            raise AttributeError(f"No attribute '{name}'")
        if name in self._data:
            return self._data[name]
        raise AttributeError(f"No column '{name}' in seed data")


class Seeds:
    """
    Container for generated seed data with attribute access.

    Allows accessing tables as attributes:
        seeds.tb_manufacturer  # List of SeedRow objects
        seeds.tb_model         # List of SeedRow objects
    """

    def __init__(self):
        self._tables: dict[str, list[SeedRow]] = {}

    def add_table(self, table_name: str, rows: list[dict[str, Any]]) -> None:
        """
        Add seed data for a table.

        Args:
            table_name: Table name
            rows: List of row dicts with column data
        """
        self._tables[table_name] = [SeedRow(_data=row) for row in rows]

    def __getattr__(self, name: str) -> list[SeedRow]:
        """
        Allow attribute access to tables.

        Args:
            name: Table name

        Returns:
            List of SeedRow objects for the table

        Raises:
            AttributeError: If table doesn't exist in seeds
        """
        if name.startswith("_"):
            raise AttributeError(f"No attribute '{name}'")
        if name in self._tables:
            return self._tables[name]
        raise AttributeError(f"No table '{name}' in seeds")


@dataclass
class SeedPlan:
    """
    Plan for generating seed data for a single table.

    Attributes:
        table: Table name
        count: Number of rows to generate
        strategy: Generation strategy ("faker" is default)
        overrides: Column overrides (callable or static value)
    """

    table: str
    count: int
    strategy: str = "faker"
    overrides: dict[str, Any] = field(default_factory=dict)
