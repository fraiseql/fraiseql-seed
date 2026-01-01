"""Backend implementations for seed data execution."""

from fraiseql_data.backends.direct import DirectBackend
from fraiseql_data.backends.staging import StagingBackend

__all__ = ["DirectBackend", "StagingBackend"]
