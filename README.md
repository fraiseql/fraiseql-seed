# fraiseql-seed

Schema-aware test data generation for PostgreSQL with automatic foreign key resolution.

This monorepo contains two packages: **fraiseql-data** (seed data generation) and **fraiseql-uuid** (pattern UUIDs with encoded metadata).

[![Quality Gate](https://github.com/fraiseql/fraiseql-seed/actions/workflows/quality-gate.yml/badge.svg)](https://github.com/fraiseql/fraiseql-seed/actions/workflows/quality-gate.yml)
[![Security & Compliance](https://github.com/fraiseql/fraiseql-seed/actions/workflows/security-compliance.yml/badge.svg)](https://github.com/fraiseql/fraiseql-seed/actions/workflows/security-compliance.yml)
[![codecov](https://codecov.io/gh/fraiseql/fraiseql-seed/branch/main/graph/badge.svg)](https://codecov.io/gh/fraiseql/fraiseql-seed)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%20%7C%203.13-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Install

```bash
pip install fraiseql-data
```

## Quick Example

```python
from psycopg import connect
from fraiseql_data import SeedBuilder

conn = connect("postgresql://user:pass@localhost/mydb")

builder = SeedBuilder(conn, schema="public")
seeds = builder.add("tb_order", count=100, auto_deps=True).execute()
# tb_order depends on tb_customer, tb_product, etc.
# All parent tables are introspected and populated automatically.

for order in seeds.tb_order:
    print(order.pk_order, order.fk_customer)
```

## Packages

### fraiseql-data

Schema-aware seed data generation for PostgreSQL.

- Introspects your schema to discover tables, columns, types, and foreign keys
- Recursively resolves FK dependencies -- request one table, get the full tree
- Generates realistic values via Faker for 30+ column name patterns (email, name, phone, address, ...)
- Supports Trinity pattern columns (pk\_\*, id, identifier)
- Handles self-referencing tables, UNIQUE constraints, and CHECK constraints
- Includes a staging backend for testing without a live database
- CLI with SQL, YAML, and JSON export

[Full documentation](./packages/fraiseql-data/README.md)

### fraiseql-uuid

UUID v4-compliant values with encoded table and instance metadata, useful for debugging.

```python
from fraiseql_uuid import Pattern, UUIDGenerator

gen = UUIDGenerator(Pattern(), table_code="012345")
uuid = gen.generate(instance=1)
# "01234521-0000-4000-8000-000000000001"
#  ^^^^^^ table   ^^^^ instance
```

[Full documentation](./packages/fraiseql-uuid/README.md)

## Development

```bash
git clone https://github.com/fraiseql/fraiseql-seed
cd fraiseql-seed
uv sync --all-extras
uv run pytest
uv run ruff check packages/
```

## License

MIT -- see [LICENSE](./LICENSE).

Part of the [FraiseQL](https://fraiseql.dev) ecosystem.
