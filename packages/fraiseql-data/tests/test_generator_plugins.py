"""Tests for custom generator plugin system."""

from fraiseql_data import (
    BaseGenerator,
    SeedBuilder,
    clear_generators,
    list_generators,
    register_generator,
)
from psycopg import Connection


def test_register_custom_generator(db_conn: Connection, test_schema: str):
    """Test registering and using custom generator."""

    # Define custom SKU generator
    class SKUGenerator(BaseGenerator):
        def generate(self, column_name, pg_type, **context):
            counter = context.get("counter", 1)
            return f"SKU-{counter:06d}"

    # Register the generator
    register_generator("sku", SKUGenerator)

    # Verify it's registered
    assert "sku" in list_generators()

    # Create table with sku column
    with db_conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_product (
                pk_product INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                sku TEXT NOT NULL UNIQUE
            )
            """
        )
        db_conn.commit()

    # Use custom generator via strategy parameter
    builder = SeedBuilder(db_conn, schema=test_schema)
    seeds = builder.add("tb_product", count=10, strategy="sku").execute()

    # Verify custom SKU format
    products = seeds.tb_product
    assert len(products) == 10

    # Verify SKU format matches expected pattern
    for i, product in enumerate(products, start=1):
        assert product.sku == f"SKU-{i:06d}", f"Expected SKU-{i:06d}, got {product.sku}"

    # Cleanup
    clear_generators()


def test_custom_generator_with_context(db_conn: Connection, test_schema: str):
    """Test custom generator receives context (instance, row_data)."""

    # Define category-aware SKU generator
    class CategorySKUGenerator(BaseGenerator):
        def generate(self, column_name, pg_type, **context):
            instance = context.get("instance", 1)
            row_data = context.get("row_data", {})
            category = row_data.get("category", "GEN")
            year = 2024
            return f"PROD-{category}-{year}-{instance:05d}"

    # Register generator
    register_generator("category_sku", CategorySKUGenerator)

    # Create table
    with db_conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_item (
                pk_item INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                category TEXT NOT NULL,
                sku TEXT NOT NULL UNIQUE
            )
            """
        )
        db_conn.commit()

    # Seed with overrides (category column needed for SKU generation)
    builder = SeedBuilder(db_conn, schema=test_schema)
    seeds = builder.add(
        "tb_item",
        count=5,
        overrides={
            "category": lambda i: ["ELEC", "FOOD", "TOOLS"][i % 3],
            # SKU generator would use category from row_data
        },
    ).execute()

    # Verify categories were set
    items = seeds.tb_item
    assert len(items) == 5
    assert all(item.category in ["ELEC", "FOOD", "TOOLS"] for item in items)

    # Cleanup
    clear_generators()


def test_list_registered_generators():
    """Test listing all registered generators."""
    # Initially should be empty (or have built-ins)
    initial_generators = list_generators()

    # Register two custom generators
    class Gen1(BaseGenerator):
        def generate(self, column_name, pg_type, **context):
            return "value1"

    class Gen2(BaseGenerator):
        def generate(self, column_name, pg_type, **context):
            return "value2"

    register_generator("gen1", Gen1)
    register_generator("gen2", Gen2)

    # Verify both are listed
    generators = list_generators()
    assert "gen1" in generators
    assert "gen2" in generators
    assert len(generators) == len(initial_generators) + 2

    # Clear and verify empty
    clear_generators()
    assert list_generators() == []
