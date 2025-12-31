"""Dependency graph and topological sorting."""

from collections import defaultdict, deque


class DependencyGraph:
    """Directed graph for table dependencies."""

    def __init__(self):
        self._graph: dict[str, set[str]] = defaultdict(set)
        self._tables: set[str] = set()

    def add_table(self, table: str) -> None:
        """Add a table to the graph."""
        self._tables.add(table)
        if table not in self._graph:
            self._graph[table] = set()

    def add_dependency(self, table: str, depends_on: str) -> None:
        """Add a dependency: table depends on depends_on."""
        self._tables.add(table)
        self._tables.add(depends_on)
        self._graph[table].add(depends_on)

    def get_dependencies(self, table: str) -> list[str]:
        """Get all tables that this table depends on."""
        return list(self._graph.get(table, set()))

    def topological_sort(self) -> list[str]:
        """
        Sort tables in dependency order using Kahn's algorithm.

        Returns tables in order such that dependencies come before dependents.
        """
        # Calculate in-degree (number of tables depending on this table)
        in_degree: dict[str, int] = {table: 0 for table in self._tables}

        for table in self._tables:
            for dep in self._graph[table]:
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
            raise ValueError(f"Circular dependency detected involving tables: {missing}")

        return result
