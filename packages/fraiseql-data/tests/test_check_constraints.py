"""Tests for CHECK constraint handling."""

import random

from fraiseql_data import SeedBuilder
from psycopg import Connection


def test_check_constraint_introspection(db_conn: Connection, test_schema: str):
    """Test CHECK constraint is introspected."""
    # Create table with CHECK (price > 0)
    with db_conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_product (
                pk_product INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                price NUMERIC NOT NULL CHECK (price > 0)
            )
            """
        )
        db_conn.commit()

    # Introspect table
    from fraiseql_data.introspection import SchemaIntrospector

    introspector = SchemaIntrospector(db_conn, test_schema)
    table_info = introspector.get_table_info("tb_product")

    # Verify CHECK constraint is detected
    assert (
        len(table_info.check_constraints) > 0
    ), "CHECK constraint should be introspected"

    # Find price CHECK constraint
    price_check = None
    for check in table_info.check_constraints:
        if "price" in check.check_clause.lower():
            price_check = check
            break

    assert price_check is not None, "Price CHECK constraint not found"
    assert ">" in price_check.check_clause or "0" in price_check.check_clause


def test_check_constraint_warning(db_conn: Connection, test_schema: str, caplog):
    """Test warning emitted for CHECK constraint without override."""
    # Create table with CHECK constraint
    with db_conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_item (
                pk_item INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('active', 'inactive', 'discontinued'))
            )
            """
        )
        db_conn.commit()

    # Seed without override (should emit warning)
    import logging

    logging.getLogger("fraiseql_data.builder").setLevel(logging.WARNING)

    builder = SeedBuilder(db_conn, schema=test_schema)

    # This should emit a warning about CHECK constraint
    try:
        builder.add("tb_item", count=5).execute()
        # If it succeeds, check that warning was logged
        # (or it might fail if generated data violates CHECK)
    except Exception:
        pass  # Expected if generated data violates CHECK

    # Verify warning was logged
    # Look for CHECK constraint warning in logs
    warning_found = False
    for record in caplog.records:
        if "CHECK constraint" in record.message or "check" in record.message.lower():
            warning_found = True
            break

    assert warning_found, "Should emit warning for CHECK constraint"


def test_check_constraint_with_override(db_conn: Connection, test_schema: str):
    """Test user override satisfies CHECK constraint."""
    # Create table with CHECK (price > 0 AND price < 10000)
    with db_conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_product (
                pk_product INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                price NUMERIC NOT NULL CHECK (price > 0 AND price < 10000),
                status TEXT NOT NULL CHECK (status IN ('active', 'inactive'))
            )
            """
        )
        db_conn.commit()

    # Provide overrides that satisfy CHECK constraints
    def generate_valid_price():
        return round(random.uniform(10.0, 9999.0), 2)

    def generate_valid_status():
        return random.choice(["active", "inactive"])

    builder = SeedBuilder(db_conn, schema=test_schema)
    seeds = (
        builder.add(
            "tb_product",
            count=50,
            overrides={
                "price": generate_valid_price,
                "status": generate_valid_status,
            },
        ).execute()
    )

    # Verify all rows satisfy CHECK constraints
    products = seeds.tb_product
    assert len(products) == 50

    for product in products:
        # Check price constraint
        assert 0 < product.price < 10000, f"Price {product.price} violates CHECK"
        # Check status constraint
        assert product.status in ["active", "inactive"], f"Status {product.status} violates CHECK"

    # Verify data is actually in database (constraints enforced)
    with db_conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {test_schema}.tb_product")
        assert cur.fetchone()[0] == 50
