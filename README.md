# FraiseQL Seed - Trinity Pattern Seed Data Management

**Automatic seed data management for FraiseQL projects with the Trinity identifier pattern.**

## What is the Trinity Pattern?

FraiseQL projects use three identifiers on every table:

```sql
CREATE TABLE catalog.tb_manufacturer (
    pk_manufacturer INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,  -- Internal (fast joins)
    id UUID DEFAULT gen_random_uuid() NOT NULL UNIQUE,                  -- Public (API)
    identifier TEXT NOT NULL UNIQUE,                                    -- Business key
    name TEXT,
    ...
);
```

This creates a challenge for seed data:
- **Seed files** use UUIDs (easy cross-referencing)
- **Production** uses INTEGER FKs (performance)
- **Resolution needed**: UUID → INTEGER mapping

## What Does This Tool Do?

`fraiseql-seed` automatically:

1. ✅ **Detects Trinity pattern** via schema introspection
2. ✅ **Generates staging schema** with UUID-based FKs
3. ✅ **Generates resolution functions** for UUID→INTEGER conversion
4. ✅ **Validates** schema compatibility and data integrity
5. ✅ **Loads seed data** with transaction-based rollback
6. ✅ **Tests** resolution functions automatically

## Installation

```bash
pip install fraiseql-seed
```

## Quick Start

```bash
# Initialize configuration
fraiseql-seed init

# Generate staging schema and resolution functions
fraiseql-seed generate

# Validate everything
fraiseql-seed validate

# Load seed data
fraiseql-seed load --environment local

# Get info
fraiseql-seed info
```

## Configuration

Create `fraiseql-seed.toml` in your project root:

```toml
[database]
url = "postgresql://localhost/myproject_local"
schemas = ["catalog", "tenant", "management"]

[trinity]
pk_prefix = "pk_"
id_column = "id"
identifier_column = "identifier"

[staging]
schema = "prep_seed"
table_prefix = "tb_"
translation_prefix = "tl_"
function_prefix = "fn_resolve_"

[seed]
data_dir = "db/seed/"
environments = ["local", "test", "staging"]
```

## Features

### Auto-Generation from Schema

The tool introspects your production database schema and automatically generates:

- **Staging tables** with UUID foreign keys
- **Resolution functions** with FK mapping logic
- **Master orchestration function** with dependency ordering
- **Two-pass handling** for self-referencing tables

### Validation Framework

Catches bugs before deployment:

- ✅ Schema compatibility checks
- ✅ Column existence validation
- ✅ FK target validation
- ✅ Row count verification
- ✅ Referential integrity checks

### Transaction-Based Loading

Safe seed data loading:

- ✅ Automatic rollback on failure
- ✅ Pre-execution validation
- ✅ Post-execution verification
- ✅ Progress reporting

## Commands

### `generate`

Generate staging schema and resolution functions:

```bash
fraiseql-seed generate                # Generate everything
fraiseql-seed generate --tables-only  # Only staging tables
fraiseql-seed generate --dry-run      # Preview without writing
fraiseql-seed generate --validate     # Generate + validate
```

### `validate`

Validate seeding system integrity:

```bash
fraiseql-seed validate                # Validate everything
fraiseql-seed validate --schema-only  # Only schema
fraiseql-seed validate --verbose      # Detailed output
```

### `load`

Load seed data into database:

```bash
fraiseql-seed load                          # Load to default DB
fraiseql-seed load --environment staging   # Load staging seed
fraiseql-seed load --dry-run                # Validate without loading
```

### `reset`

Reset database to clean state:

```bash
fraiseql-seed reset                    # Reset with confirmation
fraiseql-seed reset --force            # Skip confirmation
fraiseql-seed reset --schema-only      # Schema only, no seed data
```

### `test`

Test resolution functions:

```bash
fraiseql-seed test                     # Test all functions
fraiseql-seed test --entity tb_machine # Test specific entity
fraiseql-seed test --generate          # Generate test files
```

### `add`

Scaffold new entity:

```bash
fraiseql-seed add tb_customer                  # Interactive
fraiseql-seed add tb_customer --schema tenant  # Specify schema
```

### `info`

Display system information:

```bash
fraiseql-seed info            # Summary
fraiseql-seed info --verbose  # Detailed stats
fraiseql-seed info --json     # JSON output
```

## Example Workflow

### New FraiseQL Project

```bash
# 1. Install
pip install fraiseql-seed

# 2. Initialize
fraiseql-seed init

# 3. Generate staging schema
fraiseql-seed generate

# 4. Create seed data (SQL files in db/seed/)
# ... edit seed files ...

# 5. Load seed data
fraiseql-seed load

# 6. Validate
fraiseql-seed validate
```

### Adding New Entity

```bash
# 1. Add production table to schema
# ... edit schema files ...

# 2. Add entity with tool
fraiseql-seed add tb_customer --schema tenant

# 3. Edit generated seed file
# ... add seed data ...

# 4. Regenerate staging schema
fraiseql-seed generate

# 5. Validate
fraiseql-seed validate

# 6. Load
fraiseql-seed load
```

## Architecture

### How It Works

```
┌─────────────────────────────────────┐
│ 1. Production Schema (Source)       │
│    catalog.tb_manufacturer          │
│    pk_manufacturer INTEGER (PK)     │
│    id UUID                          │
│    fk_type INTEGER → tb_type(pk)   │
└──────────────┬──────────────────────┘
               │ INTROSPECT
               ▼
┌─────────────────────────────────────┐
│ 2. Generated Staging Schema         │
│    prep_seed.tb_manufacturer        │
│    id UUID (UNIQUE)                 │
│    fk_type_id UUID (not INTEGER!)  │
└──────────────┬──────────────────────┘
               │ LOAD SEED DATA
               ▼
┌─────────────────────────────────────┐
│ 3. Resolution Function              │
│    fn_resolve_tb_manufacturer()     │
│    • Converts fk_type_id UUID       │
│      → fk_type INTEGER              │
│    • Inserts into production        │
└──────────────┬──────────────────────┘
               │ EXECUTE
               ▼
┌─────────────────────────────────────┐
│ 4. Production Data                  │
│    catalog.tb_manufacturer          │
│    pk_manufacturer = 1 (auto)       │
│    id = 'uuid-from-seed'            │
│    fk_type = 42 (resolved!)         │
└─────────────────────────────────────┘
```

## Reference Implementation

See [PrintOptim](https://github.com/fraiseql/printoptim) for reference implementation:
- 221 tables with Trinity pattern
- 222 auto-generated resolution functions
- Comprehensive seed data examples

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT License - see [LICENSE](LICENSE)

## Links

- **Documentation**: https://fraiseql-seed.readthedocs.io
- **Source Code**: https://github.com/fraiseql/fraiseql-seed
- **Bug Reports**: https://github.com/fraiseql/fraiseql-seed/issues
- **FraiseQL**: https://github.com/fraiseql/fraiseql
