"""Tests for export command.

These tests verify that the export command works correctly with
different formats, filters, and error cases.
"""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from fraiseql_data.cli.main import cli


@pytest.fixture
def populated_db(db_conn, test_schema):
    """Create a database with test data for export tests.

    This fixture:
    1. Creates test tables
    2. Populates them with seed data
    3. Returns the seed data for verification
    """
    from fraiseql_data import SeedBuilder

    # Create seed data
    builder = SeedBuilder(db_conn, schema=test_schema)
    seeds = builder.add("tb_manufacturer", count=5).execute()

    return seeds


@pytest.fixture
def database_url():
    """Get database URL for CLI tests."""
    import os

    # Use same logic as conftest.py
    return os.getenv(
        "TEST_DATABASE_URL",
        os.getenv("DATABASE_URL", "postgresql://localhost/fraiseql_test"),
    )


def test_export_json_format(populated_db, db_conn, test_schema, database_url):
    """Test exporting data as JSON.

    This test verifies:
    - Export command returns exit code 0 (success)
    - Output is valid JSON
    - Output contains expected data
    - Row count matches what we inserted
    """
    # Create a Click test runner
    runner = CliRunner()

    # Run the export command
    result = runner.invoke(
        cli,
        [
            "export",
            "tb_manufacturer",  # Table to export
            "--database",
            database_url,
            "--schema",
            test_schema,
            "--format",
            "json",
            "--quiet",  # Suppress progress messages
        ],
    )

    # Verify command succeeded
    assert result.exit_code == 0, f"Command failed: {result.output}"

    # Parse JSON output
    data = json.loads(result.output)

    # Verify structure
    assert "tb_manufacturer" in data
    assert len(data["tb_manufacturer"]) == 5


def test_export_csv_format(populated_db, db_conn, test_schema, database_url):
    """Test exporting data as CSV.

    CSV format should have:
    - Header row with column names
    - Data rows (one per database row)
    - Comma-separated values
    """
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "export",
            "tb_manufacturer",
            "--database",
            database_url,
            "--schema",
            test_schema,
            "--format",
            "csv",
            "--quiet",
        ],
    )

    assert result.exit_code == 0

    # Split output into lines
    lines = result.output.strip().split("\n")

    # Should have header + 5 data rows
    assert len(lines) == 6  # 1 header + 5 data rows

    # Verify header contains expected columns
    header = lines[0]
    assert "pk_manufacturer" in header
    assert "name" in header


def test_export_sql_format(populated_db, db_conn, test_schema, database_url):
    """Test exporting data as SQL INSERT statements.

    SQL export should contain:
    - Comments with metadata
    - INSERT INTO statements
    - Properly formatted VALUES clauses
    """
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "export",
            "tb_manufacturer",
            "--database",
            database_url,
            "--schema",
            test_schema,
            "--format",
            "sql",
            "--quiet",
        ],
    )

    assert result.exit_code == 0

    # Verify SQL keywords present
    assert "INSERT INTO" in result.output
    assert "VALUES" in result.output
    assert test_schema in result.output  # Schema should be in table name


def test_export_with_where_clause(populated_db, db_conn, test_schema, database_url):
    """Test exporting data with WHERE clause filtering.

    This verifies that the WHERE clause correctly filters rows.
    """
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "export",
            "tb_manufacturer",
            "--database",
            database_url,
            "--schema",
            test_schema,
            "--where",
            "pk_manufacturer <= 2",  # Only first 2 rows
            "--format",
            "json",
            "--quiet",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(result.output)

    # Should only have 2 rows (not 5)
    assert len(data["tb_manufacturer"]) == 2


def test_export_with_limit(populated_db, db_conn, test_schema, database_url):
    """Test exporting data with row limit.

    This verifies that the LIMIT parameter correctly limits output.
    """
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "export",
            "tb_manufacturer",
            "--database",
            database_url,
            "--schema",
            test_schema,
            "--limit",
            "3",  # Only 3 rows
            "--format",
            "json",
            "--quiet",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(result.output)

    # Should only have 3 rows (not 5)
    assert len(data["tb_manufacturer"]) == 3


def test_export_to_file(populated_db, db_conn, test_schema, database_url, tmp_path):
    """Test exporting data to file instead of stdout.

    This verifies:
    - File is created
    - File contains expected data
    - Output path is used correctly
    """
    # tmp_path is a pytest fixture that creates a temporary directory
    output_file = tmp_path / "export.json"

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "export",
            "tb_manufacturer",
            "--database",
            database_url,
            "--schema",
            test_schema,
            "--output",
            str(output_file),  # Save to file
            "--quiet",
        ],
    )

    assert result.exit_code == 0

    # Verify file was created
    assert output_file.exists()

    # Verify file contents
    with Path(output_file).open() as f:
        data = json.load(f)
    assert len(data["tb_manufacturer"]) == 5


def test_export_multiple_tables(populated_db, db_conn, test_schema, database_url):
    """Test exporting multiple tables at once.

    This requires creating multiple tables first.
    """
    from fraiseql_data import SeedBuilder

    # Create another table
    with db_conn.cursor() as cur:
        cur.execute(f"""
            CREATE TABLE {test_schema}.tb_category (
                pk_category INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                id UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        db_conn.commit()

    # Add data to the new table
    builder = SeedBuilder(db_conn, schema=test_schema)
    builder.add("tb_category", count=3)
    builder.execute()

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "export",
            "tb_manufacturer",  # First table
            "tb_category",  # Second table
            "--database",
            database_url,
            "--schema",
            test_schema,
            "--format",
            "json",
            "--quiet",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(result.output)

    # Should have both tables
    assert "tb_manufacturer" in data
    assert "tb_category" in data
    assert len(data["tb_manufacturer"]) == 5
    assert len(data["tb_category"]) == 3


def test_export_nonexistent_table(db_conn, test_schema, database_url):
    """Test exporting a table that doesn't exist.

    This should fail with a clear error message.
    """
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "export",
            "nonexistent_table",  # This table doesn't exist
            "--database",
            database_url,
            "--schema",
            test_schema,
            "--quiet",
        ],
    )

    # Should fail (exit code 1)
    assert result.exit_code == 1

    # Error message should mention table not found
    assert "not found" in result.output.lower()


def test_export_with_invalid_database_url(test_schema):
    """Test export with invalid database connection.

    This should fail gracefully with a connection error.
    """
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "export",
            "users",
            "--database",
            "postgresql://invalid:invalid@invalid/invalid",  # Invalid
            "--schema",
            test_schema,
        ],
    )

    # Should fail with exit code 2 (DatabaseConnectionError)
    assert result.exit_code == 2

    # Error should mention connection failure
    # (exact message depends on psycopg error)


def test_export_where_clause_validation():
    """Test WHERE clause validation for SQL injection prevention."""
    runner = CliRunner()
    database_url = "postgresql://localhost/fraiseql_test"

    # Test dangerous WHERE clauses
    dangerous_clauses = [
        "1=1; DROP TABLE users;",  # Semicolon injection
        "id = 1 UNION SELECT password FROM users",  # UNION injection
        "id = 1; DELETE FROM users;",  # DELETE injection
        "id = 1 -- comment",  # SQL comment
    ]

    for dangerous_clause in dangerous_clauses:
        result = runner.invoke(
            cli,
            [
                "export",
                "users",
                "--database",
                database_url,
                "--where",
                dangerous_clause,
            ],
        )

        # Should fail with validation error
        assert result.exit_code == 1
        assert "dangerous where clause" in result.output.lower()


def test_export_where_clause_length_limit():
    """Test WHERE clause length validation."""
    runner = CliRunner()
    database_url = "postgresql://localhost/fraiseql_test"

    # Create a very long WHERE clause (> 1000 chars)
    long_where = "id = " + "1 OR " * 200 + "id = 1"

    result = runner.invoke(
        cli,
        [
            "export",
            "users",
            "--database",
            database_url,
            "--where",
            long_where,
        ],
    )

    # Should fail with length error
    assert result.exit_code == 1
    assert "too long" in result.output.lower()


def test_export_where_clause_valid():
    """Test that valid WHERE clauses work."""
    runner = CliRunner()
    database_url = "postgresql://localhost/fraiseql_test"

    # These should be considered safe
    valid_clauses = [
        "pk_manufacturer = 1",
        "name LIKE '%test%'",
        "id IS NOT NULL",
    ]

    for valid_clause in valid_clauses:
        result = runner.invoke(
            cli,
            [
                "export",
                "tb_manufacturer",
                "--database",
                database_url,
                "--where",
                valid_clause,
            ],
        )

        # Should pass WHERE validation and fail at table validation
        # (since we're not connected to a real database)
        assert result.exit_code == 1  # CLIError (table not found)
        # Should NOT contain validation error
        assert "dangerous" not in result.output.lower()
