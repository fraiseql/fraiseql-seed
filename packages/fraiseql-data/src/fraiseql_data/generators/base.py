"""Base generator interface."""

from abc import ABC, abstractmethod
from typing import Any


class BaseGenerator(ABC):
    """Base class for data generators."""

    @abstractmethod
    def generate(self, context: Any) -> Any:
        """Generate a value.

        Args:
            context: Generation context

        Returns:
            Generated value
        """
        pass
