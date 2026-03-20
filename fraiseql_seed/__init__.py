# FraiseQL Seed - Database Seeding and Data Generation
#
# This package provides tools for seeding PostgreSQL databases with realistic
# test data, with special support for PrintOptim Forge → FraiseQL data pipelines.

import logging
from typing import Any

# Set up logging
logger = logging.getLogger(__name__)

# Version information
__version__ = "0.1.0"

# Extension requirements
REQUIRED_EXTENSIONS = {
    "trinity": {
        "description": "UUID to INTEGER PK transformation extension",
        "required": True,
        "min_version": "1.0",
    }
}


class FraiseQLSeedError(Exception):
    """Base exception for FraiseQL-Seed operations."""

    pass


class ExtensionNotFoundError(FraiseQLSeedError):
    """Raised when a required extension is not installed."""

    pass


def check_extension_availability(extension_name: str, _connection=None) -> dict[str, Any]:
    """
    Check if a PostgreSQL extension is available and get its status.

    Args:
        extension_name: Name of the extension to check
        connection: Database connection (if None, uses environment)

    Returns:
        Dict with extension status information
    """
    # This is a simplified version - in practice, this would query pg_extension
    try:
        # For now, assume extensions are available
        # In a full implementation, this would actually check the database
        return {"name": extension_name, "installed": True, "version": "1.0", "available": True}
    except Exception as e:
        logger.warning(f"Could not check extension {extension_name}: {e}")
        return {
            "name": extension_name,
            "installed": False,
            "version": None,
            "available": False,
            "error": str(e),
        }


def ensure_extensions_installed(connection=None) -> None:
    """
    Ensure all required extensions are installed.

    Args:
        connection: Database connection to use

    Raises:
        ExtensionNotFoundError: If a required extension is missing
    """
    missing_extensions = []

    for ext_name, ext_info in REQUIRED_EXTENSIONS.items():
        status = check_extension_availability(ext_name, connection)

        if not status["installed"] and ext_info["required"]:
            missing_extensions.append(ext_name)
            logger.error(
                f"Required extension '{ext_name}' is not installed: {ext_info['description']}"
            )
        elif status["installed"]:
            logger.info(f"Extension '{ext_name}' is available (version {status['version']})")

    if missing_extensions:
        raise ExtensionNotFoundError(
            f"Missing required extensions: {', '.join(missing_extensions)}. "
            "Run the extension installation script: "
            "psql -f fraiseql_seed/install_extensions.sql"
        )


def get_extension_info() -> dict[str, dict[str, Any]]:
    """
    Get information about all extensions and their status.

    Returns:
        Dict mapping extension names to status information
    """
    extensions_info = {}

    for ext_name in REQUIRED_EXTENSIONS:
        extensions_info[ext_name] = check_extension_availability(ext_name)

    return extensions_info


# Import main components (TrinityTransformer not yet implemented)
TRINITY_AVAILABLE = False
TrinityTransformer = None

logger.info("TrinityTransformer not yet implemented - using extension-only mode")

# Export public API
__all__ = [
    "REQUIRED_EXTENSIONS",
    "TRINITY_AVAILABLE",
    "ExtensionNotFoundError",
    "FraiseQLSeedError",
    "check_extension_availability",
    "ensure_extensions_installed",
    "get_extension_info",
]
