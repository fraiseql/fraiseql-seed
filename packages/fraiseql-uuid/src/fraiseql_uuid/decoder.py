"""UUID decoder."""

from fraiseql_uuid.patterns.base import Pattern, UUIDComponents


class UUIDDecoder:
    """UUID decoder using a specific pattern."""

    def __init__(self, pattern: Pattern):
        """Initialize decoder.

        Args:
            pattern: Pattern instance to use
        """
        self.pattern = pattern

    def decode(self, uuid: str) -> UUIDComponents:
        """Decode a UUID.

        Args:
            uuid: UUID string to decode

        Returns:
            Decoded UUID components
        """
        return self.pattern.decode(uuid)
