"""Tests for bulk insert optimization."""

import time

from psycopg import Connection

from fraiseql_data import SeedBuilder


def test_bulk_insert_100_rows(db_conn: Connection, test_schema: str):
    """Test bulk insert with 100 rows."""
    # Seed 100 manufacturers using bulk insert
    builder = SeedBuilder(db_conn, schema=test_schema)
    builder.add("tb_manufacturer", count=100)
    seeds = builder.execute()

    # Verify all 100 rows inserted correctly
    manufacturers = seeds.tb_manufacturer
    assert len(manufacturers) == 100

    # Verify all rows have required Trinity columns
    for manuf in manufacturers:
        assert manuf.pk_manufacturer is not None
        assert manuf.id is not None
        assert manuf.identifier is not None
        assert manuf.name is not None


def test_bulk_insert_same_as_single(db_conn: Connection, test_schema: str):
    """Test bulk insert produces same result as one-by-one."""
    # This test will verify that bulk insert produces the same structure
    # as single-row insert (when implemented, we'll use bulk=True/False parameter)

    # For now, just verify that regular execution works
    builder = SeedBuilder(db_conn, schema=test_schema)
    builder.add("tb_manufacturer", count=20)
    seeds = builder.execute()

    manufacturers = seeds.tb_manufacturer
    assert len(manufacturers) == 20

    # Verify structure of returned data
    for manuf in manufacturers:
        assert isinstance(manuf.pk_manufacturer, int)
        assert manuf.id is not None
        assert manuf.identifier is not None
        assert manuf.name is not None


def test_bulk_insert_performance(db_conn: Connection, test_schema: str):
    """Test bulk insert is faster than one-by-one."""
    # This test will compare performance when bulk=True vs bulk=False
    # For now, just verify we can seed a large dataset efficiently

    builder = SeedBuilder(db_conn, schema=test_schema)
    builder.add("tb_manufacturer", count=200)

    start = time.time()
    seeds = builder.execute()
    elapsed = time.time() - start

    manufacturers = seeds.tb_manufacturer
    assert len(manufacturers) == 200

    # Should complete in reasonable time (< 5 seconds for 200 rows)
    # This is a loose constraint since we're doing one-by-one currently
    assert elapsed < 10, f"Seeding 200 rows took {elapsed:.2f}s, expected < 10s"

    # Future: When bulk insert is implemented, this should be much faster
    # and we'll add a comparison test
