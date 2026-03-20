"""Tests for ColumnGroup model, GroupRegistry, and group generators."""

import re

from fraiseql_data.generators.groups import (
    ColumnGroup,
    GroupRegistry,
    generate_address,
    generate_geo,
    generate_person,
)


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


# -- Cycle 2: Address Group Generator -----------------------------------------

ADDRESS_FIELDS = {
    "country",
    "state",
    "city",
    "postal_code",
    "street",
    "address",
    "zip",
    "zipcode",
    "zip_code",
}


class TestGenerateAddressReturnShape:
    """Test generate_address() returns dict with expected keys."""

    def test_returns_all_address_fields_plus_locale(self):
        result = generate_address({})
        for field in ADDRESS_FIELDS:
            assert field in result, f"Missing field: {field}"
        assert "_locale" in result

    def test_all_values_are_strings(self):
        result = generate_address({})
        for key, value in result.items():
            assert isinstance(value, str), f"{key} is {type(value)}, expected str"

    def test_country_is_nonempty(self):
        result = generate_address({})
        assert len(result["country"]) > 0

    def test_city_is_nonempty(self):
        result = generate_address({})
        assert len(result["city"]) > 0


class TestGenerateAddressCoherence:
    """Test postal_code format is consistent with country."""

    def test_us_postal_code_is_five_digits(self):
        result = generate_address({"country": "United States"})
        assert re.match(r"^\d{5}(-\d{4})?$", result["postal_code"]), (
            f"US postal_code '{result['postal_code']}' doesn't match expected format"
        )

    def test_france_postal_code_is_five_digits(self):
        result = generate_address({"country": "France"})
        assert re.match(r"^\d{5}$", result["postal_code"]), (
            f"FR postal_code '{result['postal_code']}' doesn't match expected format"
        )

    def test_germany_postal_code_is_five_digits(self):
        result = generate_address({"country": "Germany"})
        assert re.match(r"^\d{5}$", result["postal_code"]), (
            f"DE postal_code '{result['postal_code']}' doesn't match expected format"
        )


class TestGenerateAddressOverrideAware:
    """Test that country override drives locale selection."""

    def test_override_country_france_returns_french_locale(self):
        result = generate_address({"country": "France"})
        assert result["_locale"] == "fr_FR"
        assert result["country"] == "France"

    def test_override_country_germany_returns_german_locale(self):
        result = generate_address({"country": "Germany"})
        assert result["_locale"] == "de_DE"
        assert result["country"] == "Germany"

    def test_override_country_us_returns_us_locale(self):
        result = generate_address({"country": "United States"})
        assert result["_locale"] == "en_US"
        assert result["country"] == "United States"

    def test_override_country_japan_returns_japanese_locale(self):
        result = generate_address({"country": "Japan"})
        assert result["_locale"] == "ja_JP"
        assert result["country"] == "Japan"

    def test_unknown_country_falls_back_to_en_us(self):
        result = generate_address({"country": "Narnia"})
        assert result["_locale"] == "en_US"
        assert result["country"] == "Narnia"


class TestGenerateAddressPooling:
    """Test that repeated calls return values efficiently (no errors)."""

    def test_fifty_calls_all_return_valid_dicts(self):
        for _ in range(50):
            result = generate_address({})
            assert isinstance(result, dict)
            assert "country" in result
            assert "_locale" in result

    def test_repeated_calls_produce_variation(self):
        countries = {generate_address({})["country"] for _ in range(30)}
        # With random locale selection, we should see more than 1 country
        assert len(countries) > 1


# -- Cycle 3: Person Group Generator ------------------------------------------

PERSON_FIELDS = {"first_name", "last_name", "name", "email"}


class TestGeneratePersonReturnShape:
    """Test generate_person() returns dict with expected keys."""

    def test_returns_all_person_fields(self):
        result = generate_person({})
        for field in PERSON_FIELDS:
            assert field in result, f"Missing field: {field}"

    def test_all_values_are_strings(self):
        result = generate_person({})
        for key, value in result.items():
            assert isinstance(value, str), f"{key} is {type(value)}, expected str"

    def test_first_name_is_nonempty(self):
        result = generate_person({})
        assert len(result["first_name"]) > 0

    def test_last_name_is_nonempty(self):
        result = generate_person({})
        assert len(result["last_name"]) > 0


class TestGeneratePersonCoherence:
    """Test name and email derive from first_name/last_name."""

    def test_name_is_first_space_last(self):
        result = generate_person({})
        assert result["name"] == f"{result['first_name']} {result['last_name']}"

    def test_email_contains_first_name(self):
        result = generate_person({})
        first_lower = result["first_name"].lower()
        email_local = result["email"].split("@")[0]
        assert first_lower in email_local

    def test_email_contains_last_name(self):
        result = generate_person({})
        last_lower = result["last_name"].lower()
        email_local = result["email"].split("@")[0]
        assert last_lower in email_local

    def test_email_has_at_sign_and_domain(self):
        result = generate_person({})
        assert "@" in result["email"]
        domain = result["email"].split("@")[1]
        assert "." in domain

    def test_email_format_is_first_dot_last_at_domain(self):
        result = generate_person({})
        first_lower = result["first_name"].lower()
        last_lower = result["last_name"].lower()
        expected_local = f"{first_lower}.{last_lower}"
        actual_local = result["email"].split("@")[0]
        assert actual_local == expected_local


class TestGeneratePersonLocaleAware:
    """Test that _locale from context drives name generation locale."""

    def test_french_locale_produces_names(self):
        # Just verify it doesn't error and returns valid structure
        result = generate_person({"_locale": "fr_FR"})
        assert len(result["first_name"]) > 0
        assert len(result["last_name"]) > 0
        assert result["name"] == f"{result['first_name']} {result['last_name']}"

    def test_japanese_locale_produces_names(self):
        result = generate_person({"_locale": "ja_JP"})
        assert len(result["first_name"]) > 0
        assert len(result["last_name"]) > 0

    def test_no_locale_defaults_to_en_us(self):
        # Without _locale, should still work (default locale)
        result = generate_person({})
        assert len(result["first_name"]) > 0


class TestGeneratePersonEmailSuffix:
    """Test _email_suffix context key for UNIQUE retry fallback."""

    def test_email_suffix_appends_number(self):
        result = generate_person({"_email_suffix": 42})
        local_part = result["email"].split("@")[0]
        assert local_part.endswith("42")

    def test_email_suffix_zero(self):
        result = generate_person({"_email_suffix": 0})
        local_part = result["email"].split("@")[0]
        assert local_part.endswith("0")

    def test_no_suffix_without_key(self):
        result = generate_person({})
        local_part = result["email"].split("@")[0]
        # Should not end with digits (barring rare Faker name edge cases)
        first_lower = result["first_name"].lower()
        last_lower = result["last_name"].lower()
        assert local_part == f"{first_lower}.{last_lower}"


class TestGeneratePersonPooling:
    """Test repeated calls work efficiently."""

    def test_fifty_calls_all_return_valid_dicts(self):
        for _ in range(50):
            result = generate_person({})
            assert isinstance(result, dict)
            assert "first_name" in result
            assert "email" in result


# -- Cycle 6: Geo Group Generator ---------------------------------------------

GEO_FIELDS = {"latitude", "longitude", "lat", "lng", "lon"}


class TestGenerateGeoReturnShape:
    """Test generate_geo() returns dict with expected keys."""

    def test_returns_all_geo_fields(self):
        result = generate_geo({})
        for field in GEO_FIELDS:
            assert field in result, f"Missing field: {field}"

    def test_all_values_are_numeric(self):
        result = generate_geo({})
        for key, value in result.items():
            if key.startswith("_"):
                continue
            assert isinstance(value, float), f"{key} is {type(value)}, expected float"


class TestGenerateGeoValidCoordinates:
    """Test lat/lng pairs are valid coordinates."""

    def test_latitude_in_range(self):
        for _ in range(20):
            result = generate_geo({})
            assert -90 <= result["latitude"] <= 90
            assert result["lat"] == result["latitude"]

    def test_longitude_in_range(self):
        for _ in range(20):
            result = generate_geo({})
            assert -180 <= result["longitude"] <= 180
            assert result["lng"] == result["longitude"]
            assert result["lon"] == result["longitude"]

    def test_lat_lng_are_coherent_pair(self):
        """lat/latitude and lng/longitude/lon should be identical."""
        result = generate_geo({})
        assert result["latitude"] == result["lat"]
        assert result["longitude"] == result["lng"]
        assert result["longitude"] == result["lon"]


class TestGenerateGeoLocaleAware:
    """Test geo group uses address locale for coordinate bias."""

    def test_us_locale_biases_coordinates(self):
        """With en_US locale, coordinates should be near the US."""
        results = [generate_geo({"_locale": "en_US"}) for _ in range(10)]
        # US latitude roughly 25-50, longitude roughly -125 to -65
        for r in results:
            assert 20 <= r["latitude"] <= 55, f"US lat out of range: {r['latitude']}"
            assert -130 <= r["longitude"] <= -60, f"US lng out of range: {r['longitude']}"

    def test_france_locale_biases_coordinates(self):
        """With fr_FR locale, coordinates should be near France."""
        results = [generate_geo({"_locale": "fr_FR"}) for _ in range(10)]
        # France latitude roughly 42-51, longitude roughly -5 to 9
        for r in results:
            assert 38 <= r["latitude"] <= 55, f"FR lat out of range: {r['latitude']}"
            assert -10 <= r["longitude"] <= 14, f"FR lng out of range: {r['longitude']}"

    def test_no_locale_generates_random_valid_coordinates(self):
        result = generate_geo({})
        assert -90 <= result["latitude"] <= 90
        assert -180 <= result["longitude"] <= 180
