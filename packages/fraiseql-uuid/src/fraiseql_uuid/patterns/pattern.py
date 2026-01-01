"""UUID v4 compliant pattern with encoded metadata."""

import re
from typing import Any

from fraiseql_uuid.patterns.base import Pattern as BasePattern
from fraiseql_uuid.patterns.base import UUIDComponents


class Pattern(BasePattern):
    """UUID v4 compliant pattern with encoded metadata.

    Format (code): {table:6}{type:2}-{func:4}-4{scen:3}-8{scen:1}{test:2}-{inst:12}
    Format (docs): TTTTTTDD-FFFF-4SSS-8STT-IIIIIIIIIIII

    Components:
        T: Table code (6 digits)
        D: Seed directory (2 digits: 21=general, 22=mutation, 23=query, 00=staging)
        F: Function code (4 digits)
        4: UUID v4 version bit (fixed)
        S: Scenario code (4 digits, split as 3+1 for v4 compliance)
        8: UUID variant bit (fixed)
        T: Test case (2 digits)
        I: Instance number (12 digits)

    Example:
        01234521-0042-4100-8015-000000000001
        └─table─┘└type  func  scen  test inst
    """

    PATTERN_REGEX = re.compile(
        r"^([0-9]{6})([0-9]{2})-([0-9]{4})-4([0-9]{3})-8([0-9])([0-9]{2})-([0-9]{12})$"
    )

    def generate(self, **kwargs: Any) -> str:
        """Generate UUID v4 compliant UUID with encoded metadata.

        Args:
            table_code: Table code (6 digits)
            seed_dir: Seed directory (default: 21)
            function: Function code (default: 0)
            scenario: Scenario code (default: 0)
            test_case: Test case number (default: 0)
            instance: Instance number (required)

        Returns:
            UUID v4 compliant string

        Example:
            >>> pattern.generate(table_code="012345", instance=1)
            '01234521-0000-4000-8000-000000000001'
        """
        # Segment 1: {table:6}{type:2}
        table_code = str(kwargs["table_code"]).zfill(6)
        seed_dir = str(kwargs.get("seed_dir", 21)).zfill(2)
        part1 = f"{table_code}{seed_dir}"

        # Segment 2: {func:4}
        function = str(kwargs.get("function", 0)).zfill(4)
        part2 = function

        # Segment 3: 4{scen:3} - UUID v4 version bit + scenario high 3 digits
        scenario = str(kwargs.get("scenario", 0)).zfill(4)
        part3 = f"4{scenario[0:3]}"

        # Segment 4: 8{scen:1}{test:2} - UUID variant + scenario low digit + test case
        test_case = str(kwargs.get("test_case", 0)).zfill(2)
        part4 = f"8{scenario[3]}{test_case}"

        # Segment 5: {inst:12}
        instance = str(kwargs["instance"]).zfill(12)
        part5 = instance

        return f"{part1}-{part2}-{part3}-{part4}-{part5}"

    def decode(self, uuid: str) -> UUIDComponents:
        """Decode UUID v4 compliant UUID with encoded metadata.

        Args:
            uuid: UUID string

        Returns:
            Decoded components

        Example:
            >>> pattern.decode('01234521-0042-4100-8015-000000000001')
            UUIDComponents(table_code='012345', seed_dir=21, function=42,
                          scenario=1000, test_case=15, instance=1)
        """
        match = self.PATTERN_REGEX.match(uuid)
        if not match:
            raise ValueError(f"Invalid UUID format: {uuid}")

        table_code, seed_dir, function, scen_high, scen_low, test_case, instance = match.groups()

        # Reconstruct full scenario from split parts
        scenario = int(scen_high + scen_low)

        return UUIDComponents(
            raw_uuid=uuid,
            components={
                "table_code": table_code,
                "seed_dir": int(seed_dir),
                "function": int(function),
                "scenario": scenario,
                "test_case": int(test_case),
                "instance": int(instance),
            },
        )

    def validate_format(self, uuid: str) -> bool:
        """Validate UUID format."""
        return bool(self.PATTERN_REGEX.match(uuid))
