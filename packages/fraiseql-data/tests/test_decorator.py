"""Tests for @seed_data() pytest decorator."""

import pytest
from psycopg import Connection
from fraiseql_data import seed_data


@seed_data("tb_manufacturer", count=5)
def test_decorator_basic(seeds, db_conn: Connection, test_schema: str):
    """Should inject seeds into test function."""
    # seeds should be available as parameter
    assert hasattr(seeds, "tb_manufacturer")
    assert len(seeds.tb_manufacturer) == 5


@seed_data("tb_manufacturer", count=3)
@seed_data("tb_model", count=10)
def test_decorator_multiple_tables(seeds, db_conn: Connection, test_schema: str):
    """Should handle multiple @seed_data decorators."""
    assert hasattr(seeds, "tb_manufacturer")
    assert hasattr(seeds, "tb_model")
    assert len(seeds.tb_manufacturer) == 3
    assert len(seeds.tb_model) == 10

    # FKs should be resolved
    mfg_pks = {m.pk_manufacturer for m in seeds.tb_manufacturer}
    for model in seeds.tb_model:
        assert model.fk_manufacturer in mfg_pks


@seed_data("tb_manufacturer", count=5, strategy="faker")
def test_decorator_with_strategy(seeds, db_conn: Connection, test_schema: str):
    """Should support generation strategies."""
    assert len(seeds.tb_manufacturer) == 5

    # Should have realistic data
    mfg = seeds.tb_manufacturer[0]
    if hasattr(mfg, "email") and mfg.email:
        assert "@" in mfg.email


@seed_data("tb_manufacturer", count=2, overrides={"name": "TestCorp"})
def test_decorator_with_overrides(seeds, db_conn: Connection, test_schema: str):
    """Should support column overrides."""
    assert len(seeds.tb_manufacturer) == 2

    # All should have overridden name
    for mfg in seeds.tb_manufacturer:
        assert mfg.name == "TestCorp"


def test_decorator_cleanup(db_conn: Connection, test_schema: str):
    """Should cleanup seed data after test completes."""
    # After decorated test completes, data should be rolled back
    with db_conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {test_schema}.tb_manufacturer")
        count = cur.fetchone()[0]
        assert count == 0  # Transaction rolled back
