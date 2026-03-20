"""Faker-based data generator with fast paths for simple types."""

import logging
import os
import random
import re
import uuid as uuid_mod
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, ClassVar

from faker import Faker

fake = Faker()
logger = logging.getLogger("fraiseql_data.generators")

# ---------------------------------------------------------------------------
# Fast generators — bypass Faker overhead for simple types
# ---------------------------------------------------------------------------

_EPOCH = datetime(2024, 1, 1, tzinfo=UTC)
_YEAR_SECONDS = 365 * 86400


def _fast_int(lo: int = 1, hi: int = 1000) -> int:
    return random.randint(lo, hi)


def _fast_bigint() -> int:
    return random.randint(1, 100_000)


def _fast_smallint() -> int:
    return random.randint(1, 100)


def _fast_float() -> float:
    return round(random.uniform(0, 10_000), 4)


def _fast_bool() -> bool:
    return bool(random.getrandbits(1))


def _fast_uuid() -> str:
    return str(uuid_mod.uuid4())


def _fast_bytea() -> bytes:
    return os.urandom(16)


def _fast_timestamptz() -> datetime:
    offset = random.randint(0, _YEAR_SECONDS)
    return _EPOCH + timedelta(seconds=offset)


def _fast_timestamp() -> datetime:
    offset = random.randint(0, _YEAR_SECONDS)
    return (_EPOCH + timedelta(seconds=offset)).replace(tzinfo=None)


def _fast_date() -> date:
    return _fast_timestamp().date()


def _fast_time() -> time:
    return time(random.randint(0, 23), random.randint(0, 59), random.randint(0, 59))


def _fast_interval() -> timedelta:
    return timedelta(
        days=random.randint(0, 30),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )


def _fast_inet() -> str:
    ri = random.randint
    return f"{ri(1, 223)}.{ri(0, 255)}.{ri(0, 255)}.{ri(1, 254)}"


def _fast_cidr() -> str:
    return f"{random.randint(1, 223)}.{random.randint(0, 255)}.{random.randint(0, 255)}.0/24"


def _fast_macaddr() -> str:
    return ":".join(f"{random.randint(0, 255):02x}" for _ in range(6))


def _fast_macaddr8() -> str:
    return ":".join(f"{random.randint(0, 255):02x}" for _ in range(8))


def _fast_jsonb() -> dict[str, str]:
    return {"key": f"k{random.randint(0, 9999)}", "value": f"v{random.randint(0, 9999)}"}


# ---------------------------------------------------------------------------
# Pre-generated pools for Faker-dependent types
# ---------------------------------------------------------------------------

_POOL_SIZE = 500


class _FakerPool:
    """Pre-generate batches of Faker values and serve from pool."""

    def __init__(self, faker_fn: Any, size: int = _POOL_SIZE):
        self._faker_fn = faker_fn
        self._size = size
        self._pool: list[Any] = []
        self._idx = 0

    def __call__(self) -> Any:
        if self._idx >= len(self._pool):
            self._pool = [self._faker_fn() for _ in range(self._size)]
            self._idx = 0
        val = self._pool[self._idx]
        self._idx += 1
        return val


# Pooled Faker generators (amortize Faker's per-call overhead)
_pool_email = _FakerPool(fake.email)
_pool_first_name = _FakerPool(fake.first_name)
_pool_last_name = _FakerPool(fake.last_name)
_pool_name = _FakerPool(fake.name)
_pool_company = _FakerPool(fake.company)
_pool_phone = _FakerPool(fake.phone_number)
_pool_address = _FakerPool(fake.address)
_pool_street = _FakerPool(fake.street_address)
_pool_city = _FakerPool(fake.city)
_pool_state = _FakerPool(fake.state)
_pool_country = _FakerPool(fake.country)
_pool_zipcode = _FakerPool(fake.zipcode)
_pool_url = _FakerPool(fake.url)
_pool_text_50 = _FakerPool(lambda: fake.text(max_nb_chars=50))
_pool_text_200 = _FakerPool(lambda: fake.text(max_nb_chars=200))
_pool_text_300 = _FakerPool(lambda: fake.text(max_nb_chars=300))
_pool_word = _FakerPool(fake.word)


class FakerGenerator:
    """
    Generate realistic data using Faker library with fast paths.

    Uses intelligent column name detection and type-based fallbacks to auto-generate
    realistic test data without configuration. Maps common column names like 'email',
    'name', 'phone' to appropriate Faker methods.

    Performance: simple types (int, bool, uuid, float, bytes) bypass Faker entirely.
    Faker-dependent types (email, name, text) use pre-generated pools to amortize
    Faker's per-call overhead.

    Strategy:
        1. Try column name mapping (e.g., 'email' → pooled fake.email())
        2. Fall back to PostgreSQL type (e.g., 'integer' → random.randint())
        3. Default to generic text with warning if no match
    """

    # Column name → generator mapping (pooled Faker)
    COLUMN_MAPPINGS: ClassVar[dict[str, Any]] = {
        "email": _pool_email,
        "first_name": _pool_first_name,
        "last_name": _pool_last_name,
        "name": _pool_name,
        "company": _pool_company,
        "phone": _pool_phone,
        "phone_number": _pool_phone,
        "address": _pool_address,
        "street": _pool_street,
        "city": _pool_city,
        "state": _pool_state,
        "country": _pool_country,
        "zip": _pool_zipcode,
        "zipcode": _pool_zipcode,
        "url": _pool_url,
        "description": _pool_text_200,
        "bio": _pool_text_300,
    }

    # Type-based fallbacks (fast paths where possible)
    TYPE_FALLBACKS: ClassVar[dict[str, Any]] = {
        # Text types (pooled Faker — need realistic text)
        "text": _pool_text_50,
        "character varying": _pool_text_50,
        "varchar": _pool_text_50,
        # Numeric types (fast — no Faker needed)
        "integer": _fast_int,
        "bigint": _fast_bigint,
        "smallint": _fast_smallint,
        "numeric": _fast_float,
        "real": _fast_float,
        "double precision": _fast_float,
        "boolean": _fast_bool,
        "bool": _fast_bool,
        "timestamp without time zone": _fast_timestamp,
        "timestamp with time zone": _fast_timestamptz,
        "timestamptz": _fast_timestamptz,
        "date": _fast_date,
        "time without time zone": _fast_time,
        "time with time zone": _fast_time,
        "time": _fast_time,
        "timetz": _fast_time,
        "interval": _fast_interval,
        "uuid": _fast_uuid,
        "jsonb": _fast_jsonb,
        "json": _fast_jsonb,
        "inet": _fast_inet,
        "cidr": _fast_cidr,
        "macaddr": _fast_macaddr,
        "macaddr8": _fast_macaddr8,
        "bytea": _fast_bytea,
        # Array types (generic fallback)
        "ARRAY": lambda: [_pool_word() for _ in range(3)],
    }

    # Regex for numeric(precision, scale)
    _NUMERIC_RE = re.compile(r"^numeric\((\d+),\s*(\d+)\)$", re.IGNORECASE)

    # Regex for array types (e.g., "integer[]", "text[]")
    _ARRAY_RE = re.compile(r"^(.+)\[\]$")

    # Base type generators for array element generation
    _ARRAY_ELEMENT_GENERATORS: ClassVar[dict[str, Any]] = {
        "integer": _fast_int,
        "bigint": _fast_bigint,
        "smallint": _fast_smallint,
        "text": _pool_word,
        "character varying": _pool_word,
        "varchar": _pool_word,
        "uuid": _fast_uuid,
        "boolean": _fast_bool,
    }

    def generate(self, column_name: str, pg_type: str) -> Any:
        """
        Generate data for a column based on name and type.

        Args:
            column_name: Column name (e.g., 'email', 'name', 'phone')
            pg_type: PostgreSQL type (e.g., 'text', 'integer', 'timestamptz')

        Returns:
            Generated value appropriate for the column

        Examples:
            >>> gen.generate('email', 'text')
            'john.doe@example.com'
            >>> gen.generate('age', 'integer')
            42
            >>> gen.generate('created_at', 'timestamptz')
            datetime(2024, 1, 15, 10, 30, 0)
        """
        # Try column name mapping first
        if column_name in self.COLUMN_MAPPINGS:
            return self.COLUMN_MAPPINGS[column_name]()

        # Fall back to type-based generation
        if pg_type in self.TYPE_FALLBACKS:
            return self.TYPE_FALLBACKS[pg_type]()

        # Check for numeric(precision, scale)
        numeric_match = self._NUMERIC_RE.match(pg_type)
        if numeric_match:
            precision, scale = int(numeric_match.group(1)), int(numeric_match.group(2))
            max_val = 10 ** (precision - scale) - 10**-scale
            return round(random.uniform(0, max_val), scale)

        # Check for array types (e.g., "integer[]")
        array_match = self._ARRAY_RE.match(pg_type)
        if array_match:
            base_type = array_match.group(1)
            element_gen = self._ARRAY_ELEMENT_GENERATORS.get(base_type, _pool_word)
            return [element_gen() for _ in range(3)]

        # Unknown type: warn and fall back to text
        logger.warning(
            "Unknown PostgreSQL type '%s' for column '%s', falling back to text",
            pg_type,
            column_name,
        )
        return _pool_text_50()
