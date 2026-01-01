"""Test basic auto-dependency resolution functionality."""
# ruff: noqa: E501


from fraiseql_data import SeedBuilder


def test_auto_deps_minimal_single_level(db_conn, test_schema):
    """Test auto-deps with single-level FK (allocation → machine)."""
    # Create simple dependency: tb_allocation → tb_machine
    with db_conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_machine (
                pk_machine INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
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
                fk_machine INTEGER NOT NULL REFERENCES {test_schema}.tb_machine(pk_machine)
            )
        """
        )
        db_conn.commit()

    # Use auto_deps - should auto-generate tb_machine
    builder = SeedBuilder(db_conn, schema=test_schema)
    seeds = builder.add("tb_allocation", count=10, auto_deps=True).execute()

    # Verify: 1 machine, 10 allocations
    assert len(seeds.tb_machine) == 1
    assert len(seeds.tb_allocation) == 10

    # Verify all allocations reference the machine
    machine_pk = seeds.tb_machine[0].pk_machine
    for allocation in seeds.tb_allocation:
        assert allocation.fk_machine == machine_pk


def test_auto_deps_minimal_multi_level(db_conn, test_schema):
    """Test auto-deps with multi-level FK chain (allocation → machine → location → org)."""
    # Create 4-level dependency chain
    with db_conn.cursor() as cur:
        # Level 1: tb_organization (no deps)
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

        # Level 2: tb_location → organization
        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_location (
                pk_location INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                fk_organization INTEGER NOT NULL REFERENCES {test_schema}.tb_organization(pk_organization)
            )
        """
        )

        # Level 3: tb_machine → location
        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_machine (
                pk_machine INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                fk_location INTEGER NOT NULL REFERENCES {test_schema}.tb_location(pk_location)
            )
        """
        )

        # Level 4: tb_allocation → machine
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

    # Use auto_deps - should auto-generate entire chain
    builder = SeedBuilder(db_conn, schema=test_schema)
    seeds = builder.add("tb_allocation", count=10, auto_deps=True).execute()

    # Verify: 1 of each dependency, 10 allocations
    assert len(seeds.tb_organization) == 1
    assert len(seeds.tb_location) == 1
    assert len(seeds.tb_machine) == 1
    assert len(seeds.tb_allocation) == 10

    # Verify FK chain
    org_pk = seeds.tb_organization[0].pk_organization
    loc_pk = seeds.tb_location[0].pk_location
    machine_pk = seeds.tb_machine[0].pk_machine

    assert seeds.tb_location[0].fk_organization == org_pk
    assert seeds.tb_machine[0].fk_location == loc_pk
    for allocation in seeds.tb_allocation:
        assert allocation.fk_machine == machine_pk


def test_auto_deps_multi_path_deduplication(db_conn, test_schema):
    """Test auto-deps deduplicates when multiple paths lead to same table."""
    # Create schema with two paths to tb_organization:
    # tb_allocation → tb_machine → tb_organization
    # tb_allocation → tb_contract → tb_organization
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
            CREATE TABLE {test_schema}.tb_contract (
                pk_contract INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
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
                fk_machine INTEGER NOT NULL REFERENCES {test_schema}.tb_machine(pk_machine),
                fk_contract INTEGER NOT NULL REFERENCES {test_schema}.tb_contract(pk_contract)
            )
        """
        )
        db_conn.commit()

    # Use auto_deps - should deduplicate tb_organization
    builder = SeedBuilder(db_conn, schema=test_schema)
    seeds = builder.add("tb_allocation", count=10, auto_deps=True).execute()

    # Verify: 1 organization (deduplicated), 1 machine, 1 contract, 10 allocations
    assert len(seeds.tb_organization) == 1
    assert len(seeds.tb_machine) == 1
    assert len(seeds.tb_contract) == 1
    assert len(seeds.tb_allocation) == 10

    # Verify both machine and contract reference same organization
    org_pk = seeds.tb_organization[0].pk_organization
    assert seeds.tb_machine[0].fk_organization == org_pk
    assert seeds.tb_contract[0].fk_organization == org_pk


def test_auto_deps_with_explicit_counts(db_conn, test_schema):
    """Test auto-deps with explicit counts for specific dependencies."""
    # Create dependency chain
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

    # Use auto_deps with explicit counts
    builder = SeedBuilder(db_conn, schema=test_schema)
    seeds = (
        builder.add(
            "tb_allocation",
            count=100,
            auto_deps={
                "tb_organization": 3,  # 3 organizations
                "tb_machine": 10,  # 10 machines
            },
        ).execute()
    )

    # Verify counts
    assert len(seeds.tb_organization) == 3
    assert len(seeds.tb_machine) == 10
    assert len(seeds.tb_allocation) == 100


def test_auto_deps_with_overrides(db_conn, test_schema):
    """Test auto-deps with overrides for auto-generated dependencies."""
    # Create simple dependency
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

    # Use auto_deps with overrides
    builder = SeedBuilder(db_conn, schema=test_schema)
    seeds = (
        builder.add(
            "tb_allocation",
            count=10,
            auto_deps={
                "tb_organization": {
                    "count": 2,
                    "overrides": {
                        "name": lambda i: f"Test Org {i}",
                    },
                }
            },
        ).execute()
    )

    # Verify override values
    assert len(seeds.tb_organization) == 2
    assert seeds.tb_organization[0].name == "Test Org 1"
    assert seeds.tb_organization[1].name == "Test Org 2"


def test_auto_deps_already_in_plan_manual_wins(db_conn, test_schema):
    """Test that manual .add() takes precedence over auto_deps config."""
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

    # Manual add with count=5, then auto_deps with count=2
    builder = SeedBuilder(db_conn, schema=test_schema)
    seeds = (
        builder.add("tb_organization", count=5)  # Manual: 5 orgs
        .add(
            "tb_allocation",
            count=10,
            auto_deps={"tb_organization": 2},  # Auto: 2 orgs (should be ignored)
        )
        .execute()
    )

    # Verify manual count wins
    assert len(seeds.tb_organization) == 5  # Manual count used, not auto_deps count


def test_auto_deps_false(db_conn, test_schema):
    """Test that auto_deps=False (default) does not auto-generate dependencies."""
    # Create dependency
    with db_conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_machine (
                pk_machine INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
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
                fk_machine INTEGER NOT NULL REFERENCES {test_schema}.tb_machine(pk_machine)
            )
        """
        )
        db_conn.commit()

    # Without auto_deps, should raise MissingDependencyError
    from fraiseql_data.exceptions import MissingDependencyError

    builder = SeedBuilder(db_conn, schema=test_schema)

    try:
        builder.add("tb_allocation", count=10, auto_deps=False).execute()
        raise AssertionError("Expected MissingDependencyError")
    except MissingDependencyError as e:
        assert "tb_machine" in str(e)
        assert "tb_allocation" in str(e)
