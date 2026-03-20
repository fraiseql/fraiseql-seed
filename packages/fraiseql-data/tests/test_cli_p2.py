"""Tests for P2 features: config, formatters, and logging."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fraiseql_data.cli.config import Config, load_config
from fraiseql_data.cli.formatters import (
    CsvFormatter,
    FormatterRegistry,
    JsonFormatter,
    TableFormatter,
    YamlFormatter,
    format_output,
    get_available_formats,
    get_formatter,
)
from fraiseql_data.cli.logging import CLILogger, get_logger, setup_logging


class TestConfig:
    """Test configuration loading and management."""

    def test_config_empty(self):
        """Test empty configuration."""
        config = Config()
        assert config.get("nonexistent") is None
        assert config.get("nonexistent", "default") == "default"

    def test_config_with_data(self):
        """Test configuration with data."""
        config = Config({"database_url": "postgresql://localhost/test", "default_count": 50})
        assert config.get("database_url") == "postgresql://localhost/test"
        assert config.get("default_count") == 50

    def test_get_database_url(self):
        """Test get_database_url method."""
        config = Config({"database_url": "postgresql://localhost/test"})
        assert config.get_database_url() == "postgresql://localhost/test"

        config = Config({})
        assert config.get_database_url() is None

    def test_get_default_schema(self):
        """Test get_default_schema method."""
        config = Config({"default_schema": "custom"})
        assert config.get_default_schema() == "custom"

        config = Config({})
        assert config.get_default_schema() == "public"

    def test_get_default_count(self):
        """Test get_default_count method."""
        config = Config({"default_count": 100})
        assert config.get_default_count() == 100

        config = Config({})
        assert config.get_default_count() == 10

    def test_get_output_format(self):
        """Test get_output_format method."""
        config = Config({"output_format": "csv"})
        assert config.get_output_format() == "csv"

        config = Config({})
        assert config.get_output_format() == "json"

    def test_get_quiet(self):
        """Test get_quiet method."""
        config = Config({"quiet": True})
        assert config.get_quiet() is True

        config = Config({})
        assert config.get_quiet() is False

    def test_get_debug(self):
        """Test get_debug method."""
        config = Config({"debug": True})
        assert config.get_debug() is True

        config = Config({})
        assert config.get_debug() is False

    def test_to_dict(self):
        """Test to_dict method."""
        data = {"database_url": "test", "default_count": 50}
        config = Config(data)
        assert config.to_dict() == data

    def test_load_from_env(self):
        """Test loading config from environment variable."""
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://localhost/env_test"}):
            config = load_config()
            assert config.get_database_url() == "postgresql://localhost/env_test"

    def test_load_from_yaml_file(self):
        """Test loading config from YAML file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / ".fraiseql-data.yaml"
            config_file.write_text(
                """
database_url: postgresql://localhost/yaml_test
default_count: 75
default_schema: test_schema
"""
            )

            with patch("fraiseql_data.cli.config.Path.cwd", return_value=Path(tmpdir)):
                config = load_config()
                assert config.get_database_url() == "postgresql://localhost/yaml_test"
                assert config.get_default_count() == 75
                assert config.get_default_schema() == "test_schema"

    def test_env_overrides_file(self):
        """Test that environment variables override file config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / ".fraiseql-data.yaml"
            config_file.write_text("database_url: postgresql://localhost/file_test")

            with (
                patch("fraiseql_data.cli.config.Path.cwd", return_value=Path(tmpdir)),
                patch.dict(os.environ, {"DATABASE_URL": "postgresql://localhost/env_override"}),
            ):
                config = load_config()
                assert config.get_database_url() == "postgresql://localhost/env_override"


class TestFormatters:
    """Test output formatters."""

    def setup_method(self):
        """Set up test data."""
        self.sample_data = {
            "users": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}],
            "products": [{"id": 10, "title": "Widget"}],
        }

    def test_json_formatter(self):
        """Test JSON formatter."""
        formatter = JsonFormatter()
        assert formatter.get_name() == "json"

        output = formatter.format(self.sample_data)
        assert "users" in output
        assert "Alice" in output
        assert "Bob" in output

    def test_csv_formatter(self):
        """Test CSV formatter."""
        formatter = CsvFormatter()
        assert formatter.get_name() == "csv"

        output = formatter.format(self.sample_data)
        assert "# Table: users" in output
        assert "id,name" in output or "name,id" in output
        assert "Alice" in output
        assert "Bob" in output

    def test_csv_formatter_empty_data(self):
        """Test CSV formatter with empty data."""
        formatter = CsvFormatter()
        output = formatter.format({})
        assert output == ""

    def test_table_formatter(self):
        """Test table formatter."""
        formatter = TableFormatter()
        assert formatter.get_name() == "table"

        output = formatter.format(self.sample_data)
        assert "## users" in output
        assert "Alice" in output
        assert "Bob" in output

    def test_yaml_formatter(self):
        """Test YAML formatter."""
        try:
            import yaml  # noqa: F401

            formatter = YamlFormatter()
            assert formatter.get_name() == "yaml"

            output = formatter.format(self.sample_data)
            assert "users:" in output
            assert "Alice" in output
        except ImportError:
            pytest.skip("PyYAML not installed")

    def test_yaml_formatter_without_pyyaml(self):
        """Test YAML formatter error when PyYAML not available."""
        with patch("fraiseql_data.cli.formatters.YAML_AVAILABLE", False):
            formatter = YamlFormatter()
            with pytest.raises(RuntimeError, match="YAML support not available"):
                formatter.format(self.sample_data)

    def test_formatter_registry(self):
        """Test formatter registry."""
        registry = FormatterRegistry()

        # Check built-in formatters registered
        assert "json" in registry.get_available_formats()
        assert "csv" in registry.get_available_formats()
        assert "table" in registry.get_available_formats()

        # Get formatter
        json_formatter = registry.get("json")
        assert isinstance(json_formatter, JsonFormatter)

    def test_formatter_registry_unknown_format(self):
        """Test error for unknown format."""
        registry = FormatterRegistry()
        with pytest.raises(ValueError, match="Unknown format"):
            registry.get("unknown_format")

    def test_get_formatter(self):
        """Test get_formatter function."""
        formatter = get_formatter("json")
        assert isinstance(formatter, JsonFormatter)

        formatter = get_formatter("csv")
        assert isinstance(formatter, CsvFormatter)

    def test_get_available_formats(self):
        """Test get_available_formats function."""
        formats = get_available_formats()
        assert "json" in formats
        assert "csv" in formats
        assert "table" in formats

    def test_format_output(self):
        """Test format_output function."""
        output = format_output(self.sample_data, "json")
        assert "users" in output

        output = format_output(self.sample_data, "csv")
        assert "# Table: users" in output

    def test_format_with_seeds_object(self):
        """Test formatting with Seeds-like object."""
        # Mock Seeds object
        mock_seeds = MagicMock()
        mock_seeds.to_json.return_value = '{"users": [{"id": 1}]}'
        mock_seeds.to_dict.return_value = {"users": [{"id": 1}]}

        # JSON formatter should use to_json()
        json_formatter = JsonFormatter()
        output = json_formatter.format(mock_seeds)
        assert "users" in output
        mock_seeds.to_json.assert_called_once()

        # CSV formatter should use to_dict()
        csv_formatter = CsvFormatter()
        output = csv_formatter.format(mock_seeds)
        mock_seeds.to_dict.assert_called_once()


class TestLogging:
    """Test structured logging."""

    def test_logger_creation(self):
        """Test logger creation."""
        logger = CLILogger(name="test", debug=False)
        assert logger.name == "test"
        assert logger.debug_mode is False

    def test_logger_debug_mode(self):
        """Test logger in debug mode."""
        logger = CLILogger(name="test", debug=True)
        assert logger.debug_mode is True

    def test_log_methods(self):
        """Test logging methods."""
        logger = CLILogger(name="test", debug=False)

        # Should not raise errors
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")

    def test_log_with_context(self):
        """Test logging with context kwargs."""
        logger = CLILogger(name="test", debug=True)

        # Should not raise errors
        logger.debug("Message", key1="value1", key2="value2")
        logger.info("Message", count=10)

    def test_log_command(self):
        """Test log_command method."""
        logger = CLILogger(name="test", debug=True)
        logger.log_command("generate", {"tables": ["users"], "count": 10})
        # Should not raise error

    def test_log_database_connection(self):
        """Test log_database_connection method."""
        logger = CLILogger(name="test", debug=True)
        logger.log_database_connection("postgresql://user:***@localhost/db", True)
        logger.log_database_connection("postgresql://user:***@localhost/db", False)
        # Should not raise errors

    def test_log_data_generation(self):
        """Test log_data_generation method."""
        logger = CLILogger(name="test", debug=True)
        logger.log_data_generation("users", 100, 1234.56)
        # Should not raise error

    def test_log_error(self):
        """Test log_error method."""
        logger = CLILogger(name="test", debug=True)
        error = Exception("Test error")
        logger.log_error(error, {"command": "seed"})
        # Should not raise error

    def test_get_logger(self):
        """Test get_logger function."""
        logger1 = get_logger(debug=False)
        logger2 = get_logger(debug=False)

        # Should return same instance
        assert logger1 is logger2

    def test_get_logger_debug_change(self):
        """Test get_logger with debug mode change."""
        logger1 = get_logger(debug=False)
        logger2 = get_logger(debug=True)

        # Should create new instance when debug changes
        assert logger1.debug_mode is False
        assert logger2.debug_mode is True

    def test_setup_logging(self):
        """Test setup_logging function."""
        setup_logging(debug=False)
        logger = get_logger()
        assert logger is not None

    def test_debug_log_file_creation(self):
        """Test that debug mode creates log file."""
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            patch("fraiseql_data.cli.logging.Path.home", return_value=Path(tmpdir)),
        ):
            logger = CLILogger(name="test", debug=True)
            logger.info("Test message")

            # Check log directory created
            log_dir = Path(tmpdir) / ".fraiseql-data" / "logs"
            assert log_dir.exists()

            # Check log file created
            log_file = log_dir / "fraiseql-data.log"
            assert log_file.exists()


class TestConfigIntegration:
    """Integration tests for config with other components."""

    def test_config_with_formatters(self):
        """Test config output_format with formatters."""
        config = Config({"output_format": "csv"})
        format_name = config.get_output_format()

        formatter = get_formatter(format_name)
        assert isinstance(formatter, CsvFormatter)

    def test_config_with_logging(self):
        """Test config debug setting with logging."""
        config = Config({"debug": True})
        debug = config.get_debug()

        logger = get_logger(debug=debug)
        assert logger.debug_mode is True
