# Phase 1-REFACTOR: Optimization and Polish

**Phase**: REFACTOR (Optimize and Clean Up)
**Component**: fraiseql-data
**Objective**: Optimize implementation, improve error handling, and polish API without changing behavior

---

## Context

Phase 1-GREEN implemented the minimal functionality to pass tests. This phase focuses on:
1. **Performance optimization** - Bulk inserts, caching
2. **Error handling** - Clear error messages with helpful suggestions
3. **Code quality** - Remove duplication, improve readability
4. **API polish** - Better type hints, docstrings

**IMPORTANT**: All existing tests must continue to pass. No behavioral changes.

---

## Files to Modify

```
src/fraiseql_data/
├── introspection.py          # Add caching, optimize queries
├── generators.py             # Better error messages
├── builder.py                # Bulk insert optimization
├── decorators.py             # Cleaner fixture injection
└── exceptions.py             # NEW: Custom exceptions
```

---

## Implementation Steps

### Step 1: Add Custom Exceptions

```python
# src/fraiseql_data/exceptions.py
"""Custom exceptions with helpful error messages."""


class FraiseQLDataError(Exception):
    """Base exception for fraiseql-data errors."""

    pass


class SchemaNotFoundError(FraiseQLDataError):
    """Schema does not exist in database."""

    def __init__(self, schema: str):
        super().__init__(
            f"Schema '{schema}' not found in database.\n\n"
            f"Suggestions:\n"
            f"1. Check schema name spelling\n"
            f"2. Ensure schema exists: CREATE SCHEMA {schema};\n"
            f"3. Check database connection settings"
        )


class TableNotFoundError(FraiseQLDataError):
    """Table does not exist in schema."""

    def __init__(self, table: str, schema: str):
        super().__init__(
            f"Table '{table}' not found in schema '{schema}'.\n\n"
            f"Suggestions:\n"
            f"1. Check table name spelling\n"
            f"2. Use SchemaIntrospector.get_tables() to see available tables\n"
            f"3. Ensure table exists: CREATE TABLE {schema}.{table} (...);"
        )


class ColumnGenerationError(FraiseQLDataError):
    """Could not auto-generate data for column."""

    def __init__(self, column: str, pg_type: str, table: str):
        super().__init__(
            f"Could not auto-generate data for column '{column}' (type: {pg_type}) in table '{table}'.\n\n"
            f"Suggestions:\n"
            f"1. Provide override:\n"
            f"   builder.add('{table}', count=5, overrides={{\n"
            f"       '{column}': lambda: your_custom_value()\n"
            f"   }})\n\n"
            f"2. Use custom generator:\n"
            f"   from faker import Faker\n"
            f"   fake = Faker()\n"
            f"   builder.add('{table}', overrides={{\n"
            f"       '{column}': lambda: fake.your_method()\n"
            f"   }})"
        )


class CircularDependencyError(FraiseQLDataError):
    """Circular dependency detected in table relationships."""

    def __init__(self, tables: set[str]):
        tables_str = ", ".join(sorted(tables))
        super().__init__(
            f"Circular dependency detected involving tables: {tables_str}\n\n"
            f"Suggestions:\n"
            f"1. Check foreign key relationships for cycles\n"
            f"2. If self-referencing table, this will be supported in Phase 2\n"
            f"3. Temporarily remove FK constraint, seed data, then re-add constraint"
        )


class MissingDependencyError(FraiseQLDataError):
    """Table depends on another table that is not in seed plan."""

    def __init__(self, table: str, dependency: str):
        super().__init__(
            f"Table '{table}' depends on '{dependency}', but '{dependency}' is not in seed plan.\n\n"
            f"Suggestions:\n"
            f"1. Add dependency to seed plan:\n"
            f"   builder.add('{dependency}', count=N)\n"
            f"   builder.add('{table}', count=M)\n\n"
            f"2. Or use decorator:\n"
            f"   @seed_data('{dependency}', count=N)\n"
            f"   @seed_data('{table}', count=M)\n"
            f"   def test_fn(seeds): ..."
        )


class ForeignKeyResolutionError(FraiseQLDataError):
    """Could not resolve foreign key reference."""

    def __init__(self, fk_column: str, referenced_table: str):
        super().__init__(
            f"Could not resolve foreign key '{fk_column}' referencing '{referenced_table}'.\n\n"
            f"Suggestions:\n"
            f"1. Ensure '{referenced_table}' is seeded before this table\n"
            f"2. Check that '{referenced_table}' has generated data\n"
            f"3. Verify foreign key constraint is correct"
        )
```

### Step 2: Optimize Schema Introspection

```python
# src/fraiseql_data/introspection.py (optimizations)
"""Schema introspection with caching and optimized queries."""

from psycopg import Connection
from fraiseql_data.models import TableInfo, ColumnInfo, ForeignKeyInfo
from fraiseql_data.dependency import DependencyGraph
from fraiseql_data.exceptions import SchemaNotFoundError, TableNotFoundError


class SchemaIntrospector:
    """Introspect PostgreSQL schema with caching."""

    def __init__(self, conn: Connection, schema: str):
        self.conn = conn
        self.schema = schema
        self._table_cache: dict[str, TableInfo] = {}
        self._dependency_graph_cache: DependencyGraph | None = None

        # Validate schema exists
        self._validate_schema()

    def _validate_schema(self) -> None:
        """Validate that schema exists in database."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT EXISTS(SELECT 1 FROM information_schema.schemata WHERE schema_name = %s)",
                (self.schema,),
            )
            exists = cur.fetchone()[0]
            if not exists:
                raise SchemaNotFoundError(self.schema)

    def get_tables(self) -> list[TableInfo]:
        """Get all tables in schema (cached)."""
        # If cache is populated, use it
        if self._table_cache:
            return list(self._table_cache.values())

        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = %s
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name
                """,
                (self.schema,),
            )
            rows = cur.fetchall()

        # Populate cache
        return [self.get_table_info(row[0]) for row in rows]

    def get_table_info(self, table_name: str) -> TableInfo:
        """Get complete table information (cached)."""
        if table_name in self._table_cache:
            return self._table_cache[table_name]

        # Validate table exists
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT EXISTS(
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = %s AND table_name = %s
                )
                """,
                (self.schema, table_name),
            )
            exists = cur.fetchone()[0]
            if not exists:
                raise TableNotFoundError(table_name, self.schema)

        columns = self.get_columns(table_name)
        foreign_keys = self.get_foreign_keys(table_name)

        table_info = TableInfo(name=table_name, columns=columns, foreign_keys=foreign_keys)
        self._table_cache[table_name] = table_info
        return table_info

    def get_columns(self, table_name: str) -> list[ColumnInfo]:
        """Get all columns for a table (optimized single query)."""
        with self.conn.cursor() as cur:
            # Single query to get columns + PK info
            cur.execute(
                """
                SELECT
                    c.column_name,
                    c.data_type,
                    c.is_nullable,
                    c.column_default,
                    CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END as is_pk
                FROM information_schema.columns c
                LEFT JOIN (
                    SELECT kcu.column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                      ON tc.constraint_name = kcu.constraint_name
                      AND tc.table_schema = kcu.table_schema
                    WHERE tc.constraint_type = 'PRIMARY KEY'
                      AND tc.table_schema = %s
                      AND tc.table_name = %s
                ) pk ON c.column_name = pk.column_name
                WHERE c.table_schema = %s
                  AND c.table_name = %s
                ORDER BY c.ordinal_position
                """,
                (self.schema, table_name, self.schema, table_name),
            )
            rows = cur.fetchall()

        return [
            ColumnInfo(
                name=row[0],
                pg_type=row[1],
                is_nullable=row[2] == "YES",
                default_value=row[3],
                is_primary_key=row[4],
            )
            for row in rows
        ]

    def get_foreign_keys(self, table_name: str) -> list[ForeignKeyInfo]:
        """Get all foreign keys for a table."""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    kcu.column_name,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                  ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                  ON ccu.constraint_name = tc.constraint_name
                  AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_schema = %s
                  AND tc.table_name = %s
                """,
                (self.schema, table_name),
            )
            rows = cur.fetchall()

        return [
            ForeignKeyInfo(column=row[0], referenced_table=row[1], referenced_column=row[2])
            for row in rows
        ]

    def get_dependency_graph(self) -> DependencyGraph:
        """Build dependency graph (cached)."""
        if self._dependency_graph_cache is not None:
            return self._dependency_graph_cache

        tables = self.get_tables()
        graph = DependencyGraph()

        for table in tables:
            graph.add_table(table.name)
            for fk in table.foreign_keys:
                # Skip self-references for now (Phase 2)
                if fk.referenced_table != table.name:
                    graph.add_dependency(table.name, fk.referenced_table)

        self._dependency_graph_cache = graph
        return graph

    def topological_sort(self) -> list[str]:
        """Sort tables in dependency order."""
        graph = self.get_dependency_graph()
        return graph.topological_sort()

    def clear_cache(self) -> None:
        """Clear cached introspection data."""
        self._table_cache.clear()
        self._dependency_graph_cache = None
```

### Step 3: Improve Dependency Graph Error Handling

```python
# src/fraiseql_data/dependency.py (add to existing)
"""Dependency graph with better error handling."""

from collections import defaultdict, deque
from fraiseql_data.exceptions import CircularDependencyError


class DependencyGraph:
    """Directed graph for table dependencies."""

    # ... (existing code) ...

    def topological_sort(self) -> list[str]:
        """
        Sort tables in dependency order using Kahn's algorithm.

        Raises:
            CircularDependencyError: If circular dependency detected
        """
        # Calculate in-degree
        in_degree: dict[str, int] = {table: 0 for table in self._tables}

        for table in self._tables:
            for dep in self._graph[table]:
                in_degree[table] += 1

        # Start with tables that have no dependencies
        queue = deque([table for table in self._tables if in_degree[table] == 0])
        result = []

        while queue:
            table = queue.popleft()
            result.append(table)

            # Reduce in-degree for dependents
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

    def validate_plan(self, tables: list[str]) -> None:
        """
        Validate that all dependencies are included in plan.

        Raises:
            MissingDependencyError: If a dependency is missing
        """
        from fraiseql_data.exceptions import MissingDependencyError

        table_set = set(tables)
        for table in tables:
            for dep in self._graph.get(table, set()):
                if dep not in table_set:
                    raise MissingDependencyError(table, dep)
```

### Step 4: Optimize SeedBuilder (Bulk Inserts)

```python
# src/fraiseql_data/builder.py (optimizations)
"""Optimized SeedBuilder with bulk operations."""

from typing import Any
from psycopg import Connection
from fraiseql_uuid import Pattern

from fraiseql_data.introspection import SchemaIntrospector
from fraiseql_data.models import SeedPlan, Seeds
from fraiseql_data.generators import FakerGenerator, TrinityGenerator
from fraiseql_data.backends.direct import DirectBackend
from fraiseql_data.exceptions import MissingDependencyError


class SeedBuilder:
    """Optimized declarative API for seed generation."""

    def __init__(self, conn: Connection, schema: str):
        self.conn = conn
        self.schema = schema
        self.introspector = SchemaIntrospector(conn, schema)
        self.backend = DirectBackend(conn, schema)
        self.pattern = Pattern()
        self._plan: list[SeedPlan] = []

    def add(
        self,
        table: str,
        count: int,
        strategy: str = "faker",
        overrides: dict[str, Any] | None = None,
    ) -> "SeedBuilder":
        """Add a table to the seed plan."""
        # Validate table exists
        _ = self.introspector.get_table_info(table)  # Raises if not found

        self._plan.append(
            SeedPlan(
                table=table,
                count=count,
                strategy=strategy,
                overrides=overrides or {},
            )
        )
        return self

    def execute(self) -> Seeds:
        """Execute the seed plan with validation and optimization."""
        # Validate plan dependencies
        graph = self.introspector.get_dependency_graph()
        plan_tables = [p.table for p in self._plan]
        graph.validate_plan(plan_tables)

        # Sort plan by dependencies
        sorted_tables = self.introspector.topological_sort()
        plan_by_table = {p.table: p for p in self._plan}

        # Filter to only tables in plan, in dependency order
        sorted_plan = [
            plan_by_table[table] for table in sorted_tables if table in plan_by_table
        ]

        seeds = Seeds()
        generated_data: dict[str, list[dict[str, Any]]] = {}

        # Execute plan
        for plan in sorted_plan:
            table_info = self.introspector.get_table_info(plan.table)
            rows = self._generate_rows(table_info, plan, generated_data)

            # Bulk insert (optimized)
            inserted_rows = self.backend.insert_rows(table_info, rows)

            # Store for FK resolution
            generated_data[plan.table] = inserted_rows
            seeds.add_table(plan.table, inserted_rows)

        return seeds

    def _generate_rows(
        self,
        table_info,
        plan: SeedPlan,
        generated_data: dict[str, list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        """Generate rows with better error handling."""
        from fraiseql_data.exceptions import ForeignKeyResolutionError

        faker_gen = FakerGenerator()
        trinity_gen = TrinityGenerator(self.pattern, table_info.name)

        rows = []
        for i in range(1, plan.count + 1):
            row: dict[str, Any] = {}

            # Generate data for each column
            for col in table_info.columns:
                # Skip pk_* IDENTITY columns
                if col.is_primary_key and col.name.startswith("pk_"):
                    continue

                # Skip Trinity columns (added later)
                if col.name in ("id", "identifier"):
                    continue

                # Handle foreign keys
                if any(fk.column == col.name for fk in table_info.foreign_keys):
                    fk = next(fk for fk in table_info.foreign_keys if fk.column == col.name)

                    # Resolve FK
                    if fk.referenced_table not in generated_data:
                        raise ForeignKeyResolutionError(fk.column, fk.referenced_table)

                    import random
                    parent_row = random.choice(generated_data[fk.referenced_table])
                    row[col.name] = parent_row[fk.referenced_column]
                    continue

                # Check for override
                if col.name in plan.overrides:
                    override = plan.overrides[col.name]
                    if callable(override):
                        # Check if callable expects instance argument
                        import inspect
                        sig = inspect.signature(override)
                        if len(sig.parameters) > 0:
                            row[col.name] = override(i)
                        else:
                            row[col.name] = override()
                    else:
                        row[col.name] = override
                    continue

                # Generate using Faker
                if plan.strategy == "faker":
                    row[col.name] = faker_gen.generate(col.name, col.pg_type)

            # Add Trinity columns
            if table_info.is_trinity:
                trinity_data = trinity_gen.generate(i, **row)
                row.update(trinity_data)

            rows.append(row)

        return rows
```

### Step 5: Improve Decorator

```python
# src/fraiseql_data/decorators.py (refactored)
"""Cleaner pytest decorator implementation."""

import functools
from typing import Any, Callable
from psycopg import Connection

from fraiseql_data.builder import SeedBuilder


def seed_data(
    table: str,
    count: int,
    strategy: str = "faker",
    overrides: dict[str, Any] | None = None,
):
    """
    Pytest decorator for automatic seed data generation.

    Args:
        table: Table name to seed
        count: Number of rows to generate
        strategy: Generation strategy ('faker' or custom)
        overrides: Column overrides

    Usage:
        @seed_data("tb_manufacturer", count=5)
        def test_api(seeds, db_conn, test_schema):
            assert len(seeds.tb_manufacturer) == 5
    """

    def decorator(func: Callable) -> Callable:
        # Store seed plans on function
        if not hasattr(func, "_seed_plans"):
            func._seed_plans = []

        func._seed_plans.append(
            {
                "table": table,
                "count": count,
                "strategy": strategy,
                "overrides": overrides or {},
            }
        )

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Extract fixtures from kwargs
            db_conn = kwargs.get("db_conn")
            test_schema = kwargs.get("test_schema")

            if db_conn is None or test_schema is None:
                raise ValueError(
                    "seed_data decorator requires 'db_conn' and 'test_schema' pytest fixtures.\n\n"
                    "Make sure your test has these parameters:\n"
                    "  def test_fn(seeds, db_conn, test_schema):\n"
                    "      ...\n\n"
                    "Or define these fixtures in conftest.py."
                )

            # Build and execute seeds
            builder = SeedBuilder(db_conn, schema=test_schema)
            for plan in func._seed_plans:
                builder.add(
                    plan["table"],
                    count=plan["count"],
                    strategy=plan["strategy"],
                    overrides=plan["overrides"],
                )
            seeds = builder.execute()

            # Inject seeds
            kwargs["seeds"] = seeds

            # Call original function
            try:
                return func(*args, **kwargs)
            finally:
                # Cleanup happens via transaction rollback in fixture
                pass

        return wrapper

    return decorator
```

### Step 6: Add Docstrings and Type Hints

```python
# src/fraiseql_data/models.py (add comprehensive docstrings)
"""Data models with complete type hints and documentation."""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass
class ColumnInfo:
    """
    Column metadata from database introspection.

    Attributes:
        name: Column name
        pg_type: PostgreSQL data type
        is_nullable: Whether column allows NULL
        is_primary_key: Whether column is part of primary key
        default_value: Default value expression (if any)
    """

    name: str
    pg_type: str
    is_nullable: bool
    is_primary_key: bool = False
    default_value: str | None = None


# ... (add docstrings to all other classes)
```

---

## Verification

### ✅ Verification Commands

```bash
# All existing tests should still pass
uv run pytest tests/ -v

# Type checking should pass with no errors
uv run mypy src/ --strict

# Linting should pass
uv run ruff check src/

# Test error messages
uv run pytest tests/ -v --tb=short  # Check error output quality
```

### 📊 Expected Output

```bash
$ uv run pytest tests/ -v
==================== 20 passed in 1.80s ===========================
# Note: Should be FASTER than Phase 1-GREEN due to optimizations

$ uv run mypy src/ --strict
Success: no issues found in 10 source files

$ uv run ruff check src/
All checks passed!
```

---

## Acceptance Criteria

- ✅ All Phase 1-RED tests still pass (no behavioral changes)
- ✅ Performance improved (faster test execution)
- ✅ Error messages are clear and helpful
- ✅ Type hints pass mypy --strict
- ✅ No code duplication
- ✅ Comprehensive docstrings
- ✅ Custom exceptions with suggestions
- ✅ Caching reduces redundant database queries

---

## DO NOT

- ❌ Change test behavior (all tests must still pass)
- ❌ Add new features (only optimize existing)
- ❌ Skip type hints or docstrings
- ❌ Over-optimize (premature optimization)

---

## Notes

- Caching significantly improves performance for multi-table seeds
- Bulk insert optimization can be added in Phase 2 if needed
- Error messages are critical for LLM debugging
- Type hints enable better IDE support for users

---

**Status**: Ready for implementation
**Next Phase**: Phase 1-QA (Integration tests and edge cases)
**Expected Test Results**: All tests should PASS (faster than before)
