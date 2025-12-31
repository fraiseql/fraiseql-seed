"""
Core data models for fraiseql-seed.

Defines the data structures used throughout the package for representing
database schema information, Trinity pattern detection, and foreign key relationships.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TrinityPattern:
    """
    Represents the Trinity identifier pattern used in FraiseQL projects.

    The Trinity pattern uses three identifiers:
    - pk_{entity}: INTEGER IDENTITY (internal, fast joins)
    - id: UUID (public, API-exposed)
    - identifier: TEXT (business key, human-readable)
    """

    pk_prefix: str = "pk_"
    pk_suffix: str = ""
    id_column: str = "id"
    identifier_column: str = "identifier"

    def is_pk_column(self, column_name: str) -> bool:
        """Check if column name matches pk pattern."""
        if self.pk_suffix:
            return column_name.startswith(self.pk_prefix) and column_name.endswith(
                self.pk_suffix
            )
        return column_name.startswith(self.pk_prefix)

    def is_id_column(self, column_name: str) -> bool:
        """Check if column is the UUID id column."""
        return column_name == self.id_column

    def is_identifier_column(self, column_name: str) -> bool:
        """Check if column is the business identifier column."""
        return column_name == self.identifier_column

    def extract_entity_name(self, pk_column_name: str) -> str:
        """Extract entity name from pk column (e.g., pk_manufacturer → manufacturer)."""
        name = pk_column_name
        if name.startswith(self.pk_prefix):
            name = name[len(self.pk_prefix) :]
        if self.pk_suffix and name.endswith(self.pk_suffix):
            name = name[: -len(self.pk_suffix)]
        return name


@dataclass
class Column:
    """Represents a table column with its properties."""

    name: str
    data_type: str
    is_nullable: bool
    column_default: Optional[str]
    is_identity: bool
    is_generated: bool  # GENERATED ALWAYS AS (expr) STORED
    generation_expression: Optional[str] = None

    def is_pk(self, trinity: TrinityPattern) -> bool:
        """Check if this is a primary key column based on Trinity pattern."""
        return trinity.is_pk_column(self.name) and self.is_identity

    def is_fk(self, trinity: TrinityPattern) -> bool:
        """Check if this is a foreign key column (fk_* INTEGER pattern)."""
        return self.name.startswith("fk_") and self.data_type == "integer"

    def is_uuid_id(self, trinity: TrinityPattern) -> bool:
        """Check if this is the UUID id column."""
        return trinity.is_id_column(self.name) and self.data_type == "uuid"

    def is_identifier(self, trinity: TrinityPattern) -> bool:
        """Check if this is the business identifier column."""
        return trinity.is_identifier_column(self.name)


@dataclass
class ForeignKey:
    """Represents a foreign key constraint."""

    column_name: str
    target_schema: str
    target_table: str
    target_column: str
    constraint_name: Optional[str] = None

    @property
    def staging_column_name(self) -> str:
        """
        Convert FK column name for staging schema.

        Production: fk_manufacturer INTEGER
        Staging:    fk_manufacturer_id UUID
        """
        return f"{self.column_name}_id"

    @property
    def target_pk_column(self) -> str:
        """
        Get the target table's pk column name.

        Assumes Trinity pattern where target_column is pk_{entity}.
        """
        return self.target_column

    def is_self_reference(self, source_schema: str, source_table: str) -> bool:
        """Check if this FK references the same table (needs two-pass loading)."""
        return (
            self.target_schema == source_schema and self.target_table == source_table
        )


@dataclass
class TableInfo:
    """Complete information about a database table."""

    schema_name: str
    table_name: str
    columns: list[Column] = field(default_factory=list)
    foreign_keys: list[ForeignKey] = field(default_factory=list)
    primary_key_column: Optional[str] = None
    has_simple_id_unique: bool = True  # True if id column has simple UNIQUE constraint

    @property
    def full_name(self) -> str:
        """Get fully qualified table name."""
        return f"{self.schema_name}.{self.table_name}"

    def staging_full_name(self, staging_schema: str = "prep_seed") -> str:
        """Get fully qualified staging table name."""
        return f"{staging_schema}.{self.table_name}"

    def has_self_reference(self) -> bool:
        """Check if table has self-referencing FK (needs two-pass loading)."""
        return any(
            fk.is_self_reference(self.schema_name, self.table_name)
            for fk in self.foreign_keys
        )

    def get_self_referencing_fks(self) -> list[ForeignKey]:
        """Get all self-referencing foreign keys."""
        return [
            fk
            for fk in self.foreign_keys
            if fk.is_self_reference(self.schema_name, self.table_name)
        ]

    def get_non_self_referencing_fks(self) -> list[ForeignKey]:
        """Get all non-self-referencing foreign keys."""
        return [
            fk
            for fk in self.foreign_keys
            if not fk.is_self_reference(self.schema_name, self.table_name)
        ]

    def get_pk_column(self, trinity: TrinityPattern) -> Optional[Column]:
        """Get the primary key column."""
        for col in self.columns:
            if col.is_pk(trinity):
                return col
        return None

    def get_id_column(self, trinity: TrinityPattern) -> Optional[Column]:
        """Get the UUID id column."""
        for col in self.columns:
            if col.is_uuid_id(trinity):
                return col
        return None

    def get_identifier_column(self, trinity: TrinityPattern) -> Optional[Column]:
        """Get the business identifier column."""
        for col in self.columns:
            if col.is_identifier(trinity):
                return col
        return None

    def has_trinity_pattern(self, trinity: TrinityPattern) -> bool:
        """
        Check if this table follows the Trinity pattern.

        Returns True if table has:
        1. pk_{entity} INTEGER IDENTITY PRIMARY KEY
        2. id UUID UNIQUE
        3. identifier TEXT UNIQUE
        """
        has_pk = any(col.is_pk(trinity) for col in self.columns)
        has_id = any(col.is_uuid_id(trinity) for col in self.columns)
        has_identifier = any(col.is_identifier(trinity) for col in self.columns)
        return has_pk and has_id and has_identifier

    def get_regular_columns(self, trinity: TrinityPattern) -> list[Column]:
        """
        Get all regular columns (excluding pk, id, identifier, generated).

        These are the columns that need to be copied from staging to production.
        """
        return [
            col
            for col in self.columns
            if not col.is_pk(trinity)
            and not col.is_generated
            and col.name != trinity.id_column
        ]

    def get_insert_columns(self, trinity: TrinityPattern) -> list[str]:
        """
        Get column names for INSERT statement (production table).

        Includes: id, regular columns, FK columns
        Excludes: pk_* (auto-generated), GENERATED columns
        """
        columns = []

        # Always include id (UUID)
        if any(col.is_uuid_id(trinity) for col in self.columns):
            columns.append(trinity.id_column)

        # Include regular columns
        for col in self.get_regular_columns(trinity):
            # Include FK columns (will be resolved from UUID)
            if col.is_fk(trinity):
                columns.append(col.name)
            # Include non-generated regular columns
            elif not col.is_generated:
                columns.append(col.name)

        return columns


@dataclass
class DependencyGraph:
    """
    Represents the dependency graph for tables based on foreign key relationships.

    Used for topological sorting to determine safe resolution order.
    """

    nodes: set[str] = field(default_factory=set)
    edges: dict[str, set[str]] = field(default_factory=dict)  # table -> dependencies
    reverse_edges: dict[str, set[str]] = field(
        default_factory=dict
    )  # table -> dependents

    def add_table(self, table_name: str) -> None:
        """Add a table node to the graph."""
        self.nodes.add(table_name)
        if table_name not in self.edges:
            self.edges[table_name] = set()
        if table_name not in self.reverse_edges:
            self.reverse_edges[table_name] = set()

    def add_dependency(
        self, table_name: str, depends_on: str, is_self_reference: bool = False
    ) -> None:
        """
        Add a dependency edge.

        table_name depends on depends_on.
        Self-references are tracked but not added as hard dependencies.
        """
        self.add_table(table_name)
        self.add_table(depends_on)

        if not is_self_reference:
            self.edges[table_name].add(depends_on)
            self.reverse_edges[depends_on].add(table_name)

    def topological_sort(self) -> list[str]:
        """
        Return tables in dependency-safe order using Kahn's algorithm.

        Tables with no dependencies come first, tables that depend on others come later.
        """
        # Calculate in-degree for each node
        in_degree = {node: len(deps) for node, deps in self.edges.items()}

        # Queue of nodes with no dependencies
        queue = [node for node in self.nodes if in_degree[node] == 0]
        result = []

        while queue:
            # Sort for deterministic output
            queue.sort()
            node = queue.pop(0)
            result.append(node)

            # For each dependent, decrease in-degree
            for dependent in sorted(self.reverse_edges.get(node, [])):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        # Check for cycles
        if len(result) != len(self.nodes):
            remaining = [node for node in self.nodes if node not in result]
            raise ValueError(f"Circular dependency detected involving: {remaining}")

        return result

    def detect_cycles(self) -> list[list[str]]:
        """
        Detect circular dependencies (excluding self-references).

        Returns list of cycles, where each cycle is a list of table names.
        """
        cycles = []
        visited = set()
        path = []

        def dfs(node: str) -> None:
            if node in path:
                # Found cycle
                cycle_start = path.index(node)
                cycle = path[cycle_start:] + [node]
                if cycle not in cycles:
                    cycles.append(cycle)
                return

            if node in visited:
                return

            visited.add(node)
            path.append(node)

            for dep in self.edges.get(node, []):
                dfs(dep)

            path.pop()

        for node in self.nodes:
            if node not in visited:
                dfs(node)

        return cycles
