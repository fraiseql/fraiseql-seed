"""Tests for schema introspection functionality."""

from fraiseql_data.introspection import SchemaIntrospector
from psycopg import Connection


def test_get_tables(db_conn: Connection, test_schema: str):
    """Should discover all tables in schema."""
    introspector = SchemaIntrospector(db_conn, schema=test_schema)
    tables = introspector.get_tables()

    assert len(tables) == 2
    table_names = {t.name for t in tables}
    assert "tb_manufacturer" in table_names
    assert "tb_model" in table_names


def test_get_columns(db_conn: Connection, test_schema: str):
    """Should discover all columns for a table."""
    introspector = SchemaIntrospector(db_conn, schema=test_schema)
    columns = introspector.get_columns("tb_manufacturer")

    column_names = {c.name for c in columns}
    assert "pk_manufacturer" in column_names
    assert "id" in column_names
    assert "identifier" in column_names
    assert "name" in column_names
    assert "email" in column_names
    assert "created_at" in column_names


def test_detect_trinity_pattern(db_conn: Connection, test_schema: str):
    """Should detect Trinity pattern columns (pk_*, id, identifier)."""
    introspector = SchemaIntrospector(db_conn, schema=test_schema)
    table = introspector.get_table_info("tb_manufacturer")

    assert table.is_trinity is True
    assert table.pk_column == "pk_manufacturer"
    assert table.id_column == "id"
    assert table.identifier_column == "identifier"


def test_get_foreign_keys(db_conn: Connection, test_schema: str):
    """Should discover foreign key relationships."""
    introspector = SchemaIntrospector(db_conn, schema=test_schema)
    fks = introspector.get_foreign_keys("tb_model")

    assert len(fks) == 1
    fk = fks[0]
    assert fk.column == "fk_manufacturer"
    assert fk.referenced_table == "tb_manufacturer"
    assert fk.referenced_column == "pk_manufacturer"


def test_topological_sort(db_conn: Connection, test_schema: str):
    """Should sort tables in dependency order."""
    introspector = SchemaIntrospector(db_conn, schema=test_schema)
    sorted_tables = introspector.topological_sort()

    # tb_manufacturer must come before tb_model
    mfg_idx = next(i for i, t in enumerate(sorted_tables) if t == "tb_manufacturer")
    model_idx = next(i for i, t in enumerate(sorted_tables) if t == "tb_model")
    assert mfg_idx < model_idx
