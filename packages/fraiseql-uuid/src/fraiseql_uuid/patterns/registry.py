"""UUID pattern registry."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fraiseql_uuid.generator import UUIDGenerator

from fraiseql_uuid.patterns.base import Pattern
from fraiseql_uuid.patterns.printoptim import PrintOptimPattern
from fraiseql_uuid.patterns.sequential import SequentialPattern
from fraiseql_uuid.patterns.specql import SpecQLPattern


class UUIDPatternRegistry:
    """Registry for UUID patterns."""

    BUILTIN_PATTERNS: dict[str, type[Pattern]] = {
        "printoptim": PrintOptimPattern,
        "specql": SpecQLPattern,
        "sequential": SequentialPattern,
    }

    def __init__(self) -> None:
        """Initialize registry."""
        self.patterns: dict[str, Pattern] = {}

    @classmethod
    def load(cls, pattern_name: str, config: dict[str, Any] | None = None) -> Pattern:
        """Load a pattern by name.

        Args:
            pattern_name: Name of pattern (printoptim, specql, sequential)
            config: Optional pattern configuration

        Returns:
            Pattern instance
        """
        if pattern_name not in cls.BUILTIN_PATTERNS:
            raise ValueError(f"Unknown pattern: {pattern_name}")

        pattern_class = cls.BUILTIN_PATTERNS[pattern_name]
        pattern_config = config or {"name": pattern_name}
        return pattern_class(pattern_config)

    def register(self, name: str, pattern: Pattern) -> None:
        """Register a custom pattern.

        Args:
            name: Pattern name
            pattern: Pattern instance
        """
        self.patterns[name] = pattern

    def get_generator(self, table_name: str, **kwargs: Any) -> "UUIDGenerator":
        """Get UUID generator for a table (stub).

        Args:
            table_name: Table name (e.g., "catalog.tb_manufacturer")
            **kwargs: Pattern-specific configuration

        Returns:
            UUIDGenerator instance
        """
        # TODO: Implement generator creation
        raise NotImplementedError("Generator creation not yet implemented")
