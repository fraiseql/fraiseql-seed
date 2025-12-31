"""
fraiseql-uuid - Structured UUID Pattern Library

UUID v4 compliant pattern encoding/decoding for FraiseQL ecosystem.
"""

from fraiseql_uuid.decoder import UUIDDecoder
from fraiseql_uuid.generator import UUIDGenerator
from fraiseql_uuid.patterns import Pattern
from fraiseql_uuid.validator import UUIDValidator

__version__ = "0.1.0"

__all__ = [
    "Pattern",
    "UUIDGenerator",
    "UUIDDecoder",
    "UUIDValidator",
]
