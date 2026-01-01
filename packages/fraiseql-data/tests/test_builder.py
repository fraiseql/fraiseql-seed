"""Tests for SeedBuilder API."""

from fraiseql_data import SeedBuilder
from psycopg import Connection


def test_builder_initialization(db_conn: Connection, test_schema: str):
    """Should initialize SeedBuilder with connection and schema."""
    builder = SeedBuilder(db_conn, schema=test_schema)

    assert builder.schema == test_schema
    assert builder.conn == db_conn


def test_add_single_table(db_conn: Connection, test_schema: str):
    """Should add a table to seed plan."""
    builder = SeedBuilder(db_conn, schema=test_schema)
    builder.add("tb_manufacturer", count=5)

    # Should have 1 table in plan
    assert len(builder._plan) == 1
    assert builder._plan[0].table == "tb_manufacturer"
    assert builder._plan[0].count == 5


def test_execute_returns_seeds(db_conn: Connection, test_schema: str):
    """Should execute plan and return seed data."""
    builder = SeedBuilder(db_conn, schema=test_schema)
    builder.add("tb_manufacturer", count=5)
    seeds = builder.execute()

    # Should return Seeds object with data
    assert hasattr(seeds, "tb_manufacturer")
    assert len(seeds.tb_manufacturer) == 5


def test_execute_populates_trinity_columns(db_conn: Connection, test_schema: str):
    """Should auto-populate Trinity pattern columns."""
    builder = SeedBuilder(db_conn, schema=test_schema)
    builder.add("tb_manufacturer", count=3)
    seeds = builder.execute()

    mfg = seeds.tb_manufacturer[0]

    # Should have pk_* (from database IDENTITY)
    assert hasattr(mfg, "pk_manufacturer")
    assert isinstance(mfg.pk_manufacturer, int)

    # Should have id (UUID)
    assert hasattr(mfg, "id")
    from uuid import UUID

    assert isinstance(mfg.id, UUID)

    # Should have identifier (TEXT)
    assert hasattr(mfg, "identifier")
    assert isinstance(mfg.identifier, str)
    assert len(mfg.identifier) > 0


def test_execute_resolves_foreign_keys(db_conn: Connection, test_schema: str):
    """Should auto-resolve foreign key relationships."""
    builder = SeedBuilder(db_conn, schema=test_schema)
    builder.add("tb_manufacturer", count=5)
    builder.add("tb_model", count=20)
    seeds = builder.execute()

    # All models should reference valid manufacturers
    mfg_pks = {m.pk_manufacturer for m in seeds.tb_manufacturer}
    for model in seeds.tb_model:
        assert model.fk_manufacturer in mfg_pks


def test_execute_generates_realistic_data(db_conn: Connection, test_schema: str):
    """Should generate realistic data using Faker."""
    builder = SeedBuilder(db_conn, schema=test_schema)
    builder.add("tb_manufacturer", count=5, strategy="faker")
    seeds = builder.execute()

    # Email should be realistic (if column exists)
    mfg = seeds.tb_manufacturer[0]
    if hasattr(mfg, "email") and mfg.email:
        assert "@" in mfg.email

    # Name should exist and be non-empty
    assert mfg.name
    assert len(mfg.name) > 0
