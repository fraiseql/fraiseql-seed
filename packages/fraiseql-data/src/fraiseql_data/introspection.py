"""Schema introspection using PostgreSQL information_schema."""

from psycopg import Connection
from fraiseql_data.models import TableInfo, ColumnInfo, ForeignKeyInfo
from fraiseql_data.dependency import DependencyGraph


class SchemaIntrospector:
    """Introspect PostgreSQL schema for tables, columns, and relationships."""

    def __init__(self, conn: Connection, schema: str):
        self.conn = conn
        self.schema = schema
        self._cache: dict[str, TableInfo] = {}

    def get_tables(self) -> list[TableInfo]:
        """Get all tables in schema."""
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

        return [self.get_table_info(row[0]) for row in rows]

    def get_table_info(self, table_name: str) -> TableInfo:
        """Get complete table information."""
        if table_name in self._cache:
            return self._cache[table_name]

        columns = self.get_columns(table_name)
        foreign_keys = self.get_foreign_keys(table_name)

        table_info = TableInfo(name=table_name, columns=columns, foreign_keys=foreign_keys)
        self._cache[table_name] = table_info
        return table_info

    def get_columns(self, table_name: str) -> list[ColumnInfo]:
        """Get all columns for a table."""
        with self.conn.cursor() as cur:
            # Get column info
            cur.execute(
                """
                SELECT
                    c.column_name,
                    c.data_type,
                    c.is_nullable,
                    c.column_default
                FROM information_schema.columns c
                WHERE c.table_schema = %s
                  AND c.table_name = %s
                ORDER BY c.ordinal_position
                """,
                (self.schema, table_name),
            )
            column_rows = cur.fetchall()

            # Get primary key columns
            cur.execute(
                """
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_schema = %s
                  AND tc.table_name = %s
                """,
                (self.schema, table_name),
            )
            pk_columns = {row[0] for row in cur.fetchall()}

        columns = []
        for row in column_rows:
            col_name, data_type, is_nullable, default_value = row
            columns.append(
                ColumnInfo(
                    name=col_name,
                    pg_type=data_type,
                    is_nullable=is_nullable == "YES",
                    is_primary_key=col_name in pk_columns,
                    default_value=default_value,
                )
            )

        return columns

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

    def get_dependency_graph(self) -> "DependencyGraph":
        """Build dependency graph for all tables in schema."""
        from fraiseql_data.dependency import DependencyGraph

        tables = self.get_tables()
        graph = DependencyGraph()

        for table in tables:
            graph.add_table(table.name)
            for fk in table.foreign_keys:
                graph.add_dependency(table.name, fk.referenced_table)

        return graph

    def topological_sort(self) -> list[str]:
        """Sort tables in dependency order using topological sort."""
        graph = self.get_dependency_graph()
        return graph.topological_sort()
