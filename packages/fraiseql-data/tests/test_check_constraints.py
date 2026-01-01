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
    """Test auto-satisfaction of simple CHECK constraints (Phase 4)."""
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

    # Seed without override (should auto-satisfy CHECK constraint)
    import logging

    logging.getLogger("fraiseql_data.builder").setLevel(logging.INFO)

    builder = SeedBuilder(db_conn, schema=test_schema)

    # This should auto-satisfy the CHECK constraint
    seeds = builder.add("tb_item", count=5).execute()

    # Verify data generated successfully with valid status values
    assert len(seeds.tb_item) == 5
    for item in seeds.tb_item:
        assert item.status in ["active", "inactive", "discontinued"]

    # Verify auto-satisfaction was logged (INFO level)
    auto_satisfy_found = False
    for record in caplog.records:
        if "Auto-satisfying CHECK constraint" in record.message:
            auto_satisfy_found = True
            break

    assert auto_satisfy_found, "Should log auto-satisfaction of CHECK constraint"


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
