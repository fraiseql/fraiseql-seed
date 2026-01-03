-- Trinity Extension Phase 3: Production Readiness Tests
-- Tests for enterprise deployment, error handling, and production scenarios

-- Setup
\set test_tenant '550e8400-e29b-41d4-a716-446655440000'::UUID
SET trinity.tenant_id = '550e8400-e29b-41d4-a716-446655440000'::UUID;

-- Test counters
CREATE TEMP TABLE phase3_test_results (
    test_name TEXT PRIMARY KEY,
    passed BOOLEAN,
    error_message TEXT,
    execution_time INTERVAL
);

-- Helper function to record test results
CREATE OR REPLACE FUNCTION record_phase3_test(p_test_name TEXT, p_passed BOOLEAN, p_error TEXT DEFAULT NULL)
RETURNS VOID AS $$
DECLARE
    v_start_time TIMESTAMP := clock_timestamp();
BEGIN
    INSERT INTO phase3_test_results (test_name, passed, error_message, execution_time)
    VALUES (p_test_name, p_passed, p_error, clock_timestamp() - v_start_time)
    ON CONFLICT (test_name) DO UPDATE SET
        passed = EXCLUDED.passed,
        error_message = EXCLUDED.error_message,
        execution_time = EXCLUDED.execution_time;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- DIAGNOSTIC FUNCTION TESTS
-- ============================================================================

-- Test 1: diagnose_allocation - successful allocation
DO $$
DECLARE
    v_result JSONB;
    v_pk BIGINT;
BEGIN
    v_pk := trinity.allocate_pk('diag_test', '550e8400-e29b-41d4-a716-446655440001'::UUID, '550e8400-e29b-41d4-a716-446655440000'::UUID);
    v_result := trinity.diagnose_allocation('diag_test', '550e8400-e29b-41d4-a716-446655440001'::UUID, '550e8400-e29b-41d4-a716-446655440000'::UUID);

    IF v_result->>'status' = 'allocated' AND (v_result->>'pk_value')::BIGINT = v_pk THEN
        PERFORM record_phase3_test('diagnose_allocation_success', true);
    ELSE
        PERFORM record_phase3_test('diagnose_allocation_success', false, 'Unexpected result: ' || v_result::TEXT);
    END IF;
EXCEPTION WHEN OTHERS THEN
    PERFORM record_phase3_test('diagnose_allocation_success', false, SQLERRM);
END;
$$;

-- Test 2: diagnose_allocation - missing allocation
DO $$
DECLARE
    v_result JSONB;
BEGIN
    v_result := trinity.diagnose_allocation('diag_test', '550e8400-e29b-41d4-a716-446655440999'::UUID, '550e8400-e29b-41d4-a716-446655440000'::UUID);

    IF v_result->>'status' = 'missing' THEN
        PERFORM record_phase3_test('diagnose_allocation_missing', true);
    ELSE
        PERFORM record_phase3_test('diagnose_allocation_missing', false, 'Expected missing status, got: ' || v_result::TEXT);
    END IF;
EXCEPTION WHEN OTHERS THEN
    PERFORM record_phase3_test('diagnose_allocation_missing', false, SQLERRM);
END;
$$;

-- Test 3: check_fk_integrity
DO $$
DECLARE
    v_result JSONB;
BEGIN
    -- Create some test data first
    PERFORM trinity.allocate_pk('fk_test_table', '550e8400-e29b-41d4-a716-446655440002'::UUID, '550e8400-e29b-41d4-a716-446655440000'::UUID);

    v_result := trinity.check_fk_integrity('fk_test_table', '550e8400-e29b-41d4-a716-446655440000'::UUID);

    IF v_result->>'table_name' = 'fk_test_table' THEN
        PERFORM record_phase3_test('check_fk_integrity', true);
    ELSE
        PERFORM record_phase3_test('check_fk_integrity', false, 'Unexpected result: ' || v_result::TEXT);
    END IF;
EXCEPTION WHEN OTHERS THEN
    PERFORM record_phase3_test('check_fk_integrity', false, SQLERRM);
END;
$$;

-- Test 4: allocation_stats
DO $$
DECLARE
    v_count INT;
BEGIN
    -- Create test allocations
    PERFORM trinity.allocate_pk('stats_test', gen_random_uuid(), '550e8400-e29b-41d4-a716-446655440000'::UUID) FROM generate_series(1, 5);

    SELECT COUNT(*) INTO v_count
    FROM trinity.allocation_stats('550e8400-e29b-41d4-a716-446655440000'::UUID)
    WHERE table_name = 'stats_test';

    IF v_count = 1 THEN
        PERFORM record_phase3_test('allocation_stats', true);
    ELSE
        PERFORM record_phase3_test('allocation_stats', false, 'Expected 1 row, got ' || v_count);
    END IF;
EXCEPTION WHEN OTHERS THEN
    PERFORM record_phase3_test('allocation_stats', false, SQLERRM);
END;
$$;

-- ============================================================================
-- ERROR HANDLING TESTS
-- ============================================================================

-- Test 5: Custom error codes - invalid UUID
DO $$
BEGIN
    PERFORM trinity._validate_uuid('invalid-uuid');
    PERFORM record_phase3_test('error_invalid_uuid', false, 'Should have raised exception');
EXCEPTION WHEN invalid_parameter_value THEN
    PERFORM record_phase3_test('error_invalid_uuid', true);
WHEN OTHERS THEN
    PERFORM record_phase3_test('error_invalid_uuid', false, 'Wrong exception: ' || SQLERRM);
END;
$$;

-- Test 6: Foreign key violation with helpful message
DO $$
BEGIN
    PERFORM trinity.resolve_fk('test_source', 'nonexistent_table', '550e8400-e29b-41d4-a716-446655440003'::UUID, '550e8400-e29b-41d4-a716-446655440000'::UUID);
    PERFORM record_phase3_test('error_fk_violation', false, 'Should have raised exception');
EXCEPTION WHEN foreign_key_violation THEN
    IF strpos(SQLERRM, 'nonexistent_table') > 0 THEN
        PERFORM record_phase3_test('error_fk_violation', true);
    ELSE
        PERFORM record_phase3_test('error_fk_violation', false, 'Error message should include table name');
    END IF;
WHEN OTHERS THEN
    PERFORM record_phase3_test('error_fk_violation', false, 'Wrong exception type: ' || SQLERRM);
END;
$$;

-- ============================================================================
-- LARGE DATASET TESTS
-- ============================================================================

-- Test 7: Large batch allocation (1000 allocations)
DO $$
DECLARE
    v_start TIMESTAMP;
    v_count INT := 1000;
    v_allocated_count INT;
BEGIN
    v_start := clock_timestamp();

    -- Allocate 1000 PKs
    CREATE TEMP TABLE large_batch AS
    SELECT trinity.allocate_pk('large_test', gen_random_uuid(), '550e8400-e29b-41d4-a716-446655440000'::UUID) as pk
    FROM generate_series(1, v_count);

    SELECT COUNT(*) INTO v_allocated_count FROM large_batch;

    IF v_allocated_count = v_count THEN
        PERFORM record_phase3_test('large_batch_allocation', true);
    ELSE
        PERFORM record_phase3_test('large_batch_allocation', false, format('Expected %s allocations, got %s', v_count, v_allocated_count));
    END IF;
EXCEPTION WHEN OTHERS THEN
    PERFORM record_phase3_test('large_batch_allocation', false, SQLERRM);
END;
$$;

-- Test 8: Memory usage monitoring
DO $$
DECLARE
    v_initial_size BIGINT;
    v_final_size BIGINT;
BEGIN
    -- Check initial table size
    SELECT pg_total_relation_size('trinity.uuid_allocation_log') INTO v_initial_size;

    -- Add many allocations
    PERFORM trinity.allocate_pk('memory_test', gen_random_uuid(), '550e8400-e29b-41d4-a716-446655440000'::UUID)
    FROM generate_series(1, 5000);

    -- Check final table size
    SELECT pg_total_relation_size('trinity.uuid_allocation_log') INTO v_final_size;

    -- Size should have increased but not excessively
    IF v_final_size > v_initial_size AND v_final_size < v_initial_size * 10 THEN
        PERFORM record_phase3_test('memory_usage_reasonable', true);
    ELSE
        PERFORM record_phase3_test('memory_usage_reasonable', false, format('Size changed from %s to %s', v_initial_size, v_final_size));
    END IF;
EXCEPTION WHEN OTHERS THEN
    PERFORM record_phase3_test('memory_usage_reasonable', false, SQLERRM);
END;
$$;

-- ============================================================================
-- CONCURRENT ACCESS TESTS
-- ============================================================================

-- Test 9: Concurrent allocations (basic test - limited by single connection)
DO $$
DECLARE
    v_pk1 BIGINT;
    v_pk2 BIGINT;
BEGIN
    -- Simulate concurrent access by doing multiple allocations quickly
    v_pk1 := trinity.allocate_pk('concurrent_test', '550e8400-e29b-41d4-a716-446655440004'::UUID, '550e8400-e29b-41d4-a716-446655440000'::UUID);
    v_pk2 := trinity.allocate_pk('concurrent_test', '550e8400-e29b-41d4-a716-446655440005'::UUID, '550e8400-e29b-41d4-a716-446655440000'::UUID);

    -- Both should succeed and get different PKs
    IF v_pk1 != v_pk2 AND v_pk1 IS NOT NULL AND v_pk2 IS NOT NULL THEN
        PERFORM record_phase3_test('concurrent_allocations', true);
    ELSE
        PERFORM record_phase3_test('concurrent_allocations', false, format('PKs: %s, %s', v_pk1, v_pk2));
    END IF;
EXCEPTION WHEN OTHERS THEN
    PERFORM record_phase3_test('concurrent_allocations', false, SQLERRM);
END;
$$;

-- ============================================================================
-- TENANT ISOLATION TESTS
-- ============================================================================

-- Test 10: Strict tenant isolation
DO $$
DECLARE
    v_tenant2 UUID := '650e8400-e29b-41d4-a716-446655440000'::UUID;
    v_pk1 BIGINT;
    v_pk2 BIGINT;
BEGIN
    -- Allocate same UUID in different tenants
    v_pk1 := trinity.allocate_pk('isolation_test', '550e8400-e29b-41d4-a716-446655440006'::UUID, '550e8400-e29b-41d4-a716-446655440000'::UUID);
    v_pk2 := trinity.allocate_pk('isolation_test', '550e8400-e29b-41d4-a716-446655440006'::UUID, v_tenant2);

    -- Should get different PKs (tenant isolation)
    IF v_pk1 != v_pk2 THEN
        PERFORM record_phase3_test('tenant_isolation', true);
    ELSE
        PERFORM record_phase3_test('tenant_isolation', false, format('Same PK %s for different tenants', v_pk1));
    END IF;
EXCEPTION WHEN OTHERS THEN
    PERFORM record_phase3_test('tenant_isolation', false, SQLERRM);
END;
$$;

-- ============================================================================
-- PRODUCTION READINESS CHECKS
-- ============================================================================

-- Test 11: Extension metadata integrity
DO $$
DECLARE
    v_ext RECORD;
BEGIN
    SELECT * INTO v_ext FROM pg_extension WHERE extname = 'trinity';

    IF v_ext.extname = 'trinity' AND v_ext.extversion = '1.0' THEN
        PERFORM record_phase3_test('extension_metadata', true);
    ELSE
        PERFORM record_phase3_test('extension_metadata', false, format('Extension: %s, Version: %s', v_ext.extname, v_ext.extversion));
    END IF;
EXCEPTION WHEN OTHERS THEN
    PERFORM record_phase3_test('extension_metadata', false, SQLERRM);
END;
$$;

-- Test 12: Function availability check
DO $$
DECLARE
    v_function_count INT;
BEGIN
    SELECT COUNT(*) INTO v_function_count
    FROM pg_proc p
    JOIN pg_namespace n ON p.pronamespace = n.oid
    WHERE n.nspname = 'trinity'
      AND p.proname IN ('allocate_pk', 'generate_identifier', 'resolve_fk', 'transform_csv', 'get_uuid_to_pk_mappings');

    IF v_function_count = 5 THEN
        PERFORM record_phase3_test('core_functions_available', true);
    ELSE
        PERFORM record_phase3_test('core_functions_available', false, format('Expected 5 functions, found %s', v_function_count));
    END IF;
EXCEPTION WHEN OTHERS THEN
    PERFORM record_phase3_test('core_functions_available', false, SQLERRM);
END;
$$;

-- ============================================================================
-- PHASE 3 TEST RESULTS
-- ============================================================================

SELECT
    COUNT(*) as total_tests,
    COUNT(*) FILTER (WHERE passed) as passed,
    COUNT(*) FILTER (WHERE NOT passed) as failed,
    ROUND(COUNT(*) FILTER (WHERE passed)::numeric / COUNT(*)::numeric * 100, 1) as success_rate,
    AVG(execution_time) as avg_execution_time
FROM phase3_test_results;

-- Show failed tests with details
SELECT test_name, error_message, execution_time
FROM phase3_test_results
WHERE NOT passed
ORDER BY test_name;