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
from .interactive import InteractiveSession
from .logging import get_logger, setup_logging
from .main import cli
from .utils import display_error, get_database_url, mask_database_url, sanitize_error_message

__all__ = [
    "CLIError",
    "Config",
    "DataGenerationError",
    "DatabaseConnectionError",
    "DatabaseURLNotProvidedError",
    "GenerateHandler",
    "InspectHandler",
    "InteractiveSession",
    "SchemaInspectionError",
    "SeedHandler",
    "TableNotFoundError",
    "cli",
    "display_error",
    "format_output",
    "get_available_formats",
    "get_database_url",
    "get_formatter",
    "get_logger",
    "load_config",
    "mask_database_url",
    "sanitize_error_message",
    "setup_logging",
]
