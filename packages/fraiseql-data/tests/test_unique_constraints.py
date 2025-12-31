"""Tests for UNIQUE constraint handling."""

from psycopg import Connection

from fraiseql_data import SeedBuilder


def test_unique_text_column(db_conn: Connection, test_schema: str):
    """Test UNIQUE constraint on text column prevents duplicates."""
    # Create table with UNIQUE email column
    with db_conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_user (
                pk_user INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """
        )
        db_conn.commit()

    # Seed 100 rows
    builder = SeedBuilder(db_conn, schema=test_schema)
    builder.add("tb_user", count=100)
    seeds = builder.execute()

    # Verify no duplicate emails
    users = seeds.tb_user
    assert len(users) == 100

    emails = [u.email for u in users]
    assert len(emails) == len(set(emails)), "Found duplicate emails!"

    # Cleanup
    with db_conn.cursor() as cur:
        cur.execute(f"DROP TABLE {test_schema}.tb_user CASCADE")
        db_conn.commit()


def test_unique_integer_column(db_conn: Connection, test_schema: str):
    """Test UNIQUE constraint on integer column."""
    # Create table with UNIQUE code integer
    with db_conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_product (
                pk_product INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                name TEXT NOT NULL,
                product_code INTEGER NOT NULL UNIQUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """
        )
        db_conn.commit()

    # Seed 50 rows
    builder = SeedBuilder(db_conn, schema=test_schema)
    builder.add("tb_product", count=50)
    seeds = builder.execute()

    # Verify no duplicate codes
    products = seeds.tb_product
    assert len(products) == 50

    codes = [p.product_code for p in products]
    assert len(codes) == len(set(codes)), "Found duplicate product codes!"

    # Cleanup
    with db_conn.cursor() as cur:
        cur.execute(f"DROP TABLE {test_schema}.tb_product CASCADE")
        db_conn.commit()


def test_multiple_unique_constraints(db_conn: Connection, test_schema: str):
    """Test table with multiple UNIQUE columns."""
    # Create table with UNIQUE email and UNIQUE username
    with db_conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_account (
                pk_account INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                bio TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """
        )
        db_conn.commit()

    # Seed 50 rows
    builder = SeedBuilder(db_conn, schema=test_schema)
    builder.add("tb_account", count=50)
    seeds = builder.execute()

    # Verify both columns have no duplicates
    accounts = seeds.tb_account
    assert len(accounts) == 50

    usernames = [a.username for a in accounts]
    assert len(usernames) == len(set(usernames)), "Found duplicate usernames!"

    emails = [a.email for a in accounts]
    assert len(emails) == len(set(emails)), "Found duplicate emails!"

    # Cleanup
    with db_conn.cursor() as cur:
        cur.execute(f"DROP TABLE {test_schema}.tb_account CASCADE")
        db_conn.commit()
