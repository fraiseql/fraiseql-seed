"""Parametrized type generation unit tests.

Validates every supported PostgreSQL type produces the correct Python type
without needing a database connection.
"""

import uuid
from datetime import date, datetime, time, timedelta

import pytest
from fraiseql_data.generators.faker_generator import FakerGenerator


@pytest.fixture
def gen() -> FakerGenerator:
    return FakerGenerator()


# ---------------------------------------------------------------------------
# Parametrized: every type → expected Python type
# ---------------------------------------------------------------------------

TYPE_EXPECTATIONS = [
    # Text
    ("text", (str,)),
    ("character varying", (str,)),
    ("varchar", (str,)),
    # Numeric
    ("integer", (int,)),
    ("bigint", (int,)),
    ("smallint", (int,)),
    ("numeric", (float, int)),
    ("real", (float, int)),
    ("double precision", (float, int)),
    ("numeric(10,2)", (float, int)),
    ("numeric(5,0)", (float, int)),
    # Boolean
    ("boolean", (bool,)),
    ("bool", (bool,)),
    # Date/Time
    ("timestamp without time zone", (datetime,)),
    ("timestamp with time zone", (datetime,)),
    ("timestamptz", (datetime,)),
    ("date", (date,)),
    ("time without time zone", (time,)),
    ("time with time zone", (time,)),
    ("time", (time,)),
    ("timetz", (time,)),
    ("interval", (timedelta,)),
    # UUID
    ("uuid", (str,)),
    # JSON
    ("json", (dict,)),
    ("jsonb", (dict,)),
    # Network
    ("inet", (str,)),
    ("cidr", (str,)),
    ("macaddr", (str,)),
    ("macaddr8", (str,)),
    # Binary
    ("bytea", (bytes, memoryview)),
    # Arrays
    ("integer[]", (list,)),
    ("text[]", (list,)),
    ("uuid[]", (list,)),
    ("boolean[]", (list,)),
    ("ARRAY", (list,)),
]


@pytest.mark.parametrize(
    ("pg_type", "expected_types"),
    TYPE_EXPECTATIONS,
    ids=[t[0] for t in TYPE_EXPECTATIONS],
)
def test_generate_returns_expected_type(
    gen: FakerGenerator, pg_type: str, expected_types: tuple[type, ...]
):
    value = gen.generate("test_col", pg_type)
    assert isinstance(value, expected_types), (
        f"generate('test_col', '{pg_type}') returned {type(value).__name__}, "
        f"expected one of {[t.__name__ for t in expected_types]}"
    )


# ---------------------------------------------------------------------------
# UUID format validation
# ---------------------------------------------------------------------------


def test_uuid_type_is_valid_uuid4(gen: FakerGenerator):
    value = gen.generate("some_col", "uuid")
    parsed = uuid.UUID(str(value))
    assert parsed.version == 4


# ---------------------------------------------------------------------------
# Array element types
# ---------------------------------------------------------------------------


def test_integer_array_elements_are_ints(gen: FakerGenerator):
    value = gen.generate("scores", "integer[]")
    assert all(isinstance(v, int) for v in value)


def test_text_array_elements_are_strings(gen: FakerGenerator):
    value = gen.generate("tags", "text[]")
    assert all(isinstance(v, str) for v in value)


def test_uuid_array_elements_are_valid_uuids(gen: FakerGenerator):
    value = gen.generate("refs", "uuid[]")
    for v in value:
        uuid.UUID(str(v))  # Must not raise


def test_boolean_array_elements_are_bools(gen: FakerGenerator):
    value = gen.generate("flags", "boolean[]")
    assert all(isinstance(v, bool) for v in value)


# ---------------------------------------------------------------------------
# Numeric precision
# ---------------------------------------------------------------------------


def test_numeric_scale_2(gen: FakerGenerator):
    value = gen.generate("price", "numeric(10,2)")
    # Round-trip check: value should survive round(x, 2)
    assert value == round(value, 2)


def test_numeric_scale_0(gen: FakerGenerator):
    value = gen.generate("count", "numeric(5,0)")
    assert value == round(value, 0)


# ---------------------------------------------------------------------------
# Network type format validation
# ---------------------------------------------------------------------------


def test_cidr_has_prefix(gen: FakerGenerator):
    value = gen.generate("network", "cidr")
    assert "/" in str(value)


def test_macaddr_format(gen: FakerGenerator):
    value = gen.generate("mac", "macaddr")
    parts = str(value).split(":")
    assert len(parts) == 6


def test_macaddr8_format(gen: FakerGenerator):
    value = gen.generate("mac", "macaddr8")
    parts = str(value).split(":")
    assert len(parts) == 8


# ---------------------------------------------------------------------------
# Column name mapping takes precedence
# ---------------------------------------------------------------------------


def test_email_column_generates_email(gen: FakerGenerator):
    value = gen.generate("email", "text")
    assert "@" in value


def test_name_column_generates_name(gen: FakerGenerator):
    value = gen.generate("name", "text")
    assert len(value) > 0
