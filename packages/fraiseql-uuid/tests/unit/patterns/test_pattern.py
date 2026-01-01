"""Tests for Pattern class."""

import pytest
from fraiseql_uuid.patterns import Pattern


class TestPatternGenerate:
    """Tests for Pattern.generate()."""

    def test_generate_minimal(self) -> None:
        """Test generating UUID with minimal parameters."""
        pattern = Pattern()
        uuid = pattern.generate(table_code="012345", instance=1)

        assert uuid == "01234521-0000-4000-8000-000000000001"
        assert len(uuid) == 36
        assert uuid.count("-") == 4

    def test_generate_all_parameters(self) -> None:
        """Test generating UUID with all parameters."""
        pattern = Pattern()
        uuid = pattern.generate(
            table_code="123456",
            seed_dir=22,
            function=42,
            scenario=1234,
            test_case=15,
            instance=999,
        )

        assert uuid == "12345622-0042-4123-8415-000000000999"

    def test_generate_pads_short_values(self) -> None:
        """Test that short values are zero-padded correctly."""
        pattern = Pattern()
        uuid = pattern.generate(
            table_code="1",
            seed_dir=2,
            function=3,
            scenario=4,
            test_case=5,
            instance=6,
        )

        assert uuid == "00000102-0003-4000-8405-000000000006"

    def test_generate_default_seed_dir(self) -> None:
        """Test that seed_dir defaults to 21."""
        pattern = Pattern()
        uuid = pattern.generate(table_code="012345", instance=1)

        assert uuid[6:8] == "21"

    def test_generate_default_function(self) -> None:
        """Test that function defaults to 0."""
        pattern = Pattern()
        uuid = pattern.generate(table_code="012345", instance=1)

        assert uuid[9:13] == "0000"

    def test_generate_default_scenario(self) -> None:
        """Test that scenario defaults to 0."""
        pattern = Pattern()
        uuid = pattern.generate(table_code="012345", instance=1)

        # Scenario is split: 3 digits after '4', 1 digit after '8'
        assert uuid[15:18] == "000"  # High 3 digits (after version bit '4')
        assert uuid[20] == "0"  # Low 1 digit (after variant bit '8')

    def test_generate_default_test_case(self) -> None:
        """Test that test_case defaults to 0."""
        pattern = Pattern()
        uuid = pattern.generate(table_code="012345", instance=1)

        assert uuid[20:22] == "00"

    def test_generate_uuid_v4_compliance(self) -> None:
        """Test that generated UUIDs are v4 compliant."""
        import re

        pattern = Pattern()
        uuid = pattern.generate(table_code="012345", instance=1)

        # UUID v4 format: xxxxxxxx-xxxx-4xxx-8xxx-xxxxxxxxxxxx
        v4_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-8[0-9a-f]{3}-[0-9a-f]{12}$", re.I
        )
        assert v4_pattern.match(uuid)

    def test_generate_scenario_split(self) -> None:
        """Test that 4-digit scenario is correctly split across segments."""
        pattern = Pattern()
        uuid = pattern.generate(table_code="012345", scenario=1234, instance=1)

        # Scenario 1234 → "123" in segment 3 (after '4'), "4" in segment 4 (after '8')
        assert uuid[15:18] == "123"
        assert uuid[20] == "4"

    def test_generate_requires_table_code(self) -> None:
        """Test that table_code is required."""
        pattern = Pattern()
        with pytest.raises(KeyError):
            pattern.generate(instance=1)

    def test_generate_requires_instance(self) -> None:
        """Test that instance is required."""
        pattern = Pattern()
        with pytest.raises(KeyError):
            pattern.generate(table_code="012345")


class TestPatternDecode:
    """Tests for Pattern.decode()."""

    def test_decode_minimal(self) -> None:
        """Test decoding UUID with default values."""
        pattern = Pattern()
        decoded = pattern.decode("01234521-0000-4000-8000-000000000001")

        assert decoded["table_code"] == "012345"
        assert decoded["seed_dir"] == 21
        assert decoded["function"] == 0
        assert decoded["scenario"] == 0
        assert decoded["test_case"] == 0
        assert decoded["instance"] == 1

    def test_decode_all_components(self) -> None:
        """Test decoding UUID with all non-default values."""
        pattern = Pattern()
        decoded = pattern.decode("12345622-0042-4123-8415-000000000999")

        assert decoded["table_code"] == "123456"
        assert decoded["seed_dir"] == 22
        assert decoded["function"] == 42
        assert decoded["scenario"] == 1234
        assert decoded["test_case"] == 15
        assert decoded["instance"] == 999

    def test_decode_round_trip(self) -> None:
        """Test that encode->decode round-trips correctly."""
        pattern = Pattern()
        original_params = {
            "table_code": "987654",
            "seed_dir": 23,
            "function": 1337,
            "scenario": 5678,
            "test_case": 99,
            "instance": 123456,
        }

        uuid = pattern.generate(**original_params)
        decoded = pattern.decode(uuid)

        assert decoded["table_code"] == "987654"
        assert decoded["seed_dir"] == 23
        assert decoded["function"] == 1337
        assert decoded["scenario"] == 5678
        assert decoded["test_case"] == 99
        assert decoded["instance"] == 123456

    def test_decode_preserves_raw_uuid(self) -> None:
        """Test that decoded result includes raw UUID."""
        pattern = Pattern()
        uuid = "01234521-0000-4000-8000-000000000001"
        decoded = pattern.decode(uuid)

        assert decoded.raw_uuid == uuid

    def test_decode_invalid_format(self) -> None:
        """Test that invalid UUIDs raise ValueError."""
        pattern = Pattern()

        with pytest.raises(ValueError, match="Invalid UUID format"):
            pattern.decode("not-a-uuid")

    def test_decode_wrong_version(self) -> None:
        """Test that non-v4 UUIDs raise ValueError."""
        pattern = Pattern()

        # Version 1 UUID
        with pytest.raises(ValueError, match="Invalid UUID format"):
            pattern.decode("01234521-0000-1000-8000-000000000001")

    def test_decode_wrong_variant(self) -> None:
        """Test that UUIDs with wrong variant raise ValueError."""
        pattern = Pattern()

        # Variant should be 8, not 9
        with pytest.raises(ValueError, match="Invalid UUID format"):
            pattern.decode("01234521-0000-4000-9000-000000000001")


class TestPatternValidateFormat:
    """Tests for Pattern.validate_format()."""

    def test_validate_valid_uuid(self) -> None:
        """Test that valid UUIDs pass validation."""
        pattern = Pattern()

        assert pattern.validate_format("01234521-0000-4000-8000-000000000001") is True

    def test_validate_invalid_format(self) -> None:
        """Test that invalid formats fail validation."""
        pattern = Pattern()

        assert pattern.validate_format("not-a-uuid") is False
        assert pattern.validate_format("") is False
        assert (
            pattern.validate_format("01234521-0000-0000-0000-000000000001") is False
        )  # Wrong version

    def test_validate_wrong_segment_count(self) -> None:
        """Test that UUIDs with wrong segment count fail."""
        pattern = Pattern()

        assert pattern.validate_format("01234521-0000-4000-000000000001") is False

    def test_validate_wrong_segment_lengths(self) -> None:
        """Test that UUIDs with wrong segment lengths fail."""
        pattern = Pattern()

        assert pattern.validate_format("0123-0000-4000-8000-000000000001") is False
        assert pattern.validate_format("01234521-00-4000-8000-000000000001") is False

    def test_validate_non_numeric(self) -> None:
        """Test that non-numeric characters fail validation."""
        pattern = Pattern()

        assert pattern.validate_format("0123XX21-0000-4000-8000-000000000001") is False


class TestPatternEdgeCases:
    """Edge case tests for Pattern."""

    def test_max_values(self) -> None:
        """Test pattern with maximum values."""
        pattern = Pattern()
        uuid = pattern.generate(
            table_code="999999",
            seed_dir=99,
            function=9999,
            scenario=9999,
            test_case=99,
            instance=999999999999,
        )

        decoded = pattern.decode(uuid)
        assert decoded["table_code"] == "999999"
        assert decoded["seed_dir"] == 99
        assert decoded["function"] == 9999
        assert decoded["scenario"] == 9999
        assert decoded["test_case"] == 99
        assert decoded["instance"] == 999999999999

    def test_zero_values(self) -> None:
        """Test pattern with all zeros."""
        pattern = Pattern()
        uuid = pattern.generate(
            table_code="000000",
            seed_dir=0,
            function=0,
            scenario=0,
            test_case=0,
            instance=0,
        )

        decoded = pattern.decode(uuid)
        assert decoded["table_code"] == "000000"
        assert decoded["seed_dir"] == 0
        assert decoded["function"] == 0
        assert decoded["scenario"] == 0
        assert decoded["test_case"] == 0
        assert decoded["instance"] == 0

    def test_string_numbers_converted(self) -> None:
        """Test that string numbers are handled correctly."""
        pattern = Pattern()
        uuid = pattern.generate(
            table_code="123",  # Will be padded to "000123"
            instance="456",  # String should be converted
        )

        decoded = pattern.decode(uuid)
        assert decoded["table_code"] == "000123"
        assert decoded["instance"] == 456
