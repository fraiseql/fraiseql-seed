# fraiseql-data

Schema-aware seed data generation for PostgreSQL with Trinity pattern support.

[![Quality Gate](https://github.com/fraiseql/fraiseql-seed/actions/workflows/quality-gate.yml/badge.svg)](https://github.com/fraiseql/fraiseql-seed/actions/workflows/quality-gate.yml)
[![codecov](https://codecov.io/gh/fraiseql/fraiseql-seed/branch/main/graph/badge.svg?flag=fraiseql-data)](https://codecov.io/gh/fraiseql/fraiseql-seed?flag=fraiseql-data)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Status**: ✅ v0.1.0 Production-Ready | 🔒 Government-Grade Security | 📋 SBOM Available

## Table of Contents

- [Overview](#overview)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Core Features](#core-features)
  - [1. Automatic Dependency Resolution](#1-automatic-dependency-resolution)
  - [2. Trinity Pattern Support](#2-trinity-pattern-support)
  - [3. Realistic Data Generation](#3-realistic-data-generation)
  - [4. Custom Overrides](#4-custom-overrides)
- [Phase 2 Features](#phase-2-features-new)
  - [Self-Referencing Tables](#self-referencing-tables)
  - [UNIQUE Constraint Handling](#unique-constraint-handling)
  - [Bulk Insert Optimization](#bulk-insert-optimization)
- [Phase 3 Features](#phase-3-features)
  - [Data Export](#data-export)
- [Phase 4 Features](#phase-4-features-new)
  - [Data Import](#data-import)
  - [Staging Backend (In-Memory Testing)](#staging-backend-in-memory-testing)
  - [CHECK Constraint Auto-Satisfaction](#check-constraint-auto-satisfaction)
  - [Batch Operations API](#batch-operations-api)
- [Phase 5 Features](#phase-5-features-new)
  - [Auto-Dependency Resolution](#auto-dependency-resolution)
  - [Auto-Deps with Explicit Counts](#auto-deps-with-explicit-counts)
  - [Auto-Deps with Overrides](#auto-deps-with-overrides)
  - [Manual Precedence](#manual-precedence)
  - [Multi-Path Deduplication](#multi-path-deduplication)
  - [Auto-Deps with Batch Operations](#auto-deps-with-batch-operations)
  - [Deep Hierarchies](#deep-hierarchies)
- [Phase 6 Features](#phase-6-features-new)
  - [Seed Common Baseline](#seed-common-baseline)
  - [Format 1: Baseline Counts (Simple)](#format-1-baseline-counts-simple)
  - [Format 2: Explicit Data (Deterministic)](#format-2-explicit-data-deterministic)
  - [Environment-Specific Baselines](#environment-specific-baselines)
  - [Auto-Deps with Seed Common](#auto-deps-with-seed-common)
  - [FK Validation](#fk-validation)
  - [Self-Documenting Trinity UUIDs](#self-documenting-trinity-uuids)
  - [Migration from Phase 5](#migration-from-phase-5)
- [pytest Integration](#pytest-integration)
- [API Reference](#api-reference)
- [Examples](#examples)
  - [Complex Schema with All Features](#complex-schema-with-all-features)
  - [Testing with Seed Data](#testing-with-seed-data)
- [Development](#development)
  - [Running Tests](#running-tests)
  - [Linting](#linting)
- [Architecture](#architecture)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)
- [Links](#links)

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

## Phase 5 Features (New!)

### Auto-Dependency Resolution

Automatically generate parent dependencies without manual specification:

```python
builder = SeedBuilder(conn, schema="public")

# Before: Manual dependency specification
seeds = (
    builder
    .add("tb_organization", count=1)
    .add("tb_machine", count=5)
    .add("tb_allocation", count=20)
    .execute()
)

# After: Auto-generate dependencies
seeds = builder.add("tb_allocation", count=20, auto_deps=True).execute()

# Automatically creates:
# - 1 organization (root dependency)
# - 5 machines (inferred from FK relationships)
# - 20 allocations (requested)
```

**How it works:**
- Introspects foreign key relationships recursively
- Builds dependency tree via depth-first traversal
- Generates minimal parents (1 row per dependency by default)
- Deduplicates when multiple paths lead to same table

#### Auto-Deps with Explicit Counts

Specify custom counts for specific dependencies:

```python
seeds = builder.add(
    "tb_allocation",
    count=100,
    auto_deps={
        "tb_organization": 3,  # Create 3 organizations
        "tb_machine": 10,      # Create 10 machines
    }
).execute()

# Creates: 3 orgs → 10 machines → 100 allocations
```

#### Auto-Deps with Overrides

Customize auto-generated dependency data:

```python
seeds = builder.add(
    "tb_allocation",
    count=50,
    auto_deps={
        "tb_organization": {
            "count": 2,
            "overrides": {
                "name": lambda i: f"Test Organization {i}",
                "org_type": "nonprofit",
            }
        }
    }
).execute()

# Organizations have custom names and type
assert seeds.tb_organization[0].name == "Test Organization 1"
assert seeds.tb_organization[0].org_type == "nonprofit"
```

#### Manual Precedence

Manual `.add()` calls take precedence over auto-deps:

```python
# Manual specification wins
seeds = (
    builder
    .add("tb_organization", count=5)  # Manual: create 5
    .add("tb_machine", count=10, auto_deps={"tb_organization": 2})  # Auto-deps ignored
    .execute()
)

# Result: 5 organizations (manual count used)
# Warning logged about conflict
```

#### Multi-Path Deduplication

When multiple paths lead to same dependency, only one instance is created:

```python
# Schema:
# tb_allocation → tb_machine → tb_organization
# tb_allocation → tb_contract → tb_organization

seeds = builder.add("tb_allocation", count=10, auto_deps=True).execute()

# Result: 1 organization (deduplicated despite 2 paths)
assert len(seeds.tb_organization) == 1
assert len(seeds.tb_machine) == 1
assert len(seeds.tb_contract) == 1
```

#### Auto-Deps with Batch Operations

Auto-deps works seamlessly with batch operations:

```python
with builder.batch() as batch:
    batch.add("tb_machine", count=10, auto_deps=True)
    batch.add("tb_allocation", count=50, auto_deps=True)

# Dependencies are deduplicated across batch:
# - 1 organization (shared by both tables)
# - 10 machines
# - 50 allocations
```

#### Deep Hierarchies

Auto-deps handles deep dependency chains (6+ levels):

```python
# Schema: room → building → city → state → country → region

seeds = builder.add("tb_room", count=100, auto_deps=True).execute()

# Automatically generates entire hierarchy:
# 1 region → 1 country → 1 state → 1 city → 1 building → 100 rooms
assert len(seeds.tb_region) == 1
assert len(seeds.tb_room) == 100
```

## Phase 6 Features (New!)

### Seed Common Baseline

Define a required baseline layer that all test data builds upon, eliminating UUID collisions:

```python
# Define seed common baseline
builder = SeedBuilder(
    conn,
    schema="public",
    seed_common="db/seed_common.yaml"  # Baseline file
)

# Test data automatically starts after seed common range
seeds = builder.add("tb_allocation", count=100, auto_deps=True).execute()
```

**Instance Range Separation:**
- **1 - 1,000**: Seed common (reserved baseline, never changes)
- **1,001 - 999,999**: Test data (generated per test run)
- **1,000,000+**: Runtime generated (mass data generation)

#### Format 1: Baseline Counts (Simple)

Define just the instance counts per table:

```yaml
# db/seed_common.yaml
baseline:
  tb_organization: 5      # 5 organizations in baseline
  tb_machine: 10          # 10 machines
  tb_contract: 2          # 2 contracts
```

#### Format 2: Explicit Data (Deterministic)

Define exact baseline data with specific values:

```yaml
# db/seed_common.yaml
tb_organization:
  - identifier: "org-internal"
    name: "Internal Organization"
    org_type: "internal"

  - identifier: "org-customer-acme"
    name: "ACME Corporation"
    org_type: "customer"

tb_location:
  - identifier: "loc-warehouse-main"
    name: "Main Warehouse"
    fk_organization: 1  # References instance 1
```

#### Environment-Specific Baselines

Different baselines for dev/staging/production:

```yaml
# db/seed_common.dev.yaml (development)
baseline:
  tb_organization: 20    # More data for realistic dev testing
  tb_machine: 50

# db/seed_common.staging.yaml (CI/CD)
baseline:
  tb_organization: 3     # Minimal for fast test execution
  tb_machine: 5
```

**Auto-detection:**
```python
import os
os.environ['FRAISEQL_ENV'] = 'dev'  # or 'staging', 'prod'

builder = SeedBuilder(
    conn,
    schema="public",
    seed_common="db/"  # Auto-loads seed_common.dev.yaml
)
```

**Resolution order:**
1. `seed_common.{ENV}.yaml` (if `FRAISEQL_ENV` or `ENV` set)
2. `seed_common.yaml` (fallback)
3. `seed_common.json`
4. `1_seed_common/*.sql` (backward compatible SQL format)

#### Auto-Deps with Seed Common

Auto-dependencies use seed common instead of generating duplicates:

```python
# Seed common has 5 organizations
builder = SeedBuilder(conn, schema="public", seed_common="db/")

# Auto-deps uses existing organizations from seed common
seeds = builder.add(
    "tb_allocation",
    count=100,
    auto_deps={"tb_organization": 3}  # Uses 3 from seed common
).execute()

# Result: No new organizations generated (uses baseline)
assert len(seeds.tb_organization) == 0  # Satisfied by seed common
```

**When seed common insufficient:**
```python
# Seed common has 5 organizations, but need 10
seeds = builder.add(
    "tb_allocation",
    count=100,
    auto_deps={"tb_organization": 10}
).execute()

# Result: Generates 5 more (10 - 5 from seed common = 5 new)
assert len(seeds.tb_organization) == 5  # Generated the difference
```

#### FK Validation

Seed common validates FK relationships on load:

```python
builder = SeedBuilder(
    conn,
    schema="public",
    seed_common="db/seed_common.yaml",  # Validates by default
)

# Validation checks:
# - All FK references exist within seed common
# - FK values within valid instance ranges (1-1,000)
# - No circular dependencies
# - Instance counts ≤ SEED_COMMON_MAX (1,000)
```

**Disable validation:**
```python
builder = SeedBuilder(
    conn,
    schema="public",
    seed_common="db/seed_common.yaml",
    validate_seed_common=False  # Skip validation
)
```

#### Self-Documenting Trinity UUIDs

Trinity pattern UUIDs encode instance numbers for traceability:

```python
# Seed common instance 5:
# UUID: 2a6f3c21-0000-4000-8000-000000000005
#                                  ^^^^^^^^^^^^ instance number

# Test data instance 1,001:
# UUID: 2a6f3c21-0000-4000-8000-000000001001
#                                  ^^^^^^^^^^^^ instance number

# You can identify data origin from UUID alone!
```

#### Migration from Phase 5

Phase 6 replaces `reuse_existing` with seed common:

```python
# ❌ Phase 5 (removed in Phase 6)
builder.add("table", count=10, auto_deps=True, reuse_existing=True)

# ✅ Phase 6 (seed common baseline)
builder = SeedBuilder(conn, schema="test", seed_common="db/seed_common.yaml")
builder.add("table", count=10, auto_deps=True)
```

**Benefits:**
- ✅ No database queries for reuse (faster)
- ✅ Deterministic baseline (reproducible tests)
- ✅ Environment-specific baselines
- ✅ Self-documenting UUIDs
- ✅ FK validation on load

**See:** `examples/seed_common/` for complete examples

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

For complete API documentation including all classes, methods, parameters, and examples, see **[API.md](docs/API.md)**.

**Quick reference:**
- `SeedBuilder` - Main API for seed generation
- `Seeds` - Container for generated data with export/import
- `@seed_data` - pytest decorator for test fixtures
- Exceptions - Comprehensive error handling
- Models - TableInfo, ColumnInfo, SeedCommon

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
- **Auto-Dependency Resolver:** Recursive FK traversal, DAG-based deduplication, multi-path handling
- **Seed Common:** Baseline management with multi-format support (YAML, JSON, SQL), FK validation, environment detection
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

**Phase 5 (Complete):**
- ✅ Auto-dependency resolution (auto_deps parameter)
- ✅ Multi-path deduplication (DAG-based)
- ✅ Manual precedence handling
- ✅ Deep hierarchy support (6+ levels)
- ✅ Batch integration with auto-deps

**Phase 6 (Complete):**
- ✅ Seed common baseline system
- ✅ Multi-format support (YAML, JSON, SQL)
- ✅ Environment-specific baselines
- ✅ FK validation on load
- ✅ Instance range separation (1-1K seed, 1K-1M test, 1M+ generated)
- ✅ Self-documenting Trinity UUIDs

**Future:**
- Custom generator plugins
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
