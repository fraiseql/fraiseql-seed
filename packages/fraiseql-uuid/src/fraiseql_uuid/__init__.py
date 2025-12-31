"""
fraiseql-uuid - Structured UUID Pattern Library

Provides structured UUID encoding/decoding with support for multiple patterns
(PrintOptim, SpecQL, Sequential, Custom).
"""

from fraiseql_uuid.decoder import UUIDDecoder
from fraiseql_uuid.generator import UUIDGenerator
from fraiseql_uuid.patterns.registry import UUIDPatternRegistry
from fraiseql_uuid.validator import UUIDValidator

__version__ = "0.1.0"

__all__ = [
    "UUIDGenerator",
    "UUIDDecoder",
    "UUIDPatternRegistry",
    "UUIDValidator",
]
