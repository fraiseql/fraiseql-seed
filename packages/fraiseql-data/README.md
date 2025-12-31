# fraiseql-data

Schema-aware seed data generation for PostgreSQL.

## Installation

```bash
pip install fraiseql-data
```

## Usage

```bash
# Generate seed data
fraiseql-data seed catalog.tb_manufacturer --rows 10 --strategy realistic

# With UUID patterns
fraiseql-data seed catalog.tb_product --rows 100 --uuid-pattern printoptim
```

## Features

- Schema introspection
- Pattern-based UUID generation
- FK-aware data generation
- Multiple generator strategies (Faker, Sequential, Pattern, Reference)

See [documentation](../../../docs/) for details.
