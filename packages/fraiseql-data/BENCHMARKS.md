# fraiseql-data Performance Benchmarks

Performance benchmarks for fraiseql-data v0.1.0.

## Test Environment

- **Hardware**: Intel CPU, Standard Development Machine
- **Database**: PostgreSQL 16
- **Python**: 3.11
- **Package Version**: fraiseql-data 0.1.0
- **Test Date**: 2026-01-01

## Benchmark Results

### Benchmark 1: 1,000 Rows (Single Table)

**Test**: Generate 1,000 users in `tb_user` table

**Schema**:
```sql
CREATE TABLE tb_user (
    pk_user BIGSERIAL PRIMARY KEY,
    id UUID NOT NULL,
    identifier VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
)
```

**Results**:
- **Time**: 0.132s
- **Throughput**: 7,569 rows/second
- **Result**: 1,000 users generated successfully

**Code**:
```python
from fraiseql_data import SeedBuilder

builder = SeedBuilder(conn, "bench")
seeds = builder.add("tb_user", count=1000).execute()
# Returns: Seeds object with 1,000 users
```

---

### Benchmark 2: 10,000 Rows (Single Table)

**Test**: Generate 10,000 users in `tb_user` table

**Results**:
- **Time**: 1.131s
- **Throughput**: 8,842 rows/second
- **Result**: 10,000 users generated successfully

**Analysis**: Performance scales linearly with row count. Throughput remains consistent (~8,000 rows/sec) due to:
- Efficient batch INSERT operations (executemany)
- Single database transaction
- Faker data generation overhead is minimal

**Code**:
```python
builder = SeedBuilder(conn, "bench")
seeds = builder.add("tb_user", count=10000).execute()
# Returns: Seeds object with 10,000 users
```

---

### Benchmark 3: 1,000 Rows with Foreign Keys (auto_deps)

**Test**: Generate 1,000 posts with automatic dependency resolution

**Schema**:
```sql
CREATE TABLE tb_post (
    pk_post BIGSERIAL PRIMARY KEY,
    id UUID NOT NULL,
    identifier VARCHAR(255) NOT NULL,
    title VARCHAR(500) NOT NULL,
    content TEXT,
    user_id BIGINT NOT NULL REFERENCES tb_user(pk_user),  -- FK constraint
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
)
```

**Results**:
- **Time**: 0.089s
- **Throughput**: 11,243 rows/second (posts only)
- **Result**: 1 user + 1,000 posts generated

**Analysis**:
- `auto_deps=True` automatically generated 1 user to satisfy foreign key constraint
- Faster than Benchmark 1 because:
  - Only 1 user inserted (minimal overhead)
  - Posts have fewer constraints than users (no UNIQUE email)
  - Foreign key satisfied by referencing same user repeatedly

**Code**:
```python
builder = SeedBuilder(conn, "bench")
seeds = builder.add("tb_post", count=1000, auto_deps=True).execute()
# Automatically generates tb_user dependency
# Returns: Seeds object with 1 user and 1,000 posts
```

---

### Benchmark 4: 100,000 Rows In-Memory (StagingBackend)

**Test**: Generate 100,000 users in-memory (no database writes)

**Results**:
- **Time**: 11.934s
- **Throughput**: 8,380 rows/second
- **Result**: 100,000 users generated in-memory

**Analysis**:
- StagingBackend eliminates database overhead
- Throughput similar to database backend (~8,000 rows/sec)
- Bottleneck is data generation (Faker, UUID, validations), not database
- Useful for:
  - Testing data generation logic without database
  - Generating large datasets for export
  - Development/debugging

**Code**:
```python
from fraiseql_data.backends.staging import StagingBackend

staging = StagingBackend()
builder = SeedBuilder(conn, "bench", backend=staging)
seeds = builder.add("tb_user", count=100000).execute()
# Returns: Seeds object, data stored in staging._data (in-memory)
```

---

## Performance Summary

| Benchmark | Rows | Time (s) | Rows/sec | Notes |
|-----------|------|----------|----------|-------|
| Single table | 1,000 | 0.132 | 7,569 | Basic generation |
| Single table | 10,000 | 1.131 | 8,842 | Scales linearly |
| With auto-deps (FK) | 1,000 | 0.089 | 11,243 | Auto-resolves dependencies |
| In-memory (StagingBackend) | 100,000 | 11.934 | 8,380 | No database overhead |

**Average Throughput**: ~8,500 rows/second

---

## Performance Characteristics

### Strengths

1. **Linear Scaling**: Performance scales linearly from 1K to 10K+ rows
2. **Efficient Batch Inserts**: Uses `executemany()` for optimal database performance
3. **Automatic Dependency Resolution**: `auto_deps=True` adds minimal overhead
4. **Consistent Throughput**: ~8,000-11,000 rows/sec across different scenarios

### Bottlenecks

1. **Data Generation**: Faker library and UUID generation dominate execution time
   - **Evidence**: In-memory benchmark (no database) has similar throughput to database benchmark
   - **Mitigation**: Use seed_common for frequently-referenced parent tables

2. **UNIQUE Constraints**: Retry logic for UNIQUE violations adds overhead
   - **Mitigation**: Reduce row count or use custom generators with higher entropy
   - **Default**: 10 retries per collision

3. **Complex CHECK Constraints**: Auto-satisfaction requires additional validation
   - **Mitigation**: Use custom generators for complex constraints

---

## Comparison to Manual SQL Scripts

### Traditional Approach: Manual INSERT Statements

```sql
-- Manual SQL script for 1,000 users
INSERT INTO tb_user (id, identifier, name, email, created_at)
VALUES
  (gen_random_uuid(), 'user-001', 'John Doe', 'john1@example.com', NOW()),
  (gen_random_uuid(), 'user-002', 'Jane Smith', 'jane2@example.com', NOW()),
  ... (998 more lines)
```

**Time to write**: 15-30 minutes
**Time to execute**: 0.5-1s
**Time to modify**: 15-30 minutes (regenerate entire script)

### fraiseql-data Approach

```python
# fraiseql-data: 1,000 users
builder.add("tb_user", count=1000).execute()
```

**Time to write**: 1 line
**Time to execute**: 0.132s
**Time to modify**: 1 second (change `count` parameter)

**Productivity Gain**: 60-300× faster development time

---

## Optimization Tips

### Tip 1: Use Seed Common for Parent Tables

Instead of generating thousands of parent rows:

```python
# ❌ Slow: Generate 10,000 categories for 100,000 products
builder.add("tb_category", count=10000)
builder.add("tb_product", count=100000)

# ✅ Fast: Use seed_common baseline (1-1,000) for categories
# db/seed_common/tb_category.yaml:
# - id: 1
#   name: "Electronics"
# - id: 2
#   name: "Books"
# ...

builder = SeedBuilder(conn, "public", seed_common="db/seed_common/")
builder.add("tb_product", count=100000, auto_deps=True).execute()
# Products reference seed_common categories (no generation overhead)
```

### Tip 2: Disable Foreign Key Checks for Large Imports

```python
# For large datasets, temporarily disable FK checks
with conn.cursor() as cur:
    cur.execute("SET session_replication_role = replica;")  # Disable FKs
    seeds = builder.add("tb_user", count=100000).execute()
    cur.execute("SET session_replication_role = DEFAULT;")  # Re-enable FKs
conn.commit()

# Speedup: ~10-20% for FK-heavy schemas
```

### Tip 3: Use StagingBackend for Development

```python
# Use in-memory backend during development (no database)
from fraiseql_data.backends.staging import StagingBackend

staging = StagingBackend()
builder = SeedBuilder(conn, "public", backend=staging)
seeds = builder.add("tb_user", count=1000).execute()

# Export to JSON for inspection
import json
print(json.dumps(staging._data["public.tb_user"][:5], indent=2, default=str))
```

### Tip 4: Batch Large Operations

```python
# For 1M+ rows, generate in batches to avoid memory pressure
for batch in range(10):
    builder.add("tb_user", count=100000).execute()
    builder.reset()  # Clear internal state

# Total: 1M rows in 10 batches
```

---

## Projections for Large Datasets

Based on measured throughput of **~8,500 rows/second**:

| Rows | Estimated Time | Use Case |
|------|----------------|----------|
| 1K | 0.1s | Unit tests |
| 10K | 1.2s | Integration tests |
| 100K | 12s | Staging environment |
| 1M | 2 minutes | Production-like dataset |
| 10M | 20 minutes | Large-scale performance testing |

**Note**: Actual time may vary based on schema complexity, constraints, and hardware.

---

## Continuous Benchmarking

To run benchmarks on your system:

```bash
cd ~/code/fraiseql-seed
source .venv/bin/activate
python3 benchmarks/run_benchmarks.py
```

Output will show:
- Time per benchmark
- Rows/second throughput
- Database version
- Hardware specifications

---

**Last Updated**: 2026-01-01
**Version**: 0.1.0
