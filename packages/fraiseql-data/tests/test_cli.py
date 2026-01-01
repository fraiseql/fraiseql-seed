"""Tests for CLI commands and error handling."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from fraiseql_data.cli import (
    CLIError,
    DatabaseConnectionError,
    DatabaseURLNotProvidedError,
    DataGenerationError,
    get_database_url,
    mask_database_url,
    sanitize_error_message,
)
from fraiseql_data.cli.main import cli


class TestSecurityFunctions:
    """Test security-related utility functions."""

    def test_mask_database_url(self):
        """Test password masking in database URLs."""
        url = "postgresql://user:secret123@localhost:5432/testdb"
        masked = mask_database_url(url)
        assert masked == "postgresql://user:***@localhost:5432/testdb"
        assert "secret123" not in masked

    def test_mask_database_url_no_password(self):
        """Test masking when URL has no password."""
        url = "postgresql://localhost/testdb"
        masked = mask_database_url(url)
        # Should not crash, just return as-is or similar
        assert "postgresql://" in masked

    def test_sanitize_error_message(self):
        """Test error message sanitization."""
        url = "postgresql://user:password123@localhost/db"
        error = Exception(f"Connection failed: {url}")
        sanitized = sanitize_error_message(error, url)

        assert "password123" not in sanitized
        assert "***" in sanitized

    def test_sanitize_error_message_patterns(self):
        """Test sanitization of various password patterns."""
        error = Exception("Failed: password=secret123 and user:pass@host")
        sanitized = sanitize_error_message(error)

        assert "secret123" not in sanitized
        assert "password=***" in sanitized
        assert ":***@" in sanitized

    def test_get_database_url_from_argument(self):
        """Test getting database URL from argument."""
        url = "postgresql://localhost/testdb"
        result = get_database_url(url)
        assert result == url

    def test_get_database_url_from_env(self):
        """Test getting database URL from environment variable."""
        url = "postgresql://localhost/testdb"
        with patch.dict(os.environ, {"DATABASE_URL": url}):
            result = get_database_url(None)
            assert result == url

    def test_get_database_url_not_provided(self):
        """Test error when database URL not provided."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(DatabaseURLNotProvidedError) as exc_info:
                get_database_url(None)

            error = exc_info.value
            assert "No database connection provided" in error.message
            assert error.exit_code == 2


class TestCLIErrors:
    """Test custom CLI error types."""

    def test_cli_error_basic(self):
        """Test basic CLIError."""
        error = CLIError("Test error", "Test suggestion", exit_code=5)
        assert error.message == "Test error"
        assert error.suggestion == "Test suggestion"
        assert error.exit_code == 5

    def test_database_connection_error(self):
        """Test DatabaseConnectionError."""
        original = Exception("Connection refused")
        error = DatabaseConnectionError("postgresql://user:***@host/db", original)

        assert "Cannot connect to database" in error.message
        assert error.exit_code == 2
        assert error.original_error is original

    def test_database_url_not_provided_error(self):
        """Test DatabaseURLNotProvidedError."""
        error = DatabaseURLNotProvidedError()
        assert "No database connection provided" in error.message
        assert "DATABASE_URL" in error.suggestion

    def test_data_generation_error(self):
        """Test DataGenerationError."""
        original = Exception("Constraint violation")
        error = DataGenerationError("users", original)

        assert "users" in error.message
        assert error.exit_code == 4
        assert error.original_error is original


class TestCLICommands:
    """Test CLI commands via Click testing."""

    def test_cli_help(self):
        """Test CLI help command."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "fraiseql-data" in result.output
        assert "generate" in result.output
        assert "seed" in result.output
        assert "inspect" in result.output

    def test_cli_version(self):
        """Test CLI version command."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0

    def test_generate_help(self):
        """Test generate command help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["generate", "--help"])
        assert result.exit_code == 0
        assert "Generate test data" in result.output
        assert "--count" in result.output
        assert "--auto-deps" in result.output

    def test_seed_help(self):
        """Test seed command help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["seed", "--help"])
        assert result.exit_code == 0
        assert "Seed database" in result.output
        assert "--database" in result.output
        assert "DATABASE_URL" in result.output

    def test_inspect_help(self):
        """Test inspect command help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["inspect", "--help"])
        assert result.exit_code == 0
        assert "Inspect database schema" in result.output
        assert "--schema" in result.output

    def test_seed_dry_run(self):
        """Test seed command with --dry-run."""
        runner = CliRunner()
        # Dry run doesn't need actual database, but still needs DATABASE_URL or --database
        result = runner.invoke(
            cli, ["seed", "users", "--dry-run", "--database", "postgresql://localhost/test"]
        )
        assert result.exit_code == 0
        assert "DRY RUN MODE" in result.output
        assert "users" in result.output

    def test_seed_missing_database_url(self):
        """Test seed command without database URL."""
        runner = CliRunner()
        # Remove DATABASE_URL from env
        result = runner.invoke(cli, ["seed", "users"], env={"DATABASE_URL": ""})
        assert result.exit_code == 2
        assert "No database connection provided" in result.output


class TestCLIHandlers:
    """Test CLI handler classes."""

    def test_generate_handler_basic(self):
        """Test GenerateHandler with mocked SeedBuilder."""
        from fraiseql_data.cli.handlers import GenerateHandler

        handler = GenerateHandler(quiet=True)

        # Mock SeedBuilder - needs to patch where it's imported
        with patch("fraiseql_data.SeedBuilder") as mock_builder:
            mock_seeds = MagicMock()
            mock_seeds.users = [{"id": 1}, {"id": 2}]
            mock_builder.return_value.execute.return_value = mock_seeds

            seeds = handler.execute(tables=["users"], count=2, auto_deps=False)

            assert seeds is mock_seeds
            mock_builder.assert_called_once()

    def test_generate_handler_with_error(self):
        """Test GenerateHandler error handling."""
        from fraiseql_data.cli.handlers import GenerateHandler

        handler = GenerateHandler(quiet=True)

        with patch("fraiseql_data.SeedBuilder") as mock_builder:
            mock_builder.return_value.execute.side_effect = Exception("Test error")

            with pytest.raises(DataGenerationError) as exc_info:
                handler.execute(tables=["users"], count=2, auto_deps=False)

            error = exc_info.value
            assert "users" in error.message
            assert error.exit_code == 4
