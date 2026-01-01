"""CLI package for fraiseql-data."""

from .errors import (
    CLIError,
    DatabaseConnectionError,
    DatabaseURLNotProvidedError,
    DataGenerationError,
    SchemaInspectionError,
    TableNotFoundError,
)
from .handlers import GenerateHandler, InspectHandler, SeedHandler
from .main import cli
from .utils import display_error, get_database_url, mask_database_url, sanitize_error_message

__all__ = [
    # Main CLI
    "cli",
    # Errors
    "CLIError",
    "DataGenerationError",
    "DatabaseConnectionError",
    "DatabaseURLNotProvidedError",
    "SchemaInspectionError",
    "TableNotFoundError",
    # Handlers
    "GenerateHandler",
    "InspectHandler",
    "SeedHandler",
    # Utils
    "display_error",
    "get_database_url",
    "mask_database_url",
    "sanitize_error_message",
]
