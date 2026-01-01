# Seed Common Examples

This directory contains example seed common files demonstrating different formats and use cases.

## Files

### Basic Examples

**`seed_common.yaml`** - Baseline counts format (Format 1)
- Simplest format: just specify instance counts per table
- Use when you don't need explicit data control
- Example:
  ```yaml
  baseline:
    tb_organization: 5
    tb_machine: 10
  ```

**`seed_common_explicit.yaml`** - Explicit data format (Format 2)
- Full control over baseline data with exact values
- Use for deterministic testing with specific scenarios
- Example:
  ```yaml
  tb_organization:
    - identifier: "org-internal"
      name: "Internal Organization"
      org_type: "internal"
  ```

### Environment-Specific Examples

**`seed_common.dev.yaml`** - Development environment
- Larger baseline for realistic local development
- 20+ organizations, 50+ machines
- Rich reference data

**`seed_common.staging.yaml`** - Staging/QA environment
- Minimal production-like baseline
- Optimized for CI/CD speed
- 3 orgs, 5 machines

## Usage

### Option 1: Direct File Path

```python
from fraiseql_data import SeedBuilder

builder = SeedBuilder(
    conn,
    schema="public",
    seed_common="db/seed_common.yaml"  # Direct path
)
```

### Option 2: Directory Auto-Detection

```python
# Set environment variable
import os
os.environ['FRAISEQL_ENV'] = 'dev'

builder = SeedBuilder(
    conn,
    schema="public",
    seed_common="db/"  # Auto-loads seed_common.dev.yaml
)
```

Auto-detection order:
1. `seed_common.{ENV}.yaml` (if `FRAISEQL_ENV` or `ENV` set)
2. `seed_common.yaml` (fallback)
3. `seed_common.json`
4. `1_seed_common/*.sql` (backward compatible)

### Option 3: SQL Format (Backward Compatible)

```python
# Place SQL files in db/1_seed_common/
# fraiseql-data parses Trinity UUIDs to extract instance counts

builder = SeedBuilder(
    conn,
    schema="public",
    seed_common="db/1_seed_common"  # SQL directory
)
```

## Instance Ranges

Seed common enforces clear instance number separation:

| Range | Purpose | Example |
|-------|---------|---------|
| 1 - 1,000 | Seed common baseline | Reserved, never changes |
| 1,001 - 999,999 | Test data | Generated per test run |
| 1,000,000+ | Runtime generated | Mass data generation |

This prevents UUID collisions when creating multiple `SeedBuilder` instances.

## Choosing a Format

**Use Format 1 (baseline counts)** when:
- ✅ You just need existence of baseline data
- ✅ Exact values don't matter
- ✅ You want simplicity

**Use Format 2 (explicit data)** when:
- ✅ You need deterministic test scenarios
- ✅ Baseline data has specific business meaning
- ✅ FK relationships need exact control

**Use SQL format** when:
- ✅ You have existing SQL seed files
- ✅ You need backward compatibility
- ✅ You prefer SQL over YAML/JSON

## Migration from Phase 5

Phase 6 replaced the `reuse_existing` parameter with seed common:

```python
# ❌ Phase 5 (removed)
builder.add("table", count=10, auto_deps=True, reuse_existing=True)

# ✅ Phase 6 (seed common)
builder = SeedBuilder(conn, schema="test", seed_common="db/seed_common.yaml")
builder.add("table", count=10, auto_deps=True)
```

Benefits:
- ✅ No database queries for reuse (faster)
- ✅ Deterministic baseline (reproducible tests)
- ✅ Environment-specific baselines (dev vs staging)
- ✅ Self-documenting Trinity UUIDs (can identify origin)

## Validation

Seed common files are validated on load:
- FK references must exist within seed common
- FK values must be within valid instance ranges
- Instance counts must not exceed 1,000 (SEED_COMMON_MAX)
- No circular dependencies allowed

Validation can be disabled:
```python
builder = SeedBuilder(
    conn,
    schema="public",
    seed_common="db/seed_common.yaml",
    validate_seed_common=False  # Skip validation
)
```

## Best Practices

1. **Keep it minimal** - Seed common is baseline only, not test data
2. **Use environment variants** - Different baselines for dev/staging/prod
3. **Version control** - Commit seed common files to git
4. **Document business logic** - Add comments explaining why data exists
5. **Validate regularly** - Let validation catch FK issues early

## Examples in Tests

See `tests/test_seed_common.py` for comprehensive examples of:
- Loading all formats (YAML, JSON, SQL)
- Environment detection
- FK validation
- Integration with SeedBuilder
- Instance range management
