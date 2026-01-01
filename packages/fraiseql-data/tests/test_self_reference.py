"""Tests for self-referencing table support."""

from fraiseql_data import SeedBuilder
from psycopg import Connection


def test_self_reference_nullable(db_conn: Connection, test_schema: str):
    """Test table with nullable self-referencing FK."""
    # Create category table with parent_category FK to self
    with db_conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_category (
                pk_category INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                id UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                parent_category INTEGER REFERENCES {test_schema}.tb_category(pk_category),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """
        )
        db_conn.commit()

    # Seed 5 categories
    builder = SeedBuilder(db_conn, schema=test_schema)
    builder.add("tb_category", count=5)
    seeds = builder.execute()

    # Verify: First category has NULL parent, others have valid parent_id
    categories = seeds.tb_category
    assert len(categories) == 5

    # First category should have NULL parent
    assert categories[0].parent_category is None

    # Other categories should have valid parent references
    all_pks = {cat.pk_category for cat in categories}
    for cat in categories[1:]:
        if cat.parent_category is not None:
            assert cat.parent_category in all_pks

    # Cleanup
    with db_conn.cursor() as cur:
        cur.execute(f"DROP TABLE {test_schema}.tb_category CASCADE")
        db_conn.commit()


def test_self_reference_non_nullable_error(db_conn: Connection, test_schema: str):
    """Test non-nullable self-reference raises error."""
    # Create table with non-nullable self-ref FK
    with db_conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_node (
                pk_node INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                name TEXT NOT NULL,
                fk_parent INTEGER NOT NULL REFERENCES {test_schema}.tb_node(pk_node)
            )
        """
        )
        db_conn.commit()

    # Expect SelfReferenceError when trying to seed
    builder = SeedBuilder(db_conn, schema=test_schema)
    builder.add("tb_node", count=5)

    try:
        builder.execute()
        raise AssertionError("Expected SelfReferenceError but execution succeeded")
    except Exception as e:
        # Should raise SelfReferenceError
        assert "self-reference" in str(e).lower() or "SelfReferenceError" in str(type(e))

    # Cleanup
    with db_conn.cursor() as cur:
        cur.execute(f"DROP TABLE {test_schema}.tb_node CASCADE")
        db_conn.commit()


def test_self_reference_hierarchy(db_conn: Connection, test_schema: str):
    """Test multi-level category hierarchy."""
    # Create category table
    with db_conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_category (
                pk_category INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                id UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                parent_category INTEGER REFERENCES {test_schema}.tb_category(pk_category),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """
        )
        db_conn.commit()

    # Seed 10 categories
    builder = SeedBuilder(db_conn, schema=test_schema)
    builder.add("tb_category", count=10)
    seeds = builder.execute()

    # Verify parent relationships are valid
    categories = seeds.tb_category
    assert len(categories) == 10

    all_pks = {cat.pk_category for cat in categories}

    # Check all parent references exist in table
    for cat in categories:
        if cat.parent_category is not None:
            assert (
                cat.parent_category in all_pks
            ), f"Category {cat.pk_category} has invalid parent {cat.parent_category}"

    # Verify no cycles (no category is its own parent)
    for cat in categories:
        assert cat.parent_category != cat.pk_category

    # Cleanup
    with db_conn.cursor() as cur:
        cur.execute(f"DROP TABLE {test_schema}.tb_category CASCADE")
        db_conn.commit()
