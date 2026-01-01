# fraiseql-data Troubleshooting Guide

Common issues and solutions for fraiseql-data seed generation.

## Table of Contents

- [Installation Issues](#installation-issues)
- [Database Connection Issues](#database-connection-issues)
- [Schema Introspection Issues](#schema-introspection-issues)
- [Foreign Key Issues](#foreign-key-issues)
- [UNIQUE Constraint Issues](#unique-constraint-issues)
- [CHECK Constraint Issues](#check-constraint-issues)
- [Seed Common Issues](#seed-common-issues)
- [Performance Issues](#performance-issues)
- [Data Generation Issues](#data-generation-issues)

---

## Installation Issues

### Error: `ModuleNotFoundError: No module named 'fraiseql_data'`

**Cause**: Package not installed or installed incorrectly.

**Solution**:
```bash
# Install with uv (recommended)
uv pip install fraiseql-data

# Or with pip
pip install fraiseql-data

# For development (from source)
cd packages/fraiseql-data
uv pip install -e .
```

### Error: `ImportError: cannot import name 'SeedBuilder'`

**Cause**: Old cached `.pyc` files or incomplete installation.

**Solution**:
```bash
# Clean cache
find . -type d -name __pycache__ -exec rm -rf {} +
find . -type f -name "*.pyc" -delete

# Reinstall
uv pip install --force-reinstall fraiseql-data
```

---

## Database Connection Issues

### Error: `psycopg.OperationalError: connection to server failed`

**Cause**: PostgreSQL not running or connection parameters incorrect.

**Solution**:
```bash
# Check PostgreSQL is running
pg_isready -h localhost -p 5432

# Verify connection string
psql "postgresql://user:password@localhost:5432/dbname"

# Common fixes:
# 1. Start PostgreSQL: systemctl start postgresql
# 2. Check pg_hba.conf for authentication settings
# 3. Verify user has database access: GRANT ALL ON DATABASE dbname TO user;
```

### Error: `psycopg.errors.InvalidSchemaName: schema "public" does not exist`

**Cause**: Database created without default schema.

**Solution**:
```sql
-- Create public schema
CREATE SCHEMA IF NOT EXISTS public;

-- Grant usage
GRANT ALL ON SCHEMA public TO your_user;
```

---

## Schema Introspection Issues

### Error: `SchemaIntrospectionError: No tables found in schema 'public'`

**Cause**: Schema is empty or tables not visible to user.

**Solution**:
```python
# 1. Verify schema has tables
import psycopg

conn = psycopg.connect("postgresql://...")
with conn.cursor() as cur:
    cur.execute("""
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public'
    """)
    print(cur.fetchall())  # Should list tables

# 2. Check permissions
# GRANT SELECT ON ALL TABLES IN SCHEMA public TO your_user;

# 3. Use confiture to build schema first
# confiture build --env test
```

### Error: `IntrospectionError: Could not determine column type for 'data'`

**Cause**: Custom or unsupported PostgreSQL type.

**Solution**:
```python
# Use custom generator for unsupported types
from fraiseql_data import SeedBuilder, register_generator

@register_generator("custom_type")
def generate_custom_type():
    return "custom_value"

builder = SeedBuilder(conn, "public")
builder.add("tb_custom", count=10, custom_generators={"data": generate_custom_type})
```

---

## Foreign Key Issues

### Error: `ForeignKeyError: Foreign key 'user_id' references non-existent table 'tb_user'`

**Cause**: Referenced table not seeded yet or doesn't exist.

**Solution**:
```python
# Option 1: Use auto_deps=True to automatically resolve
builder = SeedBuilder(conn, "public")
seeds = builder.add("tb_post", count=100, auto_deps=True).execute()
# Automatically seeds tb_user first

# Option 2: Seed parent tables explicitly
seeds = (
    builder
    .add("tb_user", count=50)      # Parent first
    .add("tb_post", count=100)     # Child second
    .execute()
)

# Option 3: Use seed_common for parent data
# See seed_common section below
```

### Error: `ForeignKeyError: Circular dependency detected: tb_a -> tb_b -> tb_a`

**Cause**: Tables have circular foreign key references.

**Solution**:
```python
# Circular dependencies cannot be auto-resolved with auto_deps=True
# Options:
# 1. Make one FK nullable and seed in phases
# 2. Seed one table first, then UPDATE to add circular FK
# 3. Use seed_common to provide baseline data

# Example: Seed tb_user first, then tb_post with FK to user
seeds = (
    builder
    .add("tb_user", count=10)
    .add("tb_post", count=50)  # FK to tb_user
    .execute()
)

# Then update tb_user.favorite_post_id manually if needed
```

### Error: `ForeignKeyError: No seed common data found for 'tb_category'`

**Cause**: FK references seed_common range (1-1,000) but seed_common not provided.

**Solution**:
```python
# Provide seed_common directory
builder = SeedBuilder(conn, "public", seed_common="db/seed_common/")
seeds = builder.add("tb_product", count=100, auto_deps=True).execute()

# Or explicitly seed parent table
seeds = (
    builder
    .add("tb_category", count=10)  # Generate categories
    .add("tb_product", count=100)  # Products reference categories
    .execute()
)
```

---

## UNIQUE Constraint Issues

### Error: `UniqueConstraintError: Failed to generate unique value for 'email' after 10 attempts`

**Cause**: Too many rows requested for constrained column (e.g., 1M emails with simple pattern).

**Solution**:
```python
# Option 1: Reduce row count
builder.add("tb_user", count=1000)  # Instead of 100,000

# Option 2: Use custom generator with more entropy
from faker import Faker
fake = Faker()

def generate_unique_email():
    import uuid
    return f"user-{uuid.uuid4()}@example.com"

builder.add("tb_user", count=10000, custom_generators={"email": generate_unique_email})

# Option 3: Increase retry limit (not recommended - symptom of design issue)
# Builder retries 10 times by default
```

### Error: `UniqueConstraintError: Multi-column UNIQUE constraint violated on ('tenant_id', 'slug')`

**Cause**: Multi-column UNIQUE constraint detected, but generated combinations collide.

**Solution**:
```python
# fraiseql-data tracks multi-column UNIQUE constraints automatically
# If still failing, reduce row count or use custom generator

def generate_unique_slug(row_data):
    """Generate slug based on other row data to ensure uniqueness."""
    tenant_id = row_data.get("tenant_id", 1)
    import uuid
    return f"slug-{tenant_id}-{uuid.uuid4().hex[:8]}"

builder.add("tb_item", count=1000, custom_generators={"slug": generate_unique_slug})
```

---

## CHECK Constraint Issues

### Warning: `Could not auto-satisfy CHECK constraint: price > 0 AND price < discount_price`

**Cause**: Complex CHECK constraint requires multi-column coordination.

**Solution**:
```python
# Use custom generator to satisfy constraint
def generate_price_discount():
    """Generate coordinated price and discount_price."""
    price = random.uniform(10.0, 100.0)
    discount_price = price * random.uniform(1.1, 1.5)  # 10-50% higher
    return {"price": price, "discount_price": discount_price}

# Apply to both columns
data = generate_price_discount()
builder.add("tb_product", count=100, custom_generators={
    "price": lambda: data["price"],
    "discount_price": lambda: data["discount_price"]
})
```

### Error: `CheckConstraintError: Generated value 'active' violates CHECK constraint "status IN ('active', 'pending', 'archived')"`

**Cause**: Faker generated value outside allowed set (rare, but possible).

**Solution**:
```python
# Use custom generator with explicit choices
import random

def generate_status():
    return random.choice(["active", "pending", "archived"])

builder.add("tb_order", count=100, custom_generators={"status": generate_status})
```

---

## Seed Common Issues

### Error: `SeedCommonError: Seed common file not found: db/seed_common/tb_user.yaml`

**Cause**: `seed_common` path incorrect or file doesn't exist.

**Solution**:
```python
# Check seed_common directory structure
# db/seed_common/
#   tb_user.yaml
#   tb_category.yaml
#   ...

# Verify path is correct
import os
print(os.path.exists("db/seed_common/tb_user.yaml"))

# Provide correct path to SeedBuilder
builder = SeedBuilder(conn, "public", seed_common="db/seed_common/")
```

### Error: `SeedCommonValidationError: FK constraint violated: user_id=1005 not in seed_common range (1-1000)`

**Cause**: Seed common data references instance IDs outside seed_common range.

**Solution**:
```yaml
# db/seed_common/tb_user.yaml
# Instance IDs must be in range 1-1,000
- id: 1  # ✅ Valid
  name: "Admin"
  email: "admin@example.com"

- id: 1001  # ❌ Invalid - outside seed_common range
  name: "Test User"

# Use range 1-1,000 for seed_common
# Use range 1,001+ for test data
# Use range 1,000,000+ for generated data
```

### Warning: `Seed common not provided - UUID collisions may occur in large datasets`

**Cause**: No `seed_common` directory provided, risk of UUID collisions.

**Solution**:
```python
# Provide seed_common to avoid warning
builder = SeedBuilder(conn, "public", seed_common="db/seed_common/")

# Or suppress warning if intentional (small datasets)
import warnings
warnings.filterwarnings("ignore", category=UserWarning, message=".*seed_common.*")
```

### Error: `EnvironmentError: Could not determine environment. Set FRAISEQL_ENV or ENV variable`

**Cause**: Seed common has environment-specific variants but no environment detected.

**Solution**:
```bash
# Set environment variable
export FRAISEQL_ENV=development
python -m pytest

# Or in code
import os
os.environ["FRAISEQL_ENV"] = "development"

# Or use explicit seed_common path
builder = SeedBuilder(conn, "public", seed_common="db/seed_common/dev/")
```

---

## Performance Issues

### Issue: Seed generation takes >10 seconds for 1,000 rows

**Cause**: Multiple possible bottlenecks.

**Diagnosis**:
```python
import time

# 1. Check database connection latency
start = time.time()
with conn.cursor() as cur:
    cur.execute("SELECT 1")
print(f"DB ping: {(time.time() - start) * 1000:.2f}ms")

# 2. Check introspection time
start = time.time()
from fraiseql_data import Introspector
introspector = Introspector(conn, "public")
introspector.introspect()
print(f"Introspection: {time.time() - start:.2f}s")

# 3. Check data generation time (no DB)
from fraiseql_data.backends import StagingBackend
staging = StagingBackend()
builder = SeedBuilder(conn, "public", backend=staging)
start = time.time()
builder.add("tb_user", count=1000).execute()
print(f"Generation (in-memory): {time.time() - start:.2f}s")
```

**Solutions**:
```python
# 1. Use StagingBackend for testing (no database writes)
from fraiseql_data.backends import StagingBackend
backend = StagingBackend()
builder = SeedBuilder(conn, "public", backend=backend)

# 2. Use batch inserts (already default behavior)
# fraiseql-data uses executemany() automatically

# 3. Disable foreign key checks temporarily (use with caution)
with conn.cursor() as cur:
    cur.execute("SET session_replication_role = replica;")  # Disable FK checks
    seeds = builder.add("tb_user", count=10000).execute()
    cur.execute("SET session_replication_role = DEFAULT;")  # Re-enable FK checks
conn.commit()

# 4. Use seed_common for frequently-referenced parent tables
# Avoids generating thousands of parent rows
```

### Issue: Memory usage spikes for large datasets (100K+ rows)

**Cause**: All generated data held in memory before insertion.

**Solution**:
```python
# Generate in batches
for batch in range(10):
    seeds = builder.add("tb_user", count=10000).execute()
    builder.reset()  # Clear internal state

# Or use smaller count values
seeds = builder.add("tb_user", count=50000).execute()  # Instead of 500,000
```

---

## Data Generation Issues

### Issue: Generated data not realistic enough

**Cause**: Using default Faker mappings.

**Solution**:
```python
# Use custom generators for domain-specific data
from faker import Faker
fake = Faker()

def generate_product_name():
    """Generate realistic product names."""
    adjectives = ["Premium", "Deluxe", "Standard", "Pro", "Ultra"]
    nouns = ["Widget", "Gadget", "Device", "Tool", "Kit"]
    return f"{fake.random_element(adjectives)} {fake.random_element(nouns)}"

def generate_sku():
    """Generate realistic SKU codes."""
    return f"{fake.random_uppercase_letter()}{fake.random_uppercase_letter()}{fake.random_int(1000, 9999)}"

builder.add("tb_product", count=100, custom_generators={
    "name": generate_product_name,
    "sku": generate_sku,
    "price": lambda: round(fake.random.uniform(9.99, 999.99), 2)
})
```

### Issue: Need deterministic/reproducible data for testing

**Cause**: Faker uses random seed by default.

**Solution**:
```python
# Set Faker seed for reproducibility
from faker import Faker
Faker.seed(12345)

# Now data generation is deterministic
builder = SeedBuilder(conn, "public")
seeds = builder.add("tb_user", count=100).execute()
# Same 100 users every time with seed 12345
```

### Issue: Need Trinity pattern UUIDs (pk_*, id, identifier)

**Cause**: Using default UUID generation instead of fraiseql-uuid.

**Solution**:
```python
# Install fraiseql-uuid
# uv pip install fraiseql-uuid

# fraiseql-data automatically uses fraiseql-uuid for Trinity columns
# No configuration needed - just ensure columns follow naming convention:
# - pk_user (bigserial primary key)
# - id (UUID, indexed)
# - identifier (VARCHAR, human-readable)

# Generated UUIDs will be pattern-based: UUUU-SSSS-NNNNNNNN
# Example: USER-0001-00000042
```

### Issue: Generated JSONB data is empty `{}`

**Cause**: JSONB columns default to empty object.

**Solution**:
```python
import json

def generate_metadata():
    """Generate realistic JSONB metadata."""
    return json.dumps({
        "tags": fake.words(nb=5),
        "attributes": {
            "color": fake.color_name(),
            "size": fake.random_element(["S", "M", "L", "XL"]),
            "weight": fake.random_int(100, 5000)
        },
        "created_at": fake.iso8601()
    })

builder.add("tb_product", count=100, custom_generators={"metadata": generate_metadata})
```

---

## Getting Help

### Still having issues?

1. **Check the README**: `/packages/fraiseql-data/README.md`
2. **Check examples**: `/examples/` directory
3. **Run tests**: `pytest -xvs` to see detailed test behavior
4. **Enable debug logging**:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```
5. **File an issue**: GitHub Issues (include minimal reproducible example)

### Useful Debug Commands

```python
# Inspect generated data without inserting
from fraiseql_data.backends import StagingBackend
backend = StagingBackend()
builder = SeedBuilder(conn, "public", backend=backend)
seeds = builder.add("tb_user", count=10).execute()
print(backend.data)  # View generated rows

# Inspect introspected schema
introspector = Introspector(conn, "public")
schema = introspector.introspect()
print(f"Tables: {list(schema.keys())}")
for table, info in schema.items():
    print(f"{table}: {info['columns']}")
    print(f"  FKs: {info['foreign_keys']}")
    print(f"  UNIQUE: {info['unique_constraints']}")

# Test Faker column mapping
from fraiseql_data.generators.faker_gen import get_faker_for_column
faker = get_faker_for_column("email", "VARCHAR")
print(f"Email: {faker()}")
```

---

**Last Updated**: 2026-01-01
**Version**: 0.1.0
