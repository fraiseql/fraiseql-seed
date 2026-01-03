-- Trinity Extension Example: Performance Testing
-- Demonstrates performance benchmarking for large datasets

-- Setup: Clean tenant context
SET trinity.tenant_id = 'perf-test-tenant-12345678-1234-1234-1234-123456789abc'::UUID;

-- ============================================================================
-- PERFORMANCE TEST 1: PK Allocation Scaling
-- ============================================================================

-- Create test data generator
CREATE OR REPLACE FUNCTION generate_test_uuids(count INT)
RETURNS TABLE(uuid_val UUID) AS $$
    SELECT (gen_random_uuid())::UUID
    FROM generate_series(1, count);
$$ LANGUAGE SQL;

-- Test 1: Allocate 1000 PKs
DO $$
DECLARE
    v_start TIMESTAMP;
    v_end TIMESTAMP;
    v_duration INTERVAL;
    v_count INT := 1000;
BEGIN
    RAISE NOTICE 'Testing PK allocation performance with % UUIDs...', v_count;

    v_start := clock_timestamp();

    -- Allocate PKs for generated UUIDs
    CREATE TEMP TABLE test_allocations AS
    SELECT uuid_val, trinity.allocate_pk('perf_test', uuid_val) as pk_value
    FROM generate_test_uuids(v_count);

    v_end := clock_timestamp();
    v_duration := v_end - v_start;

    RAISE NOTICE 'Allocated % PKs in % seconds', v_count, extract(epoch from v_duration);
    RAISE NOTICE 'Average time per allocation: % ms', (extract(epoch from v_duration) / v_count) * 1000;
    RAISE NOTICE 'Throughput: % allocations/second', v_count / extract(epoch from v_duration);

    -- Verify results
    SELECT COUNT(*) as allocated_count FROM test_allocations \gset
    RAISE NOTICE 'Verification: % allocations recorded', :allocated_count;

    -- Check for duplicates (should be none)
    SELECT COUNT(*) as duplicates FROM (
        SELECT pk_value, COUNT(*) as cnt
        FROM test_allocations
        GROUP BY pk_value
        HAVING COUNT(*) > 1
    ) d \gset
    RAISE NOTICE 'Duplicates found: %', :duplicates;
END;
$$;

-- ============================================================================
-- PERFORMANCE TEST 2: CSV Transformation
-- ============================================================================

-- Generate large CSV for testing
CREATE OR REPLACE FUNCTION generate_large_csv(row_count INT)
RETURNS TEXT AS $$
DECLARE
    v_csv TEXT := 'id,name,category,value' || chr(10);
    v_uuid UUID;
BEGIN
    FOR i IN 1..row_count LOOP
        v_uuid := gen_random_uuid();
        v_csv := v_csv || v_uuid || ',Test Item ' || i || ',Category ' || (i % 10) || ',' || (random() * 1000)::INT || chr(10);
    END LOOP;

    RETURN v_csv;
END;
$$ LANGUAGE plpgsql;

-- Test CSV transformation with different sizes
DO $$
DECLARE
    v_sizes INT[] := ARRAY[100, 500, 1000];
    v_size INT;
    v_csv TEXT;
    v_start TIMESTAMP;
    v_end TIMESTAMP;
    v_duration INTERVAL;
    v_row_count INT;
BEGIN
    FOREACH v_size IN ARRAY v_sizes LOOP
        RAISE NOTICE 'Testing CSV transformation with % rows...', v_size;

        -- Generate CSV
        v_csv := generate_large_csv(v_size);
        v_start := clock_timestamp();

        -- Transform CSV
        CREATE TEMP TABLE temp_transform_ || v_size AS
        SELECT * FROM trinity.transform_csv(
            'csv_perf_test',
            v_csv,
            'pk_item',
            'id',
            'name'
        );

        v_end := clock_timestamp();
        v_duration := v_end - v_start;

        -- Count results
        EXECUTE format('SELECT COUNT(*) FROM temp_transform_%s', v_size) INTO v_row_count;

        RAISE NOTICE 'Transformed % rows in % seconds', v_row_count, extract(epoch from v_duration);
        RAISE NOTICE 'Average time per row: % ms', (extract(epoch from v_duration) / v_row_count) * 1000;
        RAISE NOTICE 'Throughput: % rows/second', v_row_count / extract(epoch from v_duration);
    END LOOP;
END;
$$;

-- ============================================================================
-- PERFORMANCE TEST 3: FK Resolution
-- ============================================================================

DO $$
DECLARE
    v_start TIMESTAMP;
    v_end TIMESTAMP;
    v_duration INTERVAL;
    v_count INT := 500;
BEGIN
    RAISE NOTICE 'Testing FK resolution performance with % lookups...', v_count;

    -- First create target allocations
    CREATE TEMP TABLE fk_targets AS
    SELECT uuid_val, trinity.allocate_pk('fk_target', uuid_val) as pk_value
    FROM generate_test_uuids(v_count / 5);  -- Fewer targets than lookups

    v_start := clock_timestamp();

    -- Perform FK resolutions (with some repeats for realistic patterns)
    CREATE TEMP TABLE fk_resolutions AS
    SELECT
        uuid_val,
        trinity.resolve_fk('fk_source', 'fk_target', uuid_val) as resolved_pk
    FROM (
        SELECT uuid_val FROM generate_test_uuids(v_count)
        UNION ALL
        SELECT uuid_val FROM fk_targets LIMIT v_count / 2  -- Add some repeats
    ) combined_uuids;

    v_end := clock_timestamp();
    v_duration := v_end - v_start;

    RAISE NOTICE 'Resolved % FKs in % seconds', v_count, extract(epoch from v_duration);
    RAISE NOTICE 'Average time per resolution: % ms', (extract(epoch from v_duration) / v_count) * 1000;
    RAISE NOTICE 'Throughput: % resolutions/second', v_count / extract(epoch from v_duration);
END;
$$;

-- ============================================================================
-- PERFORMANCE SUMMARY
-- ============================================================================

-- Overall statistics
SELECT
    table_name,
    COUNT(*) as total_allocations,
    MIN(pk_value) as first_pk,
    MAX(pk_value) as last_pk,
    EXTRACT(EPOCH FROM (MAX(allocated_at) - MIN(allocated_at))) as allocation_time_seconds
FROM trinity.uuid_allocation_log
WHERE tenant_id = 'perf-test-tenant-12345678-1234-1234-1234-123456789abc'::UUID
GROUP BY table_name
ORDER BY table_name;

-- Memory and performance info
SELECT
    schemaname,
    tablename,
    n_tup_ins as inserts,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_stat_user_tables
WHERE schemaname = 'trinity'
ORDER BY n_tup_ins DESC;

-- ============================================================================
-- CLEANUP
-- ============================================================================

-- Clean up test data (optional - Trinity logs are permanent for audit)
-- DELETE FROM trinity.uuid_allocation_log
-- WHERE tenant_id = 'perf-test-tenant-12345678-1234-1234-1234-123456789abc'::UUID;
--
-- DELETE FROM trinity.table_dependency_log
-- WHERE tenant_id = 'perf-test-tenant-12345678-1234-1234-1234-123456789abc'::UUID;