# Phase 1-RED: Core Functionality Test Cases

**Phase**: RED (Write Failing Tests)
**Component**: fraiseql-data
**Objective**: Write comprehensive test cases for Zero-Guessing Core functionality (all tests should fail initially)

---

## Context

This phase implements TDD by writing tests FIRST that define the desired behavior of fraiseql-data. All tests will fail initially because the implementation doesn't exist yet.

**Core Features to Test**:
1. Schema introspection (tables, columns, foreign keys)
2. Auto-Faker data generation (realistic data from column names)
3. Foreign key auto-resolution
4. Pattern UUID generation (fraiseql-uuid integration)
5. Trinity pattern auto-population (pk_*, id, identifier)
6. `@seed_data()` decorator for pytest

---

## Files to Create

```
tests/
├── test_introspection.py       # Schema introspection tests
├── test_generators.py          # Data generator tests
├── test_builder.py             # SeedBuilder API tests
├── test_decorator.py           # @seed_data() decorator tests
└── test_integration.py         # End-to-end integration tests
```

---

## Implementation Steps

### Step 1: Test Schema Introspection

```python
# tests/test_introspection.py
"""Tests for schema introspection functionality."""

import pytest
from psycopg import Connection
from fraiseql_data.introspection import SchemaIntrospector, TableInfo, ColumnInfo, ForeignKeyInfo


def test_get_tables(db_conn: Connection, test_schema: str):
    """Should discover all tables in schema."""
    introspector = SchemaIntrospector(db_conn, schema=test_schema)
    tables = introspector.get_tables()

    assert len(tables) == 2
    table_names = {t.name for t in tables}
    assert "tb_manufacturer" in table_names
    assert "tb_model" in table_names


def test_get_columns(db_conn: Connection, test_schema: str):
    """Should discover all columns for a table."""
    introspector = SchemaIntrospector(db_conn, schema=test_schema)
    columns = introspector.get_columns("tb_manufacturer")

    column_names = {c.name for c in columns}
    assert "pk_manufacturer" in column_names
    assert "id" in column_names
    assert "identifier" in column_names
    assert "name" in column_names
    assert "email" in column_names
    assert "created_at" in column_names

    # Check column types
    id_col = next(c for c in columns if c.name == "id")
    assert id_col.pg_type == "uuid"
    assert id_col.is_nullable is False

    name_col = next(c for c in columns if c.name == "name")
    assert name_col.pg_type == "text"
    assert name_col.is_nullable is False

    email_col = next(c for c in columns if c.name == "email")
    assert email_col.is_nullable is True


def test_detect_trinity_pattern(db_conn: Connection, test_schema: str):
    """Should detect Trinity pattern columns (pk_*, id, identifier)."""
    introspector = SchemaIntrospector(db_conn, schema=test_schema)
    table = introspector.get_table_info("tb_manufacturer")

    assert table.is_trinity is True
    assert table.pk_column == "pk_manufacturer"
    assert table.id_column == "id"
    assert table.identifier_column == "identifier"


def test_get_foreign_keys(db_conn: Connection, test_schema: str):
    """Should discover foreign key relationships."""
    introspector = SchemaIntrospector(db_conn, schema=test_schema)
    fks = introspector.get_foreign_keys("tb_model")

    assert len(fks) == 1
    fk = fks[0]
    assert fk.column == "fk_manufacturer"
    assert fk.referenced_table == "tb_manufacturer"
    assert fk.referenced_column == "pk_manufacturer"


def test_dependency_graph(db_conn: Connection, test_schema: str):
    """Should build dependency graph for topological sorting."""
    introspector = SchemaIntrospector(db_conn, schema=test_schema)
    graph = introspector.get_dependency_graph()

    # tb_manufacturer has no dependencies
    assert graph.get_dependencies("tb_manufacturer") == []

    # tb_model depends on tb_manufacturer
    deps = graph.get_dependencies("tb_model")
    assert len(deps) == 1
    assert deps[0] == "tb_manufacturer"


def test_topological_sort(db_conn: Connection, test_schema: str):
    """Should sort tables in dependency order."""
    introspector = SchemaIntrospector(db_conn, schema=test_schema)
    sorted_tables = introspector.topological_sort()

    # tb_manufacturer must come before tb_model
    mfg_idx = next(i for i, t in enumerate(sorted_tables) if t == "tb_manufacturer")
    model_idx = next(i for i, t in enumerate(sorted_tables) if t == "tb_model")
    assert mfg_idx < model_idx
```

### Step 2: Test Data Generators

```python
# tests/test_generators.py
"""Tests for data generation strategies."""

import pytest
from uuid import UUID
from fraiseql_data.generators import (
    FakerGenerator,
    PatternUUIDGenerator,
    SequentialGenerator,
    TrinityGenerator,
)
from fraiseql_uuid import Pattern


def test_faker_auto_detect_email():
    """Should auto-generate realistic email for 'email' column."""
    gen = FakerGenerator()
    email = gen.generate("email", pg_type="text")

    assert "@" in email
    assert "." in email


def test_faker_auto_detect_name():
    """Should auto-generate realistic name for 'name' column."""
    gen = FakerGenerator()
    name = gen.generate("name", pg_type="text")

    assert len(name) > 0
    assert name.strip() == name  # No leading/trailing whitespace


def test_faker_auto_detect_phone():
    """Should auto-generate phone number for 'phone' column."""
    gen = FakerGenerator()
    phone = gen.generate("phone_number", pg_type="text")

    assert len(phone) > 0


def test_faker_timestamp():
    """Should auto-generate realistic timestamp for TIMESTAMPTZ columns."""
    gen = FakerGenerator()
    timestamp = gen.generate("created_at", pg_type="timestamptz")

    from datetime import datetime
    assert isinstance(timestamp, datetime)


def test_faker_text_fallback():
    """Should generate generic text for unknown column names."""
    gen = FakerGenerator()
    text = gen.generate("unknown_column", pg_type="text")

    assert isinstance(text, str)
    assert len(text) > 0


def test_pattern_uuid_generator():
    """Should generate Pattern UUIDs using fraiseql-uuid."""
    pattern = Pattern()
    gen = PatternUUIDGenerator(pattern, table_code="012345", seed_dir=21)

    uuid1 = gen.generate(instance=1)
    uuid2 = gen.generate(instance=2)

    assert isinstance(uuid1, UUID)
    assert isinstance(uuid2, UUID)
    assert uuid1 != uuid2

    # Should follow pattern format
    uuid1_str = str(uuid1)
    assert uuid1_str.startswith("012345")


def test_sequential_generator():
    """Should generate sequential values."""
    gen = SequentialGenerator(start=1, prefix="MODEL-")

    val1 = gen.generate()
    val2 = gen.generate()
    val3 = gen.generate()

    assert val1 == "MODEL-1"
    assert val2 == "MODEL-2"
    assert val3 == "MODEL-3"


def test_trinity_generator():
    """Should auto-generate Trinity pattern columns."""
    pattern = Pattern()
    gen = TrinityGenerator(pattern, table_name="tb_manufacturer", seed_dir=21)

    row1 = gen.generate(instance=1, name="Acme Corp")
    row2 = gen.generate(instance=2, name="TechCo Inc")

    # Should generate id (UUID)
    assert "id" in row1
    assert isinstance(row1["id"], UUID)

    # Should generate identifier (from name or sequential)
    assert "identifier" in row1
    assert isinstance(row1["identifier"], str)
    assert len(row1["identifier"]) > 0

    # Each row should be unique
    assert row1["id"] != row2["id"]
    assert row1["identifier"] != row2["identifier"]
```

### Step 3: Test SeedBuilder API

```python
# tests/test_builder.py
"""Tests for SeedBuilder API."""

import pytest
from psycopg import Connection
from fraiseql_data import SeedBuilder


def test_builder_initialization(db_conn: Connection, test_schema: str):
    """Should initialize SeedBuilder with connection and schema."""
    builder = SeedBuilder(db_conn, schema=test_schema)

    assert builder.schema == test_schema
    assert builder.conn == db_conn


def test_add_single_table(db_conn: Connection, test_schema: str):
    """Should add a table to seed plan."""
    builder = SeedBuilder(db_conn, schema=test_schema)
    builder.add("tb_manufacturer", count=5)

    # Should have 1 table in plan
    assert len(builder._plan) == 1
    assert builder._plan[0].table == "tb_manufacturer"
    assert builder._plan[0].count == 5


def test_add_multiple_tables(db_conn: Connection, test_schema: str):
    """Should add multiple tables in dependency order."""
    builder = SeedBuilder(db_conn, schema=test_schema)
    builder.add("tb_manufacturer", count=5)
    builder.add("tb_model", count=20)

    # Should automatically sort by dependencies
    assert len(builder._plan) == 2


def test_add_with_strategy(db_conn: Connection, test_schema: str):
    """Should support different generation strategies."""
    builder = SeedBuilder(db_conn, schema=test_schema)
    builder.add("tb_manufacturer", count=5, strategy="faker")

    plan_item = builder._plan[0]
    assert plan_item.strategy == "faker"


def test_add_with_overrides(db_conn: Connection, test_schema: str):
    """Should support column overrides."""
    builder = SeedBuilder(db_conn, schema=test_schema)
    builder.add(
        "tb_manufacturer",
        count=5,
        overrides={"name": lambda: "Custom Name", "email": "test@example.com"},
    )

    plan_item = builder._plan[0]
    assert "name" in plan_item.overrides
    assert "email" in plan_item.overrides


def test_execute_returns_seeds(db_conn: Connection, test_schema: str):
    """Should execute plan and return seed data."""
    builder = SeedBuilder(db_conn, schema=test_schema)
    builder.add("tb_manufacturer", count=5)
    seeds = builder.execute()

    # Should return Seeds object with data
    assert hasattr(seeds, "tb_manufacturer")
    assert len(seeds.tb_manufacturer) == 5


def test_execute_populates_trinity_columns(db_conn: Connection, test_schema: str):
    """Should auto-populate Trinity pattern columns."""
    builder = SeedBuilder(db_conn, schema=test_schema)
    builder.add("tb_manufacturer", count=3)
    seeds = builder.execute()

    mfg = seeds.tb_manufacturer[0]

    # Should have pk_* (from database IDENTITY)
    assert hasattr(mfg, "pk_manufacturer")
    assert isinstance(mfg.pk_manufacturer, int)

    # Should have id (UUID)
    assert hasattr(mfg, "id")
    from uuid import UUID
    assert isinstance(mfg.id, UUID)

    # Should have identifier (TEXT)
    assert hasattr(mfg, "identifier")
    assert isinstance(mfg.identifier, str)
    assert len(mfg.identifier) > 0


def test_execute_resolves_foreign_keys(db_conn: Connection, test_schema: str):
    """Should auto-resolve foreign key relationships."""
    builder = SeedBuilder(db_conn, schema=test_schema)
    builder.add("tb_manufacturer", count=5)
    builder.add("tb_model", count=20)
    seeds = builder.execute()

    # All models should reference valid manufacturers
    mfg_pks = {m.pk_manufacturer for m in seeds.tb_manufacturer}
    for model in seeds.tb_model:
        assert model.fk_manufacturer in mfg_pks


def test_execute_generates_realistic_data(db_conn: Connection, test_schema: str):
    """Should generate realistic data using Faker."""
    builder = SeedBuilder(db_conn, schema=test_schema)
    builder.add("tb_manufacturer", count=5, strategy="faker")
    seeds = builder.execute()

    # Email should be realistic (if column exists)
    mfg = seeds.tb_manufacturer[0]
    if hasattr(mfg, "email") and mfg.email:
        assert "@" in mfg.email

    # Name should exist and be non-empty
    assert mfg.name
    assert len(mfg.name) > 0
```

### Step 4: Test @seed_data() Decorator

```python
# tests/test_decorator.py
"""Tests for @seed_data() pytest decorator."""

import pytest
from psycopg import Connection
from fraiseql_data import seed_data


@seed_data("tb_manufacturer", count=5)
def test_decorator_basic(seeds, db_conn: Connection, test_schema: str):
    """Should inject seeds into test function."""
    # seeds should be available as parameter
    assert hasattr(seeds, "tb_manufacturer")
    assert len(seeds.tb_manufacturer) == 5


@seed_data("tb_manufacturer", count=3)
@seed_data("tb_model", count=10)
def test_decorator_multiple_tables(seeds, db_conn: Connection, test_schema: str):
    """Should handle multiple @seed_data decorators."""
    assert hasattr(seeds, "tb_manufacturer")
    assert hasattr(seeds, "tb_model")
    assert len(seeds.tb_manufacturer) == 3
    assert len(seeds.tb_model) == 10

    # FKs should be resolved
    mfg_pks = {m.pk_manufacturer for m in seeds.tb_manufacturer}
    for model in seeds.tb_model:
        assert model.fk_manufacturer in mfg_pks


@seed_data("tb_manufacturer", count=5, strategy="faker")
def test_decorator_with_strategy(seeds, db_conn: Connection, test_schema: str):
    """Should support generation strategies."""
    assert len(seeds.tb_manufacturer) == 5

    # Should have realistic data
    mfg = seeds.tb_manufacturer[0]
    if hasattr(mfg, "email") and mfg.email:
        assert "@" in mfg.email


@seed_data("tb_manufacturer", count=2, overrides={"name": "TestCorp"})
def test_decorator_with_overrides(seeds, db_conn: Connection, test_schema: str):
    """Should support column overrides."""
    assert len(seeds.tb_manufacturer) == 2

    # All should have overridden name
    for mfg in seeds.tb_manufacturer:
        assert mfg.name == "TestCorp"


def test_decorator_cleanup(db_conn: Connection, test_schema: str):
    """Should cleanup seed data after test completes."""
    # After decorated test completes, data should be rolled back
    with db_conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {test_schema}.tb_manufacturer")
        count = cur.fetchone()[0]
        assert count == 0  # Transaction rolled back
```

### Step 5: Integration Tests

```python
# tests/test_integration.py
"""End-to-end integration tests."""

import pytest
from psycopg import Connection
from fraiseql_data import SeedBuilder, seed_data


def test_realistic_workflow(db_conn: Connection, test_schema: str):
    """
    Test realistic LLM workflow: generate seeds, query data, verify.

    This is what an LLM would write to test an API endpoint.
    """
    # LLM writes this without knowing data structure
    builder = SeedBuilder(db_conn, schema=test_schema)
    builder.add("tb_manufacturer", count=5, strategy="faker")
    builder.add("tb_model", count=20, strategy="faker")
    seeds = builder.execute()

    # LLM can now reference seed data
    manufacturer_id = seeds.tb_manufacturer[0].pk_manufacturer

    # Query database (simulating GraphQL query)
    with db_conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT m.name, man.name as manufacturer_name
            FROM {test_schema}.tb_model m
            JOIN {test_schema}.tb_manufacturer man ON m.fk_manufacturer = man.pk_manufacturer
            WHERE man.pk_manufacturer = %s
            """,
            (manufacturer_id,),
        )
        results = cur.fetchall()

    # Should have models for this manufacturer
    assert len(results) > 0


@seed_data("tb_manufacturer", count=10)
@seed_data("tb_model", count=50)
def test_llm_test_pattern(seeds, db_conn: Connection, test_schema: str):
    """
    Test the ideal LLM pattern: decorator-based, zero config.

    An LLM can write this without ANY knowledge of:
    - UUID values
    - FK relationships
    - Data structure
    """
    # All manufacturers should have models
    assert len(seeds.tb_manufacturer) == 10
    assert len(seeds.tb_model) == 50

    # Can pick any manufacturer and find their models
    target_mfg = seeds.tb_manufacturer[0]
    models_for_mfg = [
        m for m in seeds.tb_model if m.fk_manufacturer == target_mfg.pk_manufacturer
    ]

    assert len(models_for_mfg) > 0


def test_complex_scenario_with_overrides(db_conn: Connection, test_schema: str):
    """Test complex scenario: custom data + auto-generation."""
    builder = SeedBuilder(db_conn, schema=test_schema)

    # Specific manufacturers
    builder.add(
        "tb_manufacturer",
        count=3,
        strategy="faker",
        overrides={
            "name": lambda: "TechCorp",
            "email": lambda i: f"contact-{i}@techcorp.com",
        },
    )

    # Models auto-linked
    builder.add("tb_model", count=15, strategy="faker")

    seeds = builder.execute()

    # All manufacturers should be TechCorp
    assert all(m.name == "TechCorp" for m in seeds.tb_manufacturer)

    # Emails should be sequential
    emails = sorted([m.email for m in seeds.tb_manufacturer])
    assert emails[0].startswith("contact-")

    # Models should be distributed among manufacturers
    mfg_pks = {m.pk_manufacturer for m in seeds.tb_manufacturer}
    model_fks = {m.fk_manufacturer for m in seeds.tb_model}
    assert model_fks.issubset(mfg_pks)


def test_no_guessing_required(db_conn: Connection, test_schema: str):
    """
    Verify that LLMs don't need to guess ANYTHING.

    This test proves the core value proposition.
    """
    # LLM writes minimal code
    builder = SeedBuilder(db_conn, schema=test_schema)
    builder.add("tb_manufacturer", count=1)
    builder.add("tb_model", count=1)
    seeds = builder.execute()

    mfg = seeds.tb_manufacturer[0]
    model = seeds.tb_model[0]

    # LLM doesn't need to guess:
    # ✅ UUID format (fraiseql-uuid Pattern)
    assert mfg.id  # Exists
    from uuid import UUID
    assert isinstance(mfg.id, UUID)

    # ✅ Identifier format
    assert mfg.identifier  # Exists and non-empty
    assert len(mfg.identifier) > 0

    # ✅ FK relationship
    assert model.fk_manufacturer == mfg.pk_manufacturer  # Auto-linked

    # ✅ Data types
    assert isinstance(mfg.name, str)
    from datetime import datetime
    assert isinstance(mfg.created_at, datetime)

    # LLM can now write assertions with confidence
    assert True  # All data exists and is correct
```

---

## Verification

### ✅ Verification Commands

```bash
# All tests should FAIL (implementation doesn't exist yet)
uv run pytest tests/test_introspection.py -v
uv run pytest tests/test_generators.py -v
uv run pytest tests/test_builder.py -v
uv run pytest tests/test_decorator.py -v
uv run pytest tests/test_integration.py -v

# Summary
uv run pytest tests/ -v --tb=short
```

### 📊 Expected Output

```bash
$ uv run pytest tests/ -v --tb=short

tests/test_introspection.py::test_get_tables FAILED
tests/test_introspection.py::test_get_columns FAILED
tests/test_generators.py::test_faker_auto_detect_email FAILED
tests/test_builder.py::test_builder_initialization FAILED
tests/test_decorator.py::test_decorator_basic FAILED
tests/test_integration.py::test_realistic_workflow FAILED

================================== FAILURES ===================================
# ... (import errors, modules don't exist yet)

==================== 20 failed, 0 passed in 0.50s ==========================
```

**This is expected!** All tests fail because we haven't implemented anything yet.

---

## Acceptance Criteria

- ✅ All test files created with comprehensive test coverage
- ✅ Tests cover all core functionality (introspection, generation, builder, decorator)
- ✅ Tests verify the "zero-guessing" value proposition
- ✅ All tests FAIL with clear import errors (modules don't exist)
- ✅ Test fixtures work (test_schema creates Trinity tables)
- ✅ Tests are readable and document expected behavior

---

## DO NOT

- ❌ Implement any functionality yet (that's Phase 1-GREEN)
- ❌ Skip tests to make them pass
- ❌ Write incomplete tests
- ❌ Guess at implementation details

---

## Notes

- Tests define the complete API surface
- Tests document expected behavior for LLM workflows
- Next phase (GREEN) will implement features to make tests pass
- Tests assume Trinity pattern compliance
- Tests use realistic pytest patterns (fixtures, decorators)

---

**Status**: Ready for implementation
**Next Phase**: Phase 1-GREEN (Implement core functionality)
**Expected Test Results**: All tests should FAIL
