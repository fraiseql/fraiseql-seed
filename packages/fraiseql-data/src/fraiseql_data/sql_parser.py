"""Parse SQL seed files to extract instance counts.

This module provides utilities for parsing SQL INSERT statements to extract
Trinity pattern UUID instances and build instance count mappings.
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def parse_seed_sql(sql_file: Path) -> dict[str, int]:
    """
    Parse SQL file to extract table instance counts.

    Looks for Trinity pattern UUIDs to determine max instance per table.
    Trinity UUID format: 2a6f3c21-0000-4000-8000-{instance:012d}

    Args:
        sql_file: Path to SQL file

    Returns:
        Dict mapping table name to max instance count

    Example:
        >>> parse_seed_sql("01_organizations.sql")
        {'tb_organization': 5, 'tb_machine': 10}

        >>> # SQL file contains:
        >>> # INSERT INTO tb_organization (id, ...) VALUES
        >>> #   ('2a6f3c21-0000-4000-8000-000000000001', ...),
        >>> #   ('2a6f3c21-0000-4000-8000-000000000002', ...),
        >>> #   ('2a6f3c21-0000-4000-8000-000000000005', ...);
        >>> # Returns: {'tb_organization': 5}  # Max instance is 5
    """
    content = sql_file.read_text()

    # Trinity UUID pattern: 2a6f3c21-0000-4000-8000-{instance:012d}
    uuid_pattern = r"'2a6f3c21-0000-4000-8000-(\d{12})'"

    # Extract INSERT statements
    # Pattern matches: INSERT INTO [schema.]table
    insert_pattern = r"INSERT\s+INTO\s+(?:(\w+)\.)?(\w+)"

    tables = {}

    # Find all INSERT statements
    for match in re.finditer(insert_pattern, content, re.IGNORECASE):
        schema = match.group(1)  # Optional schema
        table = match.group(2)

        # Find UUIDs in this INSERT block
        # Extract block until next INSERT or end of file
        insert_start = match.start()
        next_insert = re.search(
            r"INSERT\s+INTO", content[insert_start + 50 :], re.IGNORECASE
        )

        if next_insert:
            insert_block = content[insert_start : insert_start + 50 + next_insert.start()]
        else:
            insert_block = content[insert_start:]

        # Extract all instance numbers from UUIDs
        instances = []
        for uuid_match in re.finditer(uuid_pattern, insert_block):
            instance = int(uuid_match.group(1))
            instances.append(instance)

        if instances:
            max_instance = max(instances)
            tables[table] = max(tables.get(table, 0), max_instance)
            logger.debug(
                f"Found {len(instances)} instances in '{table}' (max: {max_instance})"
            )

    return tables
