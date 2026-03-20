"""Tests for relaxed dependency validation.

validate_plan() should skip MissingDependencyError when all FK columns
referencing a missing table have overrides.
"""

import pytest
from fraiseql_data import SeedBuilder
from fraiseql_data.dependency import DependencyGraph
from fraiseql_data.exceptions import MissingDependencyError
from fraiseql_data.models import (
    ColumnInfo,
    ForeignKeyInfo,
    TableInfo,
)
from psycopg import Connection


class TestValidatePlanWithOverrides:
    """validate_plan accepts overridden deps."""

    def test_overridden_fk_skips_missing_dep(self):
        """Single FK column to missing dep is overridden — no error."""
        graph = DependencyGraph()
        graph.add_table("tb_child")
        graph.add_dependency("tb_child", "tb_parent", fk_column="fk_parent")

        # tb_parent is NOT in the plan, but fk_parent is overridden
        graph.validate_plan(
            tables=["tb_child"],
            overridden_fks={"tb_child": {"fk_parent"}},
        )
        # Should not raise

    def test_non_overridden_fk_still_raises(self):
        """FK column to missing dep is NOT overridden — MissingDependencyError."""
        graph = DependencyGraph()
        graph.add_table("tb_child")
        graph.add_dependency("tb_child", "tb_parent", fk_column="fk_parent")

        with pytest.raises(MissingDependencyError):
            graph.validate_plan(tables=["tb_child"])

    def test_no_overrides_backward_compatible(self):
        """Without overrides, behaviour is unchanged (all deps present)."""
        graph = DependencyGraph()
        graph.add_table("tb_child")
        graph.add_table("tb_parent")
        graph.add_dependency("tb_child", "tb_parent", fk_column="fk_parent")

        # Both tables in plan — should pass regardless of overrides
        graph.validate_plan(tables=["tb_child", "tb_parent"])


class TestPartialOverridesStillFail:
    """Partial overrides still raise."""

    def test_partial_override_raises(self):
        """Table has 2 FK columns to same dep, only 1 overridden — error."""
        graph = DependencyGraph()
        graph.add_table("tb_child")
        graph.add_dependency("tb_child", "tb_parent", fk_column="fk_parent_a")
        graph.add_dependency("tb_child", "tb_parent", fk_column="fk_parent_b")

        with pytest.raises(MissingDependencyError):
            graph.validate_plan(
                tables=["tb_child"],
                overridden_fks={"tb_child": {"fk_parent_a"}},
            )

    def test_all_multi_fk_overridden_passes(self):
        """Table has 2 FK columns to same dep, both overridden — no error."""
        graph = DependencyGraph()
        graph.add_table("tb_child")
        graph.add_dependency("tb_child", "tb_parent", fk_column="fk_parent_a")
        graph.add_dependency("tb_child", "tb_parent", fk_column="fk_parent_b")

        graph.validate_plan(
            tables=["tb_child"],
            overridden_fks={"tb_child": {"fk_parent_a", "fk_parent_b"}},
        )


class TestBuilderIntegration:
    """Builder passes overridden_fks to validate_plan."""

    def _make_staging_builder(self):
        """Create a staging builder with parent/child table schemas."""
        builder = SeedBuilder(conn=None, schema="test", backend="staging")

        parent = TableInfo(
            name="tb_parent",
            columns=[
                ColumnInfo(
                    name="pk_parent", pg_type="integer", is_nullable=False, is_primary_key=True
                ),
                ColumnInfo(name="id", pg_type="uuid", is_nullable=False, is_unique=True),
                ColumnInfo(name="identifier", pg_type="text", is_nullable=False, is_unique=True),
                ColumnInfo(name="name", pg_type="text", is_nullable=False),
            ],
        )
        child = TableInfo(
            name="tb_child",
            columns=[
                ColumnInfo(
                    name="pk_child", pg_type="integer", is_nullable=False, is_primary_key=True
                ),
                ColumnInfo(name="id", pg_type="uuid", is_nullable=False, is_unique=True),
                ColumnInfo(name="identifier", pg_type="text", is_nullable=False, is_unique=True),
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
        builder.set_table_schema("tb_parent", parent)
        builder.set_table_schema("tb_child", child)
        return builder

    def test_builder_execute_with_overridden_fk(self):
        """Builder.execute() should not raise when FK column has override."""
        builder = self._make_staging_builder()
        # Add only tb_child, NOT tb_parent.
        # Override fk_parent so the missing dep is satisfied.
        builder.add("tb_child", count=3, overrides={"fk_parent": 42})

        seeds = builder.execute()
        assert len(seeds.tb_child) == 3
        for row in seeds.tb_child:
            assert row.fk_parent == 42

    def test_builder_execute_without_override_still_raises(self):
        """Builder.execute() should still raise when FK is not overridden."""
        builder = self._make_staging_builder()
        builder.add("tb_child", count=3)

        with pytest.raises(MissingDependencyError):
            builder.execute()


class TestCrossBuilderEndToEnd:
    """End-to-end cross-builder seeding with override priority and relaxed validation."""

    def test_cross_builder_seeding(self, db_conn: Connection, test_schema: str):
        """Seed parent with builder A, then child with builder B using overrides."""
        # Builder A: seed parent table
        builder_a = SeedBuilder(db_conn, schema=test_schema)
        builder_a.add("tb_manufacturer", count=2)
        seeds_a = builder_a.execute()

        # Grab a parent PK to use as override
        parent_pk = seeds_a.tb_manufacturer[0].pk_manufacturer

        # Builder B: seed child table with override referencing existing parent
        builder_b = SeedBuilder(db_conn, schema=test_schema)
        builder_b.add(
            "tb_model",
            count=5,
            overrides={"fk_manufacturer": parent_pk},
        )
        seeds_b = builder_b.execute()

        assert len(seeds_b.tb_model) == 5
        for row in seeds_b.tb_model:
            assert row.fk_manufacturer == parent_pk
