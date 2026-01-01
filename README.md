# fraiseql-seed

**Auto-resolving test data for PostgreSQL. Need orders? We auto-generate customers, products, and payments.**

> 📦 **Monorepo containing**: `fraiseql-uuid` (Pattern UUIDs) + `fraiseql-data` (Smart test data)
> 🎯 **Install this**: `pip install fraiseql-data`

---

## ⚡ 30 Seconds to Your First Test

```bash
pip install fraiseql-data
```

```python
from fraiseql_data import seed_data

@seed_data("orders", count=100)
def test_orders(seeds):
    # ✨ Auto-generated: 100 orders + customers + products + payments
    # ✨ All foreign keys connected
    # ✨ Realistic data (names, emails, addresses)
    assert len(seeds.orders) == 100
```

**Done.** That's it. No configuration. No manual FK management. No SQL files.

---

## 🎯 The Killer Feature: Auto-Dependency Resolution

Most test data libraries make you manually create related records. **fraiseql-data doesn't.**

```python
# ❌ Other libraries: Manual FK hell
manufacturer = create_manufacturer()
category = create_category()
product = create_product(manufacturer_id=manufacturer.id, category_id=category.id)
order = create_order(product_id=product.id)
customer = create_customer()
order.customer_id = customer.id
order.save()

# ✅ fraiseql-data: Just ask for what you need
@seed_data("orders", count=1, auto_deps=True)
def test_order(seeds):
    # Auto-created: customer, product, manufacturer, category, payment
    # All FKs connected. All data realistic.
    pass
```

### Real-World Example

```python
# I want 100 orders for testing
builder = SeedBuilder(conn, "public")
seeds = builder.add("tb_order", count=100, auto_deps=True).execute()

# ✨ fraiseql-data auto-generated:
# - 100 orders
# - 50 customers (realistic sharing across orders)
# - 200 products (realistic variety)
# - 10 manufacturers (realistic distribution)
# - 5 categories (realistic grouping)
# - 100 payments (1 per order)
# - All foreign keys perfectly connected
# - All data realistic (Faker integration)
```

**That's the difference.** One line vs. hours of manual FK management.

---

## 🚀 Quick Start

### Installation

```bash
# Choose your package manager
pip install fraiseql-data
uv add fraiseql-data
poetry add fraiseql-data
```

### Your First Test

```python
import pytest
from fraiseql_data import seed_data

@seed_data("users", count=10)
def test_user_list(seeds, db_conn, test_schema):
    # seeds.users contains 10 realistic users
    assert len(seeds.users) == 10

    # Realistic data auto-generated
    assert "@" in seeds.users[0].email  # john.doe@example.com
    assert seeds.users[0].name  # John Doe
    assert seeds.users[0].id  # UUID auto-generated
```

### With Auto-Dependencies

```python
@seed_data("orders", count=50, auto_deps=True)
def test_order_analytics(seeds):
    # Auto-created: orders + customers + products + everything needed
    order = seeds.orders[0]

    # All FKs resolved
    assert order.fk_customer  # Points to auto-created customer
    assert order.fk_product   # Points to auto-created product
```

---

## 📦 What's in This Monorepo?

| Package | Purpose | Install | Status |
|---------|---------|---------|--------|
| **[fraiseql-data](./packages/fraiseql-data)** | Smart test data generation | `pip install fraiseql-data` | ✅ v0.1.0 Production |
| **[fraiseql-uuid](./packages/fraiseql-uuid)** | Pattern UUIDs (Trinity pattern) | `pip install fraiseql-uuid` | ✅ v0.1.0 Production |

### fraiseql-data: Smart Test Data

**The main package.** Auto-resolves dependencies, generates realistic data, adapts to schema changes.

**Key Features:**
- ✅ Auto-dependency resolution (recursive FK handling)
- ✅ Realistic data via Faker (30+ column types)
- ✅ PostgreSQL schema introspection
- ✅ Trinity pattern support (pk_*, id, identifier)
- ✅ Zero configuration required

[📖 Full Documentation](./packages/fraiseql-data/README.md)

### fraiseql-uuid: Pattern UUIDs

Debuggable UUIDs that encode table and instance information.

```python
from fraiseql_uuid import UUIDGenerator

gen = UUIDGenerator(pattern="product")
uuid = gen.generate(instance=1)
# → "3a4b5c21-0000-4000-8000-000000000001"
#    ^^^^^^ table code    ^^^^ instance number
```

[📖 Full Documentation](./packages/fraiseql-uuid/README.md)

---

## Status & Quality

[![Quality Gate](https://github.com/fraiseql/fraiseql-seed/actions/workflows/quality-gate.yml/badge.svg)](https://github.com/fraiseql/fraiseql-seed/actions/workflows/quality-gate.yml)
[![Security & Compliance](https://github.com/fraiseql/fraiseql-seed/actions/workflows/security-compliance.yml/badge.svg)](https://github.com/fraiseql/fraiseql-seed/actions/workflows/security-compliance.yml)
[![codecov](https://codecov.io/gh/fraiseql/fraiseql-seed/branch/main/graph/badge.svg)](https://codecov.io/gh/fraiseql/fraiseql-seed)

[![Python 3.11+](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

### Quality Metrics

- ✅ **99/99 tests passing** (100% pass rate)
- ✅ **86% code coverage** (fraiseql-data)
- ✅ **Zero lint violations** (ruff strict mode)
- ✅ **Type-safe** (mypy strict for fraiseql-uuid)
- ✅ **Multi-Python** (3.11, 3.12, 3.13)

### Security & Compliance

- 🔒 **Government-grade security** (US EO 14028, EU NIS2/CRA, PCI-DSS 4.0)
- 🔒 **SBOM with Cosign signing** (CycloneDX 1.5 + Sigstore)
- 🔒 **0 known vulnerabilities** (weekly automated scans)
- 🔒 **0 GPL dependencies** (LGPL/MIT/Apache only)
- 🔒 **Weekly security audits** (TruffleHog, Trivy, pip-audit)

---

## 💡 Why fraiseql-data?

### The Problem: Test Data is a Time Sink

You want to test your API:

```python
def test_get_order():
    response = client.get("/api/orders/123")
    assert response.status_code == 200
```

But order 123 doesn't exist. So you write seed data:

```sql
-- seeds/001_customers.sql
INSERT INTO customers (pk_customer, id, name, email) VALUES
  (1, '550e8400-...', 'Acme Corp', 'contact@acme.com');

-- seeds/002_products.sql
INSERT INTO products (pk_product, id, name, fk_manufacturer) VALUES
  (1, '550e8401-...', 'Widget', 1);

-- seeds/003_orders.sql
INSERT INTO orders (pk_order, id, fk_customer, fk_product) VALUES
  (1, '550e8402-...', 1, 1);

-- seeds/004_payments.sql
INSERT INTO payments (pk_payment, id, fk_order, amount) VALUES
  (1, '550e8403-...', 1, 99.99);
```

**30 minutes later**, your test passes.

Then your schema changes. All your seeds break. **Another 30 minutes.**

### The Solution: Auto-Generate Everything

```python
from fraiseql_data import seed_data

@seed_data("orders", count=10)
def test_get_order(seeds):
    order = seeds.orders[0]
    response = client.get(f"/api/orders/{order.pk_order}")
    assert response.status_code == 200
```

**30 seconds.** Done.

- ✅ Realistic data auto-generated
- ✅ Foreign keys auto-resolved
- ✅ UUIDs created (debuggable Pattern UUIDs)
- ✅ Schema changes? Still works
- ✅ No configuration needed

---

## 🎨 Features

### Zero Configuration

```python
# Just works - auto-generates realistic data
@seed_data("products", count=100)
def test_pagination(seeds):
    assert len(seeds.products) == 100
```

No configuration files. No class definitions. No manual column mapping.

### Auto Foreign Key Resolution

```python
# Automatically links products to categories
@seed_data("categories", count=10)
@seed_data("products", count=100)
def test_products(seeds):
    product = seeds.products[0]
    # FK automatically resolved
    assert product.fk_category in [c.pk_category for c in seeds.categories]
```

### Recursive Auto-Dependencies

**The killer feature:**

```python
# I want 100 orders
builder = SeedBuilder(conn, "public")
seeds = builder.add("tb_order", count=100, auto_deps=True).execute()

# ✨ Auto-created based on schema introspection:
# - tb_customer (50 rows - realistic sharing)
# - tb_product (200 rows - realistic variety)
# - tb_manufacturer (10 rows - linked to products)
# - tb_category (5 rows - linked to products)
# - tb_payment (100 rows - 1 per order)
#
# All FKs connected. All constraints satisfied.
```

### Realistic Data via Faker

Auto-detected columns:

```python
@seed_data("users", count=50)
def test_emails(seeds):
    for user in seeds.users:
        assert "@" in user.email  # Real email: john.doe@example.com
        assert user.name  # Real name: John Doe
        assert user.phone_number  # Real phone: +1-555-123-4567
```

Auto-detects:
- `email` → realistic emails
- `name`, `first_name`, `last_name` → realistic names
- `phone`, `phone_number` → phone numbers
- `address`, `city`, `state`, `zip_code` → addresses
- `company`, `company_name` → company names
- `description`, `bio`, `notes` → text paragraphs
- `url`, `website` → URLs
- `date_of_birth`, `birth_date` → dates
- ...and 30+ more patterns

### Custom Overrides When Needed

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

### Trinity Pattern Support (FraiseQL)

Automatically generates Trinity pattern columns:

```python
@seed_data("manufacturers", count=5)
def test_trinity(seeds):
    m = seeds.manufacturers[0]
    assert m.pk_manufacturer  # INTEGER IDENTITY (primary key)
    assert m.id  # UUID (Pattern UUID for debugging)
    assert m.identifier  # TEXT (unique, human-readable: "acme-corp")
```

Trinity pattern:
- `pk_*` → INTEGER IDENTITY (database primary key)
- `id` → UUID (using fraiseql-uuid Pattern)
- `identifier` → TEXT UNIQUE (slugified from name or auto-generated)

### Pattern UUIDs (Debuggable)

Uses [fraiseql-uuid](#fraiseql-uuid) for debuggable UUIDs:

```python
@seed_data("products", count=100)
def test_uuids(seeds):
    product = seeds.products[0]
    # UUID: 3a4b5c21-0000-4000-8000-000000000001
    #       ^^^^^^ ---- table code
    #              ^^-- seed direction
    #                              ^^^^ instance
    print(product.id)  # Easy to recognize in logs!
```

### Works With Any PostgreSQL Database

No special setup required. Works with:
- Plain PostgreSQL
- FraiseQL projects
- Django projects
- FastAPI projects
- Any Python + PostgreSQL app

---

## 📊 Comparison

| Feature | Manual Seeds | factory_boy | **fraiseql-data** |
|---------|--------------|-------------|-------------------|
| **Setup time** | 30+ min | 10 min | **30 sec** |
| **PostgreSQL introspection** | ❌ Manual | ❌ Manual | ✅ **Auto** |
| **FK resolution** | ❌ Manual | ⚠️ Configure | ✅ **Auto** |
| **Recursive dependencies** | ❌ | ❌ | ✅ **Auto** |
| **Realistic data** | ❌ Manual | ⚠️ Configure | ✅ **Auto** |
| **Schema changes** | ❌ Breaks | ⚠️ Update classes | ✅ **Adapts** |
| **AI-friendly** | ❌ | ⚠️ | ✅ **Built for AI** |
| **Trinity pattern** | ❌ | ❌ | ✅ |
| **Pattern UUIDs** | ❌ | ❌ | ✅ |

---

## 🍓 Part of the FraiseQL Ecosystem

**fraiseql-seed** is designed for the [FraiseQL](https://fraiseql.dev) ecosystem but works standalone:

### Server Stack (PostgreSQL + Python/Rust)

| Tool | Purpose | Status | Performance Gain |
|------|---------|--------|------------------|
| **[pg_tviews](https://github.com/fraiseql/pg_tviews)** | Incremental materialized views | Beta | **100-500× faster** |
| **[jsonb_delta](https://github.com/evoludigit/jsonb_delta)** | JSONB surgical updates | Stable | **2-7× faster** |
| **[pgGit](https://pggit.dev)** | Database version control | Stable | Git for databases |
| **[confiture](https://github.com/fraiseql/confiture)** | PostgreSQL migrations | Stable | **300-600× faster** |
| **[fraiseql](https://fraiseql.dev)** | GraphQL framework | Stable | **7-10× faster** |
| **[fraiseql-data](https://github.com/fraiseql/fraiseql-seed)** | Seed data generation | **v0.1.0** ⭐ | Auto-dependency resolution |

### Client Libraries (TypeScript/JavaScript)

| Library | Purpose | Framework Support |
|---------|---------|-------------------|
| **[graphql-cascade](https://github.com/graphql-cascade/graphql-cascade)** | Automatic cache invalidation | Apollo, React Query, Relay, URQL |

### How fraiseql-seed Fits

```python
from fraiseql_data import SeedBuilder

# Build schema with confiture
confiture build --env test

# Generate test data with auto-dependencies
builder = SeedBuilder(conn, "public", seed_common="db/")
seeds = builder.add("tb_order", count=100, auto_deps=True).execute()
# ✨ Auto-generates: customers, products, payments (recursive FK resolution!)

# Test fraiseql GraphQL API
response = await graphql_query("{ orders { id customer { name } } }")
assert len(response.data.orders) == 100
```

**Key integrations:**
- **fraiseql-data**: Generate realistic test data for **fraiseql** GraphQL APIs
- **fraiseql-uuid**: Trinity pattern UUIDs (pk_*, id, identifier)
- **confiture**: Works with confiture-built schemas
- **Seed common baseline**: Eliminates UUID collisions in tests

---

## 📚 Documentation

### Quick Links

- **[fraiseql-data Documentation](./packages/fraiseql-data/README.md)** - Full API reference, advanced features
- **[fraiseql-uuid Documentation](./packages/fraiseql-uuid/README.md)** - Pattern UUID details
- **[Examples](./examples/)** - Real-world usage examples
- **[SECURITY.md](./SECURITY.md)** - Security policy and vulnerability reporting

### Advanced Topics

- **[Auto-Dependency Resolution](./packages/fraiseql-data/README.md#auto-dependency-resolution)** - How recursive FK resolution works
- **[Seed Common Baseline](./packages/fraiseql-data/README.md#seed-common-baseline)** - Eliminate UUID collisions
- **[Trinity Pattern](./packages/fraiseql-data/README.md#trinity-pattern-support)** - pk_*/id/identifier explained
- **[Custom Generators](./packages/fraiseql-data/README.md#custom-generators)** - Extend Faker integration
- **[Staging Backend](./packages/fraiseql-data/README.md#staging-backend-in-memory-testing)** - Test without database

---

## 🤝 Contributing

We welcome contributions! Please see:

- **[SECURITY.md](./SECURITY.md)** - Security vulnerability reporting
- **[LICENSE](./LICENSE)** - MIT License

### Development Setup

```bash
# Clone repo
git clone https://github.com/fraiseql/fraiseql-seed
cd fraiseql-seed

# Install uv (fast Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync --all-extras

# Run tests
uv run pytest

# Run linting
uv run ruff check packages/
```

### Quality Standards

This project maintains government-grade quality standards:

- ✅ 99/99 tests passing
- ✅ 86% code coverage
- ✅ Zero lint violations
- ✅ Type-safe (mypy strict)
- ✅ Multi-Python (3.11, 3.12, 3.13)
- ✅ Weekly security scans
- ✅ SBOM with Cosign signing

See [CI/CD workflows](./.github/workflows/) for details.

---

## 📄 License

MIT License - see [LICENSE](./LICENSE) for details.

**Government-friendly**: No GPL dependencies, SBOM available, security audits automated.

---

## 🙏 Acknowledgments

Built with:
- [Faker](https://faker.readthedocs.io/) - Realistic fake data generation
- [psycopg](https://www.psycopg.org/) - PostgreSQL database adapter
- [pydantic](https://docs.pydantic.dev/) - Data validation

Part of the [FraiseQL](https://fraiseql.dev) ecosystem for high-performance PostgreSQL applications.

---

<div align="center">

**Stop writing manual seed data. Start testing.**

[Install fraiseql-data](#-quick-start) • [Read Docs](./packages/fraiseql-data/README.md) • [Report Issue](https://github.com/fraiseql/fraiseql-seed/issues)

Made with 🍓 by the FraiseQL Team

</div>
