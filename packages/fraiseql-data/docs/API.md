# fraiseql-data API Reference

Complete API documentation for fraiseql-data.

## Table of Contents

- [SeedBuilder](#seedbuilder)
  - [Constructor](#constructor)
  - [Methods](#methods)
    - [add()](#add)
    - [execute()](#execute)
    - [batch()](#batch)
    - [insert_seeds()](#insert_seeds)
    - [set_table_schema()](#set_table_schema)
- [Seeds](#seeds)
  - [Data Access](#data-access)
  - [Export Methods](#export-methods)
  - [Import Methods](#import-methods)
- [SeedRow](#seedrow)
- [Decorators](#decorators)
  - [@seed_data](#seed_data)
- [Exceptions](#exceptions)
- [Models](#models)
  - [TableInfo](#tableinfo)
  - [ColumnInfo](#columninfo)
  - [SeedCommon](#seedcommon)

---

## SeedBuilder

Main API for declarative seed generation.

### Constructor

```python
SeedBuilder(
    conn: Connection | None,
    schema: str,
    backend: str = "direct",
    seed_common: str | Path | SeedCommon | None = None,
    validate_seed_common: bool = True
)
```

**Parameters:**

- **`conn`** (Connection | None): PostgreSQL connection from psycopg
  - Required for "direct" backend
  - None for "staging" backend (in-memory testing)

- **`schema`** (str): PostgreSQL schema name to introspect and seed
  - Example: `"public"`, `"test"`, `"app"`

- **`backend`** (str, optional): Backend type for data insertion
  - `"direct"` (default): Direct database insertion via bulk INSERT
  - `"staging"`: In-memory backend (no database connection required)

- **`seed_common`** (str | Path | SeedCommon | None, optional): Seed common baseline
  - **File path**: `"db/seed_common.yaml"`, `"db/seed_common.json"`
  - **Directory path**: `"db/"` (auto-detects format and environment)
  - **SeedCommon instance**: Pre-loaded baseline object
  - **None** (default): Shows warning, may cause UUID collisions

- **`validate_seed_common`** (bool, optional): Validate FK references on load
  - `True` (default): Validates FK references exist within seed common
  - `False`: Skip validation (faster but may miss errors)

**Examples:**

```python
from psycopg import connect
from fraiseql_data import SeedBuilder

# Standard usage with seed common
conn = connect("postgresql://user:pass@localhost/mydb")
builder = SeedBuilder(
    conn,
    schema="public",
    seed_common="db/seed_common.yaml"
)

# Without seed common (shows warning)
builder = SeedBuilder(conn, schema="public")

# Staging backend (no database)
builder = SeedBuilder(None, schema="test", backend="staging")

# Environment-specific seed common
import os
os.environ['FRAISEQL_ENV'] = 'dev'
builder = SeedBuilder(
    conn,
    schema="public",
    seed_common="db/"  # Auto-loads seed_common.dev.yaml
)
```

---

### Methods

#### `add()`

Add table to seed plan.

```python
add(
    table: str,
    count: int | Callable[[], int],
    strategy: str = "faker",
    overrides: dict[str, Any | Callable] | None = None,
    auto_deps: bool | dict = False
) -> SeedBuilder
```

**Parameters:**

- **`table`** (str): Table name to seed
  - Example: `"tb_product"`, `"tb_user"`

- **`count`** (int | Callable[[], int]): Number of rows to generate
  - **Static int**: `count=100`
  - **Callable**: `count=lambda: random.randint(50, 100)`

- **`strategy`** (str, optional): Generation strategy
  - `"faker"` (default): Use Faker for realistic data

- **`overrides`** (dict, optional): Column value overrides
  - **Static value**: `{"status": "active"}`
  - **Callable**: `{"price": lambda: random.uniform(10.0, 500.0)}`
  - **Callable with index**: `{"name": lambda i: f"Item {i}"}`

- **`auto_deps`** (bool | dict, optional): Auto-generate FK dependencies
  - **False** (default): No auto-deps
  - **True**: Generate 1 row per dependency (minimal)
  - **Dict with counts**: `{"tb_organization": 3, "tb_machine": 10}`
  - **Dict with config**: `{"tb_organization": {"count": 3, "overrides": {...}}}`

**Returns:** `SeedBuilder` (for method chaining)

**Examples:**

```python
# Basic usage
builder.add("tb_product", count=100)

# With overrides
builder.add("tb_product", count=50, overrides={
    "price": lambda: round(random.uniform(10.0, 500.0), 2),
    "status": "active",  # Static value
    "created_at": lambda i: f"2024-{i:02d}-01"  # Uses instance number
})

# With auto-deps (minimal)
builder.add("tb_allocation", count=50, auto_deps=True)

# With explicit auto-deps counts
builder.add("tb_allocation", count=100, auto_deps={
    "tb_organization": 3,
    "tb_machine": 10
})

# With auto-deps config and overrides
builder.add("tb_allocation", count=50, auto_deps={
    "tb_organization": {
        "count": 2,
        "overrides": {
            "name": lambda i: f"Org {i}",
            "org_type": "nonprofit"
        }
    }
})

# Dynamic count
builder.add("tb_product", count=lambda: random.randint(50, 100))
```

---

#### `execute()`

Execute seed plan and return generated data.

```python
execute() -> Seeds
```

**Returns:** `Seeds` object containing all generated data

**Example:**

```python
seeds = (
    builder
    .add("tb_manufacturer", count=10)
    .add("tb_product", count=100)
    .execute()
)

# Access generated data
for product in seeds.tb_product:
    print(product.name, product.price)
```

---

#### `batch()`

Create batch context manager for multi-table operations.

```python
batch() -> BatchContext
```

**Returns:** `BatchContext` (context manager)

**Examples:**

```python
# Basic batch
with builder.batch() as batch:
    batch.add("tb_manufacturer", count=10)
    batch.add("tb_model", count=50)
    batch.add("tb_variant", count=200)
# Auto-executes on exit

# Conditional operations
include_test_data = True
with builder.batch() as batch:
    batch.when(include_test_data).add("tb_test_user", count=20)
    batch.when(False).add("tb_demo_product", count=100)  # Skipped

# With auto-deps
with builder.batch() as batch:
    batch.add("tb_machine", count=10, auto_deps=True)
    batch.add("tb_allocation", count=50, auto_deps=True)
# Dependencies deduplicated across batch
```

---

#### `insert_seeds()`

Insert previously generated/imported seed data.

```python
insert_seeds(seeds: Seeds) -> Seeds
```

**Parameters:**

- **`seeds`** (Seeds): Seeds object to insert (from import or previous execution)

**Returns:** `Seeds` object (same as input)

**Example:**

```python
# Import from JSON
imported = Seeds.from_json(file_path="seeds.json")

# Insert into database
builder = SeedBuilder(conn, schema="public", backend="direct")
result = builder.insert_seeds(imported)
```

---

#### `set_table_schema()`

Manually set table schema (for staging backend).

```python
set_table_schema(table_name: str, table_info: TableInfo) -> None
```

**Parameters:**

- **`table_name`** (str): Table name
- **`table_info`** (TableInfo): Table schema definition

**Example:**

```python
from fraiseql_data.models import TableInfo, ColumnInfo

builder = SeedBuilder(None, schema="test", backend="staging")

# Define schema manually
table_info = TableInfo(
    name="tb_product",
    columns=[
        ColumnInfo(name="pk_product", pg_type="integer", is_nullable=False, is_primary_key=True),
        ColumnInfo(name="id", pg_type="uuid", is_nullable=False, is_unique=True),
        ColumnInfo(name="name", pg_type="text", is_nullable=False),
        ColumnInfo(name="price", pg_type="numeric", is_nullable=True),
    ]
)
builder.set_table_schema("tb_product", table_info)

# Generate data in-memory
seeds = builder.add("tb_product", count=100).execute()
```

---

## Seeds

Container for generated seed data with attribute access.

### Data Access

Access tables as attributes, returns list of `SeedRow` objects:

```python
seeds = builder.execute()

# Access tables by name
products = seeds.tb_product  # List[SeedRow]
users = seeds.tb_user        # List[SeedRow]

# Access columns by attribute
for product in products:
    print(product.pk_product)  # Primary key
    print(product.id)          # UUID
    print(product.identifier)  # Trinity identifier
    print(product.name)        # Regular column
    print(product.price)       # Nullable column
```

**Attributes:**

- **`table_name`**: Returns `List[SeedRow]` for that table
- Raises `AttributeError` if table not in seeds

---

### Export Methods

#### `to_json()`

Export all tables to JSON string.

```python
to_json() -> str
```

**Returns:** JSON string containing all seed data

**Example:**

```python
seeds = builder.add("tb_manufacturer", count=50).execute()

# Export to JSON
json_str = seeds.to_json()

# Save to file
with open("seeds.json", "w") as f:
    f.write(json_str)
```

**JSON Format:**

```json
{
  "tb_manufacturer": [
    {
      "pk_manufacturer": 1,
      "id": "2a6f3c21-0000-4000-8000-000000000001",
      "identifier": "MANUFACTURER-001",
      "name": "ACME Corp"
    }
  ]
}
```

---

#### `to_csv()`

Export single table to CSV file.

```python
to_csv(table_name: str, file_path: str | Path) -> None
```

**Parameters:**

- **`table_name`** (str): Table to export
- **`file_path`** (str | Path): Output CSV file path

**Example:**

```python
seeds = builder.add("tb_manufacturer", count=100).execute()

# Export to CSV
seeds.to_csv("tb_manufacturer", "manufacturers.csv")
```

**CSV Format:**

```csv
pk_manufacturer,id,identifier,name
1,2a6f3c21-0000-4000-8000-000000000001,MANUFACTURER-001,ACME Corp
2,2a6f3c21-0000-4000-8000-000000000002,MANUFACTURER-002,TechCorp
```

---

### Import Methods

#### `from_json()` (class method)

Import seed data from JSON.

```python
@classmethod
from_json(
    cls,
    file_path: str | Path | None = None,
    json_str: str | None = None
) -> Seeds
```

**Parameters:**

- **`file_path`** (str | Path, optional): Path to JSON file
- **`json_str`** (str, optional): JSON string

**Returns:** `Seeds` object

**Example:**

```python
from fraiseql_data.models import Seeds

# From file
imported = Seeds.from_json(file_path="seeds.json")

# From string
json_data = '{"tb_manufacturer": [{"pk_manufacturer": 1, ...}]}'
imported = Seeds.from_json(json_str=json_data)

# Insert into database
builder = SeedBuilder(conn, schema="public")
builder.insert_seeds(imported)
```

---

#### `from_csv()` (class method)

Import single table from CSV.

```python
@classmethod
from_csv(cls, table_name: str, file_path: str | Path) -> Seeds
```

**Parameters:**

- **`table_name`** (str): Table name
- **`file_path`** (str | Path): Path to CSV file

**Returns:** `Seeds` object

**Example:**

```python
from fraiseql_data.models import Seeds

# Import from CSV
imported = Seeds.from_csv("tb_manufacturer", "manufacturers.csv")

# Insert into database
builder = SeedBuilder(conn, schema="public")
builder.insert_seeds(imported)
```

---

## SeedRow

Individual row from seed data with attribute access.

```python
# Access via Seeds
for product in seeds.tb_product:  # product is SeedRow
    print(product.pk_product)     # Attribute access
    print(product.name)
    print(product.price)

# Convert to dict
row_dict = product.__dict__
```

**Attributes:**

- Dynamic attributes based on table columns
- All column names accessible as attributes
- `None` for NULL values

---

## Decorators

### `@seed_data`

pytest decorator for automatic seed data setup/cleanup.

```python
@seed_data(
    table: str,
    count: int = 1,
    overrides: dict | None = None,
    auto_deps: bool | dict = False
)
```

**Parameters:**

- **`table`** (str): Table to seed
- **`count`** (int, optional): Number of rows (default: 1)
- **`overrides`** (dict, optional): Column overrides
- **`auto_deps`** (bool | dict, optional): Auto-generate dependencies

**Example:**

```python
import pytest
from fraiseql_data import seed_data

@seed_data("tb_manufacturer", count=5)
@seed_data("tb_model", count=20)
def test_models(seeds):
    """Test with seeded data - auto-cleanup after test."""
    manufacturers = seeds.tb_manufacturer
    models = seeds.tb_model

    assert len(manufacturers) == 5
    assert len(models) == 20

    # Verify FK relationships
    for model in models:
        assert model.fk_manufacturer in [m.pk_manufacturer for m in manufacturers]

    # Data automatically cleaned up after test
```

**Features:**

- Stacks multiple decorators for multiple tables
- Automatic setup before test
- Automatic cleanup after test (even on failure)
- Works with existing fixtures
- Injects `seeds` parameter into test function

---

## Exceptions

All exceptions inherit from `FraiseQLDataError` and provide helpful error messages.

### Schema/Table Errors

#### `SchemaNotFoundError`

Schema doesn't exist in database.

```python
from fraiseql_data.exceptions import SchemaNotFoundError

try:
    builder = SeedBuilder(conn, schema="nonexistent")
except SchemaNotFoundError as e:
    print(f"Schema error: {e}")
```

---

#### `TableNotFoundError`

Table doesn't exist in schema.

```python
from fraiseql_data.exceptions import TableNotFoundError

try:
    builder.add("tb_nonexistent", count=10)
except TableNotFoundError as e:
    print(f"Table error: {e}")
```

---

### Generation Errors

#### `ColumnGenerationError`

Cannot auto-generate column data.

```python
from fraiseql_data.exceptions import ColumnGenerationError

# Raised when Faker can't infer column type and no override provided
```

---

#### `UniqueConstraintError`

Cannot generate unique value after retries.

```python
from fraiseql_data.exceptions import UniqueConstraintError

# Raised after 10 failed attempts to generate unique value
# Solution: Use more diverse generator or reduce count
```

---

### Dependency Errors

#### `CircularDependencyError`

Circular FK dependencies detected.

```python
from fraiseql_data.exceptions import CircularDependencyError

# Raised when tables form circular dependency loop
# Example: A → B → C → A
```

---

#### `MissingDependencyError`

Referenced table not in seed plan.

```python
from fraiseql_data.exceptions import MissingDependencyError

# Raised when FK parent not included in .add() calls
# Solution: Use auto_deps=True or manually add parent table
```

---

### FK Errors

#### `ForeignKeyResolutionError`

Cannot resolve FK reference.

```python
from fraiseql_data.exceptions import ForeignKeyResolutionError

# Raised when FK column can't find matching parent row
```

---

#### `SelfReferenceError`

Non-nullable self-reference requires override.

```python
from fraiseql_data.exceptions import SelfReferenceError

# Raised for non-nullable self-referencing FK
# Solution: Provide override for FK column
```

---

## Models

### TableInfo

Table schema metadata.

```python
from fraiseql_data.models import TableInfo, ColumnInfo

table_info = TableInfo(
    name="tb_product",
    columns=[
        ColumnInfo(name="pk_product", pg_type="integer", is_nullable=False, is_primary_key=True),
        ColumnInfo(name="name", pg_type="text", is_nullable=False),
    ]
)
```

**Attributes:**

- **`name`** (str): Table name
- **`columns`** (List[ColumnInfo]): Column definitions

---

### ColumnInfo

Column schema metadata.

```python
from fraiseql_data.models import ColumnInfo

col = ColumnInfo(
    name="pk_product",
    pg_type="integer",
    is_nullable=False,
    is_primary_key=True,
    is_unique=True
)
```

**Attributes:**

- **`name`** (str): Column name
- **`pg_type`** (str): PostgreSQL type (e.g., "integer", "uuid", "text")
- **`is_nullable`** (bool): Whether column accepts NULL
- **`is_primary_key`** (bool): Whether column is primary key
- **`is_unique`** (bool): Whether column has UNIQUE constraint
- **`default`** (str | None): Default value expression

---

### SeedCommon

Seed common baseline container.

```python
from fraiseql_data.models import SeedCommon

# Load from YAML
seed_common = SeedCommon.from_yaml("db/seed_common.yaml")

# Load from JSON
seed_common = SeedCommon.from_json("db/seed_common.json")

# Access baseline data
orgs = seed_common.get_table("tb_organization")  # List[dict]
count = seed_common.get_instance_count("tb_organization")  # int
```

**Methods:**

- **`from_yaml(path)`**: Load from YAML file
- **`from_json(path)`**: Load from JSON file
- **`get_table(name)`**: Get baseline rows for table
- **`get_instance_count(name)`**: Get baseline instance count
- **`validate_fk_references(schema_info)`**: Validate FK relationships

---

## Type Annotations

All APIs use modern Python 3.10+ type hints:

```python
from typing import Callable
from psycopg import Connection
from pathlib import Path

def add(
    table: str,
    count: int | Callable[[], int],
    overrides: dict[str, Any | Callable] | None = None,
    auto_deps: bool | dict = False
) -> SeedBuilder:
    ...
```

Use with mypy for type checking:

```bash
uv run mypy your_code.py
```

---

## See Also

- [README.md](../README.md) - Quick start and examples
- [PERFORMANCE.md](../PERFORMANCE.md) - Performance benchmarks
- [COVERAGE.md](../COVERAGE.md) - Test coverage report
