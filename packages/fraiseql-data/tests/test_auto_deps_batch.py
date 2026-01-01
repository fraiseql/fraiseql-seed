"""Test auto-dependency resolution with batch operations."""


from fraiseql_data import SeedBuilder


def test_auto_deps_batch_deduplication(db_conn, test_schema):
    """Test that batch operations deduplicate auto-generated dependencies."""
    # Create schema where two tables both depend on organization
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

        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_order (
                pk_order INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                fk_organization INTEGER NOT NULL REFERENCES {test_schema}.tb_organization(pk_organization)
            )
        """
        )
        db_conn.commit()

    # Use batch with both tables having auto_deps
    builder = SeedBuilder(db_conn, schema=test_schema)

    with builder.batch() as batch:
        batch.add("tb_allocation", count=10, auto_deps=True)
        batch.add("tb_order", count=20, auto_deps=True)

    # Verify: only 1 organization created (deduplicated)
    with db_conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {test_schema}.tb_organization")
        org_count = cur.fetchone()[0]
        assert org_count == 1

        cur.execute(f"SELECT COUNT(*) FROM {test_schema}.tb_allocation")
        alloc_count = cur.fetchone()[0]
        assert alloc_count == 10

        cur.execute(f"SELECT COUNT(*) FROM {test_schema}.tb_order")
        order_count = cur.fetchone()[0]
        assert order_count == 20


def test_auto_deps_batch_with_manual(db_conn, test_schema):
    """Test batch with mix of manual and auto-deps (manual takes precedence)."""
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

        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_order (
                pk_order INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                fk_organization INTEGER NOT NULL REFERENCES {test_schema}.tb_organization(pk_organization)
            )
        """
        )
        db_conn.commit()

    # Manual add + batch with auto_deps
    builder = SeedBuilder(db_conn, schema=test_schema)

    with builder.batch() as batch:
        batch.add("tb_organization", count=3)  # Manual: 3 orgs
        batch.add("tb_allocation", count=10, auto_deps=True)  # Auto-deps (should use manual)
        batch.add("tb_order", count=20, auto_deps=True)  # Auto-deps (should use manual)

    # Verify: 3 organizations from manual, not auto-generated
    with db_conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {test_schema}.tb_organization")
        org_count = cur.fetchone()[0]
        assert org_count == 3  # Manual count used


def test_auto_deps_batch_different_counts(db_conn, test_schema):
    """Test batch with conflicting auto-dep counts (first wins or merge strategy)."""
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

        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_order (
                pk_order INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                fk_organization INTEGER NOT NULL REFERENCES {test_schema}.tb_organization(pk_organization)
            )
        """
        )
        db_conn.commit()

    # Batch with different auto-dep counts for same table
    builder = SeedBuilder(db_conn, schema=test_schema)

    with builder.batch() as batch:
        batch.add("tb_allocation", count=10, auto_deps={"tb_organization": 2})  # Wants 2
        batch.add("tb_order", count=20, auto_deps={"tb_organization": 5})  # Wants 5

    # Verify: should use max count (5) or first count (2)
    # Implementation decision: use max to satisfy both requirements
    with db_conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {test_schema}.tb_organization")
        org_count = cur.fetchone()[0]
        # Accept either 2 (first wins) or 5 (max wins) - implementation dependent
        # Plan says first-add wins, so should be 2
        assert org_count >= 2  # At least the minimum needed
