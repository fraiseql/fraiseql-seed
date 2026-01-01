"""Schema introspection with caching and optimized queries."""

from psycopg import Connection

from fraiseql_data.dependency import DependencyGraph
from fraiseql_data.exceptions import SchemaNotFoundError, TableNotFoundError
from fraiseql_data.models import (
    CheckConstraint,
    ColumnInfo,
    ForeignKeyInfo,
    MultiColumnUniqueConstraint,
    TableInfo,
)


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
        multi_unique_constraints = self.get_multi_column_unique_constraints(table_name)
        check_constraints = self.get_check_constraints(table_name)

        table_info = TableInfo(
            name=table_name,
            columns=columns,
            foreign_keys=foreign_keys,
            multi_unique_constraints=multi_unique_constraints,
            check_constraints=check_constraints,
        )
        self._table_cache[table_name] = table_info
        return table_info

    def get_columns(self, table_name: str) -> list[ColumnInfo]:
        """Get all columns for a table (optimized single query)."""
        # Get UNIQUE constraints for this table
        unique_columns = self.get_unique_constraints(table_name)

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
                is_unique=row[0] in unique_columns,
            )
            for row in rows
        ]

    def get_unique_constraints(self, table_name: str) -> set[str]:
        """
        Get column names with UNIQUE constraints.

        Queries PostgreSQL's information_schema to find columns with UNIQUE
        constraints. This information is used during seed generation to:
        - Detect collisions and retry value generation
        - Prevent duplicate key violations

        Args:
            table_name: Table name

        Returns:
            Set of column names that have UNIQUE constraints

        Example:
            >>> introspector = SchemaIntrospector(conn, "public")
            >>> unique_cols = introspector.get_unique_constraints("tb_user")
            >>> if "email" in unique_cols:
            >>>     print("Email column has UNIQUE constraint")

        Note:
            This does NOT include PRIMARY KEY columns (they're already
            tracked via is_primary_key).
        """
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'UNIQUE'
                  AND tc.table_schema = %s
                  AND tc.table_name = %s
                """,
                (self.schema, table_name),
            )
            return {row[0] for row in cur.fetchall()}

    def get_multi_column_unique_constraints(
        self, table_name: str
    ) -> list["MultiColumnUniqueConstraint"]:
        """
        Get multi-column UNIQUE constraints.

        Queries PostgreSQL's information_schema to find UNIQUE constraints
        that span multiple columns (e.g., UNIQUE(year, month, code)).

        Args:
            table_name: Table name

        Returns:
            List of MultiColumnUniqueConstraint objects, each containing:
            - columns: tuple of column names in the constraint
            - constraint_name: PostgreSQL constraint name

        Example:
            >>> introspector = SchemaIntrospector(conn, "public")
            >>> constraints = introspector.get_multi_column_unique_constraints("tb_order")
            >>> for constraint in constraints:
            >>>     print(f"UNIQUE{constraint.columns}")
            UNIQUE('customer_code', 'order_number')
            UNIQUE('year', 'month', 'customer_code')

        Note:
            Only returns constraints with 2+ columns. Single-column UNIQUE
            constraints are handled by get_unique_constraints().
        """
        with self.conn.cursor() as cur:
            # Get all UNIQUE constraints with their columns
            # Use string_agg for simplicity to avoid array parsing issues
            cur.execute(
                """
                SELECT
                    tc.constraint_name,
                    string_agg(kcu.column_name, ',' ORDER BY kcu.ordinal_position) as columns
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'UNIQUE'
                  AND tc.table_schema = %s
                  AND tc.table_name = %s
                GROUP BY tc.constraint_name
                HAVING COUNT(*) > 1
                """,
                (self.schema, table_name),
            )

            constraints = []
            for row in cur.fetchall():
                constraint_name = row[0]
                # Split comma-separated column names into tuple
                columns = tuple(row[1].split(","))
                constraints.append(
                    MultiColumnUniqueConstraint(
                        columns=columns, constraint_name=constraint_name
                    )
                )

            return constraints

    def get_check_constraints(self, table_name: str) -> list["CheckConstraint"]:
        """
        Get CHECK constraints for a table.

        Queries PostgreSQL's information_schema to find CHECK constraints
        (e.g., CHECK (price > 0), CHECK (status IN ('active', 'inactive'))).

        Args:
            table_name: Table name

        Returns:
            List of CheckConstraint objects, each containing:
            - constraint_name: PostgreSQL constraint name
            - check_clause: CHECK constraint condition

        Example:
            >>> introspector = SchemaIntrospector(conn, "public")
            >>> checks = introspector.get_check_constraints("tb_product")
            >>> for check in checks:
            >>>     print(f"{check.constraint_name}: {check.check_clause}")
            tb_product_price_check: (price > 0)

        Note:
            CHECK constraints are difficult to satisfy automatically, so
            the builder will emit warnings when they are detected without
            user-provided overrides.
        """
        with self.conn.cursor() as cur:
            # Get CHECK constraints
            cur.execute(
                """
                SELECT
                    con.conname AS constraint_name,
                    pg_get_constraintdef(con.oid) AS check_clause
                FROM pg_constraint con
                JOIN pg_namespace nsp ON con.connamespace = nsp.oid
                JOIN pg_class cls ON con.conrelid = cls.oid
                WHERE con.contype = 'c'
                  AND nsp.nspname = %s
                  AND cls.relname = %s
                """,
                (self.schema, table_name),
            )

            constraints = []
            for row in cur.fetchall():
                constraint_name = row[0]
                check_clause = row[1]
                # Remove "CHECK " prefix from clause if present
                if check_clause.startswith("CHECK "):
                    check_clause = check_clause[6:]
                constraints.append(
                    CheckConstraint(
                        constraint_name=constraint_name, check_clause=check_clause
                    )
                )

            return constraints

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
            ForeignKeyInfo(
                column=row[0],
                referenced_table=row[1],
                referenced_column=row[2],
                is_self_referencing=row[1] == table_name,
            )
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
                # Skip self-references (don't add to dependency graph)
                if not fk.is_self_referencing:
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


class MockIntrospector:
    """
    Mock introspector for staging backend (no database required).

    Allows manually setting table schemas for testing without a database connection.
    Used by SeedBuilder with backend="staging".
    """

    def __init__(self):
        """Initialize with empty schema registry."""
        self._schemas: dict[str, TableInfo] = {}

    def set_table_schema(self, table_name: str, table_info: TableInfo) -> None:
        """
        Manually set table schema.

        Args:
            table_name: Table name
            table_info: Table metadata

        Example:
            >>> introspector = MockIntrospector()
            >>> table_info = TableInfo(name="users", columns=[...])
            >>> introspector.set_table_schema("users", table_info)
        """
        self._schemas[table_name] = table_info

    def get_table_info(self, table_name: str) -> TableInfo:
        """
        Get manually-set table schema.

        Args:
            table_name: Table name

        Returns:
            TableInfo for the table

        Raises:
            ValueError: If table schema not set
        """
        if table_name not in self._schemas:
            raise ValueError(
                f"Table schema not set for '{table_name}'. "
                f"Call set_table_schema() first when using staging backend."
            )
        return self._schemas[table_name]

    def get_dependency_graph(self) -> DependencyGraph:
        """
        Get dependency graph for set tables.

        Returns:
            DependencyGraph with FK relationships
        """
        # Build graph from manually-set schemas
        graph = DependencyGraph()

        for table_name, table_info in self._schemas.items():
            # Add table
            graph.add_table(table_name)

            # Add FK dependencies (skip self-references)
            for fk in table_info.foreign_keys:
                if not fk.is_self_referencing:
                    graph.add_dependency(table_name, fk.referenced_table)

        return graph

    def topological_sort(self) -> list[str]:
        """
        Sort tables in dependency order.

        Returns:
            List of table names in dependency order
        """
        graph = self.get_dependency_graph()
        return graph.topological_sort()
