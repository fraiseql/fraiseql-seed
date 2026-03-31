"""Tests for cross-schema foreign key support (Issue #17)."""

import pytest
from fraiseql_data import SeedBuilder
from fraiseql_data.introspection import SchemaIntrospector
from fraiseql_data.models import ColumnInfo, ForeignKeyInfo, TableInfo
from psycopg import Connection


@pytest.fixture
def cross_schema(db_conn: Connection):
    """Create two schemas with a cross-schema FK relationship."""
    with db_conn.cursor() as cur:
        cur.execute("DROP SCHEMA IF EXISTS schema_parent CASCADE")
        cur.execute("DROP SCHEMA IF EXISTS schema_child CASCADE")
        cur.execute("CREATE SCHEMA schema_parent")
        cur.execute("CREATE SCHEMA schema_child")

        cur.execute("""
            CREATE TABLE schema_parent.tb_organization (
                pk_organization INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                name TEXT NOT NULL
            )
        """)
        cur.execute("""
            INSERT INTO schema_parent.tb_organization (name)
            VALUES ('Org A'), ('Org B'), ('Org C')
        """)

        cur.execute("""
            CREATE TABLE schema_child.tb_project (
                pk_project INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                name TEXT NOT NULL,
                fk_organization INTEGER NOT NULL
                    REFERENCES schema_parent.tb_organization(pk_organization)
            )
        """)
        db_conn.commit()

    yield {"parent_schema": "schema_parent", "child_schema": "schema_child"}

    with db_conn.cursor() as cur:
        cur.execute("DROP SCHEMA IF EXISTS schema_child CASCADE")
        cur.execute("DROP SCHEMA IF EXISTS schema_parent CASCADE")
        db_conn.commit()


class TestCrossSchemaFKDetection:
    """SchemaIntrospector detects cross-schema foreign keys."""

    def test_fk_has_referenced_schema(self, db_conn: Connection, cross_schema):
        introspector = SchemaIntrospector(db_conn, schema=cross_schema["child_schema"])
        fks = introspector.get_foreign_keys("tb_project")

        assert len(fks) == 1
        fk = fks[0]
        assert fk.column == "fk_organization"
        assert fk.referenced_table == "tb_organization"
        assert fk.referenced_column == "pk_organization"
        assert fk.referenced_schema == "schema_parent"
        assert fk.is_self_referencing is False

    def test_same_schema_fk_has_no_referenced_schema(self, db_conn: Connection, cross_schema):
        """Same-schema FKs should have referenced_schema=None."""
        # Add a same-schema FK to test
        with db_conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE schema_child.tb_task (
                    pk_task INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    name TEXT NOT NULL,
                    fk_project INTEGER NOT NULL
                        REFERENCES schema_child.tb_project(pk_project)
                )
            """)
            db_conn.commit()

        introspector = SchemaIntrospector(db_conn, schema=cross_schema["child_schema"])
        fks = introspector.get_foreign_keys("tb_task")

        assert len(fks) == 1
        assert fks[0].referenced_schema is None


class TestCrossSchemaDepGraph:
    """Dependency graph handles cross-schema FKs correctly."""

    def test_cross_schema_target_not_in_graph(self, db_conn: Connection, cross_schema):
        introspector = SchemaIntrospector(db_conn, schema=cross_schema["child_schema"])
        graph = introspector.get_dependency_graph()

        deps = graph.get_dependencies("tb_project")
        # Cross-schema dependency should NOT appear as a graph node
        assert "tb_organization" not in deps

    def test_cross_schema_registered_as_external(self, db_conn: Connection, cross_schema):
        introspector = SchemaIntrospector(db_conn, schema=cross_schema["child_schema"])
        graph = introspector.get_dependency_graph()

        assert "schema_parent.tb_organization" in graph._external_deps.get("tb_project", set())


class TestCrossSchemaBuilder:
    """SeedBuilder resolves cross-schema FK values from the database."""

    def test_generates_rows_with_cross_schema_fk(self, db_conn: Connection, cross_schema):
        builder = SeedBuilder(db_conn, schema=cross_schema["child_schema"])
        builder.add("tb_project", count=5)
        seeds = builder.execute()

        rows = seeds.tb_project
        assert len(rows) == 5

        # All FK values should be valid parent PKs (1, 2, or 3)
        for row in rows:
            assert row.fk_organization in (1, 2, 3)

    def test_staging_backend_raises_for_cross_schema_fk(self):
        """Staging backend cannot resolve cross-schema FKs without a DB connection."""
        builder = SeedBuilder(None, schema="test", backend="staging")
        table_info = TableInfo(
            name="tb_child",
            columns=[
                ColumnInfo(
                    name="pk_child",
                    pg_type="integer",
                    is_nullable=False,
                    is_primary_key=True,
                    is_identity=True,
                ),
                ColumnInfo(name="name", pg_type="text", is_nullable=False),
                ColumnInfo(name="fk_parent", pg_type="integer", is_nullable=False),
            ],
            foreign_keys=[
                ForeignKeyInfo(
                    column="fk_parent",
                    referenced_table="tb_parent",
                    referenced_column="pk_parent",
                    referenced_schema="other_schema",
                ),
            ],
        )
        builder.set_table_schema("tb_child", table_info)
        builder.add("tb_child", count=1)

        with pytest.raises(Exception, match="cross-schema"):
            builder.execute()


class TestCrossSchemaAutoDeps:
    """Auto-deps skips cross-schema FK targets."""

    def test_auto_deps_ignores_cross_schema(self, db_conn: Connection, cross_schema):
        """Cross-schema dependencies should not appear in auto-deps tree."""
        from fraiseql_data.auto_deps import AutoDependencyResolver
        from fraiseql_data.seed_common import SeedCommon

        introspector = SchemaIntrospector(db_conn, schema=cross_schema["child_schema"])
        resolver = AutoDependencyResolver(introspector, SeedCommon(instance_offsets={}, data=None))

        deps = resolver.build_dependency_tree("tb_project")
        # tb_organization lives in schema_parent, should be skipped
        assert "tb_organization" not in deps
