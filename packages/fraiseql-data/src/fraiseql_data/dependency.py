"""Dependency graph with better error handling."""

from collections import defaultdict, deque

from fraiseql_data.exceptions import CircularDependencyError, MissingDependencyError


class DependencyGraph:
    """Directed graph for table dependencies."""

    def __init__(self):
        self._graph: dict[str, set[str]] = defaultdict(set)
        self._tables: set[str] = set()
        # table -> dep -> set of FK column names that create this dependency
        self._fk_columns: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))

    def add_table(self, table: str) -> None:
        """Add a table to the graph."""
        self._tables.add(table)
        if table not in self._graph:
            self._graph[table] = set()

    def add_dependency(self, table: str, depends_on: str, *, fk_column: str | None = None) -> None:
        """Add a dependency: table depends on depends_on.

        Args:
            table: Dependent table.
            depends_on: Table that ``table`` depends on.
            fk_column: FK column name that creates this dependency (optional,
                       required for relaxed validation with overrides).
        """
        self._tables.add(table)
        self._tables.add(depends_on)
        self._graph[table].add(depends_on)
        if fk_column is not None:
            self._fk_columns[table][depends_on].add(fk_column)

    def get_dependencies(self, table: str) -> list[str]:
        """Get all tables that this table depends on."""
        return list(self._graph.get(table, set()))

    def topological_sort(self) -> list[str]:
        """
        Sort tables in dependency order using Kahn's algorithm.

        Returns:
            Tables in order such that dependencies come before dependents.

        Raises:
            CircularDependencyError: If circular dependency detected
        """
        # Calculate in-degree (number of tables depending on this table)
        in_degree: dict[str, int] = dict.fromkeys(self._tables, 0)

        for table in self._tables:
            for _dep in self._graph[table]:
                in_degree[table] += 1

        # Start with tables that have no dependencies
        queue = deque([table for table in self._tables if in_degree[table] == 0])
        result = []

        while queue:
            # Process table with no dependencies
            table = queue.popleft()
            result.append(table)

            # For each table that depends on this one, reduce in-degree
            for other_table in self._tables:
                if table in self._graph[other_table]:
                    in_degree[other_table] -= 1
                    if in_degree[other_table] == 0:
                        queue.append(other_table)

        # Check for cycles
        if len(result) != len(self._tables):
            missing = self._tables - set(result)
            raise CircularDependencyError(missing)

        return result

    def validate_plan(
        self,
        tables: list[str],
        overridden_fks: dict[str, set[str]] | None = None,
    ) -> None:
        """Validate that all dependencies are included in plan.

        Dependencies whose FK columns are fully covered by overrides are
        considered satisfied and do not need to be in the plan.

        Args:
            tables: List of table names in the seed plan.
            overridden_fks: ``{table_name: {fk_col, ...}}`` — FK columns that
                have explicit overrides and thus don't need the referenced
                table in the plan.

        Raises:
            MissingDependencyError: If a dependency is missing and not fully
                covered by overrides.
        """
        table_set = set(tables)
        overridden_fks = overridden_fks or {}
        for table in tables:
            for dep in self._graph.get(table, set()):
                if dep not in table_set and not self._all_fks_overridden(
                    table, dep, overridden_fks.get(table, set())
                ):
                    raise MissingDependencyError(table, dep)

    def _all_fks_overridden(self, table: str, dep: str, overrides: set[str]) -> bool:
        """Check if all FK columns from *table* to *dep* are in *overrides*."""
        fk_cols = self._fk_columns.get(table, {}).get(dep, set())
        if not fk_cols:
            return False
        return fk_cols <= overrides
