"""PrintOptim UUID pattern implementation."""

import re
from typing import Any

from fraiseql_uuid.patterns.base import Pattern, UUIDComponents


class PrintOptimPattern(Pattern):
    """PrintOptim Trinity pattern: TTTTTTDD-FFFF-0000-SSSS-000000000IIII

    Components:
        - TTTTTT: Table code (6 digits)
        - DD: Seed directory (21=general, 22=mutation, 23=query)
        - FFFF: Function code (4 digits)
        - SSSS: Scenario code (4 digits)
        - IIII: Instance number (12 digits)
    """

    PATTERN_REGEX = re.compile(
        r"^([0-9]{6})([0-9]{2})-([0-9]{4})-0000-([0-9]{4})-([0-9]{12})$"
    )

    def generate(self, **kwargs: Any) -> str:
        """Generate PrintOptim UUID.

        Args:
            table_code: Table code (6 digits)
            seed_dir: Seed directory (default: 21)
            function: Function code (default: 0)
            scenario: Scenario code (default: 0)
            instance: Instance number (required)

        Returns:
            Generated UUID string
        """
        table_code = str(kwargs["table_code"]).zfill(6)
        seed_dir = str(kwargs.get("seed_dir", 21)).zfill(2)
        function = str(kwargs.get("function", 0)).zfill(4)
        scenario = str(kwargs.get("scenario", 0)).zfill(4)
        instance = str(kwargs["instance"]).zfill(12)

        return f"{table_code}{seed_dir}-{function}-0000-{scenario}-{instance}"

    def decode(self, uuid: str) -> UUIDComponents:
        """Decode PrintOptim UUID.

        Args:
            uuid: UUID string

        Returns:
            Decoded components
        """
        match = self.PATTERN_REGEX.match(uuid)
        if not match:
            raise ValueError(f"Invalid PrintOptim UUID format: {uuid}")

        table_code, seed_dir, function, scenario, instance = match.groups()

        return UUIDComponents(
            raw_uuid=uuid,
            components={
                "table_code": table_code,
                "seed_dir": int(seed_dir),
                "function": int(function),
                "scenario": int(scenario),
                "instance": int(instance),
            }
        )

    def validate_format(self, uuid: str) -> bool:
        """Validate PrintOptim UUID format."""
        return bool(self.PATTERN_REGEX.match(uuid))
