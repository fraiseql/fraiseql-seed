"""Test batch operations API for fluent multi-table seeding."""

import random

import pytest

from fraiseql_data import SeedBuilder


def test_batch_context_manager(db_conn, test_schema):
    """Test batch operations via context manager (auto-execution on exit)."""
    builder = SeedBuilder(db_conn, schema=test_schema)

    # Use batch context manager - executes all operations on exit
    with builder.batch() as batch:
        batch.add("tb_manufacturer", count=10)
        batch.add("tb_model", count=50)

    # Verify both tables were seeded
    with db_conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {test_schema}.tb_manufacturer")
        manufacturer_count = cur.fetchone()[0]
        assert manufacturer_count == 10

        cur.execute(f"SELECT COUNT(*) FROM {test_schema}.tb_model")
        model_count = cur.fetchone()[0]
        assert model_count == 50


def test_conditional_operations(db_conn, test_schema):
    """Test conditional seed operations with .when()."""
    builder = SeedBuilder(db_conn, schema=test_schema)

    include_manufacturers = True
    include_models = False

    # Conditional operations based on flags
    with builder.batch() as batch:
        batch.when(include_manufacturers).add("tb_manufacturer", count=10)
        batch.when(include_models).add("tb_model", count=50)  # Should skip

    # Verify only manufacturers were seeded (models skipped)
    with db_conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {test_schema}.tb_manufacturer")
        manufacturer_count = cur.fetchone()[0]
        assert manufacturer_count == 10

        cur.execute(f"SELECT COUNT(*) FROM {test_schema}.tb_model")
        model_count = cur.fetchone()[0]
        assert model_count == 0, "Models should not have been seeded (condition was False)"


def test_dynamic_count(db_conn, test_schema):
    """Test dynamic count via callable (lambda)."""
    builder = SeedBuilder(db_conn, schema=test_schema)

    # Use callable for dynamic count
    random.seed(42)  # For reproducibility
    seeds = builder.add(
        "tb_manufacturer", count=lambda: random.randint(5, 15)
    ).execute()

    # Verify count is in expected range
    count = len(seeds.tb_manufacturer)
    assert (
        5 <= count <= 15
    ), f"Expected count between 5-15, got {count}"

    # Verify in database
    with db_conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {test_schema}.tb_manufacturer")
        db_count = cur.fetchone()[0]
        assert db_count == count
