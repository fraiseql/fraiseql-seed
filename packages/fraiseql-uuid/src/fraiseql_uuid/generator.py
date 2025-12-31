"""UUID generator."""

from typing import Any

from fraiseql_uuid.patterns.base import Pattern


class UUIDGenerator:
    """UUID generator using a specific pattern."""

    def __init__(self, pattern: Pattern, **kwargs: Any):
        """Initialize generator.

        Args:
            pattern: Pattern instance to use
            **kwargs: Pattern-specific default values
        """
        self.pattern = pattern
        self.defaults = kwargs

    def generate(self, instance: int, **kwargs: Any) -> str:
        """Generate a UUID.

        Args:
            instance: Instance number
            **kwargs: Pattern-specific overrides

        Returns:
            Generated UUID string
        """
        params = {**self.defaults, **kwargs, "instance": instance}
        return self.pattern.generate(**params)

    def generate_batch(
        self,
        count: int,
        start_instance: int = 1,
        **kwargs: Any
    ) -> list[str]:
        """Generate batch of UUIDs.

        Args:
            count: Number of UUIDs to generate
            start_instance: Starting instance number
            **kwargs: Pattern-specific overrides

        Returns:
            List of generated UUIDs
        """
        return [
            self.generate(start_instance + i, **kwargs)
            for i in range(count)
        ]
