"""Tests for data export functionality (JSON, CSV)."""

import json
from pathlib import Path

from fraiseql_data import SeedBuilder
from psycopg import Connection


def test_export_to_json(db_conn: Connection, test_schema: str, tmp_path: Path):
    """Test exporting seed data to JSON format."""
    # Seed manufacturer data
    builder = SeedBuilder(db_conn, schema=test_schema)
    seeds = builder.add("tb_manufacturer", count=5).execute()

    # Export to JSON file
    json_file = tmp_path / "manufacturers.json"
    seeds.to_json(json_file)

    # Verify JSON file exists and contains correct data
    assert json_file.exists()

    with json_file.open() as f:
        data = json.load(f)

    assert "tb_manufacturer" in data
    assert len(data["tb_manufacturer"]) == 5

    # Verify first row structure
    first_row = data["tb_manufacturer"][0]
    assert "pk_manufacturer" in first_row
    assert "id" in first_row
    assert "identifier" in first_row
    assert "name" in first_row


def test_export_to_csv(db_conn: Connection, test_schema: str, tmp_path: Path):
    """Test exporting single table to CSV."""
    # Seed manufacturer data
    builder = SeedBuilder(db_conn, schema=test_schema)
    seeds = builder.add("tb_manufacturer", count=10).execute()

    # Export to CSV file
    csv_file = tmp_path / "manufacturers.csv"
    seeds.to_csv("tb_manufacturer", csv_file)

    # Verify CSV file exists
    assert csv_file.exists()

    # Read CSV and verify contents
    import csv

    with csv_file.open() as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 10

    # Verify headers
    first_row = rows[0]
    assert "pk_manufacturer" in first_row
    assert "id" in first_row
    assert "identifier" in first_row
    assert "name" in first_row


def test_export_handles_uuids_and_datetimes(
    db_conn: Connection, test_schema: str, tmp_path: Path
):
    """Test JSON export with UUID and datetime columns."""
    # Create table with datetime column
    with db_conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_event (
                pk_event INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                event_date TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
            )
            """
        )
        db_conn.commit()

    # Seed event data
    builder = SeedBuilder(db_conn, schema=test_schema)
    seeds = builder.add("tb_event", count=5).execute()

    # Export to JSON
    json_file = tmp_path / "events.json"
    seeds.to_json(json_file)

    # Verify JSON is valid and UUID/datetime are serialized as strings
    with json_file.open() as f:
        data = json.load(f)

    assert "tb_event" in data
    first_event = data["tb_event"][0]

    # UUIDs should be strings
    assert isinstance(first_event["id"], str)
    assert len(first_event["id"]) > 0  # Valid UUID string

    # Datetimes should be strings
    if first_event.get("event_date"):
        assert isinstance(first_event["event_date"], str)
