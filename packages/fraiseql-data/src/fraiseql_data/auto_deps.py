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

    Example:
        >>> resolver = AutoDependencyResolver(introspector)
        >>> dep_tree = resolver.build_dependency_tree("tb_allocation")
        >>> # Returns: ["tb_organization", "tb_machine"]
    """

    def __init__(self, introspector):
        """Initialize resolver with introspector."""
        self.introspector = introspector

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

        Returns:
            List of SeedPlan objects for dependencies to add

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

            # Create plan for this dependency
            plan = SeedPlan(
                table=dep_table,
                count=dep_count,
                strategy="faker",
                overrides=dep_overrides,
            )
            plans_to_add.append(plan)

            logger.debug(
                f"Auto-added dependency: {dep_table} (count={dep_count}) "
                f"for {table}"
            )

        return plans_to_add
