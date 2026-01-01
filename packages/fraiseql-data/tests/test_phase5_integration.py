"""Integration tests for Phase 5 auto-dependency resolution with other features.

Tests auto-deps integration with:
- CHECK constraints (Phase 4)
- Batch operations (Phase 4)
- Staging backend (Phase 4)
- Dynamic counts (Phase 4)
- Self-referencing tables (Phase 2)
"""
# ruff: noqa: E501

from fraiseql_data import SeedBuilder


def test_auto_deps_with_check_constraints(db_conn, test_schema):
    """Test auto-deps with tables that have CHECK constraints."""
    # Create schema with CHECK constraints
    with db_conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_organization (
                pk_organization INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                org_type TEXT NOT NULL CHECK (org_type IN ('nonprofit', 'government', 'private'))
            )
        """
        )

        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_allocation (
                pk_allocation INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                priority INTEGER NOT NULL CHECK (priority BETWEEN 1 AND 10),
                fk_organization INTEGER NOT NULL REFERENCES {test_schema}.tb_organization(pk_organization)
            )
        """
        )
        db_conn.commit()

    # Use auto_deps with CHECK constraints
    builder = SeedBuilder(db_conn, schema=test_schema)
    seeds = builder.add("tb_allocation", count=10, auto_deps=True).execute()

    # Verify: auto-deps created organization with CHECK constraint satisfied
    assert len(seeds.tb_organization) == 1
    assert seeds.tb_organization[0].org_type in ["nonprofit", "government", "private"]

    # Verify: allocations have CHECK constraint satisfied
    assert len(seeds.tb_allocation) == 10
    for allocation in seeds.tb_allocation:
        assert 1 <= allocation.priority <= 10


def test_auto_deps_with_staging_backend(test_schema):
    """Test auto-deps works with staging backend (no database)."""
    from fraiseql_data.models import ColumnInfo, ForeignKeyInfo, TableInfo

    # Create staging builder
    builder = SeedBuilder(None, schema=test_schema, backend="staging")

    # Define schema manually
    org_table = TableInfo(
        name="tb_organization",
        columns=[
            ColumnInfo(
                name="pk_organization",
                pg_type="INTEGER",
                is_primary_key=True,
                is_nullable=False,
            ),
            ColumnInfo(name="id", pg_type="UUID", is_nullable=False, is_unique=True),
            ColumnInfo(
                name="identifier", pg_type="TEXT", is_nullable=False, is_unique=True
            ),
            ColumnInfo(name="name", pg_type="TEXT", is_nullable=False),
        ],
        foreign_keys=[],
    )

    machine_table = TableInfo(
        name="tb_machine",
        columns=[
            ColumnInfo(
                name="pk_machine",
                pg_type="INTEGER",
                is_primary_key=True,
                is_nullable=False,
            ),
            ColumnInfo(name="id", pg_type="UUID", is_nullable=False, is_unique=True),
            ColumnInfo(
                name="identifier", pg_type="TEXT", is_nullable=False, is_unique=True
            ),
            ColumnInfo(name="name", pg_type="TEXT", is_nullable=False),
            ColumnInfo(
                name="fk_organization", pg_type="INTEGER", is_nullable=False
            ),
        ],
        foreign_keys=[
            ForeignKeyInfo(
                column="fk_organization",
                referenced_table="tb_organization",
                referenced_column="pk_organization",
            )
        ],
    )

    builder.set_table_schema("tb_organization", org_table)
    builder.set_table_schema("tb_machine", machine_table)

    # Use auto_deps with staging backend
    seeds = builder.add("tb_machine", count=5, auto_deps=True).execute()

    # Verify: works without database
    assert len(seeds.tb_organization) == 1
    assert len(seeds.tb_machine) == 5

    # Verify: FKs resolved correctly
    org_pk = seeds.tb_organization[0].pk_organization
    for machine in seeds.tb_machine:
        assert machine.fk_organization == org_pk


def test_auto_deps_with_dynamic_counts(db_conn, test_schema):
    """Test auto-deps with callable counts."""
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

    # Use auto_deps with dynamic count
    builder = SeedBuilder(db_conn, schema=test_schema)

    # Callable that returns a count
    def get_machine_count():
        return 7

    seeds = builder.add("tb_machine", count=get_machine_count, auto_deps=True).execute()

    # Verify: callable was resolved
    assert len(seeds.tb_organization) == 1
    assert len(seeds.tb_machine) == 7


def test_auto_deps_with_batch_and_conditional(db_conn, test_schema):
    """Test auto-deps with batch operations and conditionals."""
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

        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_allocation (
                pk_allocation INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                fk_machine INTEGER NOT NULL REFERENCES {test_schema}.tb_machine(pk_machine)
            )
        """
        )
        db_conn.commit()

    # Use auto_deps with batch and conditionals
    builder = SeedBuilder(db_conn, schema=test_schema)

    include_machines = True
    skip_allocations = False

    with builder.batch() as batch:
        batch.when(include_machines).add("tb_machine", count=3, auto_deps=True)
        batch.when(not skip_allocations).add("tb_allocation", count=15, auto_deps=True)

    # Verify: conditional operations executed with auto_deps
    with db_conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {test_schema}.tb_organization")
        assert cur.fetchone()[0] == 1  # Deduplicated

        cur.execute(f"SELECT COUNT(*) FROM {test_schema}.tb_machine")
        assert cur.fetchone()[0] == 3

        cur.execute(f"SELECT COUNT(*) FROM {test_schema}.tb_allocation")
        assert cur.fetchone()[0] == 15


def test_auto_deps_deep_hierarchy(db_conn, test_schema):
    """Test auto-deps with deep dependency hierarchy (6+ levels)."""
    # Create 6-level hierarchy
    with db_conn.cursor() as cur:
        # Level 1: Root
        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_region (
                pk_region INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL
            )
        """
        )

        # Level 2
        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_country (
                pk_country INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                fk_region INTEGER NOT NULL REFERENCES {test_schema}.tb_region(pk_region)
            )
        """
        )

        # Level 3
        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_state (
                pk_state INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                fk_country INTEGER NOT NULL REFERENCES {test_schema}.tb_country(pk_country)
            )
        """
        )

        # Level 4
        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_city (
                pk_city INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                fk_state INTEGER NOT NULL REFERENCES {test_schema}.tb_state(pk_state)
            )
        """
        )

        # Level 5
        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_building (
                pk_building INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                fk_city INTEGER NOT NULL REFERENCES {test_schema}.tb_city(pk_city)
            )
        """
        )

        # Level 6: Leaf
        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_room (
                pk_room INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                fk_building INTEGER NOT NULL REFERENCES {test_schema}.tb_building(pk_building)
            )
        """
        )
        db_conn.commit()

    # Use auto_deps on deepest level
    builder = SeedBuilder(db_conn, schema=test_schema)
    seeds = builder.add("tb_room", count=10, auto_deps=True).execute()

    # Verify: entire hierarchy generated
    assert len(seeds.tb_region) == 1
    assert len(seeds.tb_country) == 1
    assert len(seeds.tb_state) == 1
    assert len(seeds.tb_city) == 1
    assert len(seeds.tb_building) == 1
    assert len(seeds.tb_room) == 10

    # Verify: FK chain is correct
    region_pk = seeds.tb_region[0].pk_region
    country_pk = seeds.tb_country[0].pk_country
    state_pk = seeds.tb_state[0].pk_state
    city_pk = seeds.tb_city[0].pk_city
    building_pk = seeds.tb_building[0].pk_building

    assert seeds.tb_country[0].fk_region == region_pk
    assert seeds.tb_state[0].fk_country == country_pk
    assert seeds.tb_city[0].fk_state == state_pk
    assert seeds.tb_building[0].fk_city == city_pk
    for room in seeds.tb_room:
        assert room.fk_building == building_pk


def test_auto_deps_with_export_import(db_conn, test_schema):
    """Test auto-deps generated data can be exported and re-imported."""
    import tempfile

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

    # Generate with auto_deps
    builder = SeedBuilder(db_conn, schema=test_schema)
    original_seeds = builder.add("tb_machine", count=5, auto_deps=True).execute()

    # Export to JSON
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        original_seeds.to_json(f.name)
        json_path = f.name

    # Clear database and reset sequences
    with db_conn.cursor() as cur:
        cur.execute(f"TRUNCATE {test_schema}.tb_machine, {test_schema}.tb_organization RESTART IDENTITY CASCADE")
        db_conn.commit()

    # Re-import
    from fraiseql_data.models import Seeds

    imported_seeds = Seeds.from_json(json_path)

    builder2 = SeedBuilder(db_conn, schema=test_schema)
    result = builder2.insert_seeds(imported_seeds)

    # Verify: re-imported correctly
    assert len(result.tb_organization) == 1
    assert len(result.tb_machine) == 5

    # Clean up
    import os

    os.unlink(json_path)
