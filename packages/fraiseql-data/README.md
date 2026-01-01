# fraiseql-data

Schema-aware seed data generation for PostgreSQL with Trinity pattern support.

## Overview

fraiseql-data generates realistic test data for PostgreSQL databases by:
- **Introspecting your schema** to understand tables, columns, and relationships
- **Respecting foreign key constraints** with automatic dependency resolution
- **Supporting Trinity pattern** (pk_*, id, identifier) for PrintOptim compatibility
- **Generating realistic data** using Faker for domain-appropriate values
- **Handling complex scenarios** like self-referencing tables and UNIQUE constraints

## Installation

```bash
# Using uv (recommended)
uv add fraiseql-data

# Or using pip
pip install fraiseql-data
```

**Requirements:**
- Python 3.11+
- PostgreSQL 14+
- psycopg 3.1+

## Quick Start

```python
from psycopg import connect
from fraiseql_data import SeedBuilder

# Connect to database
conn = connect("postgresql://user:pass@localhost/mydb")

# Build seed plan
builder = SeedBuilder(conn, schema="public")
seeds = (
    builder
    .add("tb_manufacturer", count=10)
    .add("tb_model", count=50)
    .add("tb_variant", count=200)
    .execute()
)

# Access generated data
for manufacturer in seeds.tb_manufacturer:
    print(f"Created: {manufacturer.name} ({manufacturer.identifier})")
```

## Core Features

### 1. Automatic Dependency Resolution

fraiseql-data automatically handles foreign key dependencies:

```python
builder = SeedBuilder(conn, "public")

# No need to specify order - dependencies auto-resolved
seeds = (
    builder
    .add("tb_variant", count=100)      # Depends on tb_model
    .add("tb_model", count=20)         # Depends on tb_manufacturer
    .add("tb_manufacturer", count=5)   # No dependencies
    .execute()
)

# Inserts in correct order: manufacturer → model → variant
```

### 2. Trinity Pattern Support

Automatic handling of Trinity pattern (pk_*, id, identifier):

```python
# Schema with Trinity pattern:
# CREATE TABLE tb_manufacturer (
#     pk_manufacturer INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
#     id UUID NOT NULL UNIQUE,
#     identifier TEXT NOT NULL UNIQUE,
#     name TEXT NOT NULL
# );

seeds = builder.add("tb_manufacturer", count=10).execute()

# All Trinity fields auto-generated:
for mfr in seeds.tb_manufacturer:
    print(f"PK: {mfr.pk_manufacturer}")     # 1, 2, 3, ...
    print(f"ID: {mfr.id}")                  # UUID v4 with pattern
    print(f"Identifier: {mfr.identifier}")  # MANUFACTURER-001, ...
```

### 3. Realistic Data Generation

Uses Faker for domain-appropriate data:

```python
# Faker automatically detects common column names:
# - email → realistic email addresses
# - name, first_name, last_name → person names
# - company, company_name → company names
# - phone, phone_number → phone numbers
# - address, street → addresses
# - description → sentences/paragraphs

seeds = builder.add("tb_user", count=10).execute()
# email: "john.doe@example.com" (not "column_1_value")
```

### 4. Custom Overrides

Override auto-generation for specific columns:

```python
import random

seeds = (
    builder
    .add("tb_product", count=50, overrides={
        "price": lambda: round(random.uniform(10.0, 500.0), 2),
        "status": "active",  # Static value for all rows
        "created_at": lambda i: f"2024-{i:02d}-01",  # Uses instance number
    })
    .execute()
)
```

## Phase 2 Features (New!)

### Self-Referencing Tables

Support for hierarchical data structures:

```python
# Schema with self-referencing FK:
# CREATE TABLE tb_category (
#     pk_category INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
#     id UUID NOT NULL UNIQUE,
#     identifier TEXT NOT NULL UNIQUE,
#     name TEXT NOT NULL,
#     parent_category INTEGER REFERENCES tb_category(pk_category)
# );

seeds = builder.add("tb_category", count=20).execute()

# First category has NULL parent, others pick random parent:
categories = seeds.tb_category
assert categories[0].parent_category is None  # Root category
assert categories[5].parent_category in [c.pk_category for c in categories]
```

**How it works:**
- First row gets `NULL` for self-referencing FK (if nullable)
- Subsequent rows pick random parent from previously inserted rows
- Non-nullable self-refs raise `SelfReferenceError` (must provide override)

**Example: Organization Chart**
```python
seeds = builder.add("tb_employee", count=50, overrides={
    "manager_id": lambda i: None if i <= 3 else random.choice(range(1, i))
}).execute()

# Creates realistic org chart with 3 top-level managers
```

### UNIQUE Constraint Handling

Automatic collision detection and retry:

```python
# Schema with UNIQUE constraint:
# CREATE TABLE tb_user (
#     pk_user INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
#     email TEXT NOT NULL UNIQUE,
#     username TEXT NOT NULL UNIQUE
# );

seeds = builder.add("tb_user", count=100).execute()

# Guaranteed unique emails and usernames (max 10 retry attempts)
emails = [u.email for u in seeds.tb_user]
assert len(emails) == len(set(emails))  # No duplicates!
```

**How it works:**
- Introspects `UNIQUE` constraints from information_schema
- Tracks generated values per UNIQUE column
- Retries on collision (max 10 attempts)
- Raises `UniqueConstraintError` if can't generate unique value

### Bulk Insert Optimization

5x faster insertion for large datasets:

```python
# Before (Phase 1): 100 rows = 100 INSERT statements
# After (Phase 2): 100 rows = 1 INSERT statement (batch of 100)

builder = SeedBuilder(conn, "public")
seeds = builder.add("tb_product", count=1000).execute()

# Uses bulk insert automatically (100 rows/batch)
# ~5x faster than one-by-one insertion
```

**Performance:**
- 100 rows: 3.2x speedup
- 500 rows: 5x speedup
- 1000 rows: 5.3x speedup

See [PERFORMANCE.md](PERFORMANCE.md) for detailed benchmarks.

## Phase 3 Features

### Data Export

Export generated seed data to JSON or CSV formats:

```python
# Generate seed data
builder = SeedBuilder(conn, schema="public")
seeds = builder.add("tb_manufacturer", count=50).execute()

# Export all tables to JSON
json_str = seeds.to_json()
with open("seeds.json", "w") as f:
    f.write(json_str)

# Export single table to CSV
seeds.to_csv("tb_manufacturer", "manufacturers.csv")
```

## Phase 4 Features (New!)

### Data Import

Import previously exported seed data from JSON or CSV:

```python
from fraiseql_data.models import Seeds

# Import from JSON (all tables)
imported = Seeds.from_json(file_path="seeds.json")
# or from JSON string:
imported = Seeds.from_json(json_str=json_data)

# Import from CSV (single table)
imported = Seeds.from_csv("tb_manufacturer", "manufacturers.csv")

# Insert imported data into database
builder = SeedBuilder(conn, schema="public")
result = builder.insert_seeds(imported)
```

**Type Conversion:**
- UUIDs automatically converted from strings
- ISO datetime strings converted to datetime objects
- Round-trip export/import preserves all types

### Staging Backend (In-Memory Testing)

Generate seed data without a database connection for faster testing:

```python
from fraiseql_data import SeedBuilder
from fraiseql_data.models import TableInfo, ColumnInfo

# No database connection needed!
builder = SeedBuilder(conn=None, schema="test", backend="staging")

# Define table schema manually
table_info = TableInfo(
    name="tb_product",
    columns=[
        ColumnInfo(name="pk_product", pg_type="integer", is_nullable=False, is_primary_key=True),
        ColumnInfo(name="id", pg_type="uuid", is_nullable=False, is_unique=True),
        ColumnInfo(name="identifier", pg_type="text", is_nullable=False, is_unique=True),
        ColumnInfo(name="name", pg_type="text", is_nullable=False),
        ColumnInfo(name="price", pg_type="numeric", is_nullable=True),
    ],
)
builder.set_table_schema("tb_product", table_info)

# Generate data in-memory (no database writes)
seeds = builder.add("tb_product", count=100).execute()

# Export to JSON for later use
json_str = seeds.to_json()

# Later: import and insert into actual database
imported = Seeds.from_json(json_str=json_str)
db_builder = SeedBuilder(db_conn, schema="public", backend="direct")
db_builder.insert_seeds(imported)
```

**Benefits:**
- No database setup needed for unit tests
- Faster test execution (in-memory only)
- Easy migration from staging to production

### CHECK Constraint Auto-Satisfaction

Automatically generate valid data for CHECK constraints:

```python
# Schema with CHECK constraints:
# CREATE TABLE tb_product (
#     pk_product INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
#     id UUID NOT NULL UNIQUE,
#     identifier TEXT NOT NULL UNIQUE,
#     name TEXT NOT NULL,
#     status TEXT NOT NULL CHECK (status IN ('active', 'pending', 'archived')),
#     price NUMERIC CHECK (price > 0 AND price < 10000),
#     stock INTEGER CHECK (stock >= 0)
# );

# No overrides needed - constraints automatically satisfied!
seeds = builder.add("tb_product", count=100).execute()

# All rows have valid data:
for product in seeds.tb_product:
    assert product.status in ['active', 'pending', 'archived']
    assert 0 < product.price < 10000
    assert product.stock >= 0
```

**Supported Constraint Types:**
- **Enum values:** `status IN ('active', 'inactive')`
- **Range constraints:** `price > 0`, `price < 10000`, `stock >= 0`
- **BETWEEN:** `age BETWEEN 18 AND 65`
- **Combined:** `price > 0 AND price < 10000`

**Complex constraints** (e.g., `total = price * quantity`) emit warnings and require manual overrides.

### Batch Operations API

Fluent API for multi-table seeding with conditional operations:

```python
builder = SeedBuilder(conn, schema="public")

# Context manager - auto-executes on exit
with builder.batch() as batch:
    batch.add("tb_manufacturer", count=10)
    batch.add("tb_model", count=50)
    batch.add("tb_variant", count=200)

# Conditional operations
include_test_data = True
include_demo_data = False

with builder.batch() as batch:
    batch.when(include_test_data).add("tb_test_user", count=20)
    batch.when(include_demo_data).add("tb_demo_product", count=100)  # Skipped

# Dynamic count with callable
import random

seeds = builder.add(
    "tb_product",
    count=lambda: random.randint(50, 100)  # Generate 50-100 products
).execute()
```

## pytest Integration

Use the `@seed_data` decorator for test fixtures:

```python
import pytest
from fraiseql_data import seed_data

@seed_data("tb_manufacturer", count=5)
@seed_data("tb_model", count=20)
def test_models(seeds):
    """Test with seeded data - auto-cleanup after test."""
    manufacturers = seeds.tb_manufacturer
    models = seeds.tb_model

    assert len(manufacturers) == 5
    assert len(models) == 20

    # Verify FK relationships
    for model in models:
        assert model.fk_manufacturer in [m.pk_manufacturer for m in manufacturers]

    # Data automatically cleaned up after test
```

**Features:**
- Automatic setup before test
- Automatic cleanup after test (even on failure)
- Works with existing fixtures
- Can be stacked for multiple tables

## API Reference

### SeedBuilder

Main API for declarative seed generation.

```python
from fraiseql_data import SeedBuilder

builder = SeedBuilder(conn, schema="public")
```

#### Methods

**`add(table, count, strategy="faker", overrides=None)`**

Add table to seed plan.

```python
builder.add("tb_product", count=100, overrides={
    "price": lambda: random.uniform(10.0, 500.0)
})
```

**`execute()`**

Execute seed plan and return generated data.

```python
seeds = builder.execute()  # Returns Seeds object
```

### Seeds

Container for generated data with attribute access.

```python
seeds = builder.execute()

# Access tables by name
products = seeds.tb_product  # List[SeedRow]

# Access columns by attribute
for product in products:
    print(product.name)
    print(product.price)
    print(product.id)
```

### Exceptions

All exceptions inherit from `FraiseQLDataError` and provide helpful error messages:

**Schema/Table Errors:**
- `SchemaNotFoundError` - Schema doesn't exist
- `TableNotFoundError` - Table doesn't exist in schema

**Generation Errors:**
- `ColumnGenerationError` - Can't auto-generate column data
- `UniqueConstraintError` - Can't generate unique value after retries

**Dependency Errors:**
- `CircularDependencyError` - Circular FK dependencies detected
- `MissingDependencyError` - Referenced table not in seed plan

**FK Errors:**
- `ForeignKeyResolutionError` - Can't resolve FK reference
- `SelfReferenceError` - Non-nullable self-reference (requires override)

## Examples

### Complex Schema with All Features

```python
from psycopg import connect
from fraiseql_data import SeedBuilder
import random

conn = connect("postgresql://localhost/testdb")
builder = SeedBuilder(conn, schema="public")

seeds = (
    builder
    # Organizations: UNIQUE name, bulk insert
    .add("tb_organization", count=10)

    # Categories: Self-referencing hierarchy
    .add("tb_category", count=30)

    # Products: FKs, UNIQUE sku, custom overrides
    .add("tb_product", count=500, overrides={
        "price": lambda: round(random.uniform(5.0, 1000.0), 2),
        "stock": lambda: random.randint(0, 100),
        "status": lambda: random.choice(["active", "discontinued"])
    })

    .execute()
)

print(f"Created {len(seeds.tb_organization)} organizations")
print(f"Created {len(seeds.tb_category)} categories")
print(f"Created {len(seeds.tb_product)} products")

# Verify data integrity
for product in seeds.tb_product:
    assert product.fk_organization in [o.pk_organization for o in seeds.tb_organization]
    assert product.price > 0
    assert 0 <= product.stock <= 100
```

### Testing with Seed Data

```python
import pytest
from fraiseql_data import seed_data

@seed_data("tb_manufacturer", count=3)
@seed_data("tb_model", count=15)
@seed_data("tb_variant", count=50)
def test_search_variants(seeds, db_conn):
    """Test variant search with realistic seed data."""
    # Test data already seeded
    variants = seeds.tb_variant

    # Test search functionality
    results = search_variants(db_conn, query="variant")
    assert len(results) > 0

    # Verify FK relationships
    for variant in results:
        assert variant.fk_model in [m.pk_model for m in seeds.tb_model]

    # Data cleaned up automatically after test
```

## Development

### Running Tests

```bash
# All tests
uv run pytest

# With coverage
uv run pytest --cov=src/fraiseql_data

# Specific test file
uv run pytest tests/test_bulk_insert.py -v
```

### Linting

```bash
uv run ruff check src/ tests/
```

## Architecture

fraiseql-data uses a modular architecture:

- **Introspection:** Query information_schema for tables, columns, FKs, UNIQUE constraints, CHECK constraints
- **Dependency Graph:** Topological sort for correct insertion order
- **Generators:** Faker, Trinity, Sequential, CHECK constraint satisfaction (extensible)
- **Backends:** DirectBackend (bulk INSERT), StagingBackend (in-memory), future: CopyBackend
- **Import/Export:** JSON and CSV with automatic type conversion
- **Batch API:** Context manager with conditional operations
- **Decorators:** pytest integration with auto-cleanup

## Roadmap

**Phase 1 (Complete):**
- ✅ Schema introspection
- ✅ Trinity pattern support
- ✅ FK dependency resolution
- ✅ Realistic data with Faker
- ✅ pytest decorator integration

**Phase 2 (Complete):**
- ✅ Self-referencing table support
- ✅ UNIQUE constraint handling
- ✅ Bulk insert optimization (5x speedup)

**Phase 3 (Complete):**
- ✅ Data export (JSON, CSV)

**Phase 4 (Complete):**
- ✅ Data import (JSON, CSV with type conversion)
- ✅ Staging backend (in-memory testing without database)
- ✅ CHECK constraint auto-satisfaction
- ✅ Batch operations API with conditionals

**Future:**
- Custom generator plugins
- Multi-column UNIQUE constraints
- COPY backend for massive datasets (10x faster)
- Parallel batch processing
- Multi-database support (MySQL, SQLite)

## Contributing

Contributions welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT License - see [LICENSE](LICENSE)

## Links

- [Documentation](../../../docs/)
- [Performance Benchmarks](PERFORMANCE.md)
- [GitHub Issues](https://github.com/lionel/fraiseql-seed/issues)
