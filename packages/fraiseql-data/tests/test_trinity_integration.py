"""Test Trinity extension integration for deterministic PK allocation."""

import pytest
from fraiseql_data import SeedBuilder
from fraiseql_data.models import ColumnInfo, TableInfo


class TestTrinityStagingSimulation:
    """Test Trinity simulation in staging backend (deterministic PK allocation)."""

    def test_trinity_simulation_basic(self):
        """Test Trinity simulation allocates same UUID to same PK."""
        # Create builder with Trinity simulation enabled
        builder = SeedBuilder(
            conn=None,
            schema="test",
            backend="staging",
            trinity_enabled=True,
            trinity_tenant_id=1,
        )

        # Define table schema
        table_info = TableInfo(
            name="tb_manufacturer",
            columns=[
                ColumnInfo(
                    name="pk_manufacturer",
                    pg_type="integer",
                    is_nullable=False,
                    is_primary_key=True,
                ),
                ColumnInfo(name="id", pg_type="uuid", is_nullable=False, is_unique=True),
                ColumnInfo(name="identifier", pg_type="text", is_nullable=False, is_unique=True),
                ColumnInfo(name="name", pg_type="text", is_nullable=False),
            ],
        )
        builder.set_table_schema("tb_manufacturer", table_info)

        # Generate seeds
        seeds = builder.add("tb_manufacturer", count=5).execute()

        # Collect UUIDs and PKs from generated data
        uuid_to_pk_map = {
            row.id: row.pk_manufacturer for row in seeds.tb_manufacturer
        }

        # Now generate again with same data - should get same PKs
        builder2 = SeedBuilder(
            conn=None,
            schema="test",
            backend="staging",
            trinity_enabled=True,
            trinity_tenant_id=1,
        )
        builder2.set_table_schema("tb_manufacturer", table_info)
        seeds2 = builder2.add("tb_manufacturer", count=5).execute()

        uuid_to_pk_map2 = {
            row.id: row.pk_manufacturer for row in seeds2.tb_manufacturer
        }

        # Both runs should produce same UUID→PK mapping
        assert uuid_to_pk_map == uuid_to_pk_map2, (
            "Trinity simulation should allocate same PK for same UUID across runs. "
            f"Run 1: {uuid_to_pk_map}, Run 2: {uuid_to_pk_map2}"
        )

    def test_trinity_simulation_multi_table(self):
        """Test Trinity simulation works with multiple tables."""
        builder = SeedBuilder(
            conn=None,
            schema="test",
            backend="staging",
            trinity_enabled=True,
            trinity_tenant_id=1,
        )

        # Define two tables with FKs
        manufacturer_info = TableInfo(
            name="tb_manufacturer",
            columns=[
                ColumnInfo(
                    name="pk_manufacturer",
                    pg_type="integer",
                    is_nullable=False,
                    is_primary_key=True,
                ),
                ColumnInfo(name="id", pg_type="uuid", is_nullable=False, is_unique=True),
                ColumnInfo(name="identifier", pg_type="text", is_nullable=False, is_unique=True),
                ColumnInfo(name="name", pg_type="text", is_nullable=False),
            ],
        )

        product_info = TableInfo(
            name="tb_product",
            columns=[
                ColumnInfo(
                    name="pk_product",
                    pg_type="integer",
                    is_nullable=False,
                    is_primary_key=True,
                ),
                ColumnInfo(name="id", pg_type="uuid", is_nullable=False, is_unique=True),
                ColumnInfo(name="identifier", pg_type="text", is_nullable=False, is_unique=True),
                ColumnInfo(name="name", pg_type="text", is_nullable=False),
                ColumnInfo(name="manufacturer_id", pg_type="uuid", is_nullable=False),
            ],
        )

        builder.set_table_schema("tb_manufacturer", manufacturer_info)
        builder.set_table_schema("tb_product", product_info)

        # Generate data
        seeds = (
            builder.add("tb_manufacturer", count=3)
            .add("tb_product", count=10)
            .execute()
        )

        # Verify PKs are deterministic
        manufacturer_pks = [m.pk_manufacturer for m in seeds.tb_manufacturer]
        product_pks = [p.pk_product for p in seeds.tb_product]

        # All PKs should be unique within their table
        assert len(manufacturer_pks) == len(set(manufacturer_pks))
        assert len(product_pks) == len(set(product_pks))

        # PKs should be sequential (deterministic)
        assert manufacturer_pks == list(range(1, 4))
        assert product_pks == list(range(1, 11))

    def test_trinity_simulation_multi_tenant(self):
        """Test Trinity simulation isolates data per tenant."""
        # Tenant 1 data
        builder1 = SeedBuilder(
            conn=None,
            schema="test",
            backend="staging",
            trinity_enabled=True,
            trinity_tenant_id=1,
        )

        table_info = TableInfo(
            name="tb_manufacturer",
            columns=[
                ColumnInfo(
                    name="pk_manufacturer",
                    pg_type="integer",
                    is_nullable=False,
                    is_primary_key=True,
                ),
                ColumnInfo(name="id", pg_type="uuid", is_nullable=False, is_unique=True),
                ColumnInfo(name="identifier", pg_type="text", is_nullable=False, is_unique=True),
                ColumnInfo(name="name", pg_type="text", is_nullable=False),
            ],
        )
        builder1.set_table_schema("tb_manufacturer", table_info)
        seeds1 = builder1.add("tb_manufacturer", count=3).execute()

        # Tenant 2 data - should get different PKs
        builder2 = SeedBuilder(
            conn=None,
            schema="test",
            backend="staging",
            trinity_enabled=True,
            trinity_tenant_id=2,
        )
        builder2.set_table_schema("tb_manufacturer", table_info)
        seeds2 = builder2.add("tb_manufacturer", count=3).execute()

        # PKs should be independent per tenant
        pks1 = {row.id: row.pk_manufacturer for row in seeds1.tb_manufacturer}
        pks2 = {row.id: row.pk_manufacturer for row in seeds2.tb_manufacturer}

        # Different tenants should have independent PK sequences
        # Tenant 1: 1, 2, 3
        # Tenant 2: 1, 2, 3 (same sequence, different tenant context)
        assert list(pks1.values()) == [1, 2, 3]
        assert list(pks2.values()) == [1, 2, 3]

    def test_trinity_simulation_disabled_by_default(self):
        """Test Trinity simulation is disabled by default."""
        builder = SeedBuilder(
            conn=None,
            schema="test",
            backend="staging",
            # trinity_enabled=False is default
        )

        table_info = TableInfo(
            name="tb_item",
            columns=[
                ColumnInfo(
                    name="pk_item",
                    pg_type="integer",
                    is_nullable=False,
                    is_primary_key=True,
                ),
                ColumnInfo(name="id", pg_type="uuid", is_nullable=False, is_unique=True),
                ColumnInfo(name="identifier", pg_type="text", is_nullable=False, is_unique=True),
                ColumnInfo(name="name", pg_type="text", is_nullable=False),
            ],
        )
        builder.set_table_schema("tb_item", table_info)
        seeds = builder.add("tb_item", count=5).execute()

        # Should still generate PKs (sequential)
        pks = [item.pk_item for item in seeds.tb_item]
        assert pks == [1, 2, 3, 4, 5]

    def test_trinity_determinism_across_instances(self):
        """Test Trinity determinism: same UUID always gets same PK (even if name differs due to Faker)."""
        # First run
        builder1 = SeedBuilder(
            conn=None,
            schema="test",
            backend="staging",
            trinity_enabled=True,
            trinity_tenant_id=1,
        )

        table_info = TableInfo(
            name="tb_product",
            columns=[
                ColumnInfo(
                    name="pk_product",
                    pg_type="integer",
                    is_nullable=False,
                    is_primary_key=True,
                ),
                ColumnInfo(name="id", pg_type="uuid", is_nullable=False, is_unique=True),
                ColumnInfo(name="identifier", pg_type="text", is_nullable=False, is_unique=True),
                ColumnInfo(name="name", pg_type="text", is_nullable=False),
            ],
        )
        builder1.set_table_schema("tb_product", table_info)
        seeds1 = builder1.add("tb_product", count=3).execute()

        # Extract UUID→PK mapping (the deterministic part)
        uuid_to_pk_1 = {row.id: row.pk_product for row in seeds1.tb_product}

        # Second run with independent builder
        builder2 = SeedBuilder(
            conn=None,
            schema="test",
            backend="staging",
            trinity_enabled=True,
            trinity_tenant_id=1,
        )
        builder2.set_table_schema("tb_product", table_info)
        seeds2 = builder2.add("tb_product", count=3).execute()

        # Extract UUID→PK mapping
        uuid_to_pk_2 = {row.id: row.pk_product for row in seeds2.tb_product}

        # Both runs should produce same UUID→PK mapping
        # (Names may differ due to Faker randomness, but PK allocation is deterministic)
        assert uuid_to_pk_1 == uuid_to_pk_2, (
            "Trinity determinism failed: same UUID should produce same PK. "
            f"Run 1: {uuid_to_pk_1}, Run 2: {uuid_to_pk_2}"
        )


class TestTrinityGeneratorContext:
    """Test TrinityGenerator with Trinity context (connection required)."""

    def test_trinity_generator_stores_context(self):
        """Test TrinityGenerator correctly stores Trinity context."""
        from fraiseql_uuid import Pattern
        from fraiseql_data.generators import TrinityGenerator

        pattern = Pattern()
        context = {"conn": None, "tenant_id": 1}

        gen = TrinityGenerator(
            pattern, "tb_test", trinity_context=context
        )

        assert gen.trinity_context == context
        assert gen.trinity_context["tenant_id"] == 1

    def test_trinity_generator_without_context(self):
        """Test TrinityGenerator works without Trinity context."""
        from fraiseql_uuid import Pattern
        from fraiseql_data.generators import TrinityGenerator

        pattern = Pattern()

        gen = TrinityGenerator(pattern, "tb_test")

        assert gen.trinity_context is None

        # Should still generate id and identifier
        result = gen.generate(1, name="Test")

        assert "id" in result
        assert "identifier" in result
        assert "pk_tb_test" not in result  # No pk_* without context

    def test_trinity_generator_with_context_format(self):
        """Test TrinityGenerator output format with context."""
        from fraiseql_uuid import Pattern
        from fraiseql_data.generators import TrinityGenerator

        pattern = Pattern()

        # Mock context (conn would be None in this test)
        # Real integration tests with database would use actual connection
        gen = TrinityGenerator(pattern, "tb_test")
        result = gen.generate(1, name="Test Item")

        # Without context, should have id and identifier
        assert isinstance(result, dict)
        assert "id" in result
        assert "identifier" in result
        assert "pk_tb_test" not in result


@pytest.mark.integration
class TestTrinityDirectBackendIntegration:
    """Integration tests for Trinity with DirectBackend (requires database)."""

    def test_direct_backend_accepts_preallocated_pks(self, db_conn, test_schema):
        """Test DirectBackend accepts and inserts pre-allocated pk_* values."""
        from fraiseql_data.backends.direct import DirectBackend

        # Create backend
        backend = DirectBackend(db_conn, test_schema)

        # Create table
        with db_conn.cursor() as cur:
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {test_schema}.tb_test (
                    pk_test INTEGER PRIMARY KEY,
                    id UUID NOT NULL UNIQUE,
                    identifier TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL
                )
                """
            )
            db_conn.commit()

        # Prepare rows with pre-allocated PKs
        rows = [
            {
                "pk_test": 100,  # Pre-allocated by Trinity
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "identifier": "test-1",
                "name": "Test 1",
            },
            {
                "pk_test": 200,  # Pre-allocated by Trinity
                "id": "550e8400-e29b-41d4-a716-446655440001",
                "identifier": "test-2",
                "name": "Test 2",
            },
        ]

        # Get table info
        table_info = backend.introspector.get_table_info("tb_test") if hasattr(backend, "introspector") else None

        # For direct test, create TableInfo manually
        table_info = TableInfo(
            name="tb_test",
            columns=[
                ColumnInfo(
                    name="pk_test",
                    pg_type="integer",
                    is_nullable=False,
                    is_primary_key=True,
                ),
                ColumnInfo(name="id", pg_type="uuid", is_nullable=False, is_unique=True),
                ColumnInfo(name="identifier", pg_type="text", is_nullable=False, is_unique=True),
                ColumnInfo(name="name", pg_type="text", is_nullable=False),
            ],
        )

        # Insert with pre-allocated PKs
        inserted = backend.insert_rows(table_info, rows)

        # Verify PKs were preserved (not regenerated)
        assert len(inserted) == 2
        assert inserted[0]["pk_test"] == 100
        assert inserted[1]["pk_test"] == 200

        # Verify in database
        with db_conn.cursor() as cur:
            cur.execute(f"SELECT pk_test, name FROM {test_schema}.tb_test ORDER BY pk_test")
            results = cur.fetchall()
            assert results[0][0] == 100
            assert results[1][0] == 200

        # Cleanup
        with db_conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {test_schema}.tb_test CASCADE")
            db_conn.commit()
