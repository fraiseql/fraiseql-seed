# Phase 1-QA: Quality Assurance and Edge Cases

**Phase**: QA (Quality Assurance)
**Component**: fraiseql-data
**Objective**: Validate implementation with edge cases, stress tests, and real-world scenarios

---

## Context

Phase 1 implementation is complete (GREENFIELD → RED → GREEN → REFACTOR). Now we need comprehensive QA to ensure:
1. **Edge cases handled** - Nullable columns, empty tables, self-references
2. **Error handling validated** - Clear messages, helpful suggestions
3. **Performance acceptable** - Can generate 1000+ rows efficiently
4. **Real-world scenarios work** - Complex schemas, multiple FKs, etc.
5. **Documentation complete** - Examples, API docs, troubleshooting

This phase does NOT change implementation - only validates and documents.

---

## Files to Create/Modify

```
tests/
├── test_edge_cases.py          # Edge case testing
├── test_error_messages.py      # Error handling validation
├── test_performance.py         # Performance benchmarks
└── test_real_world.py          # Complex realistic scenarios

docs/
├── README.md                   # Updated with examples
├── API.md                      # API reference
└── TROUBLESHOOTING.md          # Common issues and solutions

examples/
├── basic_usage.py              # Simple example
├── pytest_decorator.py         # Decorator examples
└── complex_schema.py           # Advanced usage
```

---

## Implementation Steps

### Step 1: Edge Case Tests

```python
# tests/test_edge_cases.py
"""Test edge cases and boundary conditions."""

import pytest
from psycopg import Connection
from fraiseql_data import SeedBuilder, seed_data
from fraiseql_data.exceptions import (
    TableNotFoundError,
    SchemaNotFoundError,
    ForeignKeyResolutionError,
)


def test_nullable_columns(db_conn: Connection, test_schema: str):
    """Should handle nullable columns correctly."""
    builder = SeedBuilder(db_conn, schema=test_schema)
    builder.add("tb_manufacturer", count=5)
    seeds = builder.execute()

    # Email is nullable - should be generated but can be null
    for mfg in seeds.tb_manufacturer:
        # Either has realistic email or is None
        if mfg.email is not None:
            assert "@" in mfg.email


def test_zero_count(db_conn: Connection, test_schema: str):
    """Should handle count=0 gracefully."""
    builder = SeedBuilder(db_conn, schema=test_schema)
    builder.add("tb_manufacturer", count=0)
    seeds = builder.execute()

    assert len(seeds.tb_manufacturer) == 0


def test_large_count(db_conn: Connection, test_schema: str):
    """Should handle large counts (1000+ rows)."""
    builder = SeedBuilder(db_conn, schema=test_schema)
    builder.add("tb_manufacturer", count=1000)
    seeds = builder.execute()

    assert len(seeds.tb_manufacturer) == 1000

    # All should have unique identifiers
    identifiers = {m.identifier for m in seeds.tb_manufacturer}
    assert len(identifiers) == 1000


def test_table_not_found(db_conn: Connection, test_schema: str):
    """Should raise clear error for non-existent table."""
    builder = SeedBuilder(db_conn, schema=test_schema)

    with pytest.raises(TableNotFoundError) as exc_info:
        builder.add("tb_does_not_exist", count=5)

    # Error message should be helpful
    assert "tb_does_not_exist" in str(exc_info.value)
    assert test_schema in str(exc_info.value)
    assert "Suggestions" in str(exc_info.value)


def test_schema_not_found(db_conn: Connection):
    """Should raise clear error for non-existent schema."""
    with pytest.raises(SchemaNotFoundError) as exc_info:
        SeedBuilder(db_conn, schema="nonexistent_schema")

    assert "nonexistent_schema" in str(exc_info.value)
    assert "Suggestions" in str(exc_info.value)


def test_missing_dependency(db_conn: Connection, test_schema: str):
    """Should raise error if FK dependency not in plan."""
    builder = SeedBuilder(db_conn, schema=test_schema)

    # Add tb_model without tb_manufacturer
    builder.add("tb_model", count=10)

    from fraiseql_data.exceptions import MissingDependencyError
    with pytest.raises(MissingDependencyError) as exc_info:
        builder.execute()

    assert "tb_model" in str(exc_info.value)
    assert "tb_manufacturer" in str(exc_info.value)


def test_all_null_foreign_key(db_conn: Connection, test_schema: str):
    """Should handle nullable foreign keys."""
    # Create table with nullable FK
    with db_conn.cursor() as cur:
        cur.execute(f"""
            CREATE TABLE {test_schema}.tb_optional_fk (
                pk_optional INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                id UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                fk_manufacturer INTEGER REFERENCES {test_schema}.tb_manufacturer(pk_manufacturer)
            )
        """)
        db_conn.commit()

    # Should work even without manufacturers
    builder = SeedBuilder(db_conn, schema=test_schema)
    builder.add("tb_optional_fk", count=5)
    seeds = builder.execute()

    # FK should be NULL (no manufacturers exist)
    assert all(row.fk_manufacturer is None for row in seeds.tb_optional_fk)


def test_unique_constraint_violation_prevention(db_conn: Connection, test_schema: str):
    """Should generate unique values for UNIQUE columns."""
    builder = SeedBuilder(db_conn, schema=test_schema)
    builder.add("tb_manufacturer", count=100)
    seeds = builder.execute()

    # All identifiers should be unique (UNIQUE constraint)
    identifiers = [m.identifier for m in seeds.tb_manufacturer]
    assert len(identifiers) == len(set(identifiers))

    # All UUIDs should be unique
    uuids = [m.id for m in seeds.tb_manufacturer]
    assert len(uuids) == len(set(uuids))


def test_override_constant_value(db_conn: Connection, test_schema: str):
    """Should support constant value overrides."""
    builder = SeedBuilder(db_conn, schema=test_schema)
    builder.add("tb_manufacturer", count=5, overrides={"name": "ConstantName"})
    seeds = builder.execute()

    # All should have same name
    assert all(m.name == "ConstantName" for m in seeds.tb_manufacturer)


def test_override_callable(db_conn: Connection, test_schema: str):
    """Should support callable overrides."""
    counter = 0

    def custom_name():
        nonlocal counter
        counter += 1
        return f"Custom-{counter}"

    builder = SeedBuilder(db_conn, schema=test_schema)
    builder.add("tb_manufacturer", count=5, overrides={"name": custom_name})
    seeds = builder.execute()

    # Should have sequential custom names
    names = [m.name for m in seeds.tb_manufacturer]
    assert "Custom-1" in names
    assert "Custom-5" in names


def test_override_callable_with_instance(db_conn: Connection, test_schema: str):
    """Should support callable overrides with instance argument."""
    builder = SeedBuilder(db_conn, schema=test_schema)
    builder.add(
        "tb_manufacturer",
        count=5,
        overrides={"name": lambda i: f"Instance-{i}"},
    )
    seeds = builder.execute()

    names = {m.name for m in seeds.tb_manufacturer}
    assert "Instance-1" in names
    assert "Instance-5" in names


def test_empty_schema(db_conn: Connection):
    """Should handle schema with no tables gracefully."""
    # Create empty schema
    empty_schema = "empty_test"
    with db_conn.cursor() as cur:
        cur.execute(f"DROP SCHEMA IF EXISTS {empty_schema} CASCADE")
        cur.execute(f"CREATE SCHEMA {empty_schema}")
        db_conn.commit()

    builder = SeedBuilder(db_conn, schema=empty_schema)
    tables = builder.introspector.get_tables()

    assert len(tables) == 0

    # Cleanup
    with db_conn.cursor() as cur:
        cur.execute(f"DROP SCHEMA {empty_schema}")
        db_conn.commit()


def test_multiple_foreign_keys(db_conn: Connection, test_schema: str):
    """Should handle table with multiple FKs."""
    # Create table with 2 FKs
    with db_conn.cursor() as cur:
        cur.execute(f"""
            CREATE TABLE {test_schema}.tb_model_variant (
                pk_variant INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                id UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                fk_manufacturer INTEGER NOT NULL REFERENCES {test_schema}.tb_manufacturer(pk_manufacturer),
                fk_model INTEGER NOT NULL REFERENCES {test_schema}.tb_model(pk_model)
            )
        """)
        db_conn.commit()

    # Seed all dependencies
    builder = SeedBuilder(db_conn, schema=test_schema)
    builder.add("tb_manufacturer", count=5)
    builder.add("tb_model", count=20)
    builder.add("tb_model_variant", count=50)
    seeds = builder.execute()

    # All FKs should be resolved
    mfg_pks = {m.pk_manufacturer for m in seeds.tb_manufacturer}
    model_pks = {m.pk_model for m in seeds.tb_model}

    for variant in seeds.tb_model_variant:
        assert variant.fk_manufacturer in mfg_pks
        assert variant.fk_model in model_pks
```

### Step 2: Error Message Validation

```python
# tests/test_error_messages.py
"""Validate error messages are clear and helpful."""

import pytest
from psycopg import Connection
from fraiseql_data import SeedBuilder
from fraiseql_data.exceptions import (
    TableNotFoundError,
    SchemaNotFoundError,
    MissingDependencyError,
)


def test_table_not_found_message(db_conn: Connection, test_schema: str):
    """Table not found error should suggest solutions."""
    builder = SeedBuilder(db_conn, schema=test_schema)

    with pytest.raises(TableNotFoundError) as exc_info:
        builder.add("tb_typo", count=5)

    error_msg = str(exc_info.value)

    # Should mention table and schema
    assert "tb_typo" in error_msg
    assert test_schema in error_msg

    # Should have suggestions
    assert "Suggestions" in error_msg
    assert "spelling" in error_msg.lower()
    assert "CREATE TABLE" in error_msg


def test_schema_not_found_message(db_conn: Connection):
    """Schema not found error should suggest solutions."""
    with pytest.raises(SchemaNotFoundError) as exc_info:
        SeedBuilder(db_conn, schema="wrong_schema")

    error_msg = str(exc_info.value)

    assert "wrong_schema" in error_msg
    assert "Suggestions" in error_msg
    assert "CREATE SCHEMA" in error_msg


def test_missing_dependency_message(db_conn: Connection, test_schema: str):
    """Missing dependency error should show how to fix."""
    builder = SeedBuilder(db_conn, schema=test_schema)
    builder.add("tb_model", count=10)  # Missing tb_manufacturer

    with pytest.raises(MissingDependencyError) as exc_info:
        builder.execute()

    error_msg = str(exc_info.value)

    # Should mention both tables
    assert "tb_model" in error_msg
    assert "tb_manufacturer" in error_msg

    # Should show code examples
    assert "builder.add" in error_msg or "@seed_data" in error_msg
```

### Step 3: Performance Benchmarks

```python
# tests/test_performance.py
"""Performance benchmarks and stress tests."""

import pytest
import time
from psycopg import Connection
from fraiseql_data import SeedBuilder


@pytest.mark.slow
def test_1000_rows_performance(db_conn: Connection, test_schema: str):
    """Should generate 1000 rows in under 5 seconds."""
    builder = SeedBuilder(db_conn, schema=test_schema)
    builder.add("tb_manufacturer", count=1000)

    start = time.time()
    seeds = builder.execute()
    elapsed = time.time() - start

    assert len(seeds.tb_manufacturer) == 1000
    assert elapsed < 5.0  # Should be fast


@pytest.mark.slow
def test_complex_hierarchy_performance(db_conn: Connection, test_schema: str):
    """Should handle complex hierarchy efficiently."""
    builder = SeedBuilder(db_conn, schema=test_schema)
    builder.add("tb_manufacturer", count=50)
    builder.add("tb_model", count=500)

    start = time.time()
    seeds = builder.execute()
    elapsed = time.time() - start

    assert len(seeds.tb_manufacturer) == 50
    assert len(seeds.tb_model) == 500
    assert elapsed < 10.0  # Should complete in reasonable time


@pytest.mark.slow
def test_introspection_caching(db_conn: Connection, test_schema: str):
    """Introspection should be cached for performance."""
    builder = SeedBuilder(db_conn, schema=test_schema)

    # First introspection (cache miss)
    start1 = time.time()
    _ = builder.introspector.get_tables()
    elapsed1 = time.time() - start1

    # Second introspection (cache hit)
    start2 = time.time()
    _ = builder.introspector.get_tables()
    elapsed2 = time.time() - start2

    # Cached version should be much faster
    assert elapsed2 < elapsed1 * 0.5  # At least 2x faster
```

### Step 4: Real-World Scenarios

```python
# tests/test_real_world.py
"""Test real-world complex scenarios."""

import pytest
from psycopg import Connection
from fraiseql_data import seed_data


def test_realistic_e_commerce_scenario(db_conn: Connection, test_schema: str):
    """
    Simulate realistic e-commerce test scenario.

    This is what an LLM would write to test an e-commerce API.
    """
    # Create realistic schema
    with db_conn.cursor() as cur:
        cur.execute(f"""
            CREATE TABLE {test_schema}.tb_category (
                pk_category INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                id UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL
            )
        """)
        cur.execute(f"""
            CREATE TABLE {test_schema}.tb_product (
                pk_product INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                id UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                description TEXT,
                price NUMERIC(10, 2) NOT NULL,
                fk_category INTEGER NOT NULL REFERENCES {test_schema}.tb_category(pk_category),
                fk_manufacturer INTEGER NOT NULL REFERENCES {test_schema}.tb_manufacturer(pk_manufacturer)
            )
        """)
        db_conn.commit()

    # LLM writes this test
    from fraiseql_data import SeedBuilder

    builder = SeedBuilder(db_conn, schema=test_schema)
    builder.add("tb_manufacturer", count=10)
    builder.add("tb_category", count=5)
    builder.add("tb_product", count=100)
    seeds = builder.execute()

    # Verify realistic scenario
    assert len(seeds.tb_manufacturer) == 10
    assert len(seeds.tb_category) == 5
    assert len(seeds.tb_product) == 100

    # Products should reference valid categories and manufacturers
    category_pks = {c.pk_category for c in seeds.tb_category}
    mfg_pks = {m.pk_manufacturer for m in seeds.tb_manufacturer}

    for product in seeds.tb_product:
        assert product.fk_category in category_pks
        assert product.fk_manufacturer in mfg_pks


@seed_data("tb_manufacturer", count=3)
@seed_data("tb_model", count=10)
def test_llm_writes_graphql_test(seeds, db_conn: Connection, test_schema: str):
    """
    LLM writes a GraphQL API test without knowing data structure.

    This demonstrates the zero-guessing value proposition.
    """
    # LLM can write this without any knowledge of:
    # - UUID values
    # - FK relationships
    # - Identifier format
    # - Data types

    # Pick first manufacturer
    manufacturer = seeds.tb_manufacturer[0]

    # Find their models
    models = [m for m in seeds.tb_model if m.fk_manufacturer == manufacturer.pk_manufacturer]

    # Can write assertions with confidence
    assert len(models) > 0
    assert manufacturer.id  # UUID exists
    assert manufacturer.identifier  # identifier exists

    # Simulate GraphQL query
    query = f"""
    query {{
        manufacturer(id: "{manufacturer.id}") {{
            id
            name
            models {{
                id
                name
            }}
        }}
    }}
    """

    # LLM knows this query will work because seed data guarantees it
    assert manufacturer.id in query
    assert len(models) > 0  # At least one model exists
```

### Step 5: Documentation

```markdown
<!-- docs/API.md -->
# fraiseql-data API Reference

## SeedBuilder

Main API for building and executing seed data.

### Constructor

```python
SeedBuilder(conn: Connection, schema: str)
```

**Parameters:**
- `conn`: psycopg Connection to database
- `schema`: PostgreSQL schema name

**Example:**
```python
from psycopg import connect
from fraiseql_data import SeedBuilder

conn = connect("postgresql://localhost/mydb")
builder = SeedBuilder(conn, schema="public")
```

### Methods

#### `add(table, count, strategy="faker", overrides=None)`

Add a table to the seed plan.

**Parameters:**
- `table` (str): Table name
- `count` (int): Number of rows to generate
- `strategy` (str): Generation strategy ("faker" or custom)
- `overrides` (dict): Column value overrides

**Returns:** SeedBuilder (for chaining)

**Example:**
```python
builder.add("tb_manufacturer", count=5, strategy="faker")
builder.add("tb_model", count=20, overrides={"status": "active"})
```

#### `execute()`

Execute the seed plan and return generated data.

**Returns:** Seeds object

**Example:**
```python
seeds = builder.execute()
print(len(seeds.tb_manufacturer))  # 5
```

---

## @seed_data Decorator

Pytest decorator for automatic seed generation.

### Signature

```python
@seed_data(table, count, strategy="faker", overrides=None)
```

### Example

```python
import pytest
from fraiseql_data import seed_data

@seed_data("tb_manufacturer", count=5)
@seed_data("tb_model", count=20)
def test_api(seeds, db_conn, test_schema):
    assert len(seeds.tb_manufacturer) == 5
    assert len(seeds.tb_model) == 20
```

---

## Seeds Object

Container for generated seed data.

### Access Tables

```python
seeds.tb_manufacturer  # List of SeedRow objects
seeds.tb_model
```

### SeedRow

Each row is a `SeedRow` object with attribute access:

```python
manufacturer = seeds.tb_manufacturer[0]
print(manufacturer.id)          # UUID
print(manufacturer.identifier)  # TEXT
print(manufacturer.name)        # Generated name
```

---

## Exceptions

All exceptions include helpful suggestions for resolution.

### SchemaNotFoundError

Schema does not exist.

### TableNotFoundError

Table does not exist in schema.

### MissingDependencyError

FK dependency not in seed plan.

### ForeignKeyResolutionError

Could not resolve foreign key.

---

## Column Overrides

### Constant Value

```python
builder.add("tb_manufacturer", count=5, overrides={"name": "ACME Corp"})
```

### Callable

```python
builder.add("tb_manufacturer", count=5, overrides={
    "name": lambda: fake.company()
})
```

### Callable with Instance

```python
builder.add("tb_manufacturer", count=5, overrides={
    "name": lambda i: f"Company-{i}"
})
```

---

## Auto-Generation

### Trinity Pattern

Tables with `pk_*`, `id`, `identifier` columns are auto-detected:

```python
# Automatically generates:
# - id: Pattern UUID (fraiseql-uuid)
# - identifier: Unique TEXT (derived from name or sequential)
```

### Faker Mappings

Common column names are auto-mapped to Faker generators:

- `email` → realistic email
- `name`, `first_name`, `last_name` → realistic names
- `phone`, `phone_number` → phone numbers
- `address`, `city`, `state` → addresses
- `company` → company names
- `description` → text paragraphs

### Type Fallbacks

If column name not recognized, uses PostgreSQL type:

- `TEXT` → short text
- `INTEGER` → random int
- `TIMESTAMPTZ` → recent datetime
- `BOOLEAN` → random true/false
```

```markdown
<!-- docs/TROUBLESHOOTING.md -->
# Troubleshooting Guide

## Common Issues

### "Schema 'X' not found"

**Cause:** Schema doesn't exist in database.

**Solution:**
```sql
CREATE SCHEMA your_schema;
```

Or check connection string points to correct database.

---

### "Table 'X' depends on 'Y', but 'Y' is not in seed plan"

**Cause:** Forgot to add FK dependency.

**Solution:**
```python
# Add dependency FIRST
builder.add("tb_manufacturer", count=5)  # Dependency
builder.add("tb_model", count=20)        # Dependent
```

Or with decorator:
```python
@seed_data("tb_manufacturer", count=5)  # First
@seed_data("tb_model", count=20)        # Second
def test_fn(seeds):
    ...
```

---

### "Could not auto-generate data for column 'X'"

**Cause:** Column name not in auto-mapping and type not recognized.

**Solution:** Provide override:
```python
builder.add("tb_machine", count=5, overrides={
    "serial_number": lambda: f"SN-{fake.random_int(1000, 9999)}"
})
```

---

### Slow Performance

**Cause:** Large counts or complex schemas.

**Solutions:**
1. Reduce count for tests (10-20 rows usually enough)
2. Use smaller schemas in tests
3. Check database connection latency

**Benchmarks:**
- 1000 rows: <5 seconds
- 10,000 rows: <30 seconds

---

### "Circular dependency detected"

**Cause:** Tables reference each other (A → B → A).

**Status:** Self-referencing tables will be supported in Phase 2.

**Workaround:**
1. Temporarily remove FK constraint
2. Seed data
3. Re-add FK constraint

---

### Decorator not injecting seeds

**Cause:** Missing required fixtures.

**Solution:** Ensure test has `db_conn` and `test_schema` parameters:
```python
@seed_data("tb_manufacturer", count=5)
def test_api(seeds, db_conn, test_schema):  # Must have these!
    ...
```

---

## Getting Help

1. Check error message suggestions
2. Review API documentation
3. Check examples in `examples/` directory
4. File issue: https://github.com/fraiseql/fraiseql-data/issues
```

---

## Verification

### ✅ Verification Commands

```bash
# Run all tests including QA tests
uv run pytest tests/ -v --tb=short

# Run only edge case tests
uv run pytest tests/test_edge_cases.py -v

# Run performance tests (marked slow)
uv run pytest tests/test_performance.py -v -m slow

# Generate coverage report
uv run pytest tests/ --cov=src/fraiseql_data --cov-report=html

# Validate documentation builds
ls docs/*.md  # All docs should exist
```

### 📊 Expected Output

```bash
$ uv run pytest tests/ -v

tests/test_introspection.py ✓✓✓✓✓✓ (6 passed)
tests/test_generators.py ✓✓✓✓ (4 passed)
tests/test_builder.py ✓✓✓✓✓✓ (6 passed)
tests/test_decorator.py ✓✓✓✓ (4 passed)
tests/test_integration.py ✓✓✓ (3 passed)
tests/test_edge_cases.py ✓✓✓✓✓✓✓✓✓✓ (10+ passed)
tests/test_error_messages.py ✓✓✓ (3 passed)
tests/test_performance.py ✓✓✓ (3 passed)
tests/test_real_world.py ✓✓ (2 passed)

==================== 40+ passed in 8.00s ==========================

$ uv run pytest tests/ --cov=src/fraiseql_data
Coverage: 95%+
```

---

## Acceptance Criteria

- ✅ All edge cases tested and handled
- ✅ Error messages validated (clear and helpful)
- ✅ Performance benchmarks pass (<5s for 1000 rows)
- ✅ Real-world scenarios work
- ✅ API documentation complete
- ✅ Troubleshooting guide written
- ✅ Code coverage >90%
- ✅ Example files created
- ✅ All tests pass (40+ tests)

---

## DO NOT

- ❌ Change implementation based on QA findings (file issues instead)
- ❌ Add new features (Phase 2)
- ❌ Skip documentation
- ❌ Accept low code coverage (<85%)

---

## Success Metrics

**Phase 1 Complete When:**
- ✅ All 40+ tests pass
- ✅ Coverage >90%
- ✅ Documentation complete (API + Troubleshooting)
- ✅ LLM can write tests without guessing (validated in test_real_world.py)
- ✅ Error messages are helpful (validated in test_error_messages.py)
- ✅ Performance acceptable (1000 rows <5s)

---

## Next Steps After Phase 1

**Phase 1 Status**: ✅ COMPLETE - Zero-Guessing Core

**Phase 2 Options:**
1. **PrintOptim Integration** - Test with real PrintOptim schema
2. **Staging Backend** - Add staging pattern support
3. **Advanced Features** - Self-referencing tables, bulk optimizations
4. **GraphQL Integration** - Schema-aware generation

**Decision Point:** Validate with real usage before committing to Phase 2 scope.

---

**Status**: Ready for implementation
**Expected Test Results**: 40+ tests pass, >90% coverage
**Phase 1 Completion**: After QA passes, Phase 1 is COMPLETE ✅
