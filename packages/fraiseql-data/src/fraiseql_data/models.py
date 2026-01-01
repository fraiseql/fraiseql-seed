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
class MultiColumnUniqueConstraint:
    """
    Multi-column UNIQUE constraint metadata.

    Attributes:
        columns: Tuple of column names in the constraint (e.g., ("year", "month", "code"))
        constraint_name: PostgreSQL constraint name
    """

    columns: tuple[str, ...]
    constraint_name: str


@dataclass
class CheckConstraint:
    """
    CHECK constraint metadata.

    Attributes:
        constraint_name: PostgreSQL constraint name
        check_clause: CHECK constraint condition (e.g., "price > 0")
    """

    constraint_name: str
    check_clause: str


@dataclass
class TableInfo:
    """
    Table metadata with Trinity pattern detection.

    Attributes:
        name: Table name
        columns: List of column metadata
        foreign_keys: List of foreign key relationships
        multi_unique_constraints: Multi-column UNIQUE constraints (Phase 3)
        check_constraints: CHECK constraints (Phase 3)
    """

    name: str
    columns: list[ColumnInfo]
    foreign_keys: list[ForeignKeyInfo] = field(default_factory=list)
    multi_unique_constraints: list["MultiColumnUniqueConstraint"] = field(
        default_factory=list
    )
    check_constraints: list["CheckConstraint"] = field(default_factory=list)

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

        Self-referencing FKs are relationships where a table references itself,
        commonly used for hierarchical data (e.g., parent_id -> pk_category).

        These FKs are handled specially during seed generation:
        - Not included in dependency graph (avoid circular dependencies)
        - Require one-by-one insertion to track previous rows
        - First row gets NULL (if nullable), subsequent rows pick random parent

        Returns:
            List of ForeignKeyInfo objects where is_self_referencing is True

        Example:
            >>> # Table with parent_category FK to itself
            >>> table_info = introspector.get_table_info("tb_category")
            >>> self_refs = table_info.get_self_referencing_fks()
            >>> if self_refs:
            >>>     print(f"Self-referencing FK: {self_refs[0].column}")
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

    @classmethod
    def from_json(
        cls, file_path: Any | None = None, json_str: str | None = None
    ) -> "Seeds":
        """
        Import seed data from JSON format.

        Args:
            file_path: Optional file path to read JSON from (str or Path)
            json_str: Optional JSON string to parse

        Returns:
            Seeds object with imported data

        Raises:
            ValueError: If neither file_path nor json_str provided

        Example:
            >>> # Load from file
            >>> seeds = Seeds.from_json("seed_data.json")
            >>> # Or load from string
            >>> seeds = Seeds.from_json(json_str=json_string)
        """
        import json
        from pathlib import Path

        if file_path is not None:
            path = Path(file_path)
            data = json.loads(path.read_text())
        elif json_str is not None:
            data = json.loads(json_str)
        else:
            raise ValueError("Must provide either file_path or json_str")

        seeds = cls()
        for table_name, rows_data in data.items():
            rows = [SeedRow(_data=row_dict) for row_dict in rows_data]
            seeds._tables[table_name] = rows

        return seeds

    @classmethod
    def from_csv(cls, table_name: str, file_path: Any) -> "Seeds":
        """
        Import single table from CSV format.

        Args:
            table_name: Table name for the imported data
            file_path: CSV file path (str or Path)

        Returns:
            Seeds object with imported table data

        Example:
            >>> seeds = Seeds.from_csv("tb_manufacturer", "manufacturers.csv")
            >>> print(len(seeds.tb_manufacturer))
        """
        import csv
        from pathlib import Path

        seeds = cls()
        rows = []

        path = Path(file_path)
        with path.open("r", newline="") as f:
            reader = csv.DictReader(f)
            for row_dict in reader:
                rows.append(SeedRow(_data=row_dict))

        seeds._tables[table_name] = rows
        return seeds

    def to_json(self, file_path: Any | None = None, indent: int = 2) -> str | None:
        """
        Export seed data to JSON format.

        Args:
            file_path: Optional file path to write JSON to (str or Path)
            indent: JSON indentation (default: 2)

        Returns:
            JSON string if file_path is None, otherwise None

        Example:
            >>> seeds = builder.execute()
            >>> # Get JSON string
            >>> json_str = seeds.to_json()
            >>> # Or write to file
            >>> seeds.to_json("seed_data.json")
        """
        import json
        from pathlib import Path

        # Convert SeedRow objects to dicts
        data = {
            table_name: [row._data for row in rows]
            for table_name, rows in self._tables.items()
        }

        # Serialize with default=str to handle UUID, datetime, etc.
        json_str = json.dumps(data, indent=indent, default=str)

        if file_path:
            path = Path(file_path)
            path.write_text(json_str)
            return None

        return json_str

    def to_csv(self, table_name: str, file_path: Any) -> None:
        """
        Export single table to CSV format.

        Args:
            table_name: Table name to export
            file_path: CSV file path (str or Path)

        Raises:
            ValueError: If table not in seeds

        Example:
            >>> seeds = builder.execute()
            >>> seeds.to_csv("tb_manufacturer", "manufacturers.csv")
        """
        import csv
        from pathlib import Path

        if table_name not in self._tables:
            available = ", ".join(self._tables.keys())
            raise ValueError(
                f"Table '{table_name}' not in seeds. "
                f"Available tables: {available}"
            )

        rows = self._tables[table_name]
        if not rows:
            # Empty table - write headers only
            return

        path = Path(file_path)
        with path.open("w", newline="") as f:
            fieldnames = list(rows[0]._data.keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for row in rows:
                # Convert all values to strings for CSV
                csv_row = {
                    k: str(v) if v is not None else ""
                    for k, v in row._data.items()
                }
                writer.writerow(csv_row)


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
