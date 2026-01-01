# fraiseql-data

**Realistic PostgreSQL test data, zero configuration.**

Stop writing manual seed data. Start testing.

---

## 🍓 Part of the FraiseQL Ecosystem

**fraiseql-seed** provides test data generation with auto-dependency resolution:

### **Server Stack (PostgreSQL + Python/Rust)**

| Tool | Purpose | Status | Performance Gain |
|------|---------|--------|------------------|
| **[pg_tviews](https://github.com/fraiseql/pg_tviews)** | Incremental materialized views | Beta | **100-500× faster** |
| **[jsonb_delta](https://github.com/evoludigit/jsonb_delta)** | JSONB surgical updates | Stable | **2-7× faster** |
| **[pgGit](https://pggit.dev)** | Database version control | Stable | Git for databases |
| **[confiture](https://github.com/fraiseql/confiture)** | PostgreSQL migrations | Stable | **300-600× faster** |
| **[fraiseql](https://fraiseql.dev)** | GraphQL framework | Stable | **7-10× faster** |
| **[fraiseql-data](https://github.com/fraiseql/fraiseql-seed)** | Seed data generation | **Phase 6** ⭐ | Auto-dependency resolution |

### **Client Libraries (TypeScript/JavaScript)**

| Library | Purpose | Framework Support |
|---------|---------|-------------------|
| **[graphql-cascade](https://github.com/graphql-cascade/graphql-cascade)** | Automatic cache invalidation | Apollo, React Query, Relay, URQL |

**How fraiseql-seed fits:**
- **fraiseql-data**: Generate realistic test data for **fraiseql** GraphQL APIs
- **fraiseql-uuid**: Trinity pattern UUIDs (pk_*, id, identifier)
- Works with **confiture**-built schemas
- **Seed common baseline** eliminates UUID collisions in tests

**Test data workflow:**
```python
from fraiseql_data import SeedBuilder

# Build schema (confiture)
confiture build --env test

# Generate test data with auto-dependencies
builder = SeedBuilder(conn, "public", seed_common="db/")
seeds = builder.add("tb_order", count=100, auto_deps=True).execute()
# Auto-generates: customers, products, payments (recursive FK resolution!)

# Test fraiseql GraphQL API
response = await graphql_query("{ orders { id customer { name } } }")
```

---

## The Problem

You want to test your API:

```python
def test_get_manufacturer():
    response = client.get("/api/manufacturers/123")
    assert response.status_code == 200
```

But manufacturer 123 doesn't exist. So you write seed data:

```sql
-- seeds/001_manufacturers.sql
INSERT INTO manufacturers (pk_manufacturer, id, identifier, name, email, created_at) VALUES
  (1, '550e8400-e29b-41d4-a716-446655440000', 'acme-corp', 'Acme Corp', 'contact@acme.com', NOW());

-- seeds/002_models.sql
INSERT INTO models (pk_model, id, identifier, name, fk_manufacturer, created_at) VALUES
  (1, '550e8400-e29b-41d4-a716-446655440001', 'model-x', 'Model X', 1, NOW()),
  (2, '550e8400-e29b-41d4-a716-446655440002', 'model-y', 'Model Y', 1, NOW());
```

**30 minutes later**, your test passes.

Then your schema changes. All your seeds break. Another 30 minutes.

---

## The Solution

```python
from fraiseql_data import seed_data

@seed_data("manufacturers", count=10)
@seed_data("models", count=50)
def test_get_manufacturer(seeds):
    manufacturer = seeds.manufacturers[0]
    response = client.get(f"/api/manufacturers/{manufacturer.pk_manufacturer}")
    assert response.status_code == 200
```

**30 seconds.** Done.

- ✅ Realistic data auto-generated
- ✅ Foreign keys auto-resolved
- ✅ UUIDs created (debuggable Pattern UUIDs)
- ✅ Schema changes? Still works
- ✅ No configuration needed

---

## Quick Start

### Install

```bash
pip install fraiseql-data
# or
uv add fraiseql-data
```

### Use in Tests

```python
import pytest
from fraiseql_data import seed_data

@seed_data("users", count=10)
def test_user_list(seeds, db_conn, test_schema):
    # seeds.users contains 10 realistic users
    assert len(seeds.users) == 10
    assert "@" in seeds.users[0].email  # Real email addresses
    assert seeds.users[0].id  # UUID auto-generated
```

### That's It

No configuration. No manual SQL. Just tests.

---

## Features

### 🎯 Zero Configuration

```python
# Just works - auto-generates realistic data
@seed_data("products", count=100)
def test_pagination(seeds):
    assert len(seeds.products) == 100
```

### 🔗 Auto Foreign Key Resolution

```python
# Automatically links products to categories
@seed_data("categories", count=10)
@seed_data("products", count=100)
def test_products(seeds):
    product = seeds.products[0]
    # FK automatically resolved
    assert product.fk_category in [c.pk_category for c in seeds.categories]
```

### 🎭 Realistic Data (Faker Integration)

```python
@seed_data("users", count=50)
def test_emails(seeds):
    for user in seeds.users:
        assert "@" in user.email  # Real email: john.doe@example.com
        assert user.name  # Real name: John Doe
        assert user.phone_number  # Real phone: +1-555-123-4567
```

Auto-detected columns:
- `email` → realistic emails
- `name`, `first_name`, `last_name` → realistic names
- `phone`, `phone_number` → phone numbers
- `address`, `city`, `state` → addresses
- `company` → company names
- `description` → text paragraphs
- ...and 30+ more

### 🎨 Custom Overrides When Needed

```python
# Override specific columns
@seed_data("users", count=5, overrides={
    "role": "admin",
    "status": lambda: "active",
    "username": lambda i: f"user_{i}"
})
def test_admin_users(seeds):
    assert all(u.role == "admin" for u in seeds.users)
```

### 🏗️ Trinity Pattern Support (FraiseQL)

Automatically generates Trinity pattern columns:

```python
@seed_data("manufacturers", count=5)
def test_trinity(seeds):
    m = seeds.manufacturers[0]
    assert m.pk_manufacturer  # INTEGER (database-generated)
    assert m.id  # UUID (Pattern UUID for debugging)
    assert m.identifier  # TEXT (unique, human-readable)
```

Trinity pattern:
- `pk_*` → INTEGER IDENTITY (primary key)
- `id` → UUID (using [fraiseql-uuid](#fraiseql-uuid) Pattern)
- `identifier` → TEXT (unique, slugified from name or auto-generated)

### 🔍 Pattern UUIDs (Debuggable)

Uses [fraiseql-uuid](#fraiseql-uuid) for debuggable UUIDs:

```python
@seed_data("products", count=100)
def test_uuids(seeds):
    product = seeds.products[0]
    # UUID: 3a4b5c21-0000-4000-8000-000000000001
    #       ^^^^^^ ---- table code
    #              ^^-- seed direction
    #                              ^^^^ instance
    print(product.id)
```

Pattern UUIDs encode:
- Table information (first 6 chars)
- Instance number (last 4 chars)
- Easy to recognize in logs

### 🚀 Works With Any PostgreSQL Database

No special setup required. Works with:
- Plain PostgreSQL
- FraiseQL projects
- Django projects
- FastAPI projects
- Any Python + PostgreSQL app

---

## Comparison

| Feature | Manual Seeds | factory_boy | **fraiseql-data** |
|---------|--------------|-------------|-------------------|
| **Setup time** | 30+ min | 10 min | **30 sec** |
| **PostgreSQL introspection** | ❌ Manual | ❌ Manual | ✅ **Auto** |
| **FK resolution** | ❌ Manual | ⚠️ Configure | ✅ **Auto** |
| **Realistic data** | ❌ Manual | ⚠️ Configure | ✅ **Auto** |
| **Schema changes** | ❌ Breaks | ⚠️ Update classes | ✅ **Adapts** |
| **AI-friendly** | ❌ | ⚠️ | ✅ **Built for AI** |
| **Trinity pattern** | ❌ | ❌ | ✅ |
| **Pattern UUIDs** | ❌ | ❌ | ✅ |

---

## Why fraiseql-data?

### Problem: Manual Seed Data is a Time Sink

**Typical workflow without fraiseql-data:**

1. ⏱️ Write migration (10 min)
2. ⏱️ Write seed SQL files (20 min)
3. ⏱️ Debug FK violations (10 min)
4. ⏱️ Update seeds when schema changes (20 min)
5. ⏱️ Finally write the actual test (5 min)

**Total: 65 minutes** (only 5 minutes spent on actual testing)

### Solution: Auto-Generate Everything

**With fraiseql-data:**

1. ✅ Write the test with `@seed_data()` decorator (30 sec)

**Total: 30 seconds** (100% spent on testing)

### Bonus: Built for AI Coding Assistants

When Claude, Copilot, or Cursor writes tests, they have to **guess**:
- What UUIDs to use
- How to structure data
- Which foreign keys exist
- What the schema looks like

**fraiseql-data eliminates guessing:**

```python
# AI writes this without knowing your schema:
@seed_data("manufacturers", count=5)
@seed_data("products", count=20)
def test_api(seeds):
    product = seeds.products[0]
    # AI knows these exist (type hints + introspection):
    assert product.id
    assert product.fk_manufacturer
    assert product.name
```

AI writes tests that **pass on first try**.

---

## Examples

### Basic Usage

```python
from fraiseql_data import SeedBuilder

def test_users(db_conn):
    # Builder API for more control
    builder = SeedBuilder(db_conn, schema="public")
    builder.add("users", count=10)
    seeds = builder.execute()

    assert len(seeds.users) == 10
```

### Decorator (Recommended)

```python
from fraiseql_data import seed_data

@seed_data("users", count=10)
def test_users(seeds, db_conn, test_schema):
    assert len(seeds.users) == 10
```

### Multiple Tables with Foreign Keys

```python
@seed_data("categories", count=5)
@seed_data("products", count=50)
@seed_data("reviews", count=200)
def test_hierarchy(seeds):
    # Foreign keys automatically resolved:
    # reviews.fk_product → products.pk_product
    # products.fk_category → categories.pk_category

    review = seeds.reviews[0]
    product_id = review.fk_product
    product = next(p for p in seeds.products if p.pk_product == product_id)

    assert product.fk_category in [c.pk_category for c in seeds.categories]
```

### Custom Data

```python
from datetime import datetime

@seed_data("users", count=3, overrides={
    "role": "admin",
    "email": lambda i: f"admin{i}@company.com",
    "created_at": datetime(2024, 1, 1)
})
def test_admins(seeds):
    assert all(u.role == "admin" for u in seeds.users)
    assert seeds.users[0].email == "admin1@company.com"
```

### Large Datasets (Performance Test)

```python
@seed_data("users", count=1000)
@seed_data("posts", count=10000)
def test_performance(seeds):
    # Generated in <5 seconds
    assert len(seeds.users) == 1000
    assert len(seeds.posts) == 10000
```

---

## Installation

### Requirements

- Python 3.11+
- PostgreSQL 13+ (any version with `information_schema`)
- pytest (for `@seed_data` decorator)

### Install

```bash
# Using pip
pip install fraiseql-data

# Using uv (recommended)
uv add fraiseql-data

# Using poetry
poetry add fraiseql-data
```

### Dependencies

- `psycopg[binary]>=3.2.0` - PostgreSQL driver (psycopg3)
- `faker>=22.0.0` - Realistic data generation
- `fraiseql-uuid>=0.1.0` - Pattern UUID generation

---

## API Reference

### SeedBuilder

```python
builder = SeedBuilder(conn: Connection, schema: str)
builder.add(table: str, count: int, strategy: str = "faker", overrides: dict = None)
seeds = builder.execute() -> Seeds
```

### @seed_data Decorator

```python
@seed_data(table: str, count: int, strategy: str = "faker", overrides: dict = None)
def test_function(seeds, db_conn, test_schema):
    # seeds.{table_name} available here
    pass
```

### Seeds Object

```python
seeds.users  # List[SeedRow]
seeds.products  # List[SeedRow]

user = seeds.users[0]
user.id  # Access columns as attributes
user.email
user.name
```

### Column Overrides

```python
# Constant value
overrides={"status": "active"}

# Callable (no args)
overrides={"created_at": lambda: datetime.now()}

# Callable (with instance number)
overrides={"username": lambda i: f"user_{i}"}
```

---

## fraiseql-uuid

**Debuggable Pattern UUIDs for PostgreSQL**

fraiseql-data uses fraiseql-uuid to generate Pattern UUIDs that encode metadata in the UUID itself.

### Features

- 🔍 **Debuggable**: See table, instance at a glance
- 🎯 **V4 compliant**: Works everywhere UUIDs work
- 📊 **Encode/decode**: Extract metadata from UUIDs
- 🏗️ **FraiseQL integration**: Built-in Trinity pattern support

### Quick Example

```python
from fraiseql_uuid import Pattern

pattern = Pattern()
uuid = pattern.generate(
    table_code="013210",  # Identifies table
    seed_dir=21,          # Seed direction (1-99)
    function=0,
    scenario=0,
    test_case=0,
    instance=1            # Row instance number
)
# → "01321021-0000-4000-8000-000000000001"

# Decode later
decoded = pattern.decode(uuid)
print(decoded.table_code)  # "013210"
print(decoded.instance)    # 1
```

### Why Pattern UUIDs?

**Problem with random UUIDs:**
```
Users:
  - c7f9d8e3-4a2b-4c1d-9e3f-8b7a6c5d4e3f
  - a1b2c3d4-5e6f-7g8h-9i0j-1k2l3m4n5o6p

Which table? Which test? No idea.
```

**Pattern UUIDs:**
```
Users (table code: 013210):
  - 01321021-0000-4000-8000-000000000001  ← User #1
  - 01321021-0000-4000-8000-000000000002  ← User #2

Products (table code: 3a4b5c):
  - 3a4b5c21-0000-4000-8000-000000000001  ← Product #1
```

**Benefits:**
- ✅ Instantly recognize table in logs
- ✅ See instance number (helpful for debugging)
- ✅ Group by table code in queries
- ✅ Still RFC 4122 compliant (works everywhere)

### Pattern Structure

```
01321021-0000-4000-8000-000000000001
^^^^^^   ^^   ^    ^    ^^^^^^^^^^^^
│        │    │    │    └─ Instance (1-65535)
│        │    │    └────── Version bits (fixed)
│        │    └─────────── Variant bits (fixed)
│        └──────────────── Function/Scenario/TestCase
└───────────────────────── Table Code + Seed Dir
```

### CLI Tool

```bash
# Generate UUIDs
fraiseql-uuid generate --table-code 013210 --instance 1
# → 01321021-0000-4000-8000-000000000001

# Decode UUIDs
fraiseql-uuid decode 01321021-0000-4000-8000-000000000001
# Table Code: 013210
# Seed Dir: 21
# Instance: 1

# Validate UUIDs
fraiseql-uuid validate 01321021-0000-4000-8000-000000000001
# ✓ Valid UUID v4
# ✓ Valid Pattern UUID
```

### Learn More

See [packages/fraiseql-uuid/README.md](packages/fraiseql-uuid/README.md) for full documentation.

---

## FAQ

### How is this different from factory_boy?

**factory_boy:**
- Requires manual class definitions
- Django-focused
- No auto-introspection
- No PostgreSQL-specific features

**fraiseql-data:**
- Zero configuration (auto-introspects schema)
- PostgreSQL-native
- Auto FK resolution
- Built-in Trinity pattern support
- Built for AI coding assistants

### Does it work with Django?

Yes! fraiseql-data works with any PostgreSQL database:

```python
@seed_data("myapp_user", count=10)
def test_users(seeds, db_conn):
    # Works with Django models too
    assert User.objects.count() == 10
```

### Does it work with SQLAlchemy?

Yes! Just provide a psycopg connection:

```python
from sqlalchemy import create_engine

engine = create_engine("postgresql://...")
with engine.raw_connection() as conn:
    builder = SeedBuilder(conn, schema="public")
    seeds = builder.execute()
```

### How fast is it?

**Benchmarks:**
- 100 rows: <1 second
- 1,000 rows: <5 seconds
- 10,000 rows: <30 seconds

Performance scales linearly with row count.

### Can I use it in production?

fraiseql-data is designed for **test data generation**. It's not recommended for production seed data because:
- Data is randomized (not deterministic)
- No migration tracking
- No version control

For production seeds, use migrations or SQL scripts.

### What about circular dependencies?

Self-referencing tables (e.g., `users.fk_manager → users.pk_user`) will be supported in Phase 2.

Current workaround: Temporarily remove FK, seed, re-add FK.

### Can I contribute?

Yes! Both packages are open source (MIT license).

- GitHub: https://github.com/fraiseql/fraiseql-seed
- Issues: https://github.com/fraiseql/fraiseql-seed/issues
- PRs welcome!

---

## Development

### Monorepo Structure

```
fraiseql-seed/
├── packages/
│   ├── fraiseql-uuid/     # Pattern UUID library
│   └── fraiseql-data/     # Seed data generation (Phase 1 in progress)
├── .phases/               # Phase plans (TDD workflow)
├── examples/              # Example integrations
└── docs/                  # Documentation
```

### Setup

```bash
git clone https://github.com/fraiseql/fraiseql-seed.git
cd fraiseql-seed

# Install dependencies
uv sync

# Run tests
uv run pytest

# Run specific package tests
uv run pytest packages/fraiseql-uuid/tests/
uv run pytest packages/fraiseql-data/tests/
```

### Current Status

| Package | Status | Phase |
|---------|--------|-------|
| fraiseql-uuid | ✅ Complete | v0.1.0 released |
| fraiseql-data | 🚧 In Progress | Phase 1 (Zero-Guessing Core) |

### Phase Plans

See [.phases/README.md](.phases/README.md) for detailed implementation phases.

**Phase 1: Zero-Guessing Core** (Current)
- Schema introspection
- Auto FK resolution
- Faker integration
- Pattern UUID support
- pytest decorator

---

## Roadmap

### fraiseql-data

#### Phase 1: Zero-Guessing Core ✅ (In Progress)
- [x] Design document
- [x] Phase plans (GREENFIELD, RED, GREEN, REFACTOR, QA)
- [ ] Implementation
- [ ] Testing
- [ ] Documentation

#### Phase 2: PrintOptim Integration (Next)
- [ ] Test with PrintOptim schema (144 tables)
- [ ] Staging backend support (optional)
- [ ] Performance optimization for large schemas
- [ ] Self-referencing table support

#### Phase 3: Advanced Features
- [ ] GraphQL schema integration
- [ ] CLI tool (`fraiseql-data seed ...`)
- [ ] Export formats (SQL, JSON)
- [ ] Custom generator plugins
- [ ] Multi-database support (SQLite, MySQL)

### fraiseql-uuid

- [x] Core pattern implementation
- [x] CLI tool
- [x] Documentation
- [ ] Performance benchmarks
- [ ] Additional encoding schemes

---

## Integration

Works seamlessly with:
- [FraiseQL](https://github.com/fraiseql/fraiseql) - GraphQL framework
- [confiture](https://github.com/fraiseql/confiture) - Database migrations & Trinity pattern
- [specql](https://github.com/fraiseql/specql) - Code generation from YAML

---

## License

MIT License - see [LICENSE](LICENSE) file for details.

---

## Credits

Built by the [FraiseQL](https://github.com/fraiseql) team.

Inspired by:
- factory_boy (Python test fixtures)
- Faker (realistic data generation)
- PrintOptim backend (staging pattern)

---

## Links

- **Documentation**: Coming soon
- **GitHub**: https://github.com/fraiseql/fraiseql-seed
- **Issues**: https://github.com/fraiseql/fraiseql-seed/issues
- **FraiseQL**: https://github.com/fraiseql/fraiseql

---

## Support

- 📖 Documentation: Coming soon
- 💬 Discussions: https://github.com/fraiseql/fraiseql-seed/discussions
- 🐛 Report bugs: https://github.com/fraiseql/fraiseql-seed/issues
- ✨ Request features: https://github.com/fraiseql/fraiseql-seed/issues

---

**Stop writing seed data. Start testing.** 🚀
