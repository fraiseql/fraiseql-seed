"""Faker-based data generator."""

from typing import Any

from fraiseql_data.generators.base import BaseGenerator


class FakerGenerator(BaseGenerator):
    """Generate realistic fake data using Faker."""

    def __init__(self, faker_method: str):
        """Initialize generator.

        Args:
            faker_method: Faker method name (e.g., "name", "email")
        """
        self.faker_method = faker_method

    def generate(self, context: Any) -> Any:
        """Generate fake data (stub)."""
        # TODO: Implement Faker integration
        raise NotImplementedError("Faker generation not yet implemented")
