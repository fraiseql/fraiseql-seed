"""Schema introspection with caching and optimized queries."""

from psycopg import Connection

from fraiseql_data.dependency import DependencyGraph
from fraiseql_data.exceptions import SchemaNotFoundError, TableNotFoundError
from fraiseql_data.models import ColumnInfo, ForeignKeyInfo, TableInfo


class SchemaIntrospector:
    """Introspect PostgreSQL schema with caching."""

    def __init__(self, conn: Connection, schema: str):
        self.conn = conn
        self.schema = schema
        self._table_cache: dict[str, TableInfo] = {}
        self._dependency_graph_cache: DependencyGraph | None = None

        # Validate schema exists
        self._validate_schema()

    def _validate_schema(self) -> None:
        """Validate that schema exists in database."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT EXISTS(SELECT 1 FROM information_schema.schemata WHERE schema_name = %s)",
                (self.schema,),
            )
            exists = cur.fetchone()[0]
            if not exists:
                raise SchemaNotFoundError(self.schema)

    def get_tables(self) -> list[TableInfo]:
        """Get all tables in schema (cached)."""
        # If cache is populated, use it
        if self._table_cache:
            return list(self._table_cache.values())

        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = %s
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name
                """,
                (self.schema,),
            )
            rows = cur.fetchall()

        # Populate cache
        return [self.get_table_info(row[0]) for row in rows]

    def get_table_info(self, table_name: str) -> TableInfo:
        """Get complete table information (cached)."""
        if table_name in self._table_cache:
            return self._table_cache[table_name]

        # Validate table exists
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT EXISTS(
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = %s AND table_name = %s
                )
                """,
                (self.schema, table_name),
            )
            exists = cur.fetchone()[0]
            if not exists:
                raise TableNotFoundError(table_name, self.schema)

        columns = self.get_columns(table_name)
        foreign_keys = self.get_foreign_keys(table_name)

        table_info = TableInfo(name=table_name, columns=columns, foreign_keys=foreign_keys)
        self._table_cache[table_name] = table_info
        return table_info

    def get_columns(self, table_name: str) -> list[ColumnInfo]:
        """Get all columns for a table (optimized single query)."""
        with self.conn.cursor() as cur:
            # Single query to get columns + PK info
            cur.execute(
                """
                SELECT
                    c.column_name,
                    c.data_type,
                    c.is_nullable,
                    c.column_default,
                    CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END as is_pk
                FROM information_schema.columns c
                LEFT JOIN (
                    SELECT kcu.column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                      ON tc.constraint_name = kcu.constraint_name
                      AND tc.table_schema = kcu.table_schema
                    WHERE tc.constraint_type = 'PRIMARY KEY'
                      AND tc.table_schema = %s
                      AND tc.table_name = %s
                ) pk ON c.column_name = pk.column_name
                WHERE c.table_schema = %s
                  AND c.table_name = %s
                ORDER BY c.ordinal_position
                """,
                (self.schema, table_name, self.schema, table_name),
            )
            rows = cur.fetchall()

        return [
            ColumnInfo(
                name=row[0],
                pg_type=row[1],
                is_nullable=row[2] == "YES",
                default_value=row[3],
                is_primary_key=row[4],
            )
            for row in rows
        ]

    def get_foreign_keys(self, table_name: str) -> list[ForeignKeyInfo]:
        """Get all foreign keys for a table."""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    kcu.column_name,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                  ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                  ON ccu.constraint_name = tc.constraint_name
                  AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_schema = %s
                  AND tc.table_name = %s
                """,
                (self.schema, table_name),
            )
            rows = cur.fetchall()

        return [
            ForeignKeyInfo(column=row[0], referenced_table=row[1], referenced_column=row[2])
            for row in rows
        ]

    def get_dependency_graph(self) -> DependencyGraph:
        """Build dependency graph (cached)."""
        if self._dependency_graph_cache is not None:
            return self._dependency_graph_cache

        tables = self.get_tables()
        graph = DependencyGraph()

        for table in tables:
            graph.add_table(table.name)
            for fk in table.foreign_keys:
                # Skip self-references for now (Phase 2)
                if fk.referenced_table != table.name:
                    graph.add_dependency(table.name, fk.referenced_table)

        self._dependency_graph_cache = graph
        return graph

    def topological_sort(self) -> list[str]:
        """Sort tables in dependency order."""
        graph = self.get_dependency_graph()
        return graph.topological_sort()

    def clear_cache(self) -> None:
        """Clear cached introspection data."""
        self._table_cache.clear()
        self._dependency_graph_cache = None
