"""Tests for ColumnGroup model and GroupRegistry (Phase 07, Cycle 1 RED)."""

from fraiseql_data.generators.groups import ColumnGroup, GroupRegistry


class TestColumnGroupDataclass:
    """Test ColumnGroup dataclass creation and defaults."""

    def test_create_with_all_fields(self):
        def gen(ctx):
            return {"a": 1}

        group = ColumnGroup(
            name="test",
            fields=frozenset({"a", "b", "c"}),
            generator=gen,
            min_match=3,
        )
        assert group.name == "test"
        assert group.fields == frozenset({"a", "b", "c"})
        assert group.generator is gen
        assert group.min_match == 3

    def test_default_min_match_is_two(self):
        group = ColumnGroup(
            name="test",
            fields=frozenset({"x", "y"}),
            generator=lambda _ctx: {},
        )
        assert group.min_match == 2

    def test_generator_receives_context_and_returns_dict(self):
        def gen(ctx):
            return {"col": ctx.get("key", "default")}

        group = ColumnGroup(
            name="ctx_test",
            fields=frozenset({"col"}),
            generator=gen,
        )
        result = group.generator({"key": "value"})
        assert result == {"col": "value"}

    def test_generator_with_empty_context(self):
        def gen(ctx):
            return {"col": "fallback"}

        group = ColumnGroup(
            name="empty_ctx",
            fields=frozenset({"col"}),
            generator=gen,
        )
        result = group.generator({})
        assert result == {"col": "fallback"}

    def test_fields_is_frozenset(self):
        group = ColumnGroup(
            name="frozen",
            fields=frozenset({"a", "b"}),
            generator=lambda _ctx: {},
        )
        assert isinstance(group.fields, frozenset)


class TestGroupRegistryDetection:
    """Test GroupRegistry.detect_groups() activation logic."""

    def test_address_group_activates_with_two_matching_columns(self):
        registry = GroupRegistry()
        groups = registry.detect_groups({"country", "city", "unrelated"})
        group_names = [g.name for g in groups]
        assert "address" in group_names

    def test_person_group_activates_with_two_matching_columns(self):
        registry = GroupRegistry()
        groups = registry.detect_groups({"first_name", "last_name", "unrelated"})
        group_names = [g.name for g in groups]
        assert "person" in group_names

    def test_geo_group_activates_with_two_matching_columns(self):
        registry = GroupRegistry()
        groups = registry.detect_groups({"latitude", "longitude"})
        group_names = [g.name for g in groups]
        assert "geo" in group_names

    def test_no_group_activates_below_min_match(self):
        registry = GroupRegistry()
        # Single column from each group — none should activate
        groups = registry.detect_groups({"city", "first_name", "latitude"})
        assert groups == []

    def test_no_group_activates_with_unrelated_columns(self):
        registry = GroupRegistry()
        groups = registry.detect_groups({"price", "quantity", "sku"})
        assert groups == []

    def test_multiple_groups_activate_simultaneously(self):
        registry = GroupRegistry()
        groups = registry.detect_groups(
            {
                "country",
                "city",  # address
                "first_name",
                "last_name",  # person
                "latitude",
                "longitude",  # geo
            }
        )
        group_names = [g.name for g in groups]
        assert "address" in group_names
        assert "person" in group_names
        assert "geo" in group_names

    def test_execution_order_address_before_person_before_geo(self):
        registry = GroupRegistry()
        groups = registry.detect_groups(
            {
                "latitude",
                "longitude",  # geo (listed first)
                "first_name",
                "last_name",  # person (listed second)
                "country",
                "city",  # address (listed third)
            }
        )
        group_names = [g.name for g in groups]
        assert group_names == ["address", "person", "geo"]

    def test_col_to_group_reverse_lookup(self):
        registry = GroupRegistry()
        groups = registry.detect_groups({"country", "city", "first_name", "last_name"})
        col_to_group = registry.col_to_group(groups, {"country", "city", "first_name", "last_name"})
        assert col_to_group["country"].name == "address"
        assert col_to_group["city"].name == "address"
        assert col_to_group["first_name"].name == "person"
        assert col_to_group["last_name"].name == "person"

    def test_col_to_group_only_includes_existing_columns(self):
        registry = GroupRegistry()
        groups = registry.detect_groups({"country", "city"})
        col_to_group = registry.col_to_group(groups, {"country", "city"})
        # street is in address group fields but not in table columns
        assert "street" not in col_to_group
        assert "country" in col_to_group
        assert "city" in col_to_group
