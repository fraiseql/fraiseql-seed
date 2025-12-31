#!/bin/bash
# Complete monorepo setup script
# Creates all remaining boilerplate files for fraiseql-data and shared resources

set -e

echo "🚀 Completing fraiseql-seed monorepo setup..."

# Create fraiseql-data package structure
echo "📦 Creating fraiseql-data package files..."

# Create package __init__.py files
cat > packages/fraiseql-data/src/fraiseql_data/__init__.py << 'EOF'
"""
fraiseql-data - Schema-Aware Seed Data Generation

Provides intelligent seed data generation based on PostgreSQL schema introspection.
"""

from fraiseql_data.generator import SeedGenerator
from fraiseql_data.orchestrator import SeedOrchestrator

__version__ = "0.1.0"

__all__ = [
    "SeedGenerator",
    "SeedOrchestrator",
]
EOF

# Create introspection module
cat > packages/fraiseql-data/src/fraiseql_data/introspection/__init__.py << 'EOF'
"""Schema introspection for seed generation."""

from fraiseql_data.introspection.schema import SchemaIntrospector

__all__ = ["SchemaIntrospector"]
EOF

cat > packages/fraiseql-data/src/fraiseql_data/introspection/schema.py << 'EOF'
"""PostgreSQL schema introspection."""

from typing import Any, Dict, List


class SchemaIntrospector:
    """Introspect PostgreSQL schema for seed generation."""

    def __init__(self, connection_url: str):
        """Initialize introspector.

        Args:
            connection_url: PostgreSQL connection URL
        """
        self.connection_url = connection_url

    def get_tables(self, schema: str) -> List[str]:
        """Get list of tables in schema (stub)."""
        # TODO: Implement table listing
        raise NotImplementedError("Table introspection not yet implemented")

    def get_columns(self, table: str) -> List[Dict[str, Any]]:
        """Get columns for a table (stub)."""
        # TODO: Implement column introspection
        raise NotImplementedError("Column introspection not yet implemented")

    def get_foreign_keys(self, table: str) -> List[Dict[str, Any]]:
        """Get foreign keys for a table (stub)."""
        # TODO: Implement FK introspection
        raise NotImplementedError("FK introspection not yet implemented")
EOF

# Create generators module
cat > packages/fraiseql-data/src/fraiseql_data/generators/__init__.py << 'EOF'
"""Data generators for different column types."""

from fraiseql_data.generators.base import BaseGenerator
from fraiseql_data.generators.faker_generator import FakerGenerator

__all__ = ["BaseGenerator", "FakerGenerator"]
EOF

cat > packages/fraiseql-data/src/fraiseql_data/generators/base.py << 'EOF'
"""Base generator interface."""

from abc import ABC, abstractmethod
from typing import Any


class BaseGenerator(ABC):
    """Base class for data generators."""

    @abstractmethod
    def generate(self, context: Any) -> Any:
        """Generate a value.

        Args:
            context: Generation context

        Returns:
            Generated value
        """
        pass
EOF

cat > packages/fraiseql-data/src/fraiseql_data/generators/faker_generator.py << 'EOF'
"""Faker-based data generator."""

from typing import Any

from fraiseql_data.generators.base import BaseGenerator


class FakerGenerator(BaseGenerator):
    """Generate realistic fake data using Faker."""

    def __init__(self, faker_method: str):
        """Initialize generator.

        Args:
            faker_method: Faker method name (e.g., "name", "email")
        """
        self.faker_method = faker_method

    def generate(self, context: Any) -> Any:
        """Generate fake data (stub)."""
        # TODO: Implement Faker integration
        raise NotImplementedError("Faker generation not yet implemented")
EOF

# Create orchestrator
cat > packages/fraiseql-data/src/fraiseql_data/orchestrator.py << 'EOF'
"""Seed generation orchestrator."""

from typing import Any, Dict


class SeedOrchestrator:
    """Orchestrate seed data generation across multiple tables."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize orchestrator.

        Args:
            config: Orchestration configuration
        """
        self.config = config

    def generate_seeds(self, table: str, rows: int) -> None:
        """Generate seed data for a table (stub).

        Args:
            table: Table name
            rows: Number of rows to generate
        """
        # TODO: Implement seed orchestration
        raise NotImplementedError("Seed orchestration not yet implemented")
EOF

# Create shared pattern files
echo "📋 Creating shared pattern definitions..."

cat > shared/patterns/printoptim.yaml << 'EOF'
# PrintOptim UUID Pattern Definition

name: printoptim
description: "PrintOptim Trinity pattern with table code, function, scenario, instance"
format: "{table:06d}{seed_dir:02d}-{function:04d}-0000-{scenario:04d}-{instance:012d}"

components:
  table:
    description: "Table number from schema file path"
    type: integer
    length: 6
    required: true

  seed_dir:
    description: "Seed directory code"
    type: integer
    length: 2
    default: 21
    values:
      21: "General backend seed"
      22: "Function-specific mutation tests"
      23: "GraphQL query tests"

  function:
    description: "Function number being tested"
    type: integer
    length: 4
    default: 0

  scenario:
    description: "Test scenario code"
    type: integer
    length: 4
    default: 0

  instance:
    description: "Sequential instance number"
    type: integer
    length: 12
    required: true
    auto_increment: true
EOF

# Create README files
echo "📖 Creating README files..."

cat > packages/fraiseql-uuid/README.md << 'EOF'
# fraiseql-uuid

Structured UUID pattern library with encode/decode support.

## Installation

```bash
pip install fraiseql-uuid
```

## Usage

```python
from fraiseql_uuid import UUIDPatternRegistry

# Load a pattern
registry = UUIDPatternRegistry.load("printoptim")

# Generate UUID
uuid = registry.get_generator("catalog.tb_manufacturer", table_code="013211").generate(instance=1)
print(uuid)  # → "01321121-0000-0000-0000-000000000001"
```

## Patterns

- **printoptim**: PrintOptim Trinity pattern
- **specql**: SpecQL UUID v4 variant
- **sequential**: Simple sequential UUIDs

See [documentation](../../../docs/) for details.
EOF

cat > packages/fraiseql-data/README.md << 'EOF'
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
EOF

# Create monorepo README
cat > README.md << 'EOF'
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
EOF

echo ""
echo "✅ Monorepo setup complete!"
echo ""
echo "📋 Next steps:"
echo "  1. Run: uv sync"
echo "  2. Test: uv run pytest packages/fraiseql-uuid/tests"
echo "  3. Implement: Fill in the TODO stubs in the code"
echo ""
echo "🎉 Happy coding!"
