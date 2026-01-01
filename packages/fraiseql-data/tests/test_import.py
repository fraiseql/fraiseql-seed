"""Test data import from JSON/CSV files."""

import json
import tempfile
from pathlib import Path

import pytest

from fraiseql_data import SeedBuilder
from fraiseql_data.models import Seeds


def test_import_from_json(db_conn, test_schema):
    """Test importing seed data from JSON string (round-trip)."""
    # Export seed data first
    builder = SeedBuilder(db_conn, schema=test_schema)
    original = builder.add("tb_manufacturer", count=10).execute()
    json_str = original.to_json()

    # Import from JSON string
    imported = Seeds.from_json(json_str=json_str)

    # Verify data imported correctly
    assert len(imported.tb_manufacturer) == 10
    assert imported.tb_manufacturer[0].name == original.tb_manufacturer[0].name
    # Note: UUIDs imported as strings (type conversion in REFACTOR phase)
    assert str(imported.tb_manufacturer[0].id) == str(original.tb_manufacturer[0].id)


def test_import_from_csv(db_conn, test_schema):
    """Test importing single table from CSV file."""
    # Export to CSV first
    builder = SeedBuilder(db_conn, schema=test_schema)
    original = builder.add("tb_manufacturer", count=5).execute()

    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "manufacturers.csv"
        original.to_csv("tb_manufacturer", str(csv_path))

        # Import from CSV
        imported = Seeds.from_csv("tb_manufacturer", str(csv_path))

        # Verify data imported correctly
        assert len(imported.tb_manufacturer) == 5
        assert imported.tb_manufacturer[0].name == original.tb_manufacturer[0].name


def test_insert_imported_seeds(db_conn, test_schema):
    """Test inserting imported seeds into database."""
    # Create and export seed data
    builder = SeedBuilder(db_conn, schema=test_schema)
    original = builder.add("tb_manufacturer", count=10).execute()
    json_str = original.to_json()

    # Clear the table
    with db_conn.cursor() as cur:
        cur.execute(f"DELETE FROM {test_schema}.tb_manufacturer")
        db_conn.commit()

    # Import from JSON
    imported = Seeds.from_json(json_str=json_str)

    # Insert imported seeds into database
    builder2 = SeedBuilder(db_conn, schema=test_schema)
    result = builder2.insert_seeds(imported)

    # Verify data was inserted
    with db_conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {test_schema}.tb_manufacturer")
        count = cur.fetchone()[0]
        assert count == 10

    # Verify returned seeds have database-generated values
    assert len(result.tb_manufacturer) == 10
    assert all(m.pk_manufacturer is not None for m in result.tb_manufacturer)
