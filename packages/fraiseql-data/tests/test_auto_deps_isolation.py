"""Test data isolation and reuse behavior for auto-deps."""
# ruff: noqa: E501


from fraiseql_data import SeedBuilder


def test_auto_deps_no_reuse_by_default(db_conn, test_schema):
    """Test that auto-deps creates new data each time (no reuse by default)."""
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

    # First call: create organization + allocations
    builder1 = SeedBuilder(db_conn, schema=test_schema)
    seeds1 = builder1.add("tb_allocation", count=5, auto_deps=True).execute()

    # Second call: should create NEW organization (no reuse)
    builder2 = SeedBuilder(db_conn, schema=test_schema)
    seeds2 = builder2.add("tb_allocation", count=5, auto_deps=True).execute()

    # Verify: 2 different organizations created
    org1_pk = seeds1.tb_organization[0].pk_organization
    org2_pk = seeds2.tb_organization[0].pk_organization
    assert org1_pk != org2_pk  # Different organizations

    # Verify database has 2 organizations
    with db_conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {test_schema}.tb_organization")
        count = cur.fetchone()[0]
        assert count == 2


def test_auto_deps_reuse_existing_full(db_conn, test_schema):
    """Test reuse_existing=True reuses all needed rows."""
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

    # First: manually create 3 organizations
    builder1 = SeedBuilder(db_conn, schema=test_schema)
    seeds1 = builder1.add("tb_organization", count=3).execute()
    existing_pks = [org.pk_organization for org in seeds1.tb_organization]

    # Second: use auto_deps with reuse_existing=True (need 2 orgs)
    builder2 = SeedBuilder(db_conn, schema=test_schema)
    seeds2 = (
        builder2.add(
            "tb_allocation",
            count=10,
            auto_deps={"tb_organization": 2},
            reuse_existing=True,
        ).execute()
    )

    # Verify: reused first 2 existing organizations (pk 1, 2)
    assert len(seeds2.tb_organization) == 2
    assert seeds2.tb_organization[0].pk_organization == existing_pks[0]
    assert seeds2.tb_organization[1].pk_organization == existing_pks[1]

    # Verify database still has only 3 organizations (no new ones created)
    with db_conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {test_schema}.tb_organization")
        count = cur.fetchone()[0]
        assert count == 3


def test_auto_deps_reuse_partial(db_conn, test_schema):
    """Test reuse_existing with insufficient data (reuse some, generate rest)."""
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

    # First: create only 2 organizations
    builder1 = SeedBuilder(db_conn, schema=test_schema)
    seeds1 = builder1.add("tb_organization", count=2).execute()
    existing_pks = [org.pk_organization for org in seeds1.tb_organization]

    # Second: use auto_deps needing 5 orgs with reuse_existing=True
    builder2 = SeedBuilder(db_conn, schema=test_schema)
    seeds2 = (
        builder2.add(
            "tb_allocation",
            count=10,
            auto_deps={"tb_organization": 5},  # Need 5, but only 2 exist
            reuse_existing=True,
        ).execute()
    )

    # Verify: reused 2 existing + generated 3 new = 5 total
    assert len(seeds2.tb_organization) == 5

    # First 2 should be reused
    assert seeds2.tb_organization[0].pk_organization == existing_pks[0]
    assert seeds2.tb_organization[1].pk_organization == existing_pks[1]

    # Last 3 should be new
    assert seeds2.tb_organization[2].pk_organization not in existing_pks
    assert seeds2.tb_organization[3].pk_organization not in existing_pks
    assert seeds2.tb_organization[4].pk_organization not in existing_pks

    # Verify database has 5 total organizations
    with db_conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {test_schema}.tb_organization")
        count = cur.fetchone()[0]
        assert count == 5


def test_auto_deps_reuse_none_available(db_conn, test_schema):
    """Test reuse_existing when no existing data (generates all)."""
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

    # Database is empty, but use reuse_existing=True
    builder = SeedBuilder(db_conn, schema=test_schema)
    seeds = (
        builder.add(
            "tb_allocation",
            count=10,
            auto_deps={"tb_organization": 3},
            reuse_existing=True,  # No existing data, should generate all
        ).execute()
    )

    # Verify: generated 3 organizations (none to reuse)
    assert len(seeds.tb_organization) == 3

    # Verify database has 3 organizations
    with db_conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {test_schema}.tb_organization")
        count = cur.fetchone()[0]
        assert count == 3
