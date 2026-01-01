# fraiseql-uuid

UUID v4 compliant pattern with encoded metadata for the FraiseQL ecosystem.

[![Quality Gate](https://github.com/fraiseql/fraiseql-seed/actions/workflows/quality-gate.yml/badge.svg)](https://github.com/fraiseql/fraiseql-seed/actions/workflows/quality-gate.yml)
[![codecov](https://codecov.io/gh/fraiseql/fraiseql-seed/branch/main/graph/badge.svg?flag=fraiseql-uuid)](https://codecov.io/gh/fraiseql/fraiseql-seed?flag=fraiseql-uuid)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Status**: ✅ v0.1.0 Production-Ready | 🔒 Type-Safe (mypy strict) | 📋 SBOM Available

## Installation

```bash
pip install fraiseql-uuid
```

## Quick Start

```python
from fraiseql_uuid import Pattern, UUIDGenerator

# Create pattern
pattern = Pattern()

# Generate UUID
gen = UUIDGenerator(pattern, table_code="012345")
uuid = gen.generate(instance=1)
print(uuid)  # → "01234521-0000-4000-8000-000000000001"

# Decode UUID
decoded = pattern.decode(uuid)
print(decoded["table_code"])  # → "012345"
print(decoded["instance"])    # → 1
```

## UUID Format

**Code notation:** `{table:6}{type:2}-{func:4}-4{scen:3}-8{scen:1}{test:2}-{inst:12}`
**Docs notation:** `TTTTTTDD-FFFF-4SSS-8STT-IIIIIIIIIIII`

### Components

| Symbol | Component | Length | Default | Description |
|--------|-----------|--------|---------|-------------|
| T | table_code | 6 | - | Table/Entity code (required) |
| D | seed_dir | 2 | 21 | Seed directory (21=general, 22=mutation, 23=query) |
| F | function | 4 | 0 | Function code |
| 4 | version | 1 | 4 | UUID v4 version bit (fixed) |
| S | scenario | 4 | 0 | Test scenario (split 3+1 for v4 compliance) |
| 8 | variant | 1 | 8 | UUID variant bit (fixed) |
| T | test_case | 2 | 0 | Test case number |
| I | instance | 12 | - | Instance number (required) |

### Example

```
01234521-0042-4100-8015-000000000001
│      │ │  │ │  │ │  │ └─ instance: 1
│      │ │  │ │  │ └─── test_case: 15
│      │ │  │ │  └───── scenario: 1000 (split as 100 + 0)
│      │ │  │ └──────── variant: 8
│      │ │  └─────────── version: 4
│      │ └────────────── function: 42
│      └──────────────── table: 012345
└─────────────────────── seed_dir: 21
```

## Usage Examples

### Basic Generation

```python
from fraiseql_uuid import Pattern

pattern = Pattern()

# Minimal - uses defaults
uuid = pattern.generate(table_code="012345", instance=1)
# → "01234521-0000-4000-8000-000000000001"

# Full parameters
uuid = pattern.generate(
    table_code="123456",
    seed_dir=22,        # mutation tests
    function=42,
    scenario=1000,
    test_case=5,
    instance=999
)
# → "12345622-0042-4100-8005-000000000999"
```

### Batch Generation

```python
from fraiseql_uuid import Pattern, UUIDGenerator

pattern = Pattern()
gen = UUIDGenerator(pattern, table_code="012345", scenario=1000)

# Generate batch
uuids = gen.generate_batch(count=5)
# → ["01234521-0000-4100-8000-000000000001",
#    "01234521-0000-4100-8000-000000000002",
#    ...]
```

### Decoding

```python
from fraiseql_uuid import Pattern

pattern = Pattern()
decoded = pattern.decode("01234521-0042-4100-8015-000000000001")

print(decoded["table_code"])  # → "012345"
print(decoded["seed_dir"])    # → 21
print(decoded["function"])    # → 42
print(decoded["scenario"])    # → 1000
print(decoded["test_case"])   # → 15
print(decoded["instance"])    # → 1
```

### Validation

```python
from fraiseql_uuid import Pattern, UUIDValidator

pattern = Pattern()
validator = UUIDValidator(pattern)

result = validator.validate("01234521-0000-4000-8000-000000000001")
print(result.valid)  # → True

result = validator.validate("not-a-uuid")
print(result.valid)  # → False
print(result.error)  # → "Invalid UUID format: not-a-uuid"
```

### Caching

```python
from fraiseql_uuid import UUIDCache

cache = UUIDCache()

# Store generated UUIDs
cache.set("users", instance=1, uuid="01234521-0000-4000-8000-000000000001")
cache.set("users", instance=2, uuid="01234521-0000-4000-8000-000000000002")

# Retrieve from cache
uuid = cache.get("users", instance=1)
print(uuid)  # → "01234521-0000-4000-8000-000000000001"
```

## CLI Usage

```bash
# Generate UUID
fraiseql-uuid generate --table 012345 --instance 1

# Generate batch
fraiseql-uuid generate --table 012345 --count 10

# Decode UUID
fraiseql-uuid decode 01234521-0000-4000-8000-000000000001

# Validate UUID
fraiseql-uuid validate 01234521-0000-4000-8000-000000000001
```

## UUID v4 Compliance

All generated UUIDs are **UUID v4 compliant**:
- Version bit `4` in the correct position
- Variant bit `8` in the correct position
- Can be used anywhere standard UUIDs are expected
- Compatible with database UUID columns
- Parseable by standard UUID libraries

```python
import uuid

# Works with standard UUID library
generated = pattern.generate(table_code="012345", instance=1)
parsed = uuid.UUID(generated)
print(parsed.version)  # → 4
print(parsed.variant)  # → uuid.RFC_4122
```

## Development

```bash
# Install for development
git clone https://github.com/fraiseql/fraiseql-seed
cd fraiseql-seed
uv sync

# Run tests
uv run pytest packages/fraiseql-uuid/tests -v

# Type check
uv run mypy packages/fraiseql-uuid/src
```

## License

MIT
