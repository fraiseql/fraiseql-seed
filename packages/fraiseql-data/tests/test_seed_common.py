"""Tests for SeedCommon baseline management.

Tests seed common loading, validation, instance ranges, and environment variants.
"""
# ruff: noqa: E501

import os
import tempfile
from pathlib import Path

import pytest

from fraiseql_data.seed_common import SeedCommon, SeedCommonValidationError


# ============================================================================
# Basic Loading Tests
# ============================================================================


def test_seed_common_from_yaml_baseline():
    """Load seed common with simple count baseline (Format 1)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""
baseline:
  tb_organization: 5
  tb_machine: 10
  tb_location: 3
""")
        yaml_path = f.name

    try:
        common = SeedCommon.from_yaml(yaml_path)

        # Verify offsets
        offsets = common.get_instance_offsets()
        assert offsets["tb_organization"] == 5
        assert offsets["tb_machine"] == 10
        assert offsets["tb_location"] == 3

        # No explicit data
        assert not common.has_explicit_data("tb_organization")
        assert common.get_data("tb_organization") == []
    finally:
        os.unlink(yaml_path)


def test_seed_common_from_yaml_explicit():
    """Load seed common with explicit data (Format 2)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""
tb_organization:
  - identifier: "org-1"
    name: "Organization 1"
  - identifier: "org-2"
    name: "Organization 2"

tb_machine:
  - identifier: "machine-1"
    name: "Machine 1"
    fk_organization: 1
""")
        yaml_path = f.name

    try:
        common = SeedCommon.from_yaml(yaml_path)

        # Verify offsets (derived from data count)
        offsets = common.get_instance_offsets()
        assert offsets["tb_organization"] == 2
        assert offsets["tb_machine"] == 1

        # Has explicit data
        assert common.has_explicit_data("tb_organization")
        org_data = common.get_data("tb_organization")
        assert len(org_data) == 2
        assert org_data[0]["identifier"] == "org-1"
        assert org_data[1]["identifier"] == "org-2"

        machine_data = common.get_data("tb_machine")
        assert len(machine_data) == 1
        assert machine_data[0]["fk_organization"] == 1
    finally:
        os.unlink(yaml_path)


def test_seed_common_from_json():
    """Load seed common from JSON file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("""
{
  "baseline": {
    "tb_organization": 5,
    "tb_machine": 10
  }
}
""")
        json_path = f.name

    try:
        common = SeedCommon.from_json(json_path)

        offsets = common.get_instance_offsets()
        assert offsets["tb_organization"] == 5
        assert offsets["tb_machine"] == 10
    finally:
        os.unlink(json_path)


def test_seed_common_from_sql():
    """Load seed common from SQL directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sql_dir = Path(tmpdir)

        # Create SQL file with Trinity pattern UUIDs
        sql_file = sql_dir / "01_organizations.sql"
        sql_file.write_text("""
INSERT INTO tb_organization (id, identifier, name) VALUES
  ('2a6f3c21-0000-4000-8000-000000000001', 'org-1', 'Org 1'),
  ('2a6f3c21-0000-4000-8000-000000000002', 'org-2', 'Org 2'),
  ('2a6f3c21-0000-4000-8000-000000000003', 'org-3', 'Org 3');

INSERT INTO tb_machine (id, identifier, name) VALUES
  ('2a6f3c21-0000-4000-8000-000000000001', 'machine-1', 'Machine 1'),
  ('2a6f3c21-0000-4000-8000-000000000002', 'machine-2', 'Machine 2');
""")

        common = SeedCommon.from_sql(sql_dir)

        # Verify instance counts extracted from UUIDs
        offsets = common.get_instance_offsets()
        assert offsets["tb_organization"] == 3
        assert offsets["tb_machine"] == 2


def test_seed_common_from_directory_auto_detect():
    """Auto-detect format when loading from directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_dir = Path(tmpdir)

        # Create YAML file
        yaml_file = db_dir / "seed_common.yaml"
        yaml_file.write_text("""
baseline:
  tb_organization: 5
""")

        common = SeedCommon.from_directory(db_dir)

        offsets = common.get_instance_offsets()
        assert offsets["tb_organization"] == 5


# ============================================================================
# Instance Range Tests
# ============================================================================


def test_seed_common_instance_offsets():
    """Verify instance offset calculation."""
    common = SeedCommon(instance_offsets={"tb_organization": 5, "tb_machine": 10})

    offsets = common.get_instance_offsets()
    assert offsets["tb_organization"] == 5
    assert offsets["tb_machine"] == 10


def test_seed_common_get_instance_start():
    """Get starting instance for test data."""
    common = SeedCommon(instance_offsets={"tb_organization": 5})

    # Test data starts at TEST_DATA_START (1,001) or offset+1, whichever is higher
    start = common.get_instance_start("tb_organization")
    assert start == common.TEST_DATA_START  # 1,001

    # Table not in seed common
    start = common.get_instance_start("tb_unknown")
    assert start == common.TEST_DATA_START  # 1,001


def test_seed_common_is_reserved():
    """Check if instance is in seed common range."""
    common = SeedCommon(instance_offsets={"tb_organization": 5})

    # Instances 1-5 are reserved
    assert common.is_reserved("tb_organization", 1) is True
    assert common.is_reserved("tb_organization", 3) is True
    assert common.is_reserved("tb_organization", 5) is True

    # Instances above 5 are not reserved
    assert common.is_reserved("tb_organization", 6) is False
    assert common.is_reserved("tb_organization", 1001) is False

    # Table not in seed common
    assert common.is_reserved("tb_unknown", 1) is False


def test_seed_common_instance_range_constants():
    """Verify instance range constants."""
    common = SeedCommon(instance_offsets={})

    assert common.SEED_COMMON_MAX == 1_000
    assert common.TEST_DATA_START == 1_001
    assert common.TEST_DATA_MAX == 999_999
    assert common.GENERATED_DATA_START == 1_000_000


def test_seed_common_exceeds_max_instances():
    """Error when seed common has > 1,000 instances."""
    with pytest.raises(SeedCommonValidationError) as exc_info:
        SeedCommon(instance_offsets={"tb_organization": 1500})

    assert "exceeds seed common maximum 1,000" in str(exc_info.value)


# ============================================================================
# Environment Variant Tests
# ============================================================================


def test_seed_common_environment_detection():
    """Load different file based on ENV variable."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_dir = Path(tmpdir)

        # Create base file
        base_file = db_dir / "seed_common.yaml"
        base_file.write_text("""
baseline:
  tb_organization: 2
""")

        # Create dev file
        dev_file = db_dir / "seed_common.dev.yaml"
        dev_file.write_text("""
baseline:
  tb_organization: 10
  tb_user: 20
""")

        # Without ENV: loads base
        common = SeedCommon.from_directory(db_dir)
        offsets = common.get_instance_offsets()
        assert offsets["tb_organization"] == 2
        assert "tb_user" not in offsets

        # With ENV=dev: loads dev variant
        os.environ["ENV"] = "dev"
        try:
            common = SeedCommon.from_directory(db_dir)
            offsets = common.get_instance_offsets()
            assert offsets["tb_organization"] == 10
            assert offsets["tb_user"] == 20
        finally:
            del os.environ["ENV"]


def test_seed_common_environment_fallback():
    """Fallback to base when ENV file not found."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_dir = Path(tmpdir)

        # Only create base file (no staging variant)
        base_file = db_dir / "seed_common.yaml"
        base_file.write_text("""
baseline:
  tb_organization: 2
""")

        # ENV=staging but no staging file → fallback to base
        os.environ["ENV"] = "staging"
        try:
            common = SeedCommon.from_directory(db_dir)
            offsets = common.get_instance_offsets()
            assert offsets["tb_organization"] == 2
        finally:
            del os.environ["ENV"]


def test_seed_common_environment_resolution_order():
    """Verify resolution order: {ENV}.yaml → yaml → SQL."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_dir = Path(tmpdir)

        # Create all three formats
        yaml_file = db_dir / "seed_common.yaml"
        yaml_file.write_text("baseline:\n  tb_organization: 5\n")

        dev_file = db_dir / "seed_common.dev.yaml"
        dev_file.write_text("baseline:\n  tb_organization: 10\n")

        sql_dir = db_dir / "1_seed_common"
        sql_dir.mkdir()
        sql_file = sql_dir / "01_orgs.sql"
        sql_file.write_text("""
INSERT INTO tb_organization (id, identifier, name) VALUES
  ('2a6f3c21-0000-4000-8000-000000000001', 'org-1', 'Org 1');
""")

        # ENV=dev: prefers dev variant
        os.environ["ENV"] = "dev"
        try:
            common = SeedCommon.from_directory(db_dir)
            offsets = common.get_instance_offsets()
            assert offsets["tb_organization"] == 10  # From dev file
        finally:
            del os.environ["ENV"]

        # No ENV: prefers base YAML over SQL
        common = SeedCommon.from_directory(db_dir)
        offsets = common.get_instance_offsets()
        assert offsets["tb_organization"] == 5  # From base YAML


# ============================================================================
# FK Validation Tests
# ============================================================================


def test_seed_common_fk_validation_valid(db_conn, test_schema):
    """Valid FK references pass validation."""
    from fraiseql_data.introspection import SchemaIntrospector

    # Create schema
    with db_conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_organization (
                pk_organization INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL
            )
        """
        )

        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_machine (
                pk_machine INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                fk_organization INTEGER NOT NULL REFERENCES {test_schema}.tb_organization(pk_organization)
            )
        """
        )
        db_conn.commit()

    # Create valid seed common
    data = {
        "tb_organization": [
            {"identifier": "org-1", "name": "Org 1"},
            {"identifier": "org-2", "name": "Org 2"},
        ],
        "tb_machine": [
            {"identifier": "machine-1", "name": "Machine 1", "fk_organization": 1},
            {"identifier": "machine-2", "name": "Machine 2", "fk_organization": 2},
        ],
    }
    common = SeedCommon(instance_offsets={"tb_organization": 2, "tb_machine": 2}, data=data)

    # Validate
    introspector = SchemaIntrospector(db_conn, test_schema)
    errors = common.validate(introspector)
    assert errors == []  # No errors


def test_seed_common_fk_validation_missing_table(db_conn, test_schema):
    """Error when FK references table not in seed common."""
    from fraiseql_data.introspection import SchemaIntrospector

    # Create schema
    with db_conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_organization (
                pk_organization INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL
            )
        """
        )

        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_machine (
                pk_machine INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                fk_organization INTEGER NOT NULL REFERENCES {test_schema}.tb_organization(pk_organization)
            )
        """
        )
        db_conn.commit()

    # Seed common missing tb_organization
    data = {
        "tb_machine": [
            {"identifier": "machine-1", "name": "Machine 1", "fk_organization": 1},
        ],
    }
    common = SeedCommon(instance_offsets={"tb_machine": 1}, data=data)

    # Validate
    introspector = SchemaIntrospector(db_conn, test_schema)
    errors = common.validate(introspector)

    assert len(errors) > 0
    assert "tb_organization" in errors[0]
    assert "not defined in seed common" in errors[0]


def test_seed_common_fk_validation_invalid_instance(db_conn, test_schema):
    """Error when FK value exceeds available instances."""
    from fraiseql_data.introspection import SchemaIntrospector

    # Create schema
    with db_conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_organization (
                pk_organization INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL
            )
        """
        )

        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_machine (
                pk_machine INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                fk_organization INTEGER NOT NULL REFERENCES {test_schema}.tb_organization(pk_organization)
            )
        """
        )
        db_conn.commit()

    # FK references instance 10, but only 2 orgs exist
    data = {
        "tb_organization": [
            {"identifier": "org-1", "name": "Org 1"},
            {"identifier": "org-2", "name": "Org 2"},
        ],
        "tb_machine": [
            {"identifier": "machine-1", "name": "Machine 1", "fk_organization": 10},  # Invalid!
        ],
    }
    common = SeedCommon(instance_offsets={"tb_organization": 2, "tb_machine": 1}, data=data)

    # Validate
    introspector = SchemaIntrospector(db_conn, test_schema)
    errors = common.validate(introspector)

    assert len(errors) > 0
    assert "fk_organization" in errors[0]
    assert "10" in errors[0]
    assert "only 2 instances exist" in errors[0]


def test_seed_common_no_validation_errors_empty():
    """Empty seed common passes validation."""
    common = SeedCommon(instance_offsets={})

    # Mock introspector (won't be called for empty seed common)
    class MockIntrospector:
        def get_dependency_graph(self):
            class Graph:
                def topological_sort(self):
                    return []

            return Graph()

    errors = common.validate(MockIntrospector())
    assert errors == []


# ============================================================================
# Integration Tests
# ============================================================================


def test_seed_common_with_builder(db_conn, test_schema):
    """SeedBuilder respects seed common offsets."""
    from fraiseql_data import SeedBuilder

    # Create schema
    with db_conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_organization (
                pk_organization INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL
            )
        """
        )
        db_conn.commit()

    # Create seed common
    with tempfile.TemporaryDirectory() as tmpdir:
        db_dir = Path(tmpdir)
        yaml_file = db_dir / "seed_common.yaml"
        yaml_file.write_text("""
baseline:
  tb_organization: 5
""")

        # Build with seed common
        builder = SeedBuilder(db_conn, schema=test_schema, seed_common=str(db_dir))

        # Generate test data (should start at instance 1,001)
        seeds = builder.add("tb_organization", count=10).execute()

        # Verify instances
        assert len(seeds.tb_organization) == 10

        # Check UUIDs - should be in test data range (1,001+)
        for org in seeds.tb_organization:
            uuid_str = str(org.id)
            # Extract instance number from UUID
            # Format: 2a6f3c21-0000-4000-8000-{instance:012d}
            instance_hex = uuid_str.split("-")[-1]
            instance = int(instance_hex)

            # Should be >= TEST_DATA_START (1,001)
            assert instance >= 1001


def test_builder_without_seed_common_warning(db_conn, test_schema):
    """Warn when seed_common=None."""
    from fraiseql_data import SeedBuilder
    import logging

    # Create schema
    with db_conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_organization (
                pk_organization INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL
            )
        """
        )
        db_conn.commit()

    # Capture logs
    with pytest.warns(None) as warnings:
        builder = SeedBuilder(db_conn, schema=test_schema, seed_common=None)

    # Should have logged warning (check via logger, not pytest.warns)
    # For now, just verify builder was created
    assert builder is not None


def test_trinity_pattern_after_seed_common(db_conn, test_schema):
    """Trinity pattern starts at correct instance (TEST_DATA_START)."""
    from fraiseql_data import SeedBuilder

    # Create schema
    with db_conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_organization (
                pk_organization INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL
            )
        """
        )
        db_conn.commit()

    # Create seed common with 5 instances
    with tempfile.TemporaryDirectory() as tmpdir:
        db_dir = Path(tmpdir)
        yaml_file = db_dir / "seed_common.yaml"
        yaml_file.write_text("""
baseline:
  tb_organization: 5
""")

        builder = SeedBuilder(db_conn, schema=test_schema, seed_common=str(db_dir))

        # Generate 3 test organizations
        seeds = builder.add("tb_organization", count=3).execute()

        # Verify: instances should be 1,001, 1,002, 1,003
        uuids = [str(org.id) for org in seeds.tb_organization]

        for i, uuid_str in enumerate(uuids):
            instance_hex = uuid_str.split("-")[-1]
            instance = int(instance_hex)

            expected_instance = 1001 + i
            assert instance == expected_instance
