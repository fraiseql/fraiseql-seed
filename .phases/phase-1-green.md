# Phase 1-GREEN: Core Implementation

**Phase**: GREEN (Make Tests Pass)
**Component**: fraiseql-data
**Objective**: Implement core functionality to make all Phase 1-RED tests pass

---

## Context

Implement the "Zero-Guessing Core" functionality:
1. Schema introspection (PostgreSQL information_schema)
2. Data generators (Faker, Pattern UUID, Sequential, Trinity)
3. Dependency resolution (topological sort)
4. SeedBuilder API (declarative seed generation)
5. pytest decorator (`@seed_data()`)

All implementations should be **minimal** - just enough to make tests pass. Optimization comes in REFACTOR phase.

---

## Files to Create

```
src/fraiseql_data/
├── introspection.py          # Schema introspection
├── generators.py             # Data generation strategies
├── dependency.py             # Dependency graph & topological sort
├── builder.py                # SeedBuilder API
├── decorators.py             # @seed_data() decorator
├── models.py                 # Data models (TableInfo, Seeds, etc.)
└── backends/
    ├── __init__.py
    └── direct.py             # Direct INSERT backend
```

---

## Implementation Steps

### Step 1: Data Models

```python
# src/fraiseql_data/models.py
"""Data models and type definitions."""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass
class ColumnInfo:
    """Column metadata from database introspection."""

    name: str
    pg_type: str
    is_nullable: bool
    is_primary_key: bool = False
    default_value: str | None = None


@dataclass
class ForeignKeyInfo:
    """Foreign key relationship metadata."""

    column: str
    referenced_table: str
    referenced_column: str


@dataclass
class TableInfo:
    """Table metadata with Trinity pattern detection."""

    name: str
    columns: list[ColumnInfo]
    foreign_keys: list[ForeignKeyInfo] = field(default_factory=list)

    @property
    def is_trinity(self) -> bool:
        """Check if table follows Trinity pattern (pk_*, id, identifier)."""
        col_names = {c.name for c in self.columns}
        has_pk = any(c.name.startswith("pk_") and c.is_primary_key for c in self.columns)
        has_id = "id" in col_names
        has_identifier = "identifier" in col_names
        return has_pk and has_id and has_identifier

    @property
    def pk_column(self) -> str | None:
        """Get primary key column name."""
        for col in self.columns:
            if col.is_primary_key:
                return col.name
        return None

    @property
    def id_column(self) -> str | None:
        """Get UUID id column name (Trinity pattern)."""
        if "id" in {c.name for c in self.columns}:
            return "id"
        return None

    @property
    def identifier_column(self) -> str | None:
        """Get identifier column name (Trinity pattern)."""
        if "identifier" in {c.name for c in self.columns}:
            return "identifier"
        return None


@dataclass
class SeedRow:
    """A single row of seed data."""

    _data: dict[str, Any]

    def __getattr__(self, name: str) -> Any:
        """Allow attribute access to column values."""
        if name.startswith("_"):
            raise AttributeError(f"No attribute '{name}'")
        if name in self._data:
            return self._data[name]
        raise AttributeError(f"No column '{name}' in seed data")


class Seeds:
    """Container for generated seed data."""

    def __init__(self):
        self._tables: dict[str, list[SeedRow]] = {}

    def add_table(self, table_name: str, rows: list[dict[str, Any]]) -> None:
        """Add seed data for a table."""
        self._tables[table_name] = [SeedRow(_data=row) for row in rows]

    def __getattr__(self, name: str) -> list[SeedRow]:
        """Allow attribute access to tables."""
        if name.startswith("_"):
            raise AttributeError(f"No attribute '{name}'")
        if name in self._tables:
            return self._tables[name]
        raise AttributeError(f"No table '{name}' in seeds")


@dataclass
class SeedPlan:
    """Plan for generating seed data for a single table."""

    table: str
    count: int
    strategy: str = "faker"
    overrides: dict[str, Any] = field(default_factory=dict)
```

### Step 2: Schema Introspection

```python
# src/fraiseql_data/introspection.py
"""Schema introspection using PostgreSQL information_schema."""

from psycopg import Connection
from fraiseql_data.models import TableInfo, ColumnInfo, ForeignKeyInfo
from fraiseql_data.dependency import DependencyGraph


class SchemaIntrospector:
    """Introspect PostgreSQL schema for tables, columns, and relationships."""

    def __init__(self, conn: Connection, schema: str):
        self.conn = conn
        self.schema = schema
        self._cache: dict[str, TableInfo] = {}

    def get_tables(self) -> list[TableInfo]:
        """Get all tables in schema."""
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

        return [self.get_table_info(row[0]) for row in rows]

    def get_table_info(self, table_name: str) -> TableInfo:
        """Get complete table information."""
        if table_name in self._cache:
            return self._cache[table_name]

        columns = self.get_columns(table_name)
        foreign_keys = self.get_foreign_keys(table_name)

        table_info = TableInfo(name=table_name, columns=columns, foreign_keys=foreign_keys)
        self._cache[table_name] = table_info
        return table_info

    def get_columns(self, table_name: str) -> list[ColumnInfo]:
        """Get all columns for a table."""
        with self.conn.cursor() as cur:
            # Get column info
            cur.execute(
                """
                SELECT
                    c.column_name,
                    c.data_type,
                    c.is_nullable,
                    c.column_default
                FROM information_schema.columns c
                WHERE c.table_schema = %s
                  AND c.table_name = %s
                ORDER BY c.ordinal_position
                """,
                (self.schema, table_name),
            )
            column_rows = cur.fetchall()

            # Get primary key columns
            cur.execute(
                """
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_schema = %s
                  AND tc.table_name = %s
                """,
                (self.schema, table_name),
            )
            pk_columns = {row[0] for row in cur.fetchall()}

        columns = []
        for row in column_rows:
            col_name, data_type, is_nullable, default_value = row
            columns.append(
                ColumnInfo(
                    name=col_name,
                    pg_type=data_type,
                    is_nullable=is_nullable == "YES",
                    is_primary_key=col_name in pk_columns,
                    default_value=default_value,
                )
            )

        return columns

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

    def get_dependency_graph(self) -> "DependencyGraph":
        """Build dependency graph for all tables in schema."""
        from fraiseql_data.dependency import DependencyGraph

        tables = self.get_tables()
        graph = DependencyGraph()

        for table in tables:
            graph.add_table(table.name)
            for fk in table.foreign_keys:
                graph.add_dependency(table.name, fk.referenced_table)

        return graph

    def topological_sort(self) -> list[str]:
        """Sort tables in dependency order using topological sort."""
        graph = self.get_dependency_graph()
        return graph.topological_sort()
```

### Step 3: Dependency Graph

```python
# src/fraiseql_data/dependency.py
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
```

### Step 4: Data Generators

```python
# src/fraiseql_data/generators.py
"""Data generation strategies."""

from typing import Any, Callable
from uuid import UUID
from datetime import datetime
from faker import Faker
from fraiseql_uuid import Pattern

fake = Faker()


class FakerGenerator:
    """Generate realistic data using Faker library."""

    # Column name → Faker method mapping
    COLUMN_MAPPINGS = {
        "email": lambda: fake.email(),
        "first_name": lambda: fake.first_name(),
        "last_name": lambda: fake.last_name(),
        "name": lambda: fake.name(),
        "company": lambda: fake.company(),
        "phone": lambda: fake.phone_number(),
        "phone_number": lambda: fake.phone_number(),
        "address": lambda: fake.address(),
        "street": lambda: fake.street_address(),
        "city": lambda: fake.city(),
        "state": lambda: fake.state(),
        "country": lambda: fake.country(),
        "zip": lambda: fake.zipcode(),
        "zipcode": lambda: fake.zipcode(),
        "url": lambda: fake.url(),
        "description": lambda: fake.text(max_nb_chars=200),
        "bio": lambda: fake.text(max_nb_chars=300),
    }

    # Type-based fallbacks
    TYPE_FALLBACKS = {
        "text": lambda: fake.text(max_nb_chars=50),
        "character varying": lambda: fake.text(max_nb_chars=50),
        "varchar": lambda: fake.text(max_nb_chars=50),
        "integer": lambda: fake.random_int(min=1, max=1000),
        "bigint": lambda: fake.random_int(min=1, max=100000),
        "smallint": lambda: fake.random_int(min=1, max=100),
        "numeric": lambda: fake.pyfloat(min_value=0, max_value=10000),
        "real": lambda: fake.pyfloat(min_value=0, max_value=10000),
        "double precision": lambda: fake.pyfloat(min_value=0, max_value=10000),
        "boolean": lambda: fake.boolean(),
        "timestamp without time zone": lambda: fake.date_time_this_year(),
        "timestamp with time zone": lambda: fake.date_time_this_year(),
        "timestamptz": lambda: fake.date_time_this_year(),
        "date": lambda: fake.date_this_year(),
    }

    def generate(self, column_name: str, pg_type: str) -> Any:
        """Generate data for a column based on name and type."""
        # Try column name mapping first
        if column_name in self.COLUMN_MAPPINGS:
            return self.COLUMN_MAPPINGS[column_name]()

        # Fall back to type-based generation
        if pg_type in self.TYPE_FALLBACKS:
            return self.TYPE_FALLBACKS[pg_type]()

        # Default: text
        return fake.text(max_nb_chars=50)


class PatternUUIDGenerator:
    """Generate Pattern UUIDs using fraiseql-uuid."""

    def __init__(self, pattern: Pattern, table_code: str, seed_dir: int = 21):
        self.pattern = pattern
        self.table_code = table_code
        self.seed_dir = seed_dir

    def generate(self, instance: int) -> UUID:
        """Generate a Pattern UUID for an instance."""
        return self.pattern.generate(
            table_code=self.table_code,
            seed_dir=self.seed_dir,
            function=0,
            scenario=0,
            test_case=0,
            instance=instance,
        )


class SequentialGenerator:
    """Generate sequential values with optional prefix."""

    def __init__(self, start: int = 1, prefix: str = ""):
        self.current = start
        self.prefix = prefix

    def generate(self) -> str:
        """Generate next sequential value."""
        value = f"{self.prefix}{self.current}"
        self.current += 1
        return value


class TrinityGenerator:
    """Generate Trinity pattern columns (id, identifier)."""

    def __init__(self, pattern: Pattern, table_name: str, seed_dir: int = 21):
        self.pattern = pattern
        self.table_name = table_name
        self.seed_dir = seed_dir

        # Auto-generate table code from table name
        import hashlib
        self.table_code = hashlib.md5(table_name.encode()).hexdigest()[:6]

    def generate(self, instance: int, **row_data: Any) -> dict[str, Any]:
        """Generate Trinity columns for a row."""
        trinity_data = {}

        # Generate UUID id
        trinity_data["id"] = self.pattern.generate(
            table_code=self.table_code,
            seed_dir=self.seed_dir,
            function=0,
            scenario=0,
            test_case=0,
            instance=instance,
        )

        # Generate identifier
        # Try to derive from 'name' column if it exists
        if "name" in row_data and row_data["name"]:
            base = row_data["name"]
            # Simple slugify
            identifier = base.lower().replace(" ", "-").replace("_", "-")
            # Make unique by appending instance
            trinity_data["identifier"] = f"{identifier}-{instance}"
        else:
            # Fallback: table name + instance
            trinity_data["identifier"] = f"{self.table_name}_{instance:04d}"

        return trinity_data
```

### Step 5: Direct Backend

```python
# src/fraiseql_data/backends/direct.py
"""Direct INSERT backend - generates and executes SQL directly."""

from typing import Any
from psycopg import Connection
from fraiseql_data.models import TableInfo, Seeds


class DirectBackend:
    """Execute seed generation using direct INSERT statements."""

    def __init__(self, conn: Connection, schema: str):
        self.conn = conn
        self.schema = schema

    def insert_rows(
        self, table_info: TableInfo, rows: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Insert rows into table and return inserted data with generated columns.

        Args:
            table_info: Table metadata
            rows: List of row data (without pk_* or auto-generated columns)

        Returns:
            List of complete rows including generated pk_* and defaults
        """
        if not rows:
            return []

        # Get columns to insert (exclude pk_* IDENTITY columns)
        insert_columns = [
            col.name
            for col in table_info.columns
            if not (col.is_primary_key and col.name.startswith("pk_"))
        ]

        # Build INSERT ... RETURNING statement
        columns_list = ", ".join(insert_columns)
        placeholders = ", ".join(["%s"] * len(insert_columns))

        # Return all columns including generated ones
        all_columns = ", ".join([col.name for col in table_info.columns])

        sql = f"""
            INSERT INTO {self.schema}.{table_info.name} ({columns_list})
            VALUES ({placeholders})
            RETURNING {all_columns}
        """

        inserted_rows = []
        with self.conn.cursor() as cur:
            for row in rows:
                # Extract values in correct order
                values = [row.get(col) for col in insert_columns]

                # Execute and get returned row
                cur.execute(sql, values)
                result = cur.fetchone()

                # Build complete row dict
                complete_row = {
                    col.name: result[i] for i, col in enumerate(table_info.columns)
                }
                inserted_rows.append(complete_row)

        self.conn.commit()
        return inserted_rows
```

### Step 6: SeedBuilder API

```python
# src/fraiseql_data/builder.py
"""SeedBuilder API for declarative seed generation."""

from typing import Any, Callable
from psycopg import Connection
from fraiseql_uuid import Pattern

from fraiseql_data.introspection import SchemaIntrospector
from fraiseql_data.models import SeedPlan, Seeds
from fraiseql_data.generators import FakerGenerator, TrinityGenerator
from fraiseql_data.backends.direct import DirectBackend


class SeedBuilder:
    """Declarative API for building and executing seed data plans."""

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
        """Execute the seed plan and return generated data."""
        # Sort plan by dependencies
        sorted_tables = self.introspector.topological_sort()
        plan_by_table = {p.table: p for p in self._plan}

        # Filter to only tables in plan, but in dependency order
        sorted_plan = [
            plan_by_table[table] for table in sorted_tables if table in plan_by_table
        ]

        seeds = Seeds()
        generated_data: dict[str, list[dict[str, Any]]] = {}

        for plan in sorted_plan:
            table_info = self.introspector.get_table_info(plan.table)
            rows = self._generate_rows(table_info, plan, generated_data)
            inserted_rows = self.backend.insert_rows(table_info, rows)

            # Store for reference by dependent tables
            generated_data[plan.table] = inserted_rows
            seeds.add_table(plan.table, inserted_rows)

        return seeds

    def _generate_rows(
        self,
        table_info,
        plan: SeedPlan,
        generated_data: dict[str, list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        """Generate rows for a table."""
        faker_gen = FakerGenerator()
        trinity_gen = TrinityGenerator(self.pattern, table_info.name)

        rows = []
        for i in range(1, plan.count + 1):
            row: dict[str, Any] = {}

            # Generate data for each column
            for col in table_info.columns:
                # Skip pk_* IDENTITY columns (database generates)
                if col.is_primary_key and col.name.startswith("pk_"):
                    continue

                # Skip Trinity columns for now (will add later)
                if col.name in ("id", "identifier"):
                    continue

                # Handle foreign keys
                if any(fk.column == col.name for fk in table_info.foreign_keys):
                    fk = next(fk for fk in table_info.foreign_keys if fk.column == col.name)
                    # Pick random from generated parent data
                    if fk.referenced_table in generated_data:
                        import random
                        parent_row = random.choice(generated_data[fk.referenced_table])
                        row[col.name] = parent_row[fk.referenced_column]
                    continue

                # Check for override
                if col.name in plan.overrides:
                    override = plan.overrides[col.name]
                    if callable(override):
                        row[col.name] = override(i) if override.__code__.co_argcount > 0 else override()
                    else:
                        row[col.name] = override
                    continue

                # Generate using Faker
                if plan.strategy == "faker":
                    row[col.name] = faker_gen.generate(col.name, col.pg_type)

            # Add Trinity columns if table follows pattern
            if table_info.is_trinity:
                trinity_data = trinity_gen.generate(i, **row)
                row.update(trinity_data)

            rows.append(row)

        return rows
```

### Step 7: pytest Decorator

```python
# src/fraiseql_data/decorators.py
"""Pytest decorators for seed data generation."""

import functools
from typing import Any, Callable
import pytest
from psycopg import Connection

from fraiseql_data.builder import SeedBuilder


def seed_data(
    table: str,
    count: int,
    strategy: str = "faker",
    overrides: dict[str, Any] | None = None,
):
    """
    Decorator to inject seed data into pytest test functions.

    Usage:
        @seed_data("tb_manufacturer", count=5)
        def test_api(seeds):
            assert len(seeds.tb_manufacturer) == 5
    """

    def decorator(func: Callable) -> Callable:
        # Get existing seed plans or create new list
        if not hasattr(func, "_seed_plans"):
            func._seed_plans = []

        # Add this seed plan
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
            # Extract db_conn and test_schema from kwargs/args
            db_conn = kwargs.get("db_conn")
            test_schema = kwargs.get("test_schema")

            # If not in kwargs, try to get from fixtures
            if db_conn is None or test_schema is None:
                # Try to find in args (fixture injection)
                import inspect
                sig = inspect.signature(func)
                param_names = list(sig.parameters.keys())

                for i, arg in enumerate(args):
                    if isinstance(arg, Connection):
                        db_conn = arg
                    if isinstance(arg, str) and "test" in arg:
                        test_schema = arg

            if db_conn is None:
                raise ValueError("seed_data decorator requires 'db_conn' fixture")
            if test_schema is None:
                raise ValueError("seed_data decorator requires 'test_schema' fixture")

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

            # Inject seeds into kwargs
            kwargs["seeds"] = seeds

            # Call original function
            return func(*args, **kwargs)

        return wrapper

    return decorator
```

### Step 8: Update Public API

```python
# src/fraiseql_data/__init__.py
"""
fraiseql-data: AI/LLM-native seed data generation for FraiseQL projects.

Enables LLMs to write complete tests without guessing data structures.
"""

__version__ = "0.1.0"

from fraiseql_data.builder import SeedBuilder
from fraiseql_data.decorators import seed_data
from fraiseql_data.models import Seeds, SeedRow

__all__ = [
    "__version__",
    "SeedBuilder",
    "seed_data",
    "Seeds",
    "SeedRow",
]
```

```python
# src/fraiseql_data/backends/__init__.py
"""Backend implementations for seed data execution."""

from fraiseql_data.backends.direct import DirectBackend

__all__ = ["DirectBackend"]
```

---

## Verification

### ✅ Verification Commands

```bash
# Run all tests - they should PASS now
uv run pytest tests/test_introspection.py -v
uv run pytest tests/test_generators.py -v
uv run pytest tests/test_builder.py -v
uv run pytest tests/test_decorator.py -v
uv run pytest tests/test_integration.py -v

# Full test suite
uv run pytest tests/ -v

# Type check
uv run mypy src/

# Lint
uv run ruff check src/
```

### 📊 Expected Output

```bash
$ uv run pytest tests/ -v

tests/test_introspection.py::test_get_tables PASSED
tests/test_introspection.py::test_get_columns PASSED
tests/test_introspection.py::test_detect_trinity_pattern PASSED
tests/test_introspection.py::test_get_foreign_keys PASSED
tests/test_introspection.py::test_dependency_graph PASSED
tests/test_introspection.py::test_topological_sort PASSED
tests/test_generators.py::test_faker_auto_detect_email PASSED
tests/test_generators.py::test_faker_auto_detect_name PASSED
tests/test_generators.py::test_pattern_uuid_generator PASSED
tests/test_generators.py::test_trinity_generator PASSED
tests/test_builder.py::test_builder_initialization PASSED
tests/test_builder.py::test_execute_returns_seeds PASSED
tests/test_builder.py::test_execute_populates_trinity_columns PASSED
tests/test_builder.py::test_execute_resolves_foreign_keys PASSED
tests/test_decorator.py::test_decorator_basic PASSED
tests/test_decorator.py::test_decorator_multiple_tables PASSED
tests/test_integration.py::test_realistic_workflow PASSED
tests/test_integration.py::test_llm_test_pattern PASSED
tests/test_integration.py::test_no_guessing_required PASSED

==================== 20 passed in 2.50s ===========================
```

---

## Acceptance Criteria

- ✅ All Phase 1-RED tests pass
- ✅ Schema introspection works (tables, columns, FKs)
- ✅ Dependency resolution works (topological sort)
- ✅ Data generators work (Faker, Pattern UUID, Trinity)
- ✅ SeedBuilder API works (add, execute)
- ✅ @seed_data() decorator works
- ✅ Foreign keys are auto-resolved
- ✅ Trinity pattern columns auto-generated
- ✅ Type hints pass mypy strict mode
- ✅ Linting passes (ruff)

---

## DO NOT

- ❌ Optimize prematurely (that's REFACTOR phase)
- ❌ Add features beyond test requirements
- ❌ Skip error handling (basic errors only)
- ❌ Add staging backend yet (Phase 2)

---

## Notes

- Implementation is minimal - just enough to pass tests
- Some edge cases may not be handled (will be caught in QA)
- Performance optimization deferred to REFACTOR
- Decorator implementation is simple (may need refinement)

---

**Status**: Ready for implementation
**Next Phase**: Phase 1-REFACTOR (Optimize and clean up)
**Expected Test Results**: All tests should PASS
