"""Tests for SeedBuilder.validate() pre-execution validation."""

from fraiseql_data import SeedBuilder, ValidationResult
from fraiseql_data.models import ColumnInfo, ForeignKeyInfo, TableInfo


def _make_builder_with_tables(*table_infos: TableInfo) -> SeedBuilder:
    """Create a staging builder with pre-registered table schemas."""
    builder = SeedBuilder(None, schema="test", backend="staging")
    for t in table_infos:
        builder.set_table_schema(t.name, t)
    return builder


PARENT = TableInfo(
    name="tb_parent",
    columns=[
        ColumnInfo(
            name="pk_parent",
            pg_type="integer",
            is_nullable=False,
            is_primary_key=True,
            is_identity=True,
        ),
        ColumnInfo(name="name", pg_type="text", is_nullable=False),
    ],
)

CHILD = TableInfo(
    name="tb_child",
    columns=[
        ColumnInfo(
            name="pk_child",
            pg_type="integer",
            is_nullable=False,
            is_primary_key=True,
            is_identity=True,
        ),
        ColumnInfo(name="name", pg_type="text", is_nullable=False),
        ColumnInfo(name="fk_parent", pg_type="integer", is_nullable=False),
    ],
    foreign_keys=[
        ForeignKeyInfo(
            column="fk_parent",
            referenced_table="tb_parent",
            referenced_column="pk_parent",
        ),
    ],
)


class TestValidateValidPlan:
    def test_valid_plan_returns_is_valid(self):
        builder = _make_builder_with_tables(PARENT, CHILD)
        builder.add("tb_parent", count=5)
        builder.add("tb_child", count=10)

        result = builder.validate()

        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
        assert result.errors == []

    def test_plan_summary_has_all_tables(self):
        builder = _make_builder_with_tables(PARENT, CHILD)
        builder.add("tb_parent", count=5)
        builder.add("tb_child", count=10)

        result = builder.validate()

        tables_in_summary = [s["table"] for s in result.plan_summary]
        assert "tb_parent" in tables_in_summary
        assert "tb_child" in tables_in_summary

    def test_plan_summary_sorted_by_deps(self):
        builder = _make_builder_with_tables(PARENT, CHILD)
        # Add child before parent — summary should still be sorted
        builder.add("tb_child", count=10)
        builder.add("tb_parent", count=5)

        result = builder.validate()

        tables_in_summary = [s["table"] for s in result.plan_summary]
        assert tables_in_summary.index("tb_parent") < tables_in_summary.index("tb_child")

    def test_plan_summary_includes_count_and_strategy(self):
        builder = _make_builder_with_tables(PARENT)
        builder.add("tb_parent", count=7)

        result = builder.validate()

        assert result.plan_summary[0] == {
            "table": "tb_parent",
            "count": 7,
            "strategy": "faker",
        }


class TestValidateMissingDependency:
    def test_missing_dep_returns_error(self):
        builder = _make_builder_with_tables(PARENT, CHILD)
        # Add child without parent
        builder.add("tb_child", count=10)

        result = builder.validate()

        assert result.is_valid is False
        assert len(result.errors) == 1
        assert "tb_parent" in result.errors[0]

    def test_overridden_fk_passes_validation(self):
        builder = _make_builder_with_tables(PARENT, CHILD)
        builder.add("tb_child", count=10, overrides={"fk_parent": 1})

        result = builder.validate()

        assert result.is_valid is True
        assert result.errors == []


class TestValidateEmptyPlan:
    def test_empty_plan_is_valid(self):
        builder = _make_builder_with_tables(PARENT)
        result = builder.validate()

        assert result.is_valid is True
        assert result.errors == []
        assert result.plan_summary == []


class TestValidateSingleTable:
    def test_single_table_no_deps(self):
        builder = _make_builder_with_tables(PARENT)
        builder.add("tb_parent", count=3)

        result = builder.validate()

        assert result.is_valid is True
        assert len(result.plan_summary) == 1
