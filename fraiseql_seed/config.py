"""
Configuration management for fraiseql-seed.

Loads and validates configuration from fraiseql-seed.toml files using Pydantic.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from pydantic import Field
from pydantic_settings import BaseSettings

from fraiseql_seed.core.models import TrinityPattern


class DatabaseConfig(BaseSettings):
    """Database connection configuration."""

    url: str = Field(
        default="postgresql://localhost/myproject_local",
        description="PostgreSQL connection URL",
    )
    schemas: list[str] = Field(
        default=["catalog", "tenant", "management"],
        description="Production schemas to introspect",
    )


class TrinityConfig(BaseSettings):
    """Trinity pattern configuration."""

    pk_prefix: str = Field(default="pk_", description="Primary key column prefix")
    pk_suffix: str = Field(default="", description="Primary key column suffix (optional)")
    id_column: str = Field(default="id", description="UUID identifier column name")
    identifier_column: str = Field(
        default="identifier", description="Business identifier column name"
    )

    def to_trinity_pattern(self) -> TrinityPattern:
        """Convert to TrinityPattern instance."""
        return TrinityPattern(
            pk_prefix=self.pk_prefix,
            pk_suffix=self.pk_suffix,
            id_column=self.id_column,
            identifier_column=self.identifier_column,
        )


class StagingConfig(BaseSettings):
    """Staging schema configuration."""

    schema: str = Field(default="prep_seed", description="Staging schema name")
    table_prefix: str = Field(
        default="tb_", description="Table prefix to include (e.g., tb_*)"
    )
    translation_prefix: str = Field(
        default="tl_", description="Translation table prefix (e.g., tl_*)"
    )
    function_prefix: str = Field(
        default="fn_resolve_", description="Resolution function name prefix"
    )
    output_dir: str = Field(
        default="db/0_schema/019_prep_seed",
        description="Directory for generated staging schema files",
    )


class SeedConfig(BaseSettings):
    """Seed data configuration."""

    data_dir: str = Field(default="db/seed/", description="Directory containing seed SQL files")
    environments: list[str] = Field(
        default=["local", "test", "staging"],
        description="Available seed data environments",
    )
    default_environment: str = Field(
        default="local", description="Default environment for loading"
    )


class ValidationConfig(BaseSettings):
    """Validation configuration."""

    strict_mode: bool = Field(
        default=True, description="Fail on warnings (not just errors)"
    )
    check_fk_integrity: bool = Field(
        default=True, description="Validate foreign key referential integrity"
    )
    check_row_counts: bool = Field(
        default=True, description="Validate staging vs production row counts match"
    )
    check_null_fks: bool = Field(
        default=True,
        description="Check for unexpected NULL values in NOT NULL FK columns",
    )


class Config(BaseSettings):
    """Main configuration for fraiseql-seed."""

    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    trinity: TrinityConfig = Field(default_factory=TrinityConfig)
    staging: StagingConfig = Field(default_factory=StagingConfig)
    seed: SeedConfig = Field(default_factory=SeedConfig)
    validation: ValidationConfig = Field(default_factory=ValidationConfig)

    @classmethod
    def from_toml(cls, path: Path | str) -> Config:
        """
        Load configuration from TOML file.

        Args:
            path: Path to fraiseql-seed.toml file

        Returns:
            Config instance

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config file is invalid
        """
        config_path = Path(path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, "rb") as f:
            data = tomllib.load(f)

        return cls(**data)

    @classmethod
    def find_and_load(cls, start_dir: Optional[Path] = None) -> Config:
        """
        Find and load configuration from fraiseql-seed.toml.

        Searches for fraiseql-seed.toml starting from start_dir and walking up
        parent directories until found or reaching filesystem root.

        Args:
            start_dir: Directory to start search (defaults to current directory)

        Returns:
            Config instance

        Raises:
            FileNotFoundError: If no config file found
        """
        if start_dir is None:
            start_dir = Path.cwd()

        current = Path(start_dir).resolve()

        # Walk up directory tree
        while True:
            config_path = current / "fraiseql-seed.toml"
            if config_path.exists():
                return cls.from_toml(config_path)

            # Check if we've reached filesystem root
            parent = current.parent
            if parent == current:
                break
            current = parent

        raise FileNotFoundError(
            f"No fraiseql-seed.toml found in {start_dir} or parent directories. "
            f"Run 'fraiseql-seed init' to create one."
        )

    def to_toml(self, path: Path | str) -> None:
        """
        Write configuration to TOML file.

        Args:
            path: Path to write fraiseql-seed.toml
        """
        config_path = Path(path)

        # Build TOML content manually for better formatting
        toml_content = f"""# FraiseQL Seed Configuration
# See: https://fraiseql-seed.readthedocs.io/configuration

[database]
url = "{self.database.url}"
schemas = {self.database.schemas}

[trinity]
pk_prefix = "{self.trinity.pk_prefix}"
pk_suffix = "{self.trinity.pk_suffix}"
id_column = "{self.trinity.id_column}"
identifier_column = "{self.trinity.identifier_column}"

[staging]
schema = "{self.staging.schema}"
table_prefix = "{self.staging.table_prefix}"
translation_prefix = "{self.staging.translation_prefix}"
function_prefix = "{self.staging.function_prefix}"
output_dir = "{self.staging.output_dir}"

[seed]
data_dir = "{self.seed.data_dir}"
environments = {self.seed.environments}
default_environment = "{self.seed.default_environment}"

[validation]
strict_mode = {str(self.validation.strict_mode).lower()}
check_fk_integrity = {str(self.validation.check_fk_integrity).lower()}
check_row_counts = {str(self.validation.check_row_counts).lower()}
check_null_fks = {str(self.validation.check_null_fks).lower()}
"""

        config_path.write_text(toml_content)

    def get_output_dir(self) -> Path:
        """Get the output directory as a Path object."""
        return Path(self.staging.output_dir)

    def get_seed_dir(self) -> Path:
        """Get the seed data directory as a Path object."""
        return Path(self.seed.data_dir)


# Default configuration instance
DEFAULT_CONFIG = Config()
