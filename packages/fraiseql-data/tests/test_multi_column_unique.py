"""Tests for multi-column UNIQUE constraint handling."""

from fraiseql_data import SeedBuilder
from psycopg import Connection


def test_multi_column_unique_two_columns(db_conn: Connection, test_schema: str):
    """Test UNIQUE(col1, col2) constraint."""
    # Create table with UNIQUE(category, code)
    with db_conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_product (
                pk_product INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                category TEXT NOT NULL,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                UNIQUE(category, code)
            )
            """
        )
        db_conn.commit()

    # Seed 100 rows
    builder = SeedBuilder(db_conn, schema=test_schema)
    seeds = builder.add("tb_product", count=100).execute()

    # Verify no duplicate (category, code) tuples
    products = seeds.tb_product
    assert len(products) == 100

    # Extract (category, code) tuples
    tuples = [(p.category, p.code) for p in products]

    # Verify all tuples are unique
    assert len(tuples) == len(set(tuples)), "Found duplicate (category, code) tuples"

    # This test will fail until multi-column UNIQUE is implemented
    raise AssertionError("Multi-column UNIQUE not yet implemented")


def test_multi_column_unique_three_columns(db_conn: Connection, test_schema: str):
    """Test UNIQUE(col1, col2, col3) constraint."""
    # Create table with UNIQUE(year, month, code)
    with db_conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_transaction (
                pk_transaction INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                code TEXT NOT NULL,
                amount NUMERIC NOT NULL,
                UNIQUE(year, month, code)
            )
            """
        )
        db_conn.commit()

    # Seed 50 rows
    builder = SeedBuilder(db_conn, schema=test_schema)
    seeds = (
        builder.add(
            "tb_transaction",
            count=50,
            overrides={
                "year": lambda i: 2024,
                "month": lambda i: (i % 12) + 1,  # 1-12
                "amount": lambda: 100.0,
            },
        ).execute()
    )

    # Verify no duplicate (year, month, code) tuples
    transactions = seeds.tb_transaction
    assert len(transactions) == 50

    # Extract (year, month, code) tuples
    tuples = [(t.year, t.month, t.code) for t in transactions]

    # Verify all tuples are unique
    assert len(tuples) == len(set(tuples)), "Found duplicate (year, month, code) tuples"

    # This test will fail until multi-column UNIQUE is implemented
    raise AssertionError("Multi-column UNIQUE (3 columns) not yet implemented")


def test_multiple_multi_column_unique_constraints(
    db_conn: Connection, test_schema: str
):
    """Test table with multiple multi-column UNIQUE constraints."""
    # Create table with two multi-column UNIQUE constraints
    with db_conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_order (
                pk_order INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                customer_code TEXT NOT NULL,
                order_number TEXT NOT NULL,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                UNIQUE(customer_code, order_number),
                UNIQUE(year, month, customer_code)
            )
            """
        )
        db_conn.commit()

    # Seed 30 rows
    builder = SeedBuilder(db_conn, schema=test_schema)
    seeds = (
        builder.add(
            "tb_order",
            count=30,
            overrides={
                "year": lambda i: 2024,
                "month": lambda i: (i % 12) + 1,
            },
        ).execute()
    )

    # Verify both constraints are satisfied
    orders = seeds.tb_order
    assert len(orders) == 30

    # Check first constraint: UNIQUE(customer_code, order_number)
    tuples1 = [(o.customer_code, o.order_number) for o in orders]
    assert len(tuples1) == len(set(tuples1)), "Duplicate (customer_code, order_number)"

    # Check second constraint: UNIQUE(year, month, customer_code)
    tuples2 = [(o.year, o.month, o.customer_code) for o in orders]
    assert len(tuples2) == len(set(tuples2)), "Duplicate (year, month, customer_code)"

    # This test will fail until multiple multi-column UNIQUE is supported
    raise AssertionError("Multiple multi-column UNIQUE constraints not yet implemented")
