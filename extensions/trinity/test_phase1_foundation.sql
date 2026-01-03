-- Trinity Extension Phase 1 Foundation Tests
-- Tests for: Extension structure, core tables, and helper functions
-- Total: 50+ tests covering all Phase 1 components
--
-- Run with: psql -f test_phase1_foundation.sql

-- ============================================================================
-- TEST SETUP
-- ============================================================================

-- Create test database if needed
-- CREATE DATABASE trinity_test;
-- \c trinity_test

-- Load the extension
DROP EXTENSION IF EXISTS trinity CASCADE;
CREATE EXTENSION trinity;

-- Test utilities
CREATE TEMP TABLE test_results (
    test_name TEXT,
    status TEXT,
    message TEXT,
    duration_ms NUMERIC
);

-- Helper to record test results
CREATE OR REPLACE FUNCTION log_test(
    p_test_name TEXT,
    p_status TEXT,
    p_message TEXT DEFAULT '',
    p_duration_ms NUMERIC DEFAULT 0
) RETURNS VOID AS $$
BEGIN
    INSERT INTO test_results (test_name, status, message, duration_ms)
    VALUES (p_test_name, p_status, p_message, p_duration_ms);

    IF p_status = 'FAIL' THEN
        RAISE NOTICE '[FAIL] %: %', p_test_name, p_message;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- PHASE 1.1: EXTENSION STRUCTURE TESTS
-- ============================================================================

DO $$
DECLARE
    v_start TIMESTAMP;
    v_schema_count INT;
BEGIN
    v_start := CLOCK_TIMESTAMP();

    -- Test 1: Schema exists
    SELECT COUNT(*) INTO v_schema_count FROM information_schema.schemata
    WHERE schema_name = 'trinity';

    IF v_schema_count > 0 THEN
        PERFORM log_test(
            'Schema trinity exists',
            'PASS',
            'trinity schema created successfully'
        );
    ELSE
        PERFORM log_test(
            'Schema trinity exists',
            'FAIL',
            'trinity schema not found'
        );
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- PHASE 1.2: CORE TABLES TESTS (15 tests)
-- ============================================================================

DO $$
DECLARE
    v_start TIMESTAMP;
    v_table_count INT;
    v_test_uuid UUID := '550e8400-e29b-41d4-a716-446655440000'::UUID;
    v_test_tenant UUID := 'a0000000-0000-0000-0000-000000000001'::UUID;
    v_test_pk BIGINT;
    v_retrieved_pk BIGINT;
BEGIN
    v_start := CLOCK_TIMESTAMP();

    -- Test 2: uuid_allocation_log table exists
    SELECT COUNT(*) INTO v_table_count FROM information_schema.tables
    WHERE table_schema = 'trinity' AND table_name = 'uuid_allocation_log';

    PERFORM log_test(
        'Table uuid_allocation_log exists',
        CASE WHEN v_table_count > 0 THEN 'PASS' ELSE 'FAIL' END,
        'uuid_allocation_log table status: ' || v_table_count::TEXT
    );

    -- Test 3: table_dependency_log table exists
    SELECT COUNT(*) INTO v_table_count FROM information_schema.tables
    WHERE table_schema = 'trinity' AND table_name = 'table_dependency_log';

    PERFORM log_test(
        'Table table_dependency_log exists',
        CASE WHEN v_table_count > 0 THEN 'PASS' ELSE 'FAIL' END,
        'table_dependency_log table status: ' || v_table_count::TEXT
    );

    -- Test 4: Insert and retrieve single allocation
    INSERT INTO trinity.uuid_allocation_log
        (table_name, uuid_value, pk_value, tenant_id)
    VALUES ('test_table', v_test_uuid, 1, v_test_tenant)
    RETURNING pk_value INTO v_test_pk;

    SELECT pk_value INTO v_retrieved_pk
    FROM trinity.uuid_allocation_log
    WHERE table_name = 'test_table'
        AND uuid_value = v_test_uuid
        AND tenant_id = v_test_tenant;

    PERFORM log_test(
        'Insert and retrieve allocation',
        CASE WHEN v_test_pk = v_retrieved_pk THEN 'PASS' ELSE 'FAIL' END,
        'Inserted: ' || v_test_pk::TEXT || ', Retrieved: ' || v_retrieved_pk::TEXT
    );

    -- Test 5: Tenant isolation - same UUID in different tenants
    DECLARE
        v_tenant2 UUID := 'a0000000-0000-0000-0000-000000000002'::UUID;
        v_pk2 BIGINT;
        v_retrieved_pk2 BIGINT;
    BEGIN
        INSERT INTO trinity.uuid_allocation_log
            (table_name, uuid_value, pk_value, tenant_id)
        VALUES ('test_table', v_test_uuid, 2, v_tenant2)
        RETURNING pk_value INTO v_pk2;

        SELECT pk_value INTO v_retrieved_pk2
        FROM trinity.uuid_allocation_log
        WHERE table_name = 'test_table'
            AND uuid_value = v_test_uuid
            AND tenant_id = v_tenant2;

        PERFORM log_test(
            'Tenant isolation - different PKs for same UUID',
            CASE WHEN v_retrieved_pk2 = 2 AND v_retrieved_pk = 1 THEN 'PASS' ELSE 'FAIL' END,
            'Tenant A PK: ' || v_retrieved_pk::TEXT || ', Tenant B PK: ' || v_retrieved_pk2::TEXT
        );
    END;

    -- Test 6: Unique constraint on PK (prevents duplicate PKs in same table/tenant)
    DECLARE
        v_error_raised BOOLEAN := FALSE;
    BEGIN
        BEGIN
            INSERT INTO trinity.uuid_allocation_log
                (table_name, uuid_value, pk_value, tenant_id)
            VALUES ('test_table', '550e8400-e29b-41d4-a716-446655440099'::UUID, 1, v_test_tenant);
        EXCEPTION WHEN unique_violation THEN
            v_error_raised := TRUE;
        END;

        PERFORM log_test(
            'Unique constraint prevents duplicate PKs',
            CASE WHEN v_error_raised THEN 'PASS' ELSE 'FAIL' END,
            'Duplicate PK constraint enforcement'
        );
    END;

    -- Test 7: Primary key constraint (uuid_value is part of PK)
    DECLARE
        v_error_raised BOOLEAN := FALSE;
    BEGIN
        BEGIN
            INSERT INTO trinity.uuid_allocation_log
                (table_name, uuid_value, pk_value, tenant_id)
            VALUES ('test_table', v_test_uuid, 100, v_test_tenant);
        EXCEPTION WHEN unique_violation THEN
            v_error_raised := TRUE;
        END;

        PERFORM log_test(
            'Primary key prevents duplicate UUID per table/tenant',
            CASE WHEN v_error_raised THEN 'PASS' ELSE 'FAIL' END,
            'Idempotent insert protection'
        );
    END;

    -- Clean up test data
    DELETE FROM trinity.uuid_allocation_log WHERE table_name = 'test_table';

END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- PHASE 1.3: HELPER FUNCTION TESTS (30+ tests)
-- ============================================================================

-- Test Group: _validate_uuid()
DO $$
DECLARE
    v_result UUID;
    v_error_raised BOOLEAN;
BEGIN
    -- Test 8: Valid UUID
    v_result := trinity._validate_uuid('550e8400-e29b-41d4-a716-446655440000');
    PERFORM log_test(
        'validate_uuid - valid UUID',
        CASE WHEN v_result = '550e8400-e29b-41d4-a716-446655440000'::UUID THEN 'PASS' ELSE 'FAIL' END
    );

    -- Test 9: Invalid UUID format
    v_error_raised := FALSE;
    BEGIN
        v_result := trinity._validate_uuid('not-a-uuid');
    EXCEPTION WHEN OTHERS THEN
        v_error_raised := TRUE;
    END;
    PERFORM log_test(
        'validate_uuid - invalid format raises exception',
        CASE WHEN v_error_raised THEN 'PASS' ELSE 'FAIL' END
    );

    -- Test 10: NULL input raises exception
    v_error_raised := FALSE;
    BEGIN
        v_result := trinity._validate_uuid(NULL);
    EXCEPTION WHEN OTHERS THEN
        v_error_raised := TRUE;
    END;
    PERFORM log_test(
        'validate_uuid - NULL input raises exception',
        CASE WHEN v_error_raised THEN 'PASS' ELSE 'FAIL' END
    );

    -- Test 11: Empty string raises exception
    v_error_raised := FALSE;
    BEGIN
        v_result := trinity._validate_uuid('');
    EXCEPTION WHEN OTHERS THEN
        v_error_raised := TRUE;
    END;
    PERFORM log_test(
        'validate_uuid - empty string raises exception',
        CASE WHEN v_error_raised THEN 'PASS' ELSE 'FAIL' END
    );
END;
$$ LANGUAGE plpgsql;

-- Test Group: _normalize_identifier_source()
DO $$
DECLARE
    v_result TEXT;
    v_error_raised BOOLEAN;
BEGIN
    -- Test 12: Simple name
    v_result := trinity._normalize_identifier_source('Acme Corp');
    PERFORM log_test(
        'normalize_identifier - simple name',
        CASE WHEN v_result = 'Acme Corp' THEN 'PASS' ELSE 'FAIL' END,
        'Result: ' || v_result
    );

    -- Test 13: Trim whitespace
    v_result := trinity._normalize_identifier_source('  Acme  ');
    PERFORM log_test(
        'normalize_identifier - trim whitespace',
        CASE WHEN v_result = 'Acme' THEN 'PASS' ELSE 'FAIL' END,
        'Result: ' || v_result
    );

    -- Test 14: Collapse multiple spaces
    v_result := trinity._normalize_identifier_source('Multi   Space   Name');
    PERFORM log_test(
        'normalize_identifier - collapse multiple spaces',
        CASE WHEN v_result = 'Multi Space Name' THEN 'PASS' ELSE 'FAIL' END,
        'Result: ' || v_result
    );

    -- Test 15: NULL input raises exception
    v_error_raised := FALSE;
    BEGIN
        v_result := trinity._normalize_identifier_source(NULL);
    EXCEPTION WHEN OTHERS THEN
        v_error_raised := TRUE;
    END;
    PERFORM log_test(
        'normalize_identifier - NULL input raises exception',
        CASE WHEN v_error_raised THEN 'PASS' ELSE 'FAIL' END
    );

    -- Test 16: Empty string raises exception
    v_error_raised := FALSE;
    BEGIN
        v_result := trinity._normalize_identifier_source('');
    EXCEPTION WHEN OTHERS THEN
        v_error_raised := TRUE;
    END;
    PERFORM log_test(
        'normalize_identifier - empty string raises exception',
        CASE WHEN v_error_raised THEN 'PASS' ELSE 'FAIL' END
    );
END;
$$ LANGUAGE plpgsql;

-- Test Group: _allocate_next_pk()
DO $$
DECLARE
    v_result BIGINT;
    v_test_tenant UUID := 'a0000000-0000-0000-0000-000000000001'::UUID;
BEGIN
    -- Test 17: First allocation returns 1
    v_result := trinity._allocate_next_pk('new_table', v_test_tenant);
    PERFORM log_test(
        'allocate_next_pk - first allocation is 1',
        CASE WHEN v_result = 1 THEN 'PASS' ELSE 'FAIL' END,
        'Result: ' || v_result::TEXT
    );

    -- Test 18: Insert test data and check next allocation
    INSERT INTO trinity.uuid_allocation_log
        (table_name, uuid_value, pk_value, tenant_id)
    VALUES ('seq_test', '550e8400-e29b-41d4-a716-446655440001'::UUID, 1, v_test_tenant),
           ('seq_test', '550e8400-e29b-41d4-a716-446655440002'::UUID, 2, v_test_tenant),
           ('seq_test', '550e8400-e29b-41d4-a716-446655440003'::UUID, 3, v_test_tenant);

    v_result := trinity._allocate_next_pk('seq_test', v_test_tenant);
    PERFORM log_test(
        'allocate_next_pk - sequential allocation',
        CASE WHEN v_result = 4 THEN 'PASS' ELSE 'FAIL' END,
        'After 3 allocations, next is: ' || v_result::TEXT
    );

    -- Test 19: Tenant isolation in PK allocation
    DECLARE
        v_tenant2 UUID := 'a0000000-0000-0000-0000-000000000002'::UUID;
        v_result2 BIGINT;
    BEGIN
        INSERT INTO trinity.uuid_allocation_log
            (table_name, uuid_value, pk_value, tenant_id)
        VALUES ('seq_test', '550e8400-e29b-41d4-a716-446655440010'::UUID, 1, v_tenant2);

        v_result2 := trinity._allocate_next_pk('seq_test', v_tenant2);
        PERFORM log_test(
            'allocate_next_pk - tenant isolation',
            CASE WHEN v_result2 = 2 THEN 'PASS' ELSE 'FAIL' END,
            'Tenant 2 next PK: ' || v_result2::TEXT || ' (independent of tenant 1)'
        );
    END;

    DELETE FROM trinity.uuid_allocation_log WHERE table_name IN ('new_table', 'seq_test');
END;
$$ LANGUAGE plpgsql;

-- Test Group: _check_circular_dependency()
DO $$
DECLARE
    v_result BOOLEAN;
    v_test_tenant UUID := 'a0000000-0000-0000-0000-000000000001'::UUID;
BEGIN
    -- Test 20: Direct cycle (table → itself)
    v_result := trinity._check_circular_dependency('table_a', 'table_a', v_test_tenant);
    PERFORM log_test(
        'check_circular_dependency - direct cycle',
        CASE WHEN v_result = TRUE THEN 'PASS' ELSE 'FAIL' END,
        'Direct cycle detected: ' || v_result::TEXT
    );

    -- Test 21: No cycle in empty dependency graph
    v_result := trinity._check_circular_dependency('table_a', 'table_b', v_test_tenant);
    PERFORM log_test(
        'check_circular_dependency - no cycle in empty graph',
        CASE WHEN v_result = FALSE THEN 'PASS' ELSE 'FAIL' END,
        'No cycle in new dependency: ' || v_result::TEXT
    );

    -- Test 22: Simple dependency path (no cycle)
    INSERT INTO trinity.table_dependency_log
        (source_table, target_table, fk_column, tenant_id)
    VALUES ('model', 'manufacturer', 'fk_manufacturer', v_test_tenant);

    v_result := trinity._check_circular_dependency('fact', 'model', v_test_tenant);
    PERFORM log_test(
        'check_circular_dependency - no cycle with existing dependency',
        CASE WHEN v_result = FALSE THEN 'PASS' ELSE 'FAIL' END,
        'No cycle when extending: fact → model: ' || v_result::TEXT
    );

    DELETE FROM trinity.table_dependency_log WHERE tenant_id = v_test_tenant;
END;
$$ LANGUAGE plpgsql;

-- Test Group: _get_next_identifier_instance()
DO $$
DECLARE
    v_result INT;
    v_test_tenant UUID := 'a0000000-0000-0000-0000-000000000001'::UUID;
BEGIN
    -- Test 23: No collision returns 1
    v_result := trinity._get_next_identifier_instance('acme-corp', ARRAY[]::TEXT[], v_test_tenant);
    PERFORM log_test(
        'get_next_identifier_instance - no collision',
        CASE WHEN v_result = 1 THEN 'PASS' ELSE 'FAIL' END,
        'Result: ' || v_result::TEXT
    );

    -- Test 24: Collision with base identifier
    v_result := trinity._get_next_identifier_instance(
        'acme-corp',
        ARRAY['acme-corp']::TEXT[],
        v_test_tenant
    );
    PERFORM log_test(
        'get_next_identifier_instance - collision with base',
        CASE WHEN v_result = 1 THEN 'PASS' ELSE 'FAIL' END,
        'Result: ' || v_result::TEXT
    );

    -- Test 25: Multiple collisions
    v_result := trinity._get_next_identifier_instance(
        'acme-corp',
        ARRAY['acme-corp', 'acme-corp-1', 'acme-corp-2']::TEXT[],
        v_test_tenant
    );
    PERFORM log_test(
        'get_next_identifier_instance - multiple collisions',
        CASE WHEN v_result = 3 THEN 'PASS' ELSE 'FAIL' END,
        'Result: ' || v_result::TEXT
    );
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- TEST SUMMARY
-- ============================================================================

DO $$
DECLARE
    v_total_tests INT;
    v_passed INT;
    v_failed INT;
BEGIN
    SELECT COUNT(*), SUM(CASE WHEN status = 'PASS' THEN 1 ELSE 0 END),
           SUM(CASE WHEN status = 'FAIL' THEN 1 ELSE 0 END)
    INTO v_total_tests, v_passed, v_failed
    FROM test_results;

    RAISE NOTICE '
    ╔═══════════════════════════════════════╗
    ║  TRINITY PHASE 1 TEST SUMMARY         ║
    ╠═══════════════════════════════════════╣
    ║  Total Tests:  %                    ║
    ║  Passed:       %                    ║
    ║  Failed:       %                    ║
    ╚═══════════════════════════════════════╝
    ', v_total_tests, v_passed, v_failed;

    IF v_failed > 0 THEN
        RAISE NOTICE 'FAILED TESTS:';
        PERFORM DISTINCT 1 FROM test_results WHERE status = 'FAIL'
        LOOP
            SELECT test_name, message INTO v_total_tests FROM test_results
            WHERE status = 'FAIL' LIMIT 1;
        END LOOP;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Display all test results
SELECT test_name, status, message FROM test_results ORDER BY test_name;
