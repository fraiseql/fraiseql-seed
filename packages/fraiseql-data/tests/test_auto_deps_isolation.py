"""Test data isolation behavior for auto-deps.

Note: The reuse_existing parameter was removed in Phase 6 and replaced
with the seed common baseline system. Tests for that feature have been
removed. For UUID collision prevention, use seed common baselines.
"""
# ruff: noqa: E501


from fraiseql_data import SeedBuilder


def test_auto_deps_generates_fresh_data(db_conn, test_schema):
    """Test that auto-deps generates data correctly."""
    # Create dependency
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
            CREATE TABLE {test_schema}.tb_allocation (
                pk_allocation INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                fk_organization INTEGER NOT NULL REFERENCES {test_schema}.tb_organization(pk_organization)
            )
        """
        )
        db_conn.commit()

    # Test: auto-deps generates needed data
    builder = SeedBuilder(db_conn, schema=test_schema)
    seeds = (
        builder.add(
            "tb_allocation",
            count=10,
            auto_deps={"tb_organization": 3},
        ).execute()
    )

    # Verify: generated 3 organizations + 10 allocations
    assert len(seeds.tb_organization) == 3
    assert len(seeds.tb_allocation) == 10

    # Verify database has 3 organizations
    with db_conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {test_schema}.tb_organization")
        count = cur.fetchone()[0]
        assert count == 3
