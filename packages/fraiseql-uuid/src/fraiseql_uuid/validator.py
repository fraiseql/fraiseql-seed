"""UUID validator."""

from dataclasses import dataclass

from fraiseql_uuid.patterns.base import Pattern


@dataclass
class ValidationResult:
    """UUID validation result."""

    valid: bool
    error: str | None = None
    warnings: list[str] | None = None

    def __post_init__(self) -> None:
        """Initialize warnings list."""
        if self.warnings is None:
            self.warnings = []


class UUIDValidator:
    """UUID validator using a specific pattern."""

    def __init__(self, pattern: Pattern):
        """Initialize validator.

        Args:
            pattern: Pattern instance to use
        """
        self.pattern = pattern

    def validate(self, uuid: str, strict: bool = True) -> ValidationResult:
        """Validate a UUID.

        Args:
            uuid: UUID string to validate
            strict: Enable strict validation

        Returns:
            Validation result
        """
        # Check format
        if not self.pattern.validate_format(uuid):
            return ValidationResult(
                valid=False,
                error=f"Invalid {self.pattern.name} UUID format: {uuid}"
            )

        # TODO: Add component-level validation

        return ValidationResult(valid=True)
