"""
Phase 4 Integration Tests - All features working together.

Simplified integration tests focusing on key workflows.
"""

import tempfile
from pathlib import Path

from fraiseql_data import SeedBuilder
from fraiseql_data.models import Seeds


def test_export_import_roundtrip(db_conn, test_schema):
    """Test complete export/import roundtrip with type conversion."""
    # Generate data in database
    builder = SeedBuilder(db_conn, schema=test_schema)
    original = builder.add("tb_manufacturer", count=50).execute()

    # Export to JSON
    json_str = original.to_json()

    # Import back
    imported = Seeds.from_json(json_str=json_str)

    # Verify data preserved with proper types
    assert len(imported.tb_manufacturer) == 50
    assert imported.tb_manufacturer[0].name == original.tb_manufacturer[0].name
    # UUIDs properly converted
    assert imported.tb_manufacturer[0].id == original.tb_manufacturer[0].id


def test_csv_export_import(db_conn, test_schema):
    """Test CSV export/import workflow."""
    builder = SeedBuilder(db_conn, schema=test_schema)
    original = builder.add("tb_manufacturer", count=25).execute()

    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "manufacturers.csv"

        # Export to CSV
        original.to_csv("tb_manufacturer", str(csv_path))
        assert csv_path.exists()

        # Import from CSV
        imported = Seeds.from_csv("tb_manufacturer", str(csv_path))
        assert len(imported.tb_manufacturer) == 25
        assert imported.tb_manufacturer[0].name == original.tb_manufacturer[0].name


def test_batch_operations_workflow(db_conn, test_schema):
    """Test batch API with conditional operations."""
    builder = SeedBuilder(db_conn, schema=test_schema)

    # Use batch with conditional
    include_manufacturers = True
    include_models = False

    with builder.batch() as batch:
        batch.when(include_manufacturers).add("tb_manufacturer", count=20)
        batch.when(include_models).add("tb_model", count=50)

    # Verify only manufacturers were added
    with db_conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {test_schema}.tb_manufacturer")
        assert cur.fetchone()[0] == 20

        cur.execute(f"SELECT COUNT(*) FROM {test_schema}.tb_model")
        assert cur.fetchone()[0] == 0


def test_check_constraint_auto_satisfaction(db_conn, test_schema):
    """Test CHECK constraints are auto-satisfied."""
    # Create table with CHECK constraint
    with db_conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_item (
                pk_item INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL CHECK (status IN ('active', 'pending', 'archived'))
            )
        """
        )
        db_conn.commit()

    # Generate data without overrides - CHECK constraint auto-satisfied
    builder = SeedBuilder(db_conn, schema=test_schema)
    seeds = builder.add("tb_item", count=100).execute()

    # Verify all rows have valid status
    for item in seeds.tb_item:
        assert item.status in ["active", "pending", "archived"]

    # Verify in database (constraint enforced by PostgreSQL)
    with db_conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {test_schema}.tb_item")
        assert cur.fetchone()[0] == 100


def test_insert_imported_data(db_conn, test_schema):
    """Test insert_seeds() with imported data."""
    # Generate and export
    builder = SeedBuilder(db_conn, schema=test_schema)
    original = builder.add("tb_manufacturer", count=30).execute()
    json_str = original.to_json()

    # Clear table
    with db_conn.cursor() as cur:
        cur.execute(f"DELETE FROM {test_schema}.tb_manufacturer")
        db_conn.commit()

    # Import and re-insert
    imported = Seeds.from_json(json_str=json_str)
    builder2 = SeedBuilder(db_conn, schema=test_schema)
    result = builder2.insert_seeds(imported)

    # Verify data restored
    assert len(result.tb_manufacturer) == 30
    with db_conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {test_schema}.tb_manufacturer")
        assert cur.fetchone()[0] == 30
