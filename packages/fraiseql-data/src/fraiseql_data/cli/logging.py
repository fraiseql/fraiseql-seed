"""Structured logging for fraiseql-data CLI."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.logging import RichHandler

console = Console(stderr=True)


class CLILogger:
    """Structured logger for CLI operations."""

    def __init__(self, name: str = "fraiseql-data", debug: bool = False):
        """Initialize CLI logger.

        Args:
            name: Logger name
            debug: Enable debug mode
        """
        self.name = name
        self.debug = debug
        self._logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        """Set up logger with handlers.

        Returns:
            Configured logger instance
        """
        logger = logging.getLogger(self.name)

        # Set level based on debug mode
        logger.setLevel(logging.DEBUG if self.debug else logging.INFO)

        # Remove existing handlers
        logger.handlers.clear()

        # Add Rich handler for console output
        console_handler = RichHandler(
            console=console,
            rich_tracebacks=True,
            show_time=self.debug,
            show_path=self.debug,
        )
        console_handler.setLevel(logging.DEBUG if self.debug else logging.INFO)
        console_handler.setFormatter(
            logging.Formatter("%(message)s", datefmt="[%X]")
        )
        logger.addHandler(console_handler)

        # Add file handler if debug mode
        if self.debug:
            log_dir = Path.home() / ".fraiseql-data" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "fraiseql-data.log"

            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
            )
            logger.addHandler(file_handler)

            logger.debug(f"Debug logging to: {log_file}")

        return logger

    def debug(self, message: str, **kwargs: Any):
        """Log debug message.

        Args:
            message: Message to log
            **kwargs: Additional context
        """
        if kwargs:
            message = f"{message} | {kwargs}"
        self._logger.debug(message)

    def info(self, message: str, **kwargs: Any):
        """Log info message.

        Args:
            message: Message to log
            **kwargs: Additional context
        """
        if kwargs:
            message = f"{message} | {kwargs}"
        self._logger.info(message)

    def warning(self, message: str, **kwargs: Any):
        """Log warning message.

        Args:
            message: Message to log
            **kwargs: Additional context
        """
        if kwargs:
            message = f"{message} | {kwargs}"
        self._logger.warning(message)

    def error(self, message: str, **kwargs: Any):
        """Log error message.

        Args:
            message: Message to log
            **kwargs: Additional context
        """
        if kwargs:
            message = f"{message} | {kwargs}"
        self._logger.error(message)

    def log_command(self, command: str, args: dict[str, Any]):
        """Log command execution.

        Args:
            command: Command name
            args: Command arguments (sanitized)
        """
        self.debug(f"Executing command: {command}", args=args)

    def log_database_connection(self, masked_url: str, success: bool):
        """Log database connection attempt.

        Args:
            masked_url: Masked database URL
            success: Whether connection succeeded
        """
        if success:
            self.debug(f"Connected to database: {masked_url}")
        else:
            self.error(f"Failed to connect to database: {masked_url}")

    def log_data_generation(self, table: str, count: int, duration_ms: float):
        """Log data generation.

        Args:
            table: Table name
            count: Number of rows generated
            duration_ms: Duration in milliseconds
        """
        self.debug(
            f"Generated {count} rows for {table}",
            duration_ms=f"{duration_ms:.2f}",
        )

    def log_error(self, error: Exception, context: dict[str, Any] | None = None):
        """Log error with context.

        Args:
            error: Exception that occurred
            context: Additional context
        """
        context = context or {}
        self.error(f"Error: {error}", **context)

        if self.debug:
            # Include full traceback in debug mode
            import traceback

            tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
            self.debug(f"Traceback:\n{tb}")


# Global logger instance
_logger: CLILogger | None = None


def get_logger(debug: bool = False) -> CLILogger:
    """Get or create global logger instance.

    Args:
        debug: Enable debug mode

    Returns:
        CLILogger instance
    """
    global _logger
    if _logger is None or _logger.debug != debug:
        _logger = CLILogger(debug=debug)
    return _logger


def setup_logging(debug: bool = False):
    """Set up logging for CLI.

    Args:
        debug: Enable debug mode
    """
    get_logger(debug=debug)
