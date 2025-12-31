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
