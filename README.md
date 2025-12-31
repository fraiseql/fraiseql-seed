# FraiseQL Seed - UUID Patterns & Data Generation

A monorepo containing two complementary packages for PostgreSQL seed data management:

- **fraiseql-uuid**: Structured UUID pattern library with encode/decode support
- **fraiseql-data**: Schema-aware seed data generation for PostgreSQL

## Quick Start

### Installation

```bash
# Install both packages
pip install fraiseql-uuid fraiseql-data

# Or install individually
pip install fraiseql-uuid
pip install fraiseql-data
```

### Usage

**fraiseql-uuid**: Generate pattern-based UUIDs

```python
from fraiseql_uuid import UUIDPatternRegistry

registry = UUIDPatternRegistry.load("printoptim")
gen = registry.get_generator("catalog.tb_manufacturer", table_code="013211")
uuid = gen.generate(instance=1)
# → "01321121-0000-0000-0000-000000000001"
```

**fraiseql-data**: Generate seed data

```bash
fraiseql-data seed catalog.tb_manufacturer \
    --rows 10 \
    --strategy realistic \
    --uuid-pattern printoptim
```

## Development

### Setup

```bash
git clone https://github.com/fraiseql/fraiseql-seed.git
cd fraiseql-seed

# Install dependencies
uv sync

# Run tests
uv run pytest
```

### Project Structure

```
fraiseql-seed/
├── packages/
│   ├── fraiseql-uuid/     # UUID pattern library
│   └── fraiseql-data/     # Seed data generation
├── shared/                # Shared patterns and schemas
├── examples/              # Example integrations
└── docs/                  # Documentation
```

## Packages

| Package | Description | Status |
|---------|-------------|--------|
| fraiseql-uuid | UUID pattern library | Beta |
| fraiseql-data | Seed data generation | Beta |

## Integration

Works seamlessly with:
- [confiture](https://github.com/fraiseql/confiture) - Database migrations & Trinity pattern
- [specql](https://github.com/fraiseql/specql) - Code generation from YAML
- [fraiseql](https://github.com/fraiseql/fraiseql) - GraphQL framework

## License

MIT License - see [LICENSE](LICENSE) for details.
