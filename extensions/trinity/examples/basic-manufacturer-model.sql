-- Trinity Extension Example: Basic Manufacturer/Model Relationship
-- This example demonstrates the complete Trinity pattern for related data

-- Setup: Set tenant context
SET trinity.tenant_id = 'example-tenant-12345678-1234-1234-1234-123456789abc'::UUID;

-- ============================================================================
-- STEP 1: Load Manufacturers
-- ============================================================================

-- Sample manufacturer CSV data
CREATE TEMP TABLE manufacturer_csv AS
SELECT $$
id,name,founded_year,headquarters
550e8400-e29b-41d4-a716-446655440001,Hewlett Packard,1939,Palo Alto
550e8400-e29b-41d4-a716-446655440002,Canon Inc,1937,Tokyo
550e8400-e29b-41d4-a716-446655440003,Epson Corp,1942,Suwa
$$ AS csv_content;

-- Transform manufacturer CSV
CREATE TEMP TABLE transformed_manufacturers AS
SELECT * FROM trinity.transform_csv(
    'manufacturer',
    (SELECT csv_content FROM manufacturer_csv),
    'pk_manufacturer',
    'id',
    'name'
);

-- Insert into final table structure
CREATE TABLE IF NOT EXISTS manufacturers (
    pk_manufacturer BIGINT PRIMARY KEY,
    id UUID NOT NULL UNIQUE,
    identifier TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    founded_year INTEGER,
    headquarters TEXT
);

INSERT INTO manufacturers
SELECT
    pk_value,
    id,
    identifier,
    extra_columns->>'name',
    (extra_columns->>'founded_year')::INTEGER,
    extra_columns->>'headquarters'
FROM transformed_manufacturers;

-- ============================================================================
-- STEP 2: Load Models with FK Resolution
-- ============================================================================

-- Sample model CSV data with manufacturer references
CREATE TEMP TABLE model_csv AS
SELECT $$
id,name,fk_manufacturer_id,release_year,price_usd
550e8400-e29b-41d4-a716-446655440101,LaserJet Pro P1102,550e8400-e29b-41d4-a716-446655440001,2008,199.99
550e8400-e29b-41d4-a716-446655440102,PIXMA MX922,550e8400-e29b-41d4-a716-446655440002,2012,149.99
550e8400-e29b-41d4-a716-446655440103,WorkForce WF-3640,550e8400-e29b-41d4-a716-446655440003,2015,79.99
$$ AS csv_content;

-- FK mapping: tell Trinity how to resolve manufacturer references
CREATE TEMP TABLE fk_mappings AS
SELECT $$
{
  "fk_manufacturer_id": {
    "target_table": "manufacturer"
  }
}
$$::JSONB AS mapping;

-- Transform model CSV with FK resolution
CREATE TEMP TABLE transformed_models AS
SELECT * FROM trinity.transform_csv(
    'model',
    (SELECT csv_content FROM model_csv),
    'pk_model',
    'id',
    'name',
    (SELECT mapping FROM fk_mappings)
);

-- Insert into final table structure
CREATE TABLE IF NOT EXISTS models (
    pk_model BIGINT PRIMARY KEY,
    id UUID NOT NULL UNIQUE,
    identifier TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    fk_manufacturer BIGINT NOT NULL REFERENCES manufacturers(pk_manufacturer),
    release_year INTEGER,
    price_usd DECIMAL(10,2)
);

INSERT INTO models
SELECT
    pk_value,
    id,
    identifier,
    extra_columns->>'name',
    (extra_columns->>'fk_manufacturer_id')::BIGINT,
    (extra_columns->>'release_year')::INTEGER,
    (extra_columns->>'price_usd')::DECIMAL(10,2)
FROM transformed_models;

-- ============================================================================
-- VERIFICATION: Check the Results
-- ============================================================================

-- View manufacturers
SELECT * FROM manufacturers ORDER BY pk_manufacturer;

-- View models with manufacturer names
SELECT
    m.pk_model,
    m.identifier,
    m.name,
    manuf.identifier as manufacturer_identifier,
    manuf.name as manufacturer_name,
    m.release_year,
    m.price_usd
FROM models m
JOIN manufacturers manuf ON m.fk_manufacturer = manuf.pk_manufacturer
ORDER BY m.pk_model;

-- Check Trinity allocation logs
SELECT * FROM trinity.get_uuid_to_pk_mappings('manufacturer');
SELECT * FROM trinity.get_uuid_to_pk_mappings('model');

-- Verify FK relationships are tracked
SELECT * FROM trinity.table_dependency_log;

-- ============================================================================
-- CLEANUP (Optional)
-- ============================================================================

-- Remove temporary tables
-- DROP TABLE transformed_manufacturers;
-- DROP TABLE transformed_models;
-- DROP TABLE manufacturers;
-- DROP TABLE models;

-- Note: Trinity allocation logs are permanent for audit trail
-- They can be cleaned up manually if needed:
-- DELETE FROM trinity.uuid_allocation_log WHERE tenant_id = 'example-tenant-...';
-- DELETE FROM trinity.table_dependency_log WHERE tenant_id = 'example-tenant-...';