"""Tests for SeedBuilder.seed_all() auto-discovery."""

from fraiseql_data import SeedBuilder
from fraiseql_data.models import ColumnInfo, ForeignKeyInfo, TableInfo


def _parent_table():
    return TableInfo(
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


def _child_table():
    return TableInfo(
        name="tb_child",
        columns=[
            ColumnInfo(
                name="pk_child",
                pg_type="integer",
                is_nullable=False,
                is_primary_key=True,
                is_identity=True,
            ),
            ColumnInfo(name="title", pg_type="text", is_nullable=False),
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


def _standalone_table():
    return TableInfo(
        name="tb_standalone",
        columns=[
            ColumnInfo(
                name="pk_standalone",
                pg_type="integer",
                is_nullable=False,
                is_primary_key=True,
                is_identity=True,
            ),
            ColumnInfo(name="value", pg_type="text", is_nullable=False),
        ],
    )


class TestSeedAllBasic:
    def test_seeds_all_tables(self):
        builder = SeedBuilder(None, schema="test", backend="staging")
        builder.set_table_schema("tb_parent", _parent_table())
        builder.set_table_schema("tb_child", _child_table())

        seeds = builder.seed_all(default_count=3)

        assert "tb_parent" in seeds
        assert "tb_child" in seeds
        assert len(seeds["tb_parent"]) == 3
        assert len(seeds["tb_child"]) == 3

    def test_default_count(self):
        builder = SeedBuilder(None, schema="test", backend="staging")
        builder.set_table_schema("tb_parent", _parent_table())

        seeds = builder.seed_all(default_count=7)

        assert len(seeds["tb_parent"]) == 7


class TestSeedAllCustomCounts:
    def test_per_table_counts(self):
        builder = SeedBuilder(None, schema="test", backend="staging")
        builder.set_table_schema("tb_parent", _parent_table())
        builder.set_table_schema("tb_standalone", _standalone_table())

        seeds = builder.seed_all(
            default_count=2,
            counts={"tb_parent": 10},
        )

        assert len(seeds["tb_parent"]) == 10
        assert len(seeds["tb_standalone"]) == 2


class TestSeedAllOverrides:
    def test_per_table_overrides(self):
        builder = SeedBuilder(None, schema="test", backend="staging")
        builder.set_table_schema("tb_parent", _parent_table())

        seeds = builder.seed_all(
            default_count=3,
            overrides={"tb_parent": {"name": "Fixed Name"}},
        )

        for row in seeds["tb_parent"]:
            assert row.name == "Fixed Name"


class TestSeedAllExclude:
    def test_excluded_tables_skipped(self):
        builder = SeedBuilder(None, schema="test", backend="staging")
        builder.set_table_schema("tb_parent", _parent_table())
        builder.set_table_schema("tb_standalone", _standalone_table())

        seeds = builder.seed_all(
            default_count=3,
            exclude={"tb_standalone"},
        )

        assert "tb_parent" in seeds
        assert "tb_standalone" not in seeds

    def test_exclude_as_list(self):
        builder = SeedBuilder(None, schema="test", backend="staging")
        builder.set_table_schema("tb_parent", _parent_table())
        builder.set_table_schema("tb_standalone", _standalone_table())

        seeds = builder.seed_all(
            default_count=3,
            exclude=["tb_standalone"],
        )

        assert "tb_standalone" not in seeds


class TestSeedAllFKOrder:
    def test_respects_fk_order(self):
        builder = SeedBuilder(None, schema="test", backend="staging")
        builder.set_table_schema("tb_parent", _parent_table())
        builder.set_table_schema("tb_child", _child_table())

        seeds = builder.seed_all(default_count=5)

        # Child FK values should reference generated parent PKs
        parent_pks = {row.pk_parent for row in seeds["tb_parent"]}
        for row in seeds["tb_child"]:
            assert row.fk_parent in parent_pks


class TestSeedAllCrossSchemaFK:
    def test_nullable_cross_schema_fk_empty_table(self):
        """Cross-schema FK on nullable column with no parent rows."""
        table = TableInfo(
            name="tb_local",
            columns=[
                ColumnInfo(
                    name="pk_local",
                    pg_type="integer",
                    is_nullable=False,
                    is_primary_key=True,
                    is_identity=True,
                ),
                ColumnInfo(name="name", pg_type="text", is_nullable=False),
                ColumnInfo(
                    name="fk_external",
                    pg_type="integer",
                    is_nullable=True,
                ),
            ],
            foreign_keys=[
                ForeignKeyInfo(
                    column="fk_external",
                    referenced_table="tb_remote",
                    referenced_column="pk_remote",
                    referenced_schema="other_schema",
                ),
            ],
        )

        builder = SeedBuilder(None, schema="test", backend="staging")
        builder.set_table_schema("tb_local", table)

        # Cross-schema FK on staging backend with nullable column:
        # should work if we override the FK to None
        seeds = builder.seed_all(
            default_count=3,
            overrides={"tb_local": {"fk_external": None}},
        )

        assert len(seeds["tb_local"]) == 3
        for row in seeds["tb_local"]:
            assert row.fk_external is None
