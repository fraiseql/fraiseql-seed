# fraiseql-data

Schema-aware seed data generation for PostgreSQL with Trinity pattern support.

[![Quality Gate](https://github.com/fraiseql/fraiseql-seed/actions/workflows/quality-gate.yml/badge.svg)](https://github.com/fraiseql/fraiseql-seed/actions/workflows/quality-gate.yml)
[![codecov](https://codecov.io/gh/fraiseql/fraiseql-seed/branch/main/graph/badge.svg?flag=fraiseql-data)](https://codecov.io/gh/fraiseql/fraiseql-seed?flag=fraiseql-data)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%20%7C%203.13-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

fraiseql-data generates realistic test data for PostgreSQL databases by:
- **Introspecting your schema** to understand tables, columns, and relationships
- **Respecting foreign key constraints** with automatic dependency resolution
- **Supporting Trinity pattern** (pk_*, id, identifier) for FraiseQL compatibility
- **Generating realistic data** using Faker for domain-appropriate values
- **Correlating related columns** (address, person, geo) for coherent rows
- **Handling complex scenarios** like self-referencing tables, UNIQUE and CHECK constraints

## Installation

```bash
# Using uv (recommended)
uv add fraiseql-data

# Or using pip
pip install fraiseql-data
```

**Requirements:**
- Python 3.12+
- PostgreSQL 14+
- psycopg 3.1+

## Quick Start

```python
from psycopg import connect
from fraiseql_data import SeedBuilder

# Connect to database
conn = connect("postgresql://user:pass@localhost/mydb")

# Build seed plan (with seed common baseline)
builder = SeedBuilder(
    conn,
    schema="public",
    seed_common="db/seed_common.yaml"  # Optional but recommended
)
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

## Features

### Automatic Dependency Resolution

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

# Inserts in correct order: manufacturer -> model -> variant
```

### Auto-Dependency Generation

Automatically generate parent dependencies without manual specification:

```python
# Auto-generate all FK dependencies (1 row each by default)
seeds = builder.add("tb_allocation", count=20, auto_deps=True).execute()

# Specify explicit counts per dependency
seeds = builder.add(
    "tb_allocation",
    count=100,
    auto_deps={
        "tb_organization": 3,
        "tb_machine": 10,
    }
).execute()

# With overrides on auto-generated dependencies
seeds = builder.add(
    "tb_allocation",
    count=50,
    auto_deps={
        "tb_organization": {
            "count": 2,
            "overrides": {"org_type": "nonprofit"},
        }
    }
).execute()
```

### Trinity Pattern Support

Automatic handling of Trinity pattern (pk_*, id, identifier):

```python
seeds = builder.add("tb_manufacturer", count=10).execute()

for mfr in seeds.tb_manufacturer:
    print(f"PK: {mfr.pk_manufacturer}")     # 1, 2, 3, ...
    print(f"ID: {mfr.id}")                  # UUID v4 with pattern
    print(f"Identifier: {mfr.identifier}")  # MANUFACTURER-001, ...
```

### Realistic Data Generation

Uses Faker for domain-appropriate data:

```python
# Faker automatically detects common column names:
# - email -> realistic email addresses
# - name, first_name, last_name -> person names
# - company, company_name -> company names
# - phone, phone_number -> phone numbers
# - address, street -> addresses

seeds = builder.add("tb_user", count=10).execute()
# email: "john.doe@example.com" (not "column_1_value")
```

Numeric columns with precision and scale (`numeric(p,s)`) generate values within bounds:

```python
# numeric(10,2) -> values up to 99,999,999.99
# numeric(5,3)  -> values up to 99.999
```

### Correlated Column Groups

Semantically related columns are automatically detected and generated together for coherent rows:

```python
# Address columns auto-detected and correlated
builder.add("tb_address", count=100)
# -> country/city/state/postal_code are coherent per row
# -> French address gets French city and 5-digit postal code

# Person columns auto-detected
builder.add("tb_user", count=50)
# -> first_name/last_name/email are coherent
# -> email derived as first.last@domain

# Override-aware coherence
builder.add("tb_address", count=100, overrides={"country": "France"})
# -> city, state, postal_code are all French
```

**Built-in groups** (activate when >= 2 matching columns present):

| Group | Fields | Behavior |
|-------|--------|----------|
| address | country, state, city, postal_code, street, address, zip/zipcode/zip_code | Locale-coherent components |
| person | first_name, last_name, name, email | Name pair with derived email |
| geo | latitude, longitude, lat, lng, lon | Coherent lat/lng pair, locale-biased when address group is active |

**Custom groups** for domain-specific correlation:

```python
from fraiseql_data import ColumnGroup

def product_gen(context):
    category = context.get("category") or random.choice(["Electronics", "Clothing"])
    prefix = {"Electronics": "EL", "Clothing": "CL"}[category]
    return {"category": category, "sku": f"{prefix}-{random.randint(1000, 9999)}"}

builder.add("tb_product", count=200, groups=[
    ColumnGroup("product", frozenset({"category", "sku"}), product_gen)
])

# Disable auto-detection entirely
builder.add("tb_address", count=100, groups=[])
```

### Custom Overrides

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

**Override priority:** Overrides take precedence over both automatic FK resolution and column group generation. This enables cross-builder seeding where parent data already exists:

```python
# Parent data already in database from a previous builder/migration
builder.add("tb_product", count=50, overrides={
    "fk_organization": 42,  # Use existing org, skip FK auto-resolution
})
```

When all FK columns pointing to a dependency table are overridden, that table can be omitted from the seed plan entirely.

### Self-Referencing Tables

Support for hierarchical data structures:

```python
seeds = builder.add("tb_category", count=20).execute()

# First category has NULL parent, others pick random parent
categories = seeds.tb_category
assert categories[0].parent_category is None  # Root category
```

### UNIQUE Constraint Handling

Automatic collision detection and retry:

```python
seeds = builder.add("tb_user", count=100).execute()

# Guaranteed unique emails and usernames (max 10 retry attempts)
emails = [u.email for u in seeds.tb_user]
assert len(emails) == len(set(emails))  # No duplicates!
```

For group-generated UNIQUE columns (e.g., email), the entire group is regenerated on collision to preserve coherence. After half of the retry attempts, an email suffix fallback activates (`first.last42@domain`).

### CHECK Constraint Auto-Satisfaction

Automatically generate valid data for CHECK constraints:

```python
# status TEXT NOT NULL CHECK (status IN ('active', 'pending', 'archived'))
# price NUMERIC CHECK (price > 0 AND price < 10000)

# No overrides needed - constraints automatically satisfied!
seeds = builder.add("tb_product", count=100).execute()
```

**Supported:** enum values (`IN`), range constraints (`>`, `<`, `>=`, `<=`), `BETWEEN`.

### Batch Operations

Fluent API for multi-table seeding with conditional operations:

```python
with builder.batch() as batch:
    batch.add("tb_manufacturer", count=10)
    batch.add("tb_model", count=50)
    batch.when(include_demo_data).add("tb_demo_product", count=100)
```

### Data Export / Import

```python
# Export
json_str = seeds.to_json()
seeds.to_csv("tb_manufacturer", "manufacturers.csv")

# Import
imported = Seeds.from_json(file_path="seeds.json")
imported = Seeds.from_csv("tb_manufacturer", "manufacturers.csv")
result = builder.insert_seeds(imported)
```

### Staging Backend (In-Memory Testing)

Generate seed data without a database connection:

```python
from fraiseql_data import SeedBuilder
from fraiseql_data.models import TableInfo, ColumnInfo

builder = SeedBuilder(conn=None, schema="test", backend="staging")

table_info = TableInfo(
    name="tb_product",
    columns=[
        ColumnInfo(name="pk_product", pg_type="integer", is_nullable=False, is_primary_key=True),
        ColumnInfo(name="name", pg_type="text", is_nullable=False),
        ColumnInfo(name="price", pg_type="numeric", is_nullable=True),
    ],
)
builder.set_table_schema("tb_product", table_info)

seeds = builder.add("tb_product", count=100).execute()
```

### Seed Common Baseline

Define a required baseline layer that all test data builds upon, eliminating UUID collisions:

```python
builder = SeedBuilder(
    conn, schema="public",
    seed_common="db/seed_common.yaml"
)
```

**Instance range separation:**
- **1 - 1,000**: Seed common (reserved baseline)
- **1,001 - 999,999**: Test data (generated per test run)
- **1,000,000+**: Runtime generated

Supports YAML, JSON, and environment-specific baselines (`seed_common.dev.yaml`, `seed_common.staging.yaml`).

**Warning behavior:** When `seed_common` is omitted, a warning is logged once per process. Pass `validate_seed_common=False` to suppress.

## pytest Integration

```python
from fraiseql_data import seed_data

@seed_data("tb_manufacturer", count=5)
@seed_data("tb_model", count=20)
def test_models(seeds):
    assert len(seeds.tb_manufacturer) == 5
    assert len(seeds.tb_model) == 20
```

## API Reference

For complete API documentation, see **[API.md](docs/API.md)**.

**Quick reference:**
- `SeedBuilder` - Main API for seed generation
- `ColumnGroup` - Define custom correlated column groups
- `Seeds` - Container for generated data with export/import
- `@seed_data` - pytest decorator for test fixtures

## Development

```bash
# All tests
uv run pytest

# With coverage
uv run pytest --cov=src/fraiseql_data

# Linting
uv run ruff check src/ tests/
```

## Architecture

fraiseql-data uses a modular architecture:

- **Introspection:** Query information_schema for tables, columns, FKs, UNIQUE constraints, CHECK constraints
- **Dependency Graph:** Topological sort for correct insertion order
- **Auto-Dependency Resolver:** Recursive FK traversal, DAG-based deduplication, multi-path handling
- **Seed Common:** Baseline management with multi-format support (YAML, JSON, SQL), FK validation, environment detection
- **Generators:** Faker, Trinity, Column Groups (address/person/geo), CHECK constraint satisfaction (extensible)
- **Backends:** DirectBackend (bulk INSERT), StagingBackend (in-memory)
- **Import/Export:** JSON and CSV with automatic type conversion
- **Batch API:** Context manager with conditional operations
- **Decorators:** pytest integration with auto-cleanup

## License

MIT License - see [LICENSE](../../LICENSE)

## Links
- [GitHub Issues](https://github.com/fraiseql/fraiseql-seed/issues)
