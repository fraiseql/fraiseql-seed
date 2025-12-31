"""Pytest configuration and shared fixtures."""

import pytest
import psycopg
from psycopg import Connection
from fraiseql_data import SeedBuilder


@pytest.fixture
def db_conn() -> Connection:
    """
    Provide a test database connection.

    Note: This will be replaced with actual test database setup.
    For now, returns a connection to a test database that must exist.
    """
    # TODO: Use environment variable or test database
    conn = psycopg.connect(
        "postgresql://localhost/fraiseql_test",
        autocommit=False
    )

    yield conn

    # Rollback any changes
    conn.rollback()
    conn.close()


@pytest.fixture
def test_schema(db_conn: Connection) -> str:
    """
    Create a test schema with sample tables.

    Returns the schema name.
    """
    schema_name = "test_seed"

    with db_conn.cursor() as cur:
        # Drop if exists
        cur.execute(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE")

        # Create schema
        cur.execute(f"CREATE SCHEMA {schema_name}")

        # Create simple test table (Trinity pattern)
        cur.execute(f"""
            CREATE TABLE {schema_name}.tb_manufacturer (
                pk_manufacturer INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                id UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                email TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        # Create table with FK (Trinity pattern)
        cur.execute(f"""
            CREATE TABLE {schema_name}.tb_model (
                pk_model INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                id UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                description TEXT,
                fk_manufacturer INTEGER NOT NULL REFERENCES {schema_name}.tb_manufacturer(pk_manufacturer),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        db_conn.commit()

    yield schema_name

    # Cleanup
    with db_conn.cursor() as cur:
        cur.execute(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE")
        db_conn.commit()


@pytest.fixture
def seeds(request, db_conn: Connection, test_schema: str):
    """
    Fixture for seed data - works with @seed_data() decorator.

    The decorator populates this fixture by reading _seed_plans from the test function.
    """
    # Check if test function has seed plans from decorator
    if hasattr(request.function, "_seed_plans"):
        builder = SeedBuilder(db_conn, schema=test_schema)

        for plan in request.function._seed_plans:
            builder.add(
                plan["table"],
                count=plan["count"],
                strategy=plan["strategy"],
                overrides=plan["overrides"],
            )

        return builder.execute()

    # No decorator, return None (test should not use this fixture)
    return None
