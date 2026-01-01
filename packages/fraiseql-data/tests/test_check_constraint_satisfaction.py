"""Test automatic satisfaction of CHECK constraints."""


from fraiseql_data import SeedBuilder


def test_auto_satisfy_enum_constraint(db_conn, test_schema):
    """Test automatic satisfaction of IN constraint (enum values)."""
    # Create table with CHECK constraint for enum values
    with db_conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_item (
                pk_item INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL CHECK (status IN ('active', 'inactive', 'discontinued'))
            )
        """
        )
        db_conn.commit()

    # Generate seed data WITHOUT manually providing status override
    builder = SeedBuilder(db_conn, schema=test_schema)
    seeds = builder.add("tb_item", count=100).execute()

    # Verify all rows have valid status (auto-satisfied constraint)
    assert len(seeds.tb_item) == 100
    for item in seeds.tb_item:
        assert item.status in [
            "active",
            "inactive",
            "discontinued",
        ], f"Invalid status: {item.status}"

    # Verify data actually in database (constraint validated by PostgreSQL)
    with db_conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {test_schema}.tb_item")
        count = cur.fetchone()[0]
        assert count == 100


def test_auto_satisfy_range_constraint(db_conn, test_schema):
    """Test automatic satisfaction of range constraints (>, <, BETWEEN)."""
    # Create table with range CHECK constraints
    with db_conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_product (
                pk_product INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                price NUMERIC CHECK (price > 0 AND price < 10000),
                stock INTEGER CHECK (stock >= 0)
            )
        """
        )
        db_conn.commit()

    # Generate seed data WITHOUT manually providing price/stock overrides
    builder = SeedBuilder(db_conn, schema=test_schema)
    seeds = builder.add("tb_product", count=50).execute()

    # Verify all rows satisfy range constraints
    assert len(seeds.tb_product) == 50
    for product in seeds.tb_product:
        assert (
            0 < product.price < 10000
        ), f"Price out of range: {product.price}"
        assert product.stock >= 0, f"Stock negative: {product.stock}"


def test_complex_check_emits_warning(db_conn, test_schema, caplog):
    """Test that complex CHECK constraints emit warnings (cannot auto-satisfy)."""
    # Create table with complex CHECK constraint (cannot be auto-parsed)
    with db_conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_order (
                pk_order INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                quantity INTEGER NOT NULL,
                price NUMERIC NOT NULL,
                total NUMERIC NOT NULL CHECK (total = price * quantity)
            )
        """
        )
        db_conn.commit()

    # Generate seed data - complex constraint should emit warning
    builder = SeedBuilder(db_conn, schema=test_schema)

    # Clear previous logs
    caplog.clear()

    # This should emit a warning about complex CHECK constraint
    try:
        builder.add("tb_order", count=10).execute()
        # May fail if constraint violation occurs, or succeed with warning
        db_conn.commit()
    except Exception:
        # Expected if constraint violated - rollback to clean transaction state
        db_conn.rollback()

    # Verify warning was emitted
    assert any(
        "CHECK constraint" in record.message and "total" in record.message.lower()
        for record in caplog.records
    ), "Expected warning about complex CHECK constraint"
