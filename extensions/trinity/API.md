# Trinity PostgreSQL Extension - API Reference

Complete function signatures and specifications for the Trinity extension.

## Core Functions

### allocate_pk

**Signature:**
```sql
FUNCTION trinity.allocate_pk(
    p_table_name TEXT,
    p_uuid_value UUID,
    p_tenant_id UUID DEFAULT CURRENT_SETTING('trinity.tenant_id')::UUID
) RETURNS BIGINT
```

**Purpose:** Allocates INTEGER primary keys for UUIDs in an idempotent manner.

**Parameters:**
- `p_table_name`: Name of the table (required, TEXT)
- `p_uuid_value`: UUID to allocate PK for (required, UUID)
- `p_tenant_id`: Tenant identifier for isolation (optional, UUID)

**Returns:** BIGINT - The allocated primary key value

**Behavior:**
- Idempotent: Same UUID always returns same PK
- Sequential: PKs allocated sequentially (1, 2, 3, ...)
- Tenant-isolated: Same UUID different PKs per tenant

**Errors:**
- `invalid_parameter_value`: Invalid table name or UUID
- `null_value_not_allowed`: NULL inputs
- `unique_violation`: Constraint violation (rare)

**Performance:** <2-5ms per call

---

### generate_identifier

**Signature:**
```sql
FUNCTION trinity.generate_identifier(
    p_name TEXT,
    p_instance INT DEFAULT NULL,
    p_separator TEXT DEFAULT '-'
) RETURNS TEXT
```

**Purpose:** Generates URL-safe identifier slugs from names.

**Parameters:**
- `p_name`: Name to convert (required, TEXT)
- `p_instance`: Instance number for duplicates (optional, INT)
- `p_separator`: Separator character (optional, TEXT, default '-')

**Returns:** TEXT - URL-safe identifier

**Behavior:**
- Lowercase conversion
- Special character removal/replacement
- Multiple space collapse
- Instance suffix for duplicates (e.g., 'name-2')

**Errors:**
- `null_value_not_allowed`: NULL name input

**Performance:** <0.1ms per call

---

### resolve_fk

**Signature:**
```sql
FUNCTION trinity.resolve_fk(
    p_source_table TEXT,
    p_target_table TEXT,
    p_uuid_fk UUID,
    p_tenant_id UUID DEFAULT CURRENT_SETTING('trinity.tenant_id')::UUID
) RETURNS BIGINT
```

**Purpose:** Resolves UUID foreign keys to INTEGER primary keys.

**Parameters:**
- `p_source_table`: Table containing the FK (required, TEXT)
- `p_target_table`: Referenced table (required, TEXT)
- `p_uuid_fk`: UUID FK value (optional, UUID - NULL allowed)
- `p_tenant_id`: Tenant identifier (optional, UUID)

**Returns:** BIGINT - Resolved PK value, or NULL if input was NULL

**Behavior:**
- NULL-safe: NULL input returns NULL
- Validates existence: Raises error if UUID not allocated
- Dependency tracking: Records FK relationships
- Circular dependency detection

**Errors:**
- `invalid_parameter_value`: Invalid table names
- `null_value_not_allowed`: NULL tenant
- `foreign_key_violation`: UUID not allocated in target table
- `unique_violation`: Circular dependency detected

**Performance:** <1ms per lookup

---

### transform_csv

**Signature:**
```sql
FUNCTION trinity.transform_csv(
    p_table_name TEXT,
    p_csv_content TEXT,
    p_pk_column TEXT,
    p_id_column TEXT DEFAULT 'id',
    p_name_column TEXT DEFAULT NULL,
    p_fk_mappings JSONB DEFAULT NULL,
    p_tenant_id UUID DEFAULT CURRENT_SETTING('trinity.tenant_id')::UUID
) RETURNS TABLE (
    pk_value BIGINT,
    id UUID,
    identifier TEXT,
    extra_columns JSONB
)
```

**Purpose:** Bulk transforms CSV data with PK allocation and FK resolution.

**Parameters:**
- `p_table_name`: Target table name (required, TEXT)
- `p_csv_content`: CSV content with header (required, TEXT)
- `p_pk_column`: Name for PK column in output (required, TEXT)
- `p_id_column`: UUID column name in CSV (optional, TEXT, default 'id')
- `p_name_column`: Name column for identifier generation (optional, TEXT)
- `p_fk_mappings`: FK resolution mapping (optional, JSONB)
- `p_tenant_id`: Tenant identifier (optional, UUID)

**Returns:** TABLE with transformed rows

**FK Mappings Format:**
```json
{
  "fk_column_name": {
    "target_table": "referenced_table_name"
  }
}
```

**Behavior:**
- Parses CSV with header row
- Allocates PKs for each UUID
- Generates identifiers from name column (if provided)
- Resolves FKs according to mappings
- Returns all columns as JSONB extras

**Errors:**
- `invalid_parameter_value`: Invalid parameters or malformed CSV
- `null_value_not_allowed`: NULL required parameters

**Performance:** <2s for 1M rows

---

### get_uuid_to_pk_mappings

**Signature:**
```sql
FUNCTION trinity.get_uuid_to_pk_mappings(
    p_table_name TEXT,
    p_tenant_id UUID DEFAULT CURRENT_SETTING('trinity.tenant_id')::UUID
) RETURNS TABLE (
    uuid_value UUID,
    pk_value BIGINT,
    allocated_at TIMESTAMP WITH TIME ZONE
)
```

**Purpose:** Retrieves UUID to PK mappings for verification.

**Parameters:**
- `p_table_name`: Table name to query (required, TEXT)
- `p_tenant_id`: Tenant identifier (optional, UUID)

**Returns:** TABLE with mapping data ordered by PK

**Performance:** Fast SELECT query

---

## Diagnostic Functions

### diagnose_allocation

**Signature:**
```sql
FUNCTION trinity.diagnose_allocation(
    p_table_name TEXT,
    p_uuid_value UUID,
    p_tenant_id UUID DEFAULT CURRENT_SETTING('trinity.tenant_id')::UUID
) RETURNS JSONB
```

**Returns:** Allocation status and diagnostic information

---

### check_fk_integrity

**Signature:**
```sql
FUNCTION trinity.check_fk_integrity(
    p_table_name TEXT,
    p_tenant_id UUID DEFAULT CURRENT_SETTING('trinity.tenant_id')::UUID
) RETURNS JSONB
```

**Returns:** FK integrity statistics and issues

---

### detect_circular_dependencies

**Signature:**
```sql
FUNCTION trinity.detect_circular_dependencies(
    p_tenant_id UUID DEFAULT CURRENT_SETTING('trinity.tenant_id')::UUID
) RETURNS TABLE (cycle_path TEXT)
```

**Returns:** Detected circular dependency cycles

---

### allocation_stats

**Signature:**
```sql
FUNCTION trinity.allocation_stats(
    p_tenant_id UUID DEFAULT CURRENT_SETTING('trinity.tenant_id')::UUID
) RETURNS TABLE (
    table_name TEXT,
    allocation_count BIGINT,
    min_pk BIGINT,
    max_pk BIGINT,
    latest_allocation TIMESTAMP WITH TIME ZONE
)
```

**Returns:** Allocation statistics per table

---

## Internal Functions

### _validate_uuid
### _normalize_identifier_source
### _allocate_next_pk
### _check_circular_dependency
### _get_next_identifier_instance
### _raise_error
### _detect_cycle_dfs

*These are internal utility functions not intended for direct use.*

---

## Data Types

### UUID Allocation Log
```sql
CREATE TABLE trinity.uuid_allocation_log (
    table_name TEXT NOT NULL,
    uuid_value UUID NOT NULL,
    pk_value BIGINT NOT NULL,
    tenant_id UUID NOT NULL,
    allocated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT DEFAULT SESSION_USER,
    PRIMARY KEY (table_name, uuid_value, tenant_id),
    UNIQUE (table_name, pk_value, tenant_id)
);
```

### Table Dependency Log
```sql
CREATE TABLE trinity.table_dependency_log (
    source_table TEXT NOT NULL,
    target_table TEXT NOT NULL,
    fk_column TEXT NOT NULL,
    tenant_id UUID NOT NULL,
    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (source_table, target_table, fk_column, tenant_id)
);
```

### UUID to PK Mapping View
```sql
CREATE VIEW trinity.uuid_to_pk_mapping AS
SELECT table_name, uuid_value, pk_value, tenant_id, allocated_at, created_by
FROM trinity.uuid_allocation_log
ORDER BY table_name, pk_value;
```

---

## Error Codes

| Code | SQLSTATE | Description |
|------|----------|-------------|
| T0001 | invalid_parameter_value | Invalid UUID format |
| T0002 | invalid_parameter_value | Invalid table name |
| T0003 | foreign_key_violation | Missing foreign key allocation |
| T0004 | unique_violation | Circular dependency detected |
| T0005 | unique_violation | Identifier collision |
| T0006 | unique_violation | Constraint violation |
| T0007 | invalid_parameter_value | CSV parse error |
| T0008 | insufficient_privilege | Tenant isolation error |

---

**Version:** 1.0
**Last Updated:** 2026-01-03
