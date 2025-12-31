"""Base pattern interface and models."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class UUIDComponents:
    """Decoded UUID components."""

    raw_uuid: str
    components: dict[str, Any]

    def __getitem__(self, key: str) -> Any:
        """Get component by name."""
        return self.components[key]

    def get(self, key: str, default: Any = None) -> Any:
        """Get component with default."""
        return self.components.get(key, default)


class Pattern(ABC):
    """Base class for UUID patterns."""

    @abstractmethod
    def generate(self, **kwargs: Any) -> str:
        """Generate UUID from components.

        Args:
            **kwargs: Pattern-specific components (table_code, instance, etc.)

        Returns:
            Generated UUID string
        """
        pass

    @abstractmethod
    def decode(self, uuid: str) -> UUIDComponents:
        """Decode UUID into components.

        Args:
            uuid: UUID string to decode

        Returns:
            Decoded UUID components
        """
        pass

    @abstractmethod
    def validate_format(self, uuid: str) -> bool:
        """Validate UUID format.

        Args:
            uuid: UUID string to validate

        Returns:
            True if valid format
        """
        pass
