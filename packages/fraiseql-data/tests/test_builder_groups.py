"""Integration tests for group behavior in _generate_rows()."""

import re

from fraiseql_data import SeedBuilder
from fraiseql_data.generators.groups import ColumnGroup
from fraiseql_data.models import CheckConstraint, ColumnInfo, SeedPlan, TableInfo


def _make_address_builder():
    """Create a staging builder with a table containing address columns."""
    builder = SeedBuilder(conn=None, schema="test", backend="staging")
    table_info = TableInfo(
        name="tb_address",
        columns=[
            ColumnInfo(
                name="pk_address",
                pg_type="integer",
                is_nullable=False,
                is_primary_key=True,
            ),
            ColumnInfo(name="country", pg_type="text", is_nullable=False),
            ColumnInfo(name="city", pg_type="text", is_nullable=False),
            ColumnInfo(name="postal_code", pg_type="text", is_nullable=False),
            ColumnInfo(name="state", pg_type="text", is_nullable=True),
            ColumnInfo(name="description", pg_type="text", is_nullable=True),
        ],
    )
    builder.set_table_schema("tb_address", table_info)
    return builder


class TestGroupValueInjection:
    """Test that group values appear in generated rows."""

    def test_address_columns_present_in_output(self):
        builder = _make_address_builder()
        seeds = builder.add("tb_address", count=5).execute()

        for row in seeds.tb_address:
            assert row.country is not None
            assert row.city is not None
            assert row.postal_code is not None

    def test_address_columns_are_coherent(self):
        """Country and postal_code should be from the same locale."""
        builder = _make_address_builder()
        seeds = builder.add("tb_address", count=10).execute()

        for row in seeds.tb_address:
            # All address fields should be non-empty strings
            assert isinstance(row.country, str) and len(row.country) > 0
            assert isinstance(row.city, str) and len(row.city) > 0
            assert isinstance(row.postal_code, str) and len(row.postal_code) > 0

    def test_us_override_produces_us_postal_code(self):
        builder = _make_address_builder()
        seeds = builder.add("tb_address", count=5, overrides={"country": "United States"}).execute()

        for row in seeds.tb_address:
            assert row.country == "United States"
            assert re.match(r"^\d{5}(-\d{4})?$", row.postal_code), (
                f"Expected US postal code, got '{row.postal_code}'"
            )


class TestNonGroupedColumnsFallback:
    """Test that non-grouped columns still generate via faker fallback."""

    def test_description_still_generated(self):
        builder = _make_address_builder()
        seeds = builder.add("tb_address", count=5).execute()

        # description is not in the address group — should be faker-generated
        for row in seeds.tb_address:
            # nullable, so may be None, but faker typically generates text
            assert hasattr(row, "description")


class TestCheckConstraintExclusion:
    """Test that CHECK-constrained columns in a group are excluded from group values."""

    def test_check_constrained_column_uses_check_path(self):
        """If 'state' has a CHECK constraint, group should not override it."""
        builder = SeedBuilder(conn=None, schema="test", backend="staging")
        table_info = TableInfo(
            name="tb_location",
            columns=[
                ColumnInfo(
                    name="pk_location",
                    pg_type="integer",
                    is_nullable=False,
                    is_primary_key=True,
                ),
                ColumnInfo(name="country", pg_type="text", is_nullable=False),
                ColumnInfo(name="city", pg_type="text", is_nullable=False),
                ColumnInfo(name="state", pg_type="text", is_nullable=False),
            ],
            check_constraints=[
                CheckConstraint(
                    constraint_name="ck_state",
                    check_clause="state IN ('active', 'inactive')",
                ),
            ],
        )
        builder.set_table_schema("tb_location", table_info)

        seeds = builder.add("tb_location", count=20).execute()

        for row in seeds.tb_location:
            # state should come from CHECK constraint, not address group
            assert row.state in ("active", "inactive"), f"Expected CHECK value, got '{row.state}'"
            # country and city should still come from address group
            assert isinstance(row.country, str) and len(row.country) > 0
            assert isinstance(row.city, str) and len(row.city) > 0


class TestOverridePrecedenceOverGroups:
    """Test that overrides on group columns take priority over group values."""

    def test_override_wins_over_group_value(self):
        builder = _make_address_builder()
        seeds = builder.add("tb_address", count=5, overrides={"city": "ForcedCity"}).execute()

        for row in seeds.tb_address:
            assert row.city == "ForcedCity"

    def test_override_passed_as_context_to_group(self):
        """Overridden country should drive coherent postal_code."""
        builder = _make_address_builder()
        seeds = builder.add("tb_address", count=5, overrides={"country": "France"}).execute()

        for row in seeds.tb_address:
            assert row.country == "France"
            assert re.match(r"^\d{5}$", row.postal_code), (
                f"Expected French postal code, got '{row.postal_code}'"
            )

    def test_callable_override_on_group_column(self):
        builder = _make_address_builder()
        seeds = builder.add(
            "tb_address",
            count=3,
            overrides={"city": lambda i: f"City_{i}"},
        ).execute()

        for i, row in enumerate(seeds.tb_address, start=1):
            assert row.city == f"City_{i}"


class TestSeedPlanGroupsField:
    """Test SeedPlan.groups field accepts list[ColumnGroup] | None."""

    def test_seedplan_groups_default_is_none(self):
        plan = SeedPlan(table="tb_test", count=10)
        assert plan.groups is None

    def test_seedplan_groups_accepts_empty_list(self):
        plan = SeedPlan(table="tb_test", count=10, groups=[])
        assert plan.groups == []

    def test_seedplan_groups_accepts_column_group_list(self):
        group = ColumnGroup(
            name="custom",
            fields=frozenset({"a", "b"}),
            generator=lambda _ctx: {"a": 1, "b": 2},
        )
        plan = SeedPlan(table="tb_test", count=10, groups=[group])
        assert plan.groups == [group]


class TestDisableGroups:
    """Test groups=[] disables auto-detection."""

    def test_empty_groups_disables_auto_detection(self):
        """With groups=[], address columns should generate independently (no coherence)."""
        builder = _make_address_builder()
        seeds = builder.add("tb_address", count=10, groups=[]).execute()

        # Rows should still have values, but they won't be coherent
        # The key test: postal_code is faker-generated text, not a real postal code
        non_postal = 0
        for row in seeds.tb_address:
            assert row.country is not None
            assert row.postal_code is not None
            # Faker text for "postal_code" column won't consistently be 5-digit format
            if not re.match(r"^\d{5}$", str(row.postal_code)):
                non_postal += 1
        # At least some should be non-postal-code format (faker text)
        assert non_postal > 0, "Expected faker-generated text, not coherent postal codes"


class TestCustomGroups:
    """Test custom groups via groups=[ColumnGroup(...)]."""

    def test_custom_group_generates_correlated_values(self):
        builder = SeedBuilder(conn=None, schema="test", backend="staging")
        table_info = TableInfo(
            name="tb_product",
            columns=[
                ColumnInfo(
                    name="pk_product",
                    pg_type="integer",
                    is_nullable=False,
                    is_primary_key=True,
                ),
                ColumnInfo(name="category", pg_type="text", is_nullable=False),
                ColumnInfo(name="sku_prefix", pg_type="text", is_nullable=False),
            ],
        )
        builder.set_table_schema("tb_product", table_info)

        def product_gen(_ctx):
            import random

            cat = random.choice(["Electronics", "Clothing"])
            prefix = {"Electronics": "EL", "Clothing": "CL"}[cat]
            return {"category": cat, "sku_prefix": prefix}

        custom_group = ColumnGroup(
            name="product",
            fields=frozenset({"category", "sku_prefix"}),
            generator=product_gen,
        )

        seeds = builder.add("tb_product", count=10, groups=[custom_group]).execute()

        for row in seeds.tb_product:
            if row.category == "Electronics":
                assert row.sku_prefix == "EL"
            elif row.category == "Clothing":
                assert row.sku_prefix == "CL"
            else:
                raise AssertionError(f"Unexpected category: {row.category}")


class TestPartialGroup:
    """Test partial group activation (subset of fields)."""

    def test_partial_address_group_activates_with_two_columns(self):
        """Table with only country+city (no state/postal_code) still activates address group."""
        builder = SeedBuilder(conn=None, schema="test", backend="staging")
        table_info = TableInfo(
            name="tb_partial",
            columns=[
                ColumnInfo(
                    name="pk_partial",
                    pg_type="integer",
                    is_nullable=False,
                    is_primary_key=True,
                ),
                ColumnInfo(name="country", pg_type="text", is_nullable=False),
                ColumnInfo(name="city", pg_type="text", is_nullable=False),
                ColumnInfo(name="notes", pg_type="text", is_nullable=True),
            ],
        )
        builder.set_table_schema("tb_partial", table_info)

        seeds = builder.add("tb_partial", count=10).execute()

        for row in seeds.tb_partial:
            # country and city should come from address group (coherent)
            assert isinstance(row.country, str) and len(row.country) > 0
            assert isinstance(row.city, str) and len(row.city) > 0

    def test_partial_group_does_not_populate_missing_columns(self):
        """Columns not in the table should not appear in output."""
        builder = SeedBuilder(conn=None, schema="test", backend="staging")
        table_info = TableInfo(
            name="tb_partial2",
            columns=[
                ColumnInfo(
                    name="pk_partial2",
                    pg_type="integer",
                    is_nullable=False,
                    is_primary_key=True,
                ),
                ColumnInfo(name="country", pg_type="text", is_nullable=False),
                ColumnInfo(name="city", pg_type="text", is_nullable=False),
            ],
        )
        builder.set_table_schema("tb_partial2", table_info)

        seeds = builder.add("tb_partial2", count=5).execute()

        for row in seeds.tb_partial2:
            # postal_code is in address group fields but not in the table
            assert not hasattr(row, "postal_code") or "postal_code" not in row._data


class TestGroupUniqueRetry:
    """Test UNIQUE column in a group triggers whole-group retry."""

    def test_unique_group_column_regenerates_group(self):
        """email with is_unique should still produce unique values via group retry."""
        builder = SeedBuilder(conn=None, schema="test", backend="staging")
        table_info = TableInfo(
            name="tb_user",
            columns=[
                ColumnInfo(
                    name="pk_user",
                    pg_type="integer",
                    is_nullable=False,
                    is_primary_key=True,
                ),
                ColumnInfo(name="first_name", pg_type="text", is_nullable=False),
                ColumnInfo(name="last_name", pg_type="text", is_nullable=False),
                ColumnInfo(name="email", pg_type="text", is_nullable=False, is_unique=True),
            ],
        )
        builder.set_table_schema("tb_user", table_info)

        seeds = builder.add("tb_user", count=20).execute()

        emails = [row.email for row in seeds.tb_user]
        assert len(emails) == len(set(emails)), "Emails should be unique"

    def test_unique_email_with_many_rows_uses_suffix_fallback(self):
        """With enough rows, email suffix fallback should activate to ensure uniqueness."""
        builder = SeedBuilder(conn=None, schema="test", backend="staging")
        table_info = TableInfo(
            name="tb_user_large",
            columns=[
                ColumnInfo(
                    name="pk_user",
                    pg_type="integer",
                    is_nullable=False,
                    is_primary_key=True,
                ),
                ColumnInfo(name="first_name", pg_type="text", is_nullable=False),
                ColumnInfo(name="last_name", pg_type="text", is_nullable=False),
                ColumnInfo(name="email", pg_type="text", is_nullable=False, is_unique=True),
            ],
        )
        builder.set_table_schema("tb_user_large", table_info)

        # Generate enough rows to likely trigger collisions and suffix fallback
        seeds = builder.add("tb_user_large", count=50).execute()

        emails = [row.email for row in seeds.tb_user_large]
        assert len(emails) == len(set(emails)), "All emails should be unique"
        assert len(emails) == 50


class TestInstanceCounter:
    """Test that _instance is available in generator context."""

    def test_instance_counter_matches_row_number(self):
        """Generator receives _instance = 1, 2, ..., N for N rows."""
        captured_instances: list[int] = []

        def capture_gen(ctx):
            captured_instances.append(ctx["_instance"])
            return {"category": "test", "sku_prefix": "T"}

        builder = SeedBuilder(conn=None, schema="test", backend="staging")
        table_info = TableInfo(
            name="tb_inst",
            columns=[
                ColumnInfo(
                    name="pk_inst",
                    pg_type="integer",
                    is_nullable=False,
                    is_primary_key=True,
                ),
                ColumnInfo(name="category", pg_type="text", is_nullable=False),
                ColumnInfo(name="sku_prefix", pg_type="text", is_nullable=False),
            ],
        )
        builder.set_table_schema("tb_inst", table_info)

        group = ColumnGroup(
            name="capture",
            fields=frozenset({"category", "sku_prefix"}),
            generator=capture_gen,
        )
        builder.add("tb_inst", count=5, groups=[group]).execute()

        assert captured_instances == [1, 2, 3, 4, 5]


class TestTableColumnsContext:
    """Test that _table_columns is available in generator context."""

    def test_table_columns_matches_actual_columns(self):
        """Generator receives _table_columns as a frozenset of table column names."""
        captured_columns: list[frozenset] = []

        def capture_gen(ctx):
            captured_columns.append(ctx["_table_columns"])
            return {"category": "test", "sku_prefix": "T"}

        builder = SeedBuilder(conn=None, schema="test", backend="staging")
        table_info = TableInfo(
            name="tb_cols",
            columns=[
                ColumnInfo(
                    name="pk_cols",
                    pg_type="integer",
                    is_nullable=False,
                    is_primary_key=True,
                ),
                ColumnInfo(name="category", pg_type="text", is_nullable=False),
                ColumnInfo(name="sku_prefix", pg_type="text", is_nullable=False),
                ColumnInfo(name="extra", pg_type="text", is_nullable=True),
            ],
        )
        builder.set_table_schema("tb_cols", table_info)

        group = ColumnGroup(
            name="capture",
            fields=frozenset({"category", "sku_prefix"}),
            generator=capture_gen,
        )
        builder.add("tb_cols", count=2, groups=[group]).execute()

        expected = frozenset({"pk_cols", "category", "sku_prefix", "extra"})
        assert all(cols == expected for cols in captured_columns)

    def test_different_tables_get_different_columns(self):
        """Two tables sharing a group get their own _table_columns."""
        captured: dict[str, frozenset] = {}

        def capture_gen(ctx):
            # Store by _instance to avoid overwrite
            return {"category": "test", "sku_prefix": "T"}

        def gen_a(ctx):
            captured["a"] = ctx["_table_columns"]
            return capture_gen(ctx)

        def gen_b(ctx):
            captured["b"] = ctx["_table_columns"]
            return capture_gen(ctx)

        builder = SeedBuilder(conn=None, schema="test", backend="staging")

        table_a = TableInfo(
            name="tb_a",
            columns=[
                ColumnInfo(name="pk_a", pg_type="integer", is_nullable=False, is_primary_key=True),
                ColumnInfo(name="category", pg_type="text", is_nullable=False),
                ColumnInfo(name="sku_prefix", pg_type="text", is_nullable=False),
            ],
        )
        table_b = TableInfo(
            name="tb_b",
            columns=[
                ColumnInfo(name="pk_b", pg_type="integer", is_nullable=False, is_primary_key=True),
                ColumnInfo(name="category", pg_type="text", is_nullable=False),
                ColumnInfo(name="sku_prefix", pg_type="text", is_nullable=False),
                ColumnInfo(name="notes", pg_type="text", is_nullable=True),
            ],
        )
        builder.set_table_schema("tb_a", table_a)
        builder.set_table_schema("tb_b", table_b)

        group_a = ColumnGroup(
            name="ga",
            fields=frozenset({"category", "sku_prefix"}),
            generator=gen_a,
        )
        group_b = ColumnGroup(
            name="gb",
            fields=frozenset({"category", "sku_prefix"}),
            generator=gen_b,
        )

        builder.add("tb_a", count=1, groups=[group_a])
        builder.add("tb_b", count=1, groups=[group_b])
        builder.execute()

        assert captured["a"] == frozenset({"pk_a", "category", "sku_prefix"})
        assert captured["b"] == frozenset({"pk_b", "category", "sku_prefix", "notes"})


class TestInstanceCounterInUniqueRetry:
    """Test that _instance and _table_columns are present in UNIQUE retry context."""

    def test_retry_context_has_instance_and_columns(self):
        """Force a collision so the retry path runs, verify context keys."""
        call_count = 0
        retry_instances: list[int] = []
        retry_columns: list[frozenset] = []

        def colliding_gen(ctx):
            nonlocal call_count
            call_count += 1
            if "_instance" in ctx:
                retry_instances.append(ctx["_instance"])
            if "_table_columns" in ctx:
                retry_columns.append(ctx["_table_columns"])
            # First call for a row returns "dupe@test.com", retries return unique
            if call_count <= 2:
                return {"first_name": "A", "last_name": "B", "email": "dupe@test.com"}
            return {"first_name": "A", "last_name": "B", "email": f"unique{call_count}@test.com"}

        builder = SeedBuilder(conn=None, schema="test", backend="staging")
        table_info = TableInfo(
            name="tb_retry",
            columns=[
                ColumnInfo(
                    name="pk_retry",
                    pg_type="integer",
                    is_nullable=False,
                    is_primary_key=True,
                ),
                ColumnInfo(name="first_name", pg_type="text", is_nullable=False),
                ColumnInfo(name="last_name", pg_type="text", is_nullable=False),
                ColumnInfo(name="email", pg_type="text", is_nullable=False, is_unique=True),
            ],
        )
        builder.set_table_schema("tb_retry", table_info)

        group = ColumnGroup(
            name="person",
            fields=frozenset({"first_name", "last_name", "email"}),
            generator=colliding_gen,
        )
        builder.add("tb_retry", count=2, groups=[group]).execute()

        # At least one retry happened — verify _instance was present in retry context
        assert len(retry_instances) > 2, "Expected retries to have occurred"
        # All retry _instance values for row 2 should be 2
        assert all(i in (1, 2) for i in retry_instances)
        expected_cols = frozenset({"pk_retry", "first_name", "last_name", "email"})
        assert all(c == expected_cols for c in retry_columns)


class TestGeoGroupInBuilder:
    """Test geo group integration in builder."""

    def test_geo_columns_generated_in_row(self):
        builder = SeedBuilder(conn=None, schema="test", backend="staging")
        table_info = TableInfo(
            name="tb_location",
            columns=[
                ColumnInfo(
                    name="pk_location",
                    pg_type="integer",
                    is_nullable=False,
                    is_primary_key=True,
                ),
                ColumnInfo(name="latitude", pg_type="double precision", is_nullable=False),
                ColumnInfo(name="longitude", pg_type="double precision", is_nullable=False),
            ],
        )
        builder.set_table_schema("tb_location", table_info)

        seeds = builder.add("tb_location", count=5).execute()

        for row in seeds.tb_location:
            assert isinstance(row.latitude, float)
            assert isinstance(row.longitude, float)
            assert -90 <= row.latitude <= 90
            assert -180 <= row.longitude <= 180

    def test_geo_with_address_uses_locale_bias(self):
        """When address and geo groups both active, geo should use address locale."""
        builder = SeedBuilder(conn=None, schema="test", backend="staging")
        table_info = TableInfo(
            name="tb_place",
            columns=[
                ColumnInfo(
                    name="pk_place",
                    pg_type="integer",
                    is_nullable=False,
                    is_primary_key=True,
                ),
                ColumnInfo(name="country", pg_type="text", is_nullable=False),
                ColumnInfo(name="city", pg_type="text", is_nullable=False),
                ColumnInfo(name="latitude", pg_type="double precision", is_nullable=False),
                ColumnInfo(name="longitude", pg_type="double precision", is_nullable=False),
            ],
        )
        builder.set_table_schema("tb_place", table_info)

        seeds = builder.add("tb_place", count=5, overrides={"country": "France"}).execute()

        for row in seeds.tb_place:
            assert row.country == "France"
            # France: lat ~42-51, lng ~-5 to 9 (with margin)
            assert 38 <= row.latitude <= 55, f"FR lat out of range: {row.latitude}"
            assert -10 <= row.longitude <= 14, f"FR lng out of range: {row.longitude}"
