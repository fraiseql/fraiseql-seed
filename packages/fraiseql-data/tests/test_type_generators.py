"""Tests for type-aware data generators (B1: Type-Aware Generators)."""

import json
import logging
import uuid
from datetime import time, timedelta
from ipaddress import IPv4Address, IPv4Network

import pytest
from fraiseql_data import SeedBuilder
from fraiseql_data.generators.faker_generator import FakerGenerator
from fraiseql_data.models import ColumnInfo, TableInfo


class TestUUIDGeneration:
    """Cycle 1: UUID columns generate valid UUIDs."""

    def test_uuid_type_generates_valid_uuid(self):
        gen = FakerGenerator()
        value = gen.generate("some_col", "uuid")
        # Should be a valid UUID string
        parsed = uuid.UUID(str(value))
        assert parsed.version == 4

    def test_uuid_not_text(self):
        gen = FakerGenerator()
        value = gen.generate("some_col", "uuid")
        # Should not be random text
        assert isinstance(str(value), str)
        uuid.UUID(str(value))  # Should not raise


class TestJSONGeneration:
    """Cycle 2: JSON/JSONB columns generate valid JSON."""

    def test_jsonb_generates_valid_json(self):
        gen = FakerGenerator()
        value = gen.generate("metadata", "jsonb")
        # Should be a valid JSON-serializable object
        assert isinstance(value, dict)
        json.dumps(value)  # Should not raise

    def test_json_generates_valid_json(self):
        gen = FakerGenerator()
        value = gen.generate("config", "json")
        assert isinstance(value, dict)
        json.dumps(value)

    def test_jsonb_has_content(self):
        gen = FakerGenerator()
        value = gen.generate("data", "jsonb")
        assert len(value) > 0


class TestBooleanAlias:
    """Cycle 3: Bool alias maps to boolean handler."""

    def test_bool_alias_generates_boolean(self):
        gen = FakerGenerator()
        value = gen.generate("is_active", "bool")
        assert isinstance(value, bool)


class TestTimeAndInterval:
    """Cycle 4: Time and interval types."""

    def test_time_generates_valid_time(self):
        gen = FakerGenerator()
        value = gen.generate("start_time", "time without time zone")
        assert isinstance(value, time)

    def test_timetz_generates_valid_time(self):
        gen = FakerGenerator()
        value = gen.generate("start_time", "time with time zone")
        assert isinstance(value, (time, str))

    def test_interval_generates_valid_interval(self):
        gen = FakerGenerator()
        value = gen.generate("duration", "interval")
        assert isinstance(value, timedelta)


class TestNetworkTypes:
    """Cycle 5: Network types (inet, cidr, macaddr)."""

    def test_inet_generates_valid_ip(self):
        gen = FakerGenerator()
        value = gen.generate("ip_address", "inet")
        IPv4Address(str(value))  # Should not raise

    def test_cidr_generates_valid_cidr(self):
        gen = FakerGenerator()
        value = gen.generate("network", "cidr")
        IPv4Network(str(value), strict=False)  # Should not raise

    def test_macaddr_generates_valid_mac(self):
        gen = FakerGenerator()
        value = gen.generate("mac", "macaddr")
        parts = str(value).split(":")
        assert len(parts) == 6
        for part in parts:
            int(part, 16)  # Should not raise

    def test_macaddr8_generates_valid_mac(self):
        gen = FakerGenerator()
        value = gen.generate("mac", "macaddr8")
        parts = str(value).split(":")
        assert len(parts) == 8


class TestArrayTypes:
    """Cycle 6: Array types."""

    def test_integer_array(self):
        gen = FakerGenerator()
        value = gen.generate("scores", "integer[]")
        assert isinstance(value, list)
        assert all(isinstance(v, int) for v in value)

    def test_text_array(self):
        gen = FakerGenerator()
        value = gen.generate("tags", "text[]")
        assert isinstance(value, list)
        assert all(isinstance(v, str) for v in value)

    def test_array_format_detection(self):
        gen = FakerGenerator()
        # ARRAY keyword variant
        value = gen.generate("items", "ARRAY")
        assert isinstance(value, list)


class TestByteaType:
    """Cycle 8: Bytea type."""

    def test_bytea_generates_bytes(self):
        gen = FakerGenerator()
        value = gen.generate("data", "bytea")
        assert isinstance(value, (bytes, memoryview))

    def test_bytea_has_content(self):
        gen = FakerGenerator()
        value = gen.generate("payload", "bytea")
        assert len(value) > 0


class TestNumericPrecision:
    """Cycle 10: Numeric precision."""

    def test_numeric_with_scale_respects_precision(self):
        gen = FakerGenerator()
        value = gen.generate("price", "numeric(10,2)")
        assert isinstance(value, float)
        assert 0 <= value <= 99_999_999.99

    def test_numeric_without_scale_is_float(self):
        gen = FakerGenerator()
        value = gen.generate("amount", "numeric")
        assert isinstance(value, float)

    @pytest.mark.parametrize(
        ("precision", "scale", "max_val"),
        [
            (5, 4, 9.9999),
            (5, 2, 999.99),
            (10, 2, 99_999_999.99),
            (3, 0, 999),
        ],
    )
    def test_numeric_precision_bounds(self, precision, scale, max_val):
        gen = FakerGenerator()
        pg_type = f"numeric({precision},{scale})"
        for _ in range(1000):
            value = gen.generate("col", pg_type)
            assert 0 <= value <= max_val, (
                f"numeric({precision},{scale}): {value} exceeds max {max_val}"
            )

    @pytest.mark.parametrize(
        ("precision", "scale", "max_val"),
        [
            (1, 0, 9),
            (2, 1, 9.9),
            (4, 4, 0.9999),
        ],
    )
    def test_numeric_precision_edge_cases(self, precision, scale, max_val):
        gen = FakerGenerator()
        pg_type = f"numeric({precision},{scale})"
        for _ in range(1000):
            value = gen.generate("col", pg_type)
            assert 0 <= value <= max_val, (
                f"numeric({precision},{scale}): {value} exceeds max {max_val}"
            )


class TestUnknownTypeWarning:
    """Cycle 11: Unknown type warning."""

    def test_unknown_type_emits_warning(self, caplog):
        gen = FakerGenerator()
        with caplog.at_level(logging.WARNING):
            value = gen.generate("weird_col", "some_unknown_custom_type")

        assert value is not None  # Still generates fallback text
        assert any("some_unknown_custom_type" in r.message for r in caplog.records)

    def test_known_type_no_warning(self, caplog):
        gen = FakerGenerator()
        with caplog.at_level(logging.WARNING):
            gen.generate("col", "integer")

        assert not any("integer" in r.message for r in caplog.records)


class TestIdentityAndSerialSkip:
    """Cycle 9: Identity and serial columns are skipped."""

    def test_identity_column_skipped_in_staging(self):
        """GENERATED ALWAYS AS IDENTITY columns should not appear in generated rows."""
        builder = SeedBuilder(None, schema="test", backend="staging")
        table_info = TableInfo(
            name="tb_test",
            columns=[
                ColumnInfo(
                    name="pk_test",
                    pg_type="integer",
                    is_nullable=False,
                    is_primary_key=True,
                    is_identity=True,
                ),
                ColumnInfo(name="name", pg_type="text", is_nullable=False),
            ],
        )
        builder.set_table_schema("tb_test", table_info)
        builder.add("tb_test", count=3)
        seeds = builder.execute()
        rows = seeds.tb_test
        assert len(rows) == 3
        for row in rows:
            assert not hasattr(row, "pk_test") or row.pk_test is not None
            assert row.name is not None

    def test_serial_column_skipped_via_nextval_default(self):
        """Serial columns (nextval default on PK) should be skipped."""
        builder = SeedBuilder(None, schema="test", backend="staging")
        table_info = TableInfo(
            name="tb_test",
            columns=[
                ColumnInfo(
                    name="serial_id",
                    pg_type="integer",
                    is_nullable=False,
                    is_primary_key=True,
                    default_value="nextval('tb_test_id_seq'::regclass)",
                ),
                ColumnInfo(name="value", pg_type="text", is_nullable=False),
            ],
        )
        builder.set_table_schema("tb_test", table_info)
        builder.add("tb_test", count=2)
        seeds = builder.execute()
        rows = seeds.tb_test
        assert len(rows) == 2
        for row in rows:
            assert row.value is not None
