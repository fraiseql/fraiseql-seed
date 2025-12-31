"""UUID pattern definitions and registry."""

from fraiseql_uuid.patterns.base import Pattern
from fraiseql_uuid.patterns.printoptim import PrintOptimPattern
from fraiseql_uuid.patterns.registry import UUIDPatternRegistry
from fraiseql_uuid.patterns.sequential import SequentialPattern
from fraiseql_uuid.patterns.specql import SpecQLPattern

__all__ = [
    "Pattern",
    "PrintOptimPattern",
    "SpecQLPattern",
    "SequentialPattern",
    "UUIDPatternRegistry",
]
