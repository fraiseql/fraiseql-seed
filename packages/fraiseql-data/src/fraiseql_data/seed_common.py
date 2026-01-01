"""Seed common baseline management.

This module provides the SeedCommon class for managing seed common baselines,
which define a required foundation layer that all test data builds upon.

Seed common eliminates UUID collisions and provides clear separation between:
- Seed common (instances 1-1,000): Required baseline
- Test data (instances 1,001-999,999): Test-specific data
- Generated data (instances 1,000,000+): Runtime generation
"""

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SeedCommonValidationError(Exception):
    """Raised when seed common validation fails."""

    pass


class SeedCommon:
    """
    Manages seed common baseline data and instance offsets.

    Seed common defines a required baseline layer that all test data
    builds upon. This eliminates UUID collisions and provides a clear
    foundation for test isolation.

    Instance Ranges:
        - 1 - 1,000: Seed common (reserved baseline)
        - 1,001 - 999,999: Test data (test-specific data)
        - 1,000,000+: Generated data (runtime generation)

    Attributes:
        SEED_COMMON_MAX: Maximum instances in seed common (1,000)
        TEST_DATA_START: Starting instance for test data (1,001)
        TEST_DATA_MAX: Maximum instance for test data (999,999)
        GENERATED_DATA_START: Starting instance for generated data (1,000,000)

    Example:
        >>> # Load from YAML
        >>> common = SeedCommon.from_yaml("db/seed_common.yaml")
        >>> offsets = common.get_instance_offsets()
        >>> {'tb_organization': 5, 'tb_machine': 10}
        >>>
        >>> # Get starting instance for test data
        >>> start = common.get_instance_start("tb_organization")
        >>> 1001  # Test data starts after seed common
    """

    # Instance range constants
    SEED_COMMON_MAX = 1_000
    TEST_DATA_START = 1_001
    TEST_DATA_MAX = 999_999
    GENERATED_DATA_START = 1_000_000

    def __init__(
        self,
        instance_offsets: dict[str, int],
        data: dict[str, list[dict]] | None = None,
    ):
        """
        Initialize seed common.

        Args:
            instance_offsets: Table → max instance count (e.g., {'tb_org': 5})
            data: Optional explicit seed data per table

        Raises:
            SeedCommonValidationError: If instance count exceeds SEED_COMMON_MAX
        """
        self._instance_offsets = instance_offsets
        self._data = data or {}

        # Validate instance counts don't exceed max
        for table, count in instance_offsets.items():
            if count > self.SEED_COMMON_MAX:
                raise SeedCommonValidationError(
                    f"Table '{table}' has {count} instances, "
                    f"exceeds seed common maximum {self.SEED_COMMON_MAX:,}"
                )

    @classmethod
    def from_directory(cls, directory: str | Path) -> "SeedCommon":
        """
        Load seed common from directory with environment detection.

        Resolution order:
        1. seed_common.{ENV}.yaml (if FRAISEQL_ENV or ENV is set)
        2. seed_common.yaml (fallback)
        3. seed_common.json
        4. 1_seed_common/*.sql (SQL format fallback)

        Args:
            directory: Directory containing seed common files

        Returns:
            SeedCommon instance

        Raises:
            FileNotFoundError: If no seed common files found

        Example:
            >>> # With ENV=dev, loads seed_common.dev.yaml
            >>> common = SeedCommon.from_directory("db/")
        """
        directory = Path(directory)

        # Check environment variable
        env = os.getenv("FRAISEQL_ENV") or os.getenv("ENV")

        if env:
            # Try environment-specific YAML
            env_yaml = directory / f"seed_common.{env}.yaml"
            if env_yaml.exists():
                logger.info(f"Loading seed common for environment: {env}")
                return cls.from_yaml(env_yaml)

            # Try environment-specific JSON
            env_json = directory / f"seed_common.{env}.json"
            if env_json.exists():
                logger.info(f"Loading seed common for environment: {env} (JSON)")
                return cls.from_json(env_json)

        # Fallback to base YAML
        base_yaml = directory / "seed_common.yaml"
        if base_yaml.exists():
            logger.info("Loading base seed common (YAML)")
            return cls.from_yaml(base_yaml)

        # Fallback to base JSON
        base_json = directory / "seed_common.json"
        if base_json.exists():
            logger.info("Loading base seed common (JSON)")
            return cls.from_json(base_json)

        # Fallback to SQL directory
        sql_dir = directory / "1_seed_common"
        if sql_dir.exists() and sql_dir.is_dir():
            logger.info("Loading seed common from SQL files")
            return cls.from_sql(sql_dir)

        # Nothing found
        raise FileNotFoundError(
            f"No seed common found in {directory}. Expected:\n"
            f"  - seed_common.yaml or seed_common.json\n"
            + (f"  - seed_common.{env}.yaml (if ENV={env})\n" if env else "")
            + f"  - 1_seed_common/ directory (SQL format)"
        )

    @classmethod
    def from_yaml(cls, path: str | Path) -> "SeedCommon":
        """
        Load seed common from YAML file.

        Supports two formats:
        1. Baseline counts: `baseline: {tb_org: 5}`
        2. Explicit data: `tb_org: [{identifier: "org-1", ...}]`

        Args:
            path: Path to YAML file

        Returns:
            SeedCommon instance

        Example:
            >>> common = SeedCommon.from_yaml("db/seed_common.yaml")
        """
        import yaml

        path = Path(path)
        with open(path) as f:
            config = yaml.safe_load(f)

        # Handle Format 1: baseline counts
        if "baseline" in config:
            offsets = config["baseline"]
            return cls(instance_offsets=offsets, data=None)

        # Handle Format 2: explicit data
        offsets = {}
        data = {}
        for table, rows in config.items():
            if table in ("ranges", "config"):  # Reserved keys
                continue
            if not isinstance(rows, list):
                continue

            offsets[table] = len(rows)
            data[table] = rows

        return cls(instance_offsets=offsets, data=data)

    @classmethod
    def from_json(cls, path: str | Path) -> "SeedCommon":
        """
        Load seed common from JSON file.

        Args:
            path: Path to JSON file

        Returns:
            SeedCommon instance

        Example:
            >>> common = SeedCommon.from_json("db/seed_common.json")
        """
        import json

        path = Path(path)
        with open(path) as f:
            config = json.load(f)

        # Handle Format 1: baseline counts
        if "baseline" in config:
            return cls(instance_offsets=config["baseline"], data=None)

        # Handle Format 2: explicit data
        offsets = {}
        data = {}
        for table, rows in config.items():
            if table in ("ranges", "config"):
                continue
            if not isinstance(rows, list):
                continue

            offsets[table] = len(rows)
            data[table] = rows

        return cls(instance_offsets=offsets, data=data)

    @classmethod
    def from_sql(cls, directory: str | Path) -> "SeedCommon":
        """
        Load seed common from SQL directory.

        Parses INSERT statements to extract instance counts from Trinity UUIDs.

        Args:
            directory: Directory containing SQL files

        Returns:
            SeedCommon instance

        Example:
            >>> common = SeedCommon.from_sql("db/1_seed_common/")
        """
        from fraiseql_data.sql_parser import parse_seed_sql

        directory = Path(directory)
        offsets = {}

        for sql_file in sorted(directory.glob("*.sql")):
            tables = parse_seed_sql(sql_file)
            for table, count in tables.items():
                offsets[table] = max(offsets.get(table, 0), count)

        return cls(instance_offsets=offsets, data=None)

    def get_instance_offsets(self) -> dict[str, int]:
        """
        Get instance offset per table (max instance in seed common).

        Returns:
            Dict mapping table name to max instance count

        Example:
            >>> common.get_instance_offsets()
            {'tb_organization': 5, 'tb_machine': 10}
        """
        return self._instance_offsets.copy()

    def get_instance_start(self, table: str) -> int:
        """
        Get starting instance number for new test data.

        Returns TEST_DATA_START (1,001) or offset+1, whichever is higher.
        This ensures test data never collides with seed common.

        Args:
            table: Table name

        Returns:
            Instance number to start at (≥ TEST_DATA_START)

        Example:
            >>> # Seed common has 5 instances
            >>> common.get_instance_start("tb_organization")
            1001  # Test data starts at 1,001
        """
        offset = self._instance_offsets.get(table, 0)

        # Test data starts at TEST_DATA_START (1,001) or after seed common
        return max(self.TEST_DATA_START, offset + 1)

    def is_reserved(self, table: str, instance: int) -> bool:
        """
        Check if instance number is reserved by seed common.

        Args:
            table: Table name
            instance: Instance number to check

        Returns:
            True if instance is in seed common range (1 to offset)

        Example:
            >>> common.is_reserved("tb_organization", 3)
            True  # Instance 3 is in seed common (1-5)
            >>> common.is_reserved("tb_organization", 1001)
            False  # Instance 1001 is test data
        """
        offset = self._instance_offsets.get(table, 0)
        return 1 <= instance <= offset

    def get_data(self, table: str) -> list[dict[str, Any]]:
        """
        Get explicit seed data for table (if defined).

        Args:
            table: Table name

        Returns:
            List of row dicts, or empty list if no explicit data

        Example:
            >>> common.get_data("tb_organization")
            [{'identifier': 'org-1', 'name': 'Org 1'}, ...]
        """
        return self._data.get(table, [])

    def has_explicit_data(self, table: str) -> bool:
        """
        Check if table has explicit data defined.

        Args:
            table: Table name

        Returns:
            True if table has explicit data (Format 2)

        Example:
            >>> common.has_explicit_data("tb_organization")
            True  # Explicit data defined
        """
        return table in self._data

    def validate(self, introspector) -> list[str]:
        """
        Validate seed common consistency.

        Checks:
        - Instance counts within bounds (≤ 1,000)
        - FK references exist
        - FK values within valid range
        - Topological ordering possible (no circular dependencies)

        Args:
            introspector: SchemaIntrospector for FK information

        Returns:
            List of validation errors (empty if valid)

        Example:
            >>> errors = common.validate(introspector)
            >>> if errors:
            ...     raise SeedCommonValidationError("\\n".join(errors))
        """
        errors = []

        # Get dependency graph
        graph = introspector.get_dependency_graph()

        # Check topological order (detect circular dependencies)
        try:
            sorted_tables = graph.topological_sort()
        except Exception as e:
            errors.append(f"Circular dependency or invalid graph: {e}")
            return errors

        # Validate each table's data
        for table in sorted_tables:
            if table not in self._data:
                continue

            table_info = introspector.get_table_info(table)
            rows = self._data[table]

            # Check instance count within bounds
            if len(rows) > self.SEED_COMMON_MAX:
                errors.append(
                    f"Table '{table}' has {len(rows)} rows, "
                    f"exceeds seed common maximum {self.SEED_COMMON_MAX}"
                )

            # Validate FK references
            for i, row in enumerate(rows):
                instance = i + 1

                for fk in table_info.foreign_keys:
                    if fk.column not in row:
                        continue

                    fk_value = row[fk.column]
                    ref_table = fk.referenced_table

                    # Check referenced table exists in seed common
                    if ref_table not in self._data:
                        errors.append(
                            f"Table '{table}' row {instance}: "
                            f"FK '{fk.column}' references '{ref_table}' "
                            f"which is not defined in seed common"
                        )
                        continue

                    # Check referenced instance exists
                    ref_count = len(self._data[ref_table])
                    if fk_value < 1 or fk_value > ref_count:
                        errors.append(
                            f"Table '{table}' row {instance}: "
                            f"FK '{fk.column}' = {fk_value} references "
                            f"'{ref_table}' instance {fk_value}, but only "
                            f"{ref_count} instances exist (valid: 1-{ref_count})"
                        )

        return errors
