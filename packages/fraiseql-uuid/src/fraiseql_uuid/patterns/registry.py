"""UUID pattern registry."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fraiseql_uuid.generator import UUIDGenerator

from fraiseql_uuid.patterns.base import Pattern
from fraiseql_uuid.patterns.printoptim import PrintOptimPattern


class UUIDPatternRegistry:
    """Registry for UUID patterns.

    Currently supports one unified UUID v4 compliant pattern that works
    for all FraiseQL/PrintOptim use cases.
    """

    BUILTIN_PATTERNS: dict[str, type[Pattern]] = {
        "printoptim": PrintOptimPattern,
    }

    def __init__(self) -> None:
        """Initialize registry."""
        self.patterns: dict[str, Pattern] = {}

    @classmethod
    def load(cls, pattern_name: str, config: dict[str, Any] | None = None) -> Pattern:
        """Load a pattern by name.

        Args:
            pattern_name: Name of pattern ('printoptim')
            config: Optional pattern configuration

        Returns:
            Pattern instance (UUID v4 compliant)

        Raises:
            ValueError: If pattern name is not recognized

        Example:
            >>> pattern = UUIDPatternRegistry.load('printoptim')
            >>> uuid = pattern.generate(table_code='012345', instance=1)
        """
        if pattern_name not in cls.BUILTIN_PATTERNS:
            raise ValueError(
                f"Unknown pattern: {pattern_name}. "
                f"Available: {', '.join(cls.BUILTIN_PATTERNS.keys())}"
            )

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
