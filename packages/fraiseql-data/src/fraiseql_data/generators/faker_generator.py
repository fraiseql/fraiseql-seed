"""Faker-based data generator."""

import logging
import os
import random
import re
import uuid as uuid_mod
from datetime import timedelta
from typing import Any, ClassVar

from faker import Faker

fake = Faker()
logger = logging.getLogger("fraiseql_data.generators")


def _generate_macaddr8() -> str:
    """Generate a valid EUI-64 MAC address."""
    octets = [random.randint(0, 255) for _ in range(8)]
    return ":".join(f"{o:02x}" for o in octets)


class FakerGenerator:
    """
    Generate realistic data using Faker library.

    Uses intelligent column name detection and type-based fallbacks to auto-generate
    realistic test data without configuration. Maps common column names like 'email',
    'name', 'phone' to appropriate Faker methods.

    Strategy:
        1. Try column name mapping (e.g., 'email' → fake.email())
        2. Fall back to PostgreSQL type (e.g., 'text' → fake.text())
        3. Default to generic text with warning if no match
    """

    # Column name → Faker method mapping
    COLUMN_MAPPINGS: ClassVar[dict[str, Any]] = {
        "email": lambda: fake.email(),
        "first_name": lambda: fake.first_name(),
        "last_name": lambda: fake.last_name(),
        "name": lambda: fake.name(),
        "company": lambda: fake.company(),
        "phone": lambda: fake.phone_number(),
        "phone_number": lambda: fake.phone_number(),
        "address": lambda: fake.address(),
        "street": lambda: fake.street_address(),
        "city": lambda: fake.city(),
        "state": lambda: fake.state(),
        "country": lambda: fake.country(),
        "zip": lambda: fake.zipcode(),
        "zipcode": lambda: fake.zipcode(),
        "url": lambda: fake.url(),
        "description": lambda: fake.text(max_nb_chars=200),
        "bio": lambda: fake.text(max_nb_chars=300),
    }

    # Type-based fallbacks
    TYPE_FALLBACKS: ClassVar[dict[str, Any]] = {
        # Text types
        "text": lambda: fake.text(max_nb_chars=50),
        "character varying": lambda: fake.text(max_nb_chars=50),
        "varchar": lambda: fake.text(max_nb_chars=50),
        # Numeric types
        "integer": lambda: fake.random_int(min=1, max=1000),
        "bigint": lambda: fake.random_int(min=1, max=100000),
        "smallint": lambda: fake.random_int(min=1, max=100),
        "numeric": lambda: fake.pyfloat(min_value=0, max_value=10000),
        "real": lambda: fake.pyfloat(min_value=0, max_value=10000),
        "double precision": lambda: fake.pyfloat(min_value=0, max_value=10000),
        # Boolean
        "boolean": lambda: fake.boolean(),
        "bool": lambda: fake.boolean(),
        # Timestamp/date
        "timestamp without time zone": lambda: fake.date_time_this_year(),
        "timestamp with time zone": lambda: fake.date_time_this_year(),
        "timestamptz": lambda: fake.date_time_this_year(),
        "date": lambda: fake.date_this_year(),
        # Time
        "time without time zone": lambda: fake.time_object(),
        "time with time zone": lambda: fake.time_object(),
        "time": lambda: fake.time_object(),
        "timetz": lambda: fake.time_object(),
        # Interval
        "interval": lambda: timedelta(
            days=random.randint(0, 30),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
        ),
        # UUID
        "uuid": lambda: str(uuid_mod.uuid4()),
        # JSON
        "jsonb": lambda: {"key": fake.word(), "value": fake.sentence()},
        "json": lambda: {"key": fake.word(), "value": fake.sentence()},
        # Network types
        "inet": lambda: fake.ipv4(),
        "cidr": lambda: f"{fake.ipv4()}/24",
        "macaddr": lambda: fake.mac_address(),
        "macaddr8": _generate_macaddr8,
        # Binary
        "bytea": lambda: os.urandom(16),
        # Array types
        "ARRAY": lambda: [fake.word() for _ in range(3)],
    }

    # Regex for numeric(precision, scale)
    _NUMERIC_RE = re.compile(r"^numeric\((\d+),\s*(\d+)\)$", re.IGNORECASE)

    # Regex for array types (e.g., "integer[]", "text[]")
    _ARRAY_RE = re.compile(r"^(.+)\[\]$")

    # Base type generators for array element generation
    _ARRAY_ELEMENT_GENERATORS: ClassVar[dict[str, Any]] = {
        "integer": lambda: fake.random_int(min=1, max=1000),
        "bigint": lambda: fake.random_int(min=1, max=100000),
        "smallint": lambda: fake.random_int(min=1, max=100),
        "text": lambda: fake.word(),
        "character varying": lambda: fake.word(),
        "varchar": lambda: fake.word(),
        "uuid": lambda: str(uuid_mod.uuid4()),
        "boolean": lambda: fake.boolean(),
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
            _precision, scale = int(numeric_match.group(1)), int(numeric_match.group(2))
            value = fake.pyfloat(min_value=0, max_value=10000)
            return round(value, scale)

        # Check for array types (e.g., "integer[]")
        array_match = self._ARRAY_RE.match(pg_type)
        if array_match:
            base_type = array_match.group(1)
            element_gen = self._ARRAY_ELEMENT_GENERATORS.get(
                base_type, lambda: fake.word()
            )
            return [element_gen() for _ in range(3)]

        # Unknown type: warn and fall back to text
        logger.warning(
            "Unknown PostgreSQL type '%s' for column '%s', falling back to text",
            pg_type,
            column_name,
        )
        return fake.text(max_nb_chars=50)
