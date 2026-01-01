"""Auto-dependency resolution for seed generation.

This module provides functionality to automatically generate parent dependencies
when seeding data, eliminating the need to manually specify each dependency.

Example:
    >>> # Auto-generate full hierarchy
    >>> builder.add("tb_allocation", count=10, auto_deps=True)
    >>> # Automatically creates: organization → machine → allocation
"""

import logging
from typing import Any

from fraiseql_data.models import SeedPlan

logger = logging.getLogger(__name__)


class AutoDependencyResolver:
    """Resolves auto-dependencies for seed generation.

    This class handles automatic dependency tree building and resolution,
    including multi-path deduplication and conflict detection.

    Args:
        introspector: Database introspector for FK information
        seed_common: SeedCommon instance for baseline data

    Example:
        >>> resolver = AutoDependencyResolver(introspector, seed_common)
        >>> dep_tree = resolver.build_dependency_tree("tb_allocation")
        >>> # Returns: ["tb_organization", "tb_machine"]
    """

    def __init__(self, introspector, seed_common):
        """Initialize resolver with introspector and seed common."""
        self.introspector = introspector
        self.seed_common = seed_common

    def build_dependency_tree(self, table: str) -> list[str]:
        """
        Build dependency tree for a table (recursive FK traversal).

        Uses depth-first search with DAG-based deduplication to build a
        topologically-sorted list of dependencies. When multiple FK paths
        lead to the same table, it appears only once in the result.

        Args:
            table: Table name to build dependency tree for

        Returns:
            List of table names in topological order (root → leaf),
            excluding the target table itself. Deduplicated.

        Example:
            >>> # Schema: allocation → machine → location → organization
            >>> resolver.build_dependency_tree("tb_allocation")
            >>> # Returns: ["tb_organization", "tb_location", "tb_machine"]

            >>> # Multi-path: allocation → machine → org
            >>> #                        → contract → org
            >>> resolver.build_dependency_tree("tb_allocation")
            >>> # Returns: ["tb_organization", "tb_machine", "tb_contract"]
            >>> # (organization appears once despite multiple paths)
        """
        visited = set()
        dependency_list = []

        def visit(current_table: str):
            if current_table in visited:
                return
            visited.add(current_table)

            # Get table info and foreign keys
            table_info = self.introspector.get_table_info(current_table)
            fks = table_info.foreign_keys

            # Visit dependencies first (depth-first)
            for fk in fks:
                # Skip self-referencing FKs
                if fk.referenced_table != current_table:
                    visit(fk.referenced_table)

            # Add current table after dependencies (post-order)
            if current_table != table:  # Don't include target table
                dependency_list.append(current_table)

        visit(table)
        return dependency_list

    def _query_existing_rows(self, table: str, count: int) -> list[dict[str, Any]]:
        """
        Query existing rows from database for reuse.

        Args:
            table: Table name to query
            count: Maximum number of rows to fetch

        Returns:
            List of row dicts (may be less than count if insufficient data)

        Example:
            >>> rows = resolver._query_existing_rows("tb_organization", 5)
            >>> # Returns: [{pk_organization: 1, ...}, {pk_organization: 2, ...}]
        """
        if not self.conn or not self.schema:
            return []

        table_info = self.introspector.get_table_info(table)

        # Find primary key column
        pk_column = None
        for col in table_info.columns:
            if col.is_primary_key:
                pk_column = col.name
                break

        if not pk_column:
            logger.warning(
                f"Cannot reuse rows from '{table}': no primary key found"
            )
            return []

        # Build column list for SELECT
        columns = [col.name for col in table_info.columns if not col.name.startswith("pk_")]

        # Include pk column for ordering
        if pk_column not in columns:
            columns.insert(0, pk_column)

        column_list = ", ".join(columns)

        # Query existing rows ordered by PK
        query = f"""
            SELECT {column_list}
            FROM {self.schema}.{table}
            ORDER BY {pk_column}
            LIMIT {count}
        """

        with self.conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()

        # Convert to list of dicts
        row_dicts = []
        for row in rows:
            row_dict = {}
            for i, col_name in enumerate(columns):
                row_dict[col_name] = row[i]
            row_dicts.append(row_dict)

        logger.debug(
            f"Reused {len(row_dicts)} existing rows from '{table}' "
            f"(requested {count})"
        )

        return row_dicts

    def resolve_dependencies(
        self,
        table: str,
        auto_deps_config: bool | dict[str, int | dict[str, Any]],
        current_plan: list[SeedPlan],
        target_count: int | None = None,
    ) -> list[SeedPlan]:
        """
        Resolve auto-dependencies and return plans to add.

        Builds dependency tree, parses auto_deps configuration, checks for
        conflicts with existing plan, and returns list of SeedPlan objects
        to add for missing dependencies.

        Args:
            table: Target table name
            auto_deps_config: Auto-deps configuration
                - True: Generate 1 of each dependency (minimal)
                - dict: Explicit counts/overrides per table
            current_plan: Existing seed plans (to check for conflicts)
            target_count: Target table count (for warnings if dep > target)
            reuse_existing: Whether to reuse existing database rows

        Returns:
            Tuple of (plans_to_add, reused_data)
            - plans_to_add: List of SeedPlan objects for dependencies to add
            - reused_data: Dict mapping table name to list of reused row dicts

        Raises:
            None - Logs warnings for conflicts/unusual configs

        Example:
            >>> # Minimal auto-deps
            >>> plans = resolver.resolve_dependencies(
            ...     "tb_allocation",
            ...     auto_deps_config=True,
            ...     current_plan=[]
            ... )
            >>> # Returns: [SeedPlan(table="tb_organization", count=1), ...]

            >>> # Explicit counts with overrides
            >>> plans = resolver.resolve_dependencies(
            ...     "tb_allocation",
            ...     auto_deps_config={
            ...         "tb_organization": {
            ...             "count": 2,
            ...             "overrides": {"name": lambda i: f"Org {i}"}
            ...         }
            ...     },
            ...     current_plan=[]
            ... )
            >>> # Returns plans with custom counts/overrides
        """
        # Build dependency tree
        dep_tree = self.build_dependency_tree(table)

        # Get tables already in plan
        plan_tables = {plan.table for plan in current_plan}

        # Parse auto_deps config
        if auto_deps_config is True:
            # Minimal: 1 of each dependency
            dep_config = {}
        elif isinstance(auto_deps_config, dict):
            dep_config = auto_deps_config
        else:
            dep_config = {}

        # Collect plans to add
        plans_to_add = []

        # Add each dependency if not already in plan
        for dep_table in dep_tree:
            if dep_table in plan_tables:
                # Dependency already manually added - check for count conflict
                if dep_table in dep_config:
                    # User specified auto_deps count, but table already in plan
                    existing_plan = next(
                        p for p in current_plan if p.table == dep_table
                    )
                    requested_count = dep_config[dep_table]
                    if isinstance(requested_count, dict):
                        requested_count = requested_count.get("count", 1)

                    if existing_plan.count != requested_count:
                        logger.warning(
                            f"Dependency '{dep_table}' already in plan with "
                            f"count={existing_plan.count}. "
                            f"Ignoring auto_deps count={requested_count}. "
                            f"Using existing count={existing_plan.count}."
                        )
                continue

            # Determine count and overrides for this dependency
            if dep_table in dep_config:
                config = dep_config[dep_table]
                if isinstance(config, dict):
                    # Dict with count and overrides
                    dep_count = config.get("count", 1)
                    dep_overrides = config.get("overrides", {})
                elif isinstance(config, int):
                    # Just a count
                    dep_count = config
                    dep_overrides = {}
                else:
                    dep_count = 1
                    dep_overrides = {}
            else:
                # Default: count=1, no overrides
                dep_count = 1
                dep_overrides = {}

            # Check for unusual counts (warning only, not error)
            if target_count and dep_count > target_count:
                logger.warning(
                    f"Auto-dependency '{dep_table}' count ({dep_count}) exceeds "
                    f"target table '{table}' count ({target_count}). "
                    f"This is unusual but allowed. Most parent rows will have "
                    f"no child rows."
                )

            # Check if seed common provides enough instances
            seed_common_count = self.seed_common.get_instance_offsets().get(
                dep_table, 0
            )

            if seed_common_count >= dep_count:
                # Seed common has enough! No generation needed
                logger.info(
                    f"Auto-dependency '{dep_table}': Using {dep_count} instances "
                    f"from seed common (has {seed_common_count})"
                )
                # Add plan with count=0 (dependency satisfied by seed common)
                plan = SeedPlan(
                    table=dep_table,
                    count=0,
                    strategy="faker",
                    overrides={},
                )
                plans_to_add.append(plan)
            else:
                # Need to generate more beyond seed common
                rows_needed = dep_count - seed_common_count
                if seed_common_count > 0:
                    logger.info(
                        f"Auto-dependency '{dep_table}': Seed common has "
                        f"{seed_common_count}, generating {rows_needed} more "
                        f"(total needed: {dep_count})"
                    )
                else:
                    logger.debug(
                        f"Auto-added dependency: {dep_table} (count={rows_needed}) "
                        f"for {table}"
                    )

                plan = SeedPlan(
                    table=dep_table,
                    count=rows_needed,
                    strategy="faker",
                    overrides=dep_overrides,
                )
                plans_to_add.append(plan)

        return plans_to_add
