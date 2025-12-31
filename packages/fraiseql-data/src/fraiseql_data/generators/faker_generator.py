"""Faker-based data generator."""

from typing import Any
from faker import Faker

fake = Faker()


class FakerGenerator:
    """Generate realistic data using Faker library."""

    # Column name → Faker method mapping
    COLUMN_MAPPINGS = {
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
    TYPE_FALLBACKS = {
        "text": lambda: fake.text(max_nb_chars=50),
        "character varying": lambda: fake.text(max_nb_chars=50),
        "varchar": lambda: fake.text(max_nb_chars=50),
        "integer": lambda: fake.random_int(min=1, max=1000),
        "bigint": lambda: fake.random_int(min=1, max=100000),
        "smallint": lambda: fake.random_int(min=1, max=100),
        "numeric": lambda: fake.pyfloat(min_value=0, max_value=10000),
        "real": lambda: fake.pyfloat(min_value=0, max_value=10000),
        "double precision": lambda: fake.pyfloat(min_value=0, max_value=10000),
        "boolean": lambda: fake.boolean(),
        "timestamp without time zone": lambda: fake.date_time_this_year(),
        "timestamp with time zone": lambda: fake.date_time_this_year(),
        "timestamptz": lambda: fake.date_time_this_year(),
        "date": lambda: fake.date_this_year(),
    }

    def generate(self, column_name: str, pg_type: str) -> Any:
        """Generate data for a column based on name and type."""
        # Try column name mapping first
        if column_name in self.COLUMN_MAPPINGS:
            return self.COLUMN_MAPPINGS[column_name]()

        # Fall back to type-based generation
        if pg_type in self.TYPE_FALLBACKS:
            return self.TYPE_FALLBACKS[pg_type]()

        # Default: text
        return fake.text(max_nb_chars=50)
