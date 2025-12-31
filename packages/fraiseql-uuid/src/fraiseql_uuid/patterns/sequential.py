"""Sequential UUID pattern implementation."""

import re
from typing import Any

from fraiseql_uuid.patterns.base import Pattern, UUIDComponents


class SequentialPattern(Pattern):
    """Simple sequential pattern: PREFIX-0000-0000-0000-INSTANCE"""

    PATTERN_REGEX = re.compile(
        r"^([0-9a-f]{16})-0000-0000-0000-([0-9a-f]{12})$"
    )

    def generate(self, **kwargs: Any) -> str:
        """Generate sequential UUID (stub)."""
        # TODO: Implement sequential UUID generation
        raise NotImplementedError("Sequential pattern generation not yet implemented")

    def decode(self, uuid: str) -> UUIDComponents:
        """Decode sequential UUID (stub)."""
        # TODO: Implement sequential UUID decoding
        raise NotImplementedError("Sequential pattern decoding not yet implemented")

    def validate_format(self, uuid: str) -> bool:
        """Validate sequential UUID format."""
        return bool(self.PATTERN_REGEX.match(uuid))
