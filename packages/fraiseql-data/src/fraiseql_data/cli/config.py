"""Configuration file support for fraiseql-data CLI."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


class Config:
    """Configuration for fraiseql-data CLI.

    Configuration priority (highest to lowest):
    1. Command-line arguments
    2. Environment variables
    3. User config file (~/.fraiseql-data.yaml)
    4. Project config file (.fraiseql-data.yaml in current directory)
    5. Defaults
    """

    def __init__(self, data: dict[str, Any] | None = None):
        """Initialize config.

        Args:
            data: Configuration dictionary
        """
        self.data = data or {}

    @classmethod
    def load(cls) -> Config:
        """Load configuration from files and environment.

        Returns:
            Config instance with merged configuration
        """
        config_data: dict[str, Any] = {}

        # Load project config (.fraiseql-data.yaml in current directory)
        project_config_path = Path.cwd() / ".fraiseql-data.yaml"
        if project_config_path.exists():
            project_data = cls._load_yaml_file(project_config_path)
            if project_data:
                config_data.update(project_data)

        # Load user config (~/.fraiseql-data.yaml)
        user_config_path = Path.home() / ".fraiseql-data.yaml"
        if user_config_path.exists():
            user_data = cls._load_yaml_file(user_config_path)
            if user_data:
                # User config overrides project config
                config_data.update(user_data)

        # Environment variables override file config
        if "DATABASE_URL" in os.environ:
            config_data["database_url"] = os.environ["DATABASE_URL"]

        return cls(config_data)

    @staticmethod
    def _load_yaml_file(path: Path) -> dict[str, Any] | None:
        """Load YAML configuration file.

        Args:
            path: Path to YAML file

        Returns:
            Configuration dictionary or None if failed
        """
        if not YAML_AVAILABLE:
            return None

        try:
            with path.open() as f:
                data = yaml.safe_load(f)
                return data if isinstance(data, dict) else {}
        except Exception:
            # Silently ignore config file errors
            return None

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        return self.data.get(key, default)

    def get_database_url(self) -> str | None:
        """Get database URL from configuration.

        Returns:
            Database URL or None if not configured
        """
        return self.get("database_url")

    def get_default_schema(self) -> str:
        """Get default database schema.

        Returns:
            Default schema name (default: "public")
        """
        return self.get("default_schema", "public")

    def get_database_schema(self) -> str | None:
        """Get database schema from config.

        Returns:
            Schema name if configured, None otherwise
        """
        return self.get("database_schema")

    def get_default_count(self) -> int:
        """Get default row count for data generation.

        Returns:
            Default row count (default: 10)
        """
        return self.get("default_count", 10)

    def get_output_format(self) -> str:
        """Get default output format.

        Returns:
            Default output format (default: "json")
        """
        return self.get("output_format", "json")

    def get_quiet(self) -> bool:
        """Get quiet mode setting.

        Returns:
            Whether quiet mode is enabled (default: False)
        """
        return self.get("quiet", False)

    def get_debug(self) -> bool:
        """Get debug mode setting.

        Returns:
            Whether debug mode is enabled (default: False)
        """
        return self.get("debug", False)

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary.

        Returns:
            Configuration dictionary
        """
        return self.data.copy()


def load_config() -> Config:
    """Load configuration from all sources.

    Returns:
        Config instance
    """
    return Config.load()
