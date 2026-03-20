# Trinity PostgreSQL Extension - Usage Guide

This guide provides practical examples and patterns for using the Trinity extension in FraiseQL data pipelines.

## Table of Contents

- [Quick Start](#quick-start)
- [Core Functions](#core-functions)
- [Common Patterns](#common-patterns)
- [Multi-Tenant Setup](#multi-tenant-setup)
- [Performance Tips](#performance-tips)
- [Error Handling](#error-handling)

## Quick Start

### Basic PK Allocation

```sql
-- Set tenant context
SET trinity.tenant_id = 'your-tenant-uuid'::UUID;

-- Allocate PK for a manufacturer
SELECT trinity.allocate_pk('manufacturer', 'uuid-from-forge'::UUID);

-- Result: 1 (first allocation)

-- Allocate another PK
SELECT trinity.allocate_pk('manufacturer', 'another-uuid'::UUID);

-- Result: 2 (sequential allocation)

-- Same UUID returns same PK (idempotent)
SELECT trinity.allocate_pk('manufacturer', 'uuid-from-forge'::UUID);

-- Result: 1 (same as before)
```

### CSV Transformation

```sql
-- Sample CSV data
CREATE TEMP TABLE temp_csv AS
SELECT $$
id,name
550e8400-e29b-41d4-a716-446655440001,Hewlett Packard
550e8400-e29b-41d4-a716-446655440002,Canon Inc
$$ AS csv_content;

-- Transform CSV to Trinity format
SELECT * FROM trinity.transform_csv(
    'manufacturer',           -- table name
    (SELECT csv_content FROM temp_csv),  -- CSV data
    'pk_manufacturer',        -- PK column name
    'id',                     -- UUID column name
    'name'                    -- name column for identifiers
);

-- Result:
-- pk_value | id                                   | identifier       | extra_columns
-- ----------+--------------------------------------+--------------------+---------------
-- 1        | 550e8400-e29b-41d4-a716-446655440001 | hewlett-packard   | {"name": "Hewlett Packard"}
-- 2        | 550e8400-e29b-41d4-a716-446655440002 | canon-inc         | {"name": "Canon Inc"}
```

## Core Functions

### allocate_pk()

**Purpose:** Allocate INTEGER PKs for UUIDs (idempotent)

**Signature:**
```sql
trinity.allocate_pk(table_name TEXT, uuid_value UUID, tenant_id UUID DEFAULT ...) → BIGINT
```

**Examples:**

```sql
-- Basic allocation
SELECT trinity.allocate_pk('product', '550e8400-e29b-41d4-a716-446655440000'::UUID);

-- With explicit tenant
SELECT trinity.allocate_pk('product', uuid, 'tenant-123'::UUID);

-- Batch allocation
INSERT INTO products (pk_product, id, name)
SELECT
    trinity.allocate_pk('product', id),
    id,
    name
FROM forge_products;
```

### generate_identifier()

**Purpose:** Create URL-safe slugs from names

**Signature:**
```sql
trinity.generate_identifier(name TEXT, instance INT DEFAULT NULL, separator TEXT DEFAULT '-') → TEXT
```

**Examples:**

```sql
-- Basic identifier
SELECT trinity.generate_identifier('Hewlett Packard Inc.');
-- Result: 'hewlett-packard-inc'

-- With custom separator
SELECT trinity.generate_identifier('Test Name', NULL, '_');
-- Result: 'test_name'

-- Handle duplicates
SELECT trinity.generate_identifier('Acme Corp', 2);
-- Result: 'acme-corp-2'
```

### resolve_fk()

**Purpose:** Convert UUID FKs to INTEGER PKs

**Signature:**
```sql
trinity.resolve_fk(source_table TEXT, target_table TEXT, uuid_fk UUID, tenant_id UUID DEFAULT ...) → BIGINT
```

**Examples:**

```sql
-- Resolve manufacturer FK in product
SELECT trinity.resolve_fk('product', 'manufacturer', 'manufacturer-uuid'::UUID);

-- Handle nullable FKs
SELECT trinity.resolve_fk('product', 'manufacturer',
    CASE WHEN manufacturer_id IS NOT NULL THEN manufacturer_id::UUID ELSE NULL END);
```

### transform_csv()

**Purpose:** Bulk CSV transformation with PK allocation and FK resolution

**Signature:**
```sql
trinity.transform_csv(table_name TEXT, csv_content TEXT, pk_column TEXT,
    id_column TEXT DEFAULT 'id', name_column TEXT DEFAULT NULL,
    fk_mappings JSONB DEFAULT NULL, tenant_id UUID DEFAULT ...) → TABLE
```

**Examples:**

```sql
-- Simple transformation
SELECT * FROM trinity.transform_csv(
    'manufacturer',
    'id,name\nuuid1,Company A\nuuid2,Company B',
    'pk_manufacturer'
);

-- With FK resolution
SELECT * FROM trinity.transform_csv(
    'model',
    'id,name,fk_manufacturer_id\nuuid1,Model X,manuf-uuid',
    'pk_model',
    'id',
    'name',
    '{"fk_manufacturer_id": {"target_table": "manufacturer"}}'::JSONB
);
```

### get_uuid_to_pk_mappings()

**Purpose:** Query UUID→PK mappings for verification

**Signature:**
```sql
trinity.get_uuid_to_pk_mappings(table_name TEXT, tenant_id UUID DEFAULT ...) → TABLE
```

**Examples:**

```sql
-- Get all mappings for a table
SELECT * FROM trinity.get_uuid_to_pk_mappings('manufacturer');

-- Verify specific allocation
SELECT pk_value FROM trinity.get_uuid_to_pk_mappings('manufacturer')
WHERE uuid_value = 'your-uuid'::UUID;
```

## Common Patterns

### Manufacturer → Model Relationship

```sql
-- Step 1: Load manufacturers
CREATE TABLE temp_manufacturers AS
SELECT * FROM trinity.transform_csv(
    'manufacturer',
    %CSV_DATA%,
    'pk_manufacturer'
);

-- Step 2: Load models with FK resolution
CREATE TABLE temp_models AS
SELECT * FROM trinity.transform_csv(
    'model',
    %CSV_DATA%,
    'pk_model',
    'id',
    'name',
    '{"fk_manufacturer_id": {"target_table": "manufacturer"}}'::JSONB
);

-- Step 3: Insert into final tables
INSERT INTO manufacturers SELECT pk_manufacturer, id, identifier, extra_columns->>'name' FROM temp_manufacturers;
INSERT INTO models SELECT pk_model, id, identifier, (extra_columns->>'fk_manufacturer_id')::BIGINT, extra_columns->>'name' FROM temp_models;
```

### Batch Processing

```sql
-- Process large CSV in chunks
CREATE OR REPLACE FUNCTION process_large_csv(csv_data TEXT, batch_size INT DEFAULT 1000)
RETURNS VOID AS $$
DECLARE
    lines TEXT[];
    header TEXT;
    batch TEXT;
    i INT := 2; -- Start after header
BEGIN
    lines := string_to_array(csv_data, chr(10));
    header := lines[1];

    WHILE i <= array_length(lines, 1) LOOP
        -- Build batch
        batch := header;
        FOR j IN 1..batch_size LOOP
            EXIT WHEN i + j - 1 > array_length(lines, 1);
            batch := batch || chr(10) || lines[i + j - 1];
        END LOOP;

        -- Process batch
        PERFORM trinity.transform_csv('your_table', batch, 'pk_column');

        i := i + batch_size;
    END LOOP;
END;
$$ LANGUAGE plpgsql;
```

### Error Recovery

```sql
-- Function with error handling
CREATE OR REPLACE FUNCTION safe_allocate(table_name TEXT, uuid_val UUID)
RETURNS BIGINT AS $$
BEGIN
    RETURN trinity.allocate_pk(table_name, uuid_val);
EXCEPTION WHEN OTHERS THEN
    -- Log error and continue
    RAISE WARNING 'Failed to allocate PK for % in table %: %', uuid_val, table_name, SQLERRM;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;
```

## Multi-Tenant Setup

### Session-Level Tenant Isolation

```sql
-- Set tenant for session
SET trinity.tenant_id = 'tenant-a-uuid'::UUID;

-- All operations in this session are tenant-isolated
SELECT trinity.allocate_pk('product', 'uuid1'::UUID); -- PK: 1 for tenant A
SELECT trinity.allocate_pk('product', 'uuid2'::UUID); -- PK: 2 for tenant A

-- Switch tenant
SET trinity.tenant_id = 'tenant-b-uuid'::UUID;

-- Same UUIDs get different PKs
SELECT trinity.allocate_pk('product', 'uuid1'::UUID); -- PK: 1 for tenant B
SELECT trinity.allocate_pk('product', 'uuid2'::UUID); -- PK: 2 for tenant B
```

### Application-Level Tenant Management

```sql
-- Helper function for tenant operations
CREATE OR REPLACE FUNCTION with_tenant(tenant_uuid UUID, query TEXT)
RETURNS JSONB AS $$
DECLARE
    result JSONB;
BEGIN
    EXECUTE format('SET LOCAL trinity.tenant_id = %L', tenant_uuid);
    EXECUTE format('SELECT to_jsonb(result) FROM (%s) result', query) INTO result;
    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- Usage
SELECT with_tenant('tenant-123'::UUID,
    'SELECT trinity.allocate_pk(''product'', ''uuid1''::UUID)');
```

## Performance Tips

### Indexing Strategy

```sql
-- Ensure proper indexes exist (created automatically by extension)
SELECT * FROM pg_indexes WHERE schemaname = 'trinity';

-- Manual index creation for high-throughput scenarios
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_custom_lookup
    ON trinity.uuid_allocation_log (tenant_id, table_name, pk_value);
```

### Batch Operations

```sql
-- Use batch processing for large datasets
BEGIN;
    -- Allocate PKs in batch
    CREATE TEMP TABLE temp_allocations AS
    SELECT id, trinity.allocate_pk('table', id) as pk
    FROM source_data;

    -- Bulk insert
    INSERT INTO target_table
    SELECT pk, id, other_columns
    FROM temp_allocations;
COMMIT;
```

### Connection Pooling

```sql
-- For high-throughput applications
-- Use PgBouncer or similar connection pooler
-- Configure with:
--   pool_mode = transaction
--   max_client_conn = 1000
--   default_pool_size = 20
```

### Memory Management

```sql
-- Increase memory for large transformations
SET work_mem = '512MB';
SET maintenance_work_mem = '1GB';
SET temp_buffers = '256MB';

-- Monitor memory usage
SELECT * FROM pg_stat_activity
WHERE state = 'active' AND query LIKE '%trinity%';
```

## Error Handling

### Common Errors and Solutions

**Foreign Key Violation:**
```sql
-- Error: no allocation found for UUID
-- Solution: Allocate target first
SELECT trinity.allocate_pk('manufacturer', 'missing-uuid'::UUID);
SELECT trinity.resolve_fk('product', 'manufacturer', 'missing-uuid'::UUID);
```

**Circular Dependency:**
```sql
-- Error: circular dependency detected
-- Solution: Check dependency graph
SELECT * FROM trinity.detect_circular_dependencies();
-- Remove problematic relationship
DELETE FROM trinity.table_dependency_log
WHERE source_table = 'problem_table';
```

**Constraint Violation:**
```sql
-- Error: duplicate PK detected
-- Solution: Check for race conditions or data corruption
SELECT * FROM trinity.allocation_stats();
SELECT trinity.diagnose_allocation('table', 'problem-uuid'::UUID);
```

### Diagnostic Queries

```sql
-- Check allocation health
SELECT table_name, COUNT(*) as allocations
FROM trinity.uuid_allocation_log
GROUP BY table_name
ORDER BY allocations DESC;

-- Find potential issues
SELECT * FROM trinity.check_fk_integrity('your_table');

-- Monitor performance
SELECT schemaname, funcname, calls, total_time, mean_time
FROM pg_stat_user_functions
WHERE schemaname = 'trinity'
ORDER BY mean_time DESC;
```

## Advanced Usage

### Custom Identifier Generation

```sql
-- Create custom identifier rules
CREATE OR REPLACE FUNCTION custom_identifier(name TEXT, category TEXT)
RETURNS TEXT AS $$
BEGIN
    -- Add category prefix
    RETURN category || '-' || trinity.generate_identifier(name);
END;
$$ LANGUAGE plpgsql;

-- Usage
SELECT custom_identifier('LaserJet Pro', 'printer');
-- Result: 'printer-laserjet-pro'
```

### Migration Helpers

```sql
-- Migrate existing UUID-based data
CREATE OR REPLACE FUNCTION migrate_to_trinity(table_name TEXT, uuid_column TEXT, pk_column TEXT)
RETURNS VOID AS $$
DECLARE
    rec RECORD;
BEGIN
    FOR rec IN EXECUTE format('SELECT %I as uuid_val FROM %I WHERE %I IS NOT NULL', uuid_column, table_name, pk_column) LOOP
        -- Allocate PK for existing UUID
        PERFORM trinity.allocate_pk(table_name, rec.uuid_val);
    END LOOP;
END;
$$ LANGUAGE plpgsql;
```

---

**Version:** 1.0
**Last Updated:** 2026-01-03
**See Also:** [API Reference](API.md), [Troubleshooting](TROUBLESHOOTING.md)
