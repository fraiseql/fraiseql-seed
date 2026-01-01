"""Integration tests for Phase 2 features combined."""

from fraiseql_data import SeedBuilder
from psycopg import Connection


def test_all_phase2_features_together(db_conn: Connection, test_schema: str):
    """
    Integration test combining self-reference, UNIQUE constraints, and bulk insert.

    Tests a realistic scenario:
    - tb_organization: Bulk insert with UNIQUE name
    - tb_category: Self-referencing with parent_category FK
    - tb_product: References both, has UNIQUE sku column
    """
    # Create schema with all Phase 2 features
    with db_conn.cursor() as cur:
        # Organizations table: UNIQUE constraint + bulk insert
        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_organization (
                pk_organization INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL UNIQUE,
                industry TEXT
            )
            """
        )

        # Categories table: Self-referencing FK
        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_category (
                pk_category INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                parent_category INTEGER REFERENCES {test_schema}.tb_category(pk_category)
            )
            """
        )

        # Products table: FKs + UNIQUE sku
        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_product (
                pk_product INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                sku TEXT NOT NULL UNIQUE,
                fk_organization INTEGER NOT NULL
                    REFERENCES {test_schema}.tb_organization(pk_organization),
                fk_category INTEGER
                    REFERENCES {test_schema}.tb_category(pk_category)
            )
            """
        )
        db_conn.commit()

    # Execute seed plan with all features
    builder = SeedBuilder(db_conn, test_schema)
    seeds = (
        builder.add("tb_organization", count=50)  # Bulk insert test
        .add("tb_category", count=20)  # Self-reference test
        .add("tb_product", count=100)  # UNIQUE + FKs test
        .execute()
    )

    # Verify tb_organization (bulk insert + UNIQUE constraint)
    assert len(seeds.tb_organization) == 50
    org_names = [org._data["name"] for org in seeds.tb_organization]
    assert len(org_names) == len(set(org_names)), "Organization names should be unique"

    # Verify tb_category (self-referencing FK)
    assert len(seeds.tb_category) == 20

    # First category should have NULL parent
    first_cat = seeds.tb_category[0]
    assert first_cat._data["parent_category"] is None, "First category should have no parent"

    # At least some categories should have parents
    categories_with_parents = [
        cat for cat in seeds.tb_category if cat._data["parent_category"] is not None
    ]
    assert len(categories_with_parents) > 0, "Some categories should have parent_category set"

    # All parent references should be valid
    all_pks = {cat._data["pk_category"] for cat in seeds.tb_category}
    for cat in categories_with_parents:
        parent_pk = cat._data["parent_category"]
        assert parent_pk in all_pks, f"Parent PK {parent_pk} should exist in category PKs"

    # Verify tb_product (UNIQUE sku + FKs)
    assert len(seeds.tb_product) == 100

    # UNIQUE sku constraint
    product_skus = [prod._data["sku"] for prod in seeds.tb_product]
    assert len(product_skus) == len(set(product_skus)), "Product SKUs should be unique"

    # FK to tb_organization
    org_pks = {org._data["pk_organization"] for org in seeds.tb_organization}
    for prod in seeds.tb_product:
        fk_org = prod._data["fk_organization"]
        assert fk_org in org_pks, f"FK org {fk_org} should exist in organization PKs"

    # Verify data is actually in database (not just in memory)
    with db_conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {test_schema}.tb_organization")
        assert cur.fetchone()[0] == 50

        cur.execute(f"SELECT COUNT(*) FROM {test_schema}.tb_category")
        assert cur.fetchone()[0] == 20

        cur.execute(f"SELECT COUNT(*) FROM {test_schema}.tb_product")
        assert cur.fetchone()[0] == 100


def test_complex_hierarchy(db_conn: Connection, test_schema: str):
    """
    Test complex self-referencing hierarchy with multiple levels.

    Verifies that hierarchical structures can be built correctly.
    """
    with db_conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE {test_schema}.tb_employee (
                pk_employee INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id UUID NOT NULL UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                fk_manager INTEGER REFERENCES {test_schema}.tb_employee(pk_employee)
            )
            """
        )
        db_conn.commit()

    # Seed 30 employees (should create org chart)
    builder = SeedBuilder(db_conn, test_schema)
    seeds = builder.add("tb_employee", count=30).execute()

    assert len(seeds.tb_employee) == 30

    # First employee has no manager
    assert seeds.tb_employee[0]._data["fk_manager"] is None

    # Remaining employees should mostly have managers
    employees_with_managers = [
        emp for emp in seeds.tb_employee if emp._data["fk_manager"] is not None
    ]
    assert len(employees_with_managers) >= 25, "Most employees should have managers"

    # Verify no circular references (employee can't be own manager)
    for emp in seeds.tb_employee:
        fk_manager = emp._data["fk_manager"]
        if fk_manager is not None:
            assert fk_manager != emp._data["pk_employee"], "Employee can't be own manager"
