"""UUID pattern definitions and registry."""

from fraiseql_uuid.patterns.base import Pattern
from fraiseql_uuid.patterns.printoptim import PrintOptimPattern
from fraiseql_uuid.patterns.registry import UUIDPatternRegistry

__all__ = [
    "Pattern",
    "PrintOptimPattern",
    "UUIDPatternRegistry",
]
