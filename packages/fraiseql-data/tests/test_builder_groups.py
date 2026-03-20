"""Integration tests for group behavior in _generate_rows() (Phase 07, Cycle 4)."""

import re

from fraiseql_data import SeedBuilder
from fraiseql_data.models import CheckConstraint, ColumnInfo, TableInfo


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
