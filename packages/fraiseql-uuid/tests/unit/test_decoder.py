"""Tests for UUIDDecoder class."""

import pytest
from fraiseql_uuid import Pattern, UUIDDecoder


class TestUUIDDecoderInit:
    """Tests for UUIDDecoder.__init__()."""

    def test_init_with_pattern(self) -> None:
        """Test initialization with pattern."""
        pattern = Pattern()
        decoder = UUIDDecoder(pattern)

        assert decoder.pattern is pattern


class TestUUIDDecoderDecode:
    """Tests for UUIDDecoder.decode()."""

    def test_decode_minimal_uuid(self) -> None:
        """Test decoding UUID with minimal/default values."""
        pattern = Pattern()
        decoder = UUIDDecoder(pattern)
        decoded = decoder.decode("01234521-0000-4000-8000-000000000001")

        assert decoded.raw_uuid == "01234521-0000-4000-8000-000000000001"
        assert decoded["table_code"] == "012345"
        assert decoded["seed_dir"] == 21
        assert decoded["function"] == 0
        assert decoded["scenario"] == 0
        assert decoded["test_case"] == 0
        assert decoded["instance"] == 1

    def test_decode_all_components(self) -> None:
        """Test decoding UUID with all non-default values."""
        pattern = Pattern()
        decoder = UUIDDecoder(pattern)
        decoded = decoder.decode("12345622-0042-4123-8415-000000000999")

        assert decoded["table_code"] == "123456"
        assert decoded["seed_dir"] == 22
        assert decoded["function"] == 42
        assert decoded["scenario"] == 1234
        assert decoded["test_case"] == 15
        assert decoded["instance"] == 999

    def test_decode_preserves_raw_uuid(self) -> None:
        """Test that decoded result preserves original UUID."""
        pattern = Pattern()
        decoder = UUIDDecoder(pattern)
        uuid = "01234521-0000-4000-8000-000000000001"
        decoded = decoder.decode(uuid)

        assert decoded.raw_uuid == uuid

    def test_decode_dict_access(self) -> None:
        """Test that components can be accessed like a dict."""
        pattern = Pattern()
        decoder = UUIDDecoder(pattern)
        decoded = decoder.decode("12345622-0042-4123-8415-000000000999")

        # Using [] operator
        assert decoded["table_code"] == "123456"
        assert decoded["instance"] == 999

    def test_decode_get_method(self) -> None:
        """Test that components can be accessed via get() method."""
        pattern = Pattern()
        decoder = UUIDDecoder(pattern)
        decoded = decoder.decode("12345622-0042-4123-8415-000000000999")

        # Using get() with default
        assert decoded.get("table_code") == "123456"
        assert decoded.get("nonexistent", "default") == "default"
        assert decoded.get("nonexistent") is None

    def test_decode_invalid_format(self) -> None:
        """Test that invalid UUID format raises ValueError."""
        pattern = Pattern()
        decoder = UUIDDecoder(pattern)

        with pytest.raises(ValueError, match="Invalid UUID format"):
            decoder.decode("not-a-uuid")

    def test_decode_wrong_version(self) -> None:
        """Test that non-v4 UUIDs raise ValueError."""
        pattern = Pattern()
        decoder = UUIDDecoder(pattern)

        # Version 1 UUID (has '1' instead of '4' in third segment)
        with pytest.raises(ValueError, match="Invalid UUID format"):
            decoder.decode("01234521-0000-1000-8000-000000000001")

    def test_decode_wrong_variant(self) -> None:
        """Test that UUIDs with wrong variant raise ValueError."""
        pattern = Pattern()
        decoder = UUIDDecoder(pattern)

        # Variant should be '8', not '9'
        with pytest.raises(ValueError, match="Invalid UUID format"):
            decoder.decode("01234521-0000-4000-9000-000000000001")

    def test_decode_empty_string(self) -> None:
        """Test that empty string raises ValueError."""
        pattern = Pattern()
        decoder = UUIDDecoder(pattern)

        with pytest.raises(ValueError, match="Invalid UUID format"):
            decoder.decode("")

    def test_decode_wrong_segment_count(self) -> None:
        """Test that UUID with wrong segment count raises ValueError."""
        pattern = Pattern()
        decoder = UUIDDecoder(pattern)

        with pytest.raises(ValueError, match="Invalid UUID format"):
            decoder.decode("01234521-0000-4000-000000000001")

    def test_decode_wrong_segment_lengths(self) -> None:
        """Test that UUID with wrong segment lengths raises ValueError."""
        pattern = Pattern()
        decoder = UUIDDecoder(pattern)

        with pytest.raises(ValueError, match="Invalid UUID format"):
            decoder.decode("0123-0000-4000-8000-000000000001")


class TestUUIDDecoderRoundTrip:
    """Tests for encode-decode round trips."""

    def test_round_trip_minimal(self) -> None:
        """Test that minimal encode->decode round-trips correctly."""
        pattern = Pattern()
        decoder = UUIDDecoder(pattern)

        # Generate UUID
        uuid = pattern.generate(table_code="012345", instance=1)

        # Decode it
        decoded = decoder.decode(uuid)

        # Verify components
        assert decoded["table_code"] == "012345"
        assert decoded["instance"] == 1
        assert decoded["seed_dir"] == 21  # default

    def test_round_trip_all_components(self) -> None:
        """Test that full encode->decode round-trips correctly."""
        pattern = Pattern()
        decoder = UUIDDecoder(pattern)

        original_params = {
            "table_code": "987654",
            "seed_dir": 23,
            "function": 1337,
            "scenario": 5678,
            "test_case": 99,
            "instance": 123456,
        }

        # Generate UUID
        uuid = pattern.generate(**original_params)

        # Decode it
        decoded = decoder.decode(uuid)

        # Verify all components match
        assert decoded["table_code"] == "987654"
        assert decoded["seed_dir"] == 23
        assert decoded["function"] == 1337
        assert decoded["scenario"] == 5678
        assert decoded["test_case"] == 99
        assert decoded["instance"] == 123456

    def test_round_trip_multiple_uuids(self) -> None:
        """Test round-trip with multiple different UUIDs."""
        pattern = Pattern()
        decoder = UUIDDecoder(pattern)

        test_cases = [
            {"table_code": "111111", "instance": 1},
            {"table_code": "222222", "instance": 2, "seed_dir": 22},
            {"table_code": "333333", "instance": 3, "function": 42, "scenario": 100},
        ]

        for params in test_cases:
            uuid = pattern.generate(**params)
            decoded = decoder.decode(uuid)

            for key, expected_value in params.items():
                assert decoded[key] == expected_value


class TestUUIDDecoderEdgeCases:
    """Edge case tests for UUIDDecoder."""

    def test_decode_max_values(self) -> None:
        """Test decoding UUID with maximum values."""
        pattern = Pattern()
        decoder = UUIDDecoder(pattern)

        uuid = pattern.generate(
            table_code="999999",
            seed_dir=99,
            function=9999,
            scenario=9999,
            test_case=99,
            instance=999999999999,
        )

        decoded = decoder.decode(uuid)
        assert decoded["table_code"] == "999999"
        assert decoded["seed_dir"] == 99
        assert decoded["function"] == 9999
        assert decoded["scenario"] == 9999
        assert decoded["test_case"] == 99
        assert decoded["instance"] == 999999999999

    def test_decode_zero_values(self) -> None:
        """Test decoding UUID with all zeros."""
        pattern = Pattern()
        decoder = UUIDDecoder(pattern)

        uuid = pattern.generate(
            table_code="000000",
            seed_dir=0,
            function=0,
            scenario=0,
            test_case=0,
            instance=0,
        )

        decoded = decoder.decode(uuid)
        assert decoded["table_code"] == "000000"
        assert decoded["seed_dir"] == 0
        assert decoded["function"] == 0
        assert decoded["scenario"] == 0
        assert decoded["test_case"] == 0
        assert decoded["instance"] == 0

    def test_decoder_reuse(self) -> None:
        """Test that decoder can be reused multiple times."""
        pattern = Pattern()
        decoder = UUIDDecoder(pattern)

        uuid1 = "01234521-0000-4000-8000-000000000001"
        uuid2 = "56789022-0042-4100-8515-000000000999"

        decoded1 = decoder.decode(uuid1)
        decoded2 = decoder.decode(uuid2)

        assert decoded1["table_code"] == "012345"
        assert decoded2["table_code"] == "567890"

    def test_multiple_decoders_independent(self) -> None:
        """Test that multiple decoders are independent."""
        pattern = Pattern()
        decoder1 = UUIDDecoder(pattern)
        decoder2 = UUIDDecoder(pattern)

        uuid = "01234521-0000-4000-8000-000000000001"

        decoded1 = decoder1.decode(uuid)
        decoded2 = decoder2.decode(uuid)

        assert decoded1.raw_uuid == decoded2.raw_uuid
        assert decoded1["instance"] == decoded2["instance"]
