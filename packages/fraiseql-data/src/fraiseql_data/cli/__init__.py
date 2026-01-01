"""CLI package for fraiseql-data."""

from .config import Config, load_config
from .errors import (
    CLIError,
    DatabaseConnectionError,
    DatabaseURLNotProvidedError,
    DataGenerationError,
    SchemaInspectionError,
    TableNotFoundError,
)
from .formatters import format_output, get_available_formats, get_formatter
from .handlers import GenerateHandler, InspectHandler, SeedHandler
from .logging import get_logger, setup_logging
from .main import cli
from .utils import display_error, get_database_url, mask_database_url, sanitize_error_message

__all__ = [
    # Main CLI
    "cli",
    # Config
    "Config",
    "load_config",
    # Errors
    "CLIError",
    "DataGenerationError",
    "DatabaseConnectionError",
    "DatabaseURLNotProvidedError",
    "SchemaInspectionError",
    "TableNotFoundError",
    # Formatters
    "format_output",
    "get_available_formats",
    "get_formatter",
    # Handlers
    "GenerateHandler",
    "InspectHandler",
    "SeedHandler",
    # Logging
    "get_logger",
    "setup_logging",
    # Utils
    "display_error",
    "get_database_url",
    "mask_database_url",
    "sanitize_error_message",
]
