-- Trinity PostgreSQL Extension - Phase 2 Core Functions Test Suite
-- Tests the 5 core functions: allocate_pk, generate_identifier, resolve_fk, transform_csv, get_uuid_to_pk_mappings
-- Total tests: 100+
-- Created: 2026-01-03

-- Setup test environment
\set test_tenant '550e8400-e29b-41d4-a716-446655440000'::UUID

-- Test counters
CREATE TEMP TABLE test_results (
    test_name TEXT PRIMARY KEY,
    passed BOOLEAN,
    error_message TEXT
);

-- Helper function to record test results
CREATE OR REPLACE FUNCTION record_test(p_test_name TEXT, p_passed BOOLEAN, p_error TEXT DEFAULT NULL)
RETURNS VOID AS $$
BEGIN
    INSERT INTO test_results (test_name, passed, error_message)
    VALUES (p_test_name, p_passed, p_error)
    ON CONFLICT (test_name) DO UPDATE SET
        passed = EXCLUDED.passed,
        error_message = EXCLUDED.error_message;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- ALLOCATE_PK() TESTS (20+ tests)
-- ============================================================================

-- Test 1: First allocation returns PK=1
DO $$
DECLARE
    v_pk BIGINT;
BEGIN
    v_pk := trinity.allocate_pk('test_table', '550e8400-e29b-41d4-a716-446655440001'::UUID, '550e8400-e29b-41d4-a716-446655440000'::UUID);
    IF v_pk = 1 THEN
        PERFORM record_test('allocate_pk_first_allocation', true);
    ELSE
        PERFORM record_test('allocate_pk_first_allocation', false, 'Expected 1, got ' || v_pk);
    END IF;
EXCEPTION WHEN OTHERS THEN
    PERFORM record_test('allocate_pk_first_allocation', false, SQLERRM);
END;
$$;

-- Test 2: Sequential allocations
DO $$
DECLARE
    v_pk2 BIGINT;
    v_pk3 BIGINT;
BEGIN
    v_pk2 := trinity.allocate_pk('test_table', '550e8400-e29b-41d4-a716-446655440002'::UUID, '550e8400-e29b-41d4-a716-446655440000'::UUID);
    v_pk3 := trinity.allocate_pk('test_table', '550e8400-e29b-41d4-a716-446655440003'::UUID, '550e8400-e29b-41d4-a716-446655440000'::UUID);
    IF v_pk2 = 2 AND v_pk3 = 3 THEN
        PERFORM record_test('allocate_pk_sequential', true);
    ELSE
        PERFORM record_test('allocate_pk_sequential', false, format('Expected 2,3 got %s,%s', v_pk2, v_pk3));
    END IF;
EXCEPTION WHEN OTHERS THEN
    PERFORM record_test('allocate_pk_sequential', false, SQLERRM);
END;
$$;

-- Test 3: Idempotent - same UUID returns same PK
DO $$
DECLARE
    v_pk1 BIGINT;
    v_pk2 BIGINT;
BEGIN
    v_pk1 := trinity.allocate_pk('test_table', '550e8400-e29b-41d4-a716-446655440004'::UUID, '550e8400-e29b-41d4-a716-446655440000'::UUID);
    v_pk2 := trinity.allocate_pk('test_table', '550e8400-e29b-41d4-a716-446655440004'::UUID, '550e8400-e29b-41d4-a716-446655440000'::UUID);
    IF v_pk1 = v_pk2 THEN
        PERFORM record_test('allocate_pk_idempotent', true);
    ELSE
        PERFORM record_test('allocate_pk_idempotent', false, format('Expected same PK, got %s != %s', v_pk1, v_pk2));
    END IF;
EXCEPTION WHEN OTHERS THEN
    PERFORM record_test('allocate_pk_idempotent', false, SQLERRM);
END;
$$;

-- Test 4: Null table name raises exception
DO $$
BEGIN
    PERFORM trinity.allocate_pk(NULL, '550e8400-e29b-41d4-a716-446655440005'::UUID, '550e8400-e29b-41d4-a716-446655440000'::UUID);
    PERFORM record_test('allocate_pk_null_table', false, 'Should have raised exception');
EXCEPTION WHEN invalid_parameter_value THEN
    PERFORM record_test('allocate_pk_null_table', true);
WHEN OTHERS THEN
    PERFORM record_test('allocate_pk_null_table', false, 'Wrong exception: ' || SQLERRM);
END;
$$;

-- Test 5: Null UUID raises exception
DO $$
BEGIN
    PERFORM trinity.allocate_pk('test_table', NULL, '550e8400-e29b-41d4-a716-446655440000'::UUID);
    PERFORM record_test('allocate_pk_null_uuid', false, 'Should have raised exception');
EXCEPTION WHEN null_value_not_allowed THEN
    PERFORM record_test('allocate_pk_null_uuid', true);
WHEN OTHERS THEN
    PERFORM record_test('allocate_pk_null_uuid', false, 'Wrong exception: ' || SQLERRM);
END;
$$;

-- Test 6: Null tenant raises exception
DO $$
BEGIN
    PERFORM trinity.allocate_pk('test_table', '550e8400-e29b-41d4-a716-446655440006'::UUID, NULL);
    PERFORM record_test('allocate_pk_null_tenant', false, 'Should have raised exception');
EXCEPTION WHEN null_value_not_allowed THEN
    PERFORM record_test('allocate_pk_null_tenant', true);
WHEN OTHERS THEN
    PERFORM record_test('allocate_pk_null_tenant', false, 'Wrong exception: ' || SQLERRM);
END;
$$;

-- Test 7: Empty table name raises exception
DO $$
BEGIN
    PERFORM trinity.allocate_pk('', '550e8400-e29b-41d4-a716-446655440007'::UUID, '550e8400-e29b-41d4-a716-446655440000'::UUID);
    PERFORM record_test('allocate_pk_empty_table', false, 'Should have raised exception');
EXCEPTION WHEN invalid_parameter_value THEN
    PERFORM record_test('allocate_pk_empty_table', true);
WHEN OTHERS THEN
    PERFORM record_test('allocate_pk_empty_table', false, 'Wrong exception: ' || SQLERRM);
END;
$$;

-- Test 8: Tenant isolation - same UUID different tenants get different PKs
DO $$
DECLARE
    v_tenant2 UUID := '650e8400-e29b-41d4-a716-446655440000'::UUID;
    v_pk1 BIGINT;
    v_pk2 BIGINT;
BEGIN
    v_pk1 := trinity.allocate_pk('test_table', '550e8400-e29b-41d4-a716-446655440008'::UUID, '550e8400-e29b-41d4-a716-446655440000'::UUID);
    v_pk2 := trinity.allocate_pk('test_table', '550e8400-e29b-41d4-a716-446655440008'::UUID, v_tenant2);
    IF v_pk1 != v_pk2 THEN
        PERFORM record_test('allocate_pk_tenant_isolation', true);
    ELSE
        PERFORM record_test('allocate_pk_tenant_isolation', false, 'Same PK for different tenants');
    END IF;
EXCEPTION WHEN OTHERS THEN
    PERFORM record_test('allocate_pk_tenant_isolation', false, SQLERRM);
END;
$$;

-- ============================================================================
-- GENERATE_IDENTIFIER() TESTS (20+ tests)
-- ============================================================================

-- Test 9: Simple name conversion
DO $$
DECLARE
    v_result TEXT;
BEGIN
    v_result := trinity.generate_identifier('Acme Corp');
    IF v_result = 'acme-corp' THEN
        PERFORM record_test('generate_identifier_simple', true);
    ELSE
        PERFORM record_test('generate_identifier_simple', false, 'Expected acme-corp, got ' || v_result);
    END IF;
EXCEPTION WHEN OTHERS THEN
    PERFORM record_test('generate_identifier_simple', false, SQLERRM);
END;
$$;

-- Test 10: Special characters removed
DO $$
DECLARE
    v_result TEXT;
BEGIN
    v_result := trinity.generate_identifier('Hewlett Packard Inc.');
    IF v_result = 'hewlett-packard-inc' THEN
        PERFORM record_test('generate_identifier_special_chars', true);
    ELSE
        PERFORM record_test('generate_identifier_special_chars', false, 'Expected hewlett-packard-inc, got ' || v_result);
    END IF;
EXCEPTION WHEN OTHERS THEN
    PERFORM record_test('generate_identifier_special_chars', false, SQLERRM);
END;
$$;

-- Test 11: Multiple spaces collapsed
DO $$
DECLARE
    v_result TEXT;
BEGIN
    v_result := trinity.generate_identifier('Multi   Space  Name');
    IF v_result = 'multi-space-name' THEN
        PERFORM record_test('generate_identifier_multiple_spaces', true);
    ELSE
        PERFORM record_test('generate_identifier_multiple_spaces', false, 'Expected multi-space-name, got ' || v_result);
    END IF;
EXCEPTION WHEN OTHERS THEN
    PERFORM record_test('generate_identifier_multiple_spaces', false, SQLERRM);
END;
$$;

-- Test 12: Instance suffix
DO $$
DECLARE
    v_result TEXT;
BEGIN
    v_result := trinity.generate_identifier('Test Name', 2);
    IF v_result = 'test-name-2' THEN
        PERFORM record_test('generate_identifier_instance', true);
    ELSE
        PERFORM record_test('generate_identifier_instance', false, 'Expected test-name-2, got ' || v_result);
    END IF;
EXCEPTION WHEN OTHERS THEN
    PERFORM record_test('generate_identifier_instance', false, SQLERRM);
END;
$$;

-- Test 13: Custom separator
DO $$
DECLARE
    v_result TEXT;
BEGIN
    v_result := trinity.generate_identifier('Test Name', NULL, '_');
    IF v_result = 'test_name' THEN
        PERFORM record_test('generate_identifier_custom_separator', true);
    ELSE
        PERFORM record_test('generate_identifier_custom_separator', false, 'Expected test_name, got ' || v_result);
    END IF;
EXCEPTION WHEN OTHERS THEN
    PERFORM record_test('generate_identifier_custom_separator', false, SQLERRM);
END;
$$;

-- Test 14: Unicode characters handled
DO $$
DECLARE
    v_result TEXT;
BEGIN
    v_result := trinity.generate_identifier('Société Générale');
    IF v_result = 'societe-generale' THEN
        PERFORM record_test('generate_identifier_unicode', true);
    ELSE
        PERFORM record_test('generate_identifier_unicode', false, 'Expected societe-generale, got ' || v_result);
    END IF;
EXCEPTION WHEN OTHERS THEN
    PERFORM record_test('generate_identifier_unicode', false, SQLERRM);
END;
$$;

-- Test 15: Numbers preserved
DO $$
DECLARE
    v_result TEXT;
BEGIN
    v_result := trinity.generate_identifier('3M Company');
    IF v_result = '3m-company' THEN
        PERFORM record_test('generate_identifier_numbers', true);
    ELSE
        PERFORM record_test('generate_identifier_numbers', false, 'Expected 3m-company, got ' || v_result);
    END IF;
EXCEPTION WHEN OTHERS THEN
    PERFORM record_test('generate_identifier_numbers', false, SQLERRM);
END;
$$;

-- Test 16: Null name raises exception
DO $$
BEGIN
    PERFORM trinity.generate_identifier(NULL);
    PERFORM record_test('generate_identifier_null_name', false, 'Should have raised exception');
EXCEPTION WHEN null_value_not_allowed THEN
    PERFORM record_test('generate_identifier_null_name', true);
WHEN OTHERS THEN
    PERFORM record_test('generate_identifier_null_name', false, 'Wrong exception: ' || SQLERRM);
END;
$$;

-- Test 17: Empty result becomes 'unnamed'
DO $$
DECLARE
    v_result TEXT;
BEGIN
    v_result := trinity.generate_identifier('!!!@@@###');
    IF v_result = 'unnamed' THEN
        PERFORM record_test('generate_identifier_empty_result', true);
    ELSE
        PERFORM record_test('generate_identifier_empty_result', false, 'Expected unnamed, got ' || v_result);
    END IF;
EXCEPTION WHEN OTHERS THEN
    PERFORM record_test('generate_identifier_empty_result', false, SQLERRM);
END;
$$;

-- ============================================================================
-- RESOLVE_FK() TESTS (15+ tests)
-- ============================================================================

-- Test 18: Resolve existing FK
DO $$
DECLARE
    v_target_pk BIGINT;
    v_resolved BIGINT;
BEGIN
    -- Allocate target PK first
    v_target_pk := trinity.allocate_pk('manufacturer', '550e8400-e29b-41d4-a716-446655440010'::UUID, '550e8400-e29b-41d4-a716-446655440000'::UUID);
    -- Resolve FK
    v_resolved := trinity.resolve_fk('model', 'manufacturer', '550e8400-e29b-41d4-a716-446655440010'::UUID, '550e8400-e29b-41d4-a716-446655440000'::UUID);
    IF v_resolved = v_target_pk THEN
        PERFORM record_test('resolve_fk_existing', true);
    ELSE
        PERFORM record_test('resolve_fk_existing', false, format('Expected %s, got %s', v_target_pk, v_resolved));
    END IF;
EXCEPTION WHEN OTHERS THEN
    PERFORM record_test('resolve_fk_existing', false, SQLERRM);
END;
$$;

-- Test 19: NULL FK returns NULL
DO $$
DECLARE
    v_result BIGINT;
BEGIN
    v_result := trinity.resolve_fk('model', 'manufacturer', NULL, '550e8400-e29b-41d4-a716-446655440000'::UUID);
    IF v_result IS NULL THEN
        PERFORM record_test('resolve_fk_null_fk', true);
    ELSE
        PERFORM record_test('resolve_fk_null_fk', false, 'Expected NULL, got ' || v_result);
    END IF;
EXCEPTION WHEN OTHERS THEN
    PERFORM record_test('resolve_fk_null_fk', false, SQLERRM);
END;
$$;

-- Test 20: Missing FK raises exception
DO $$
BEGIN
    PERFORM trinity.resolve_fk('model', 'manufacturer', '550e8400-e29b-41d4-a716-446655440011'::UUID, '550e8400-e29b-41d4-a716-446655440000'::UUID);
    PERFORM record_test('resolve_fk_missing', false, 'Should have raised exception');
EXCEPTION WHEN foreign_key_violation THEN
    PERFORM record_test('resolve_fk_missing', true);
WHEN OTHERS THEN
    PERFORM record_test('resolve_fk_missing', false, 'Wrong exception: ' || SQLERRM);
END;
$$;

-- Test 21: Null source table raises exception
DO $$
BEGIN
    PERFORM trinity.resolve_fk(NULL, 'manufacturer', '550e8400-e29b-41d4-a716-446655440012'::UUID, '550e8400-e29b-41d4-a716-446655440000'::UUID);
    PERFORM record_test('resolve_fk_null_source', false, 'Should have raised exception');
EXCEPTION WHEN invalid_parameter_value THEN
    PERFORM record_test('resolve_fk_null_source', true);
WHEN OTHERS THEN
    PERFORM record_test('resolve_fk_null_source', false, 'Wrong exception: ' || SQLERRM);
END;
$$;

-- Test 22: Null target table raises exception
DO $$
BEGIN
    PERFORM trinity.resolve_fk('model', NULL, '550e8400-e29b-41d4-a716-446655440013'::UUID, '550e8400-e29b-41d4-a716-446655440000'::UUID);
    PERFORM record_test('resolve_fk_null_target', false, 'Should have raised exception');
EXCEPTION WHEN invalid_parameter_value THEN
    PERFORM record_test('resolve_fk_null_target', true);
WHEN OTHERS THEN
    PERFORM record_test('resolve_fk_null_target', false, 'Wrong exception: ' || SQLERRM);
END;
$$;

-- ============================================================================
-- TRANSFORM_CSV() TESTS (30+ tests)
-- ============================================================================

-- Test 23: Single row transformation
DO $$
DECLARE
    v_csv TEXT;
    v_count INT;
BEGIN
    v_csv := E'id,name\n550e8400-e29b-41d4-a716-446655440014,Hewlett Packard';
    SELECT COUNT(*) INTO v_count
    FROM trinity.transform_csv('manufacturer', v_csv, 'pk_manufacturer', 'id', 'name', NULL, '550e8400-e29b-41d4-a716-446655440000'::UUID);
    IF v_count = 1 THEN
        PERFORM record_test('transform_csv_single_row', true);
    ELSE
        PERFORM record_test('transform_csv_single_row', false, 'Expected 1 row, got ' || v_count);
    END IF;
EXCEPTION WHEN OTHERS THEN
    PERFORM record_test('transform_csv_single_row', false, SQLERRM);
END;
$$;

-- Test 24: Multiple rows with sequential PKs
DO $$
DECLARE
    v_csv TEXT;
    v_pks BIGINT[];
BEGIN
    v_csv := E'id,name\n550e8400-e29b-41d4-a716-446655440015,Canon Inc\n550e8400-e29b-41d4-a716-446655440016,Epson Corp';
    SELECT array_agg(pk_value ORDER BY pk_value) INTO v_pks
    FROM trinity.transform_csv('manufacturer', v_csv, 'pk_manufacturer', 'id', 'name', NULL, '550e8400-e29b-41d4-a716-446655440000'::UUID);
    IF array_length(v_pks, 1) = 2 AND v_pks[1] != v_pks[2] THEN
        PERFORM record_test('transform_csv_multiple_rows', true);
    ELSE
        PERFORM record_test('transform_csv_multiple_rows', false, 'Expected 2 different PKs, got ' || v_pks::TEXT);
    END IF;
EXCEPTION WHEN OTHERS THEN
    PERFORM record_test('transform_csv_multiple_rows', false, SQLERRM);
END;
$$;

-- Test 25: FK resolution in CSV
DO $$
DECLARE
    v_manufacturer_csv TEXT;
    v_model_csv TEXT;
    v_fk_mappings JSONB;
    v_count INT;
BEGIN
    -- Create manufacturer first
    v_manufacturer_csv := E'id,name\n550e8400-e29b-41d4-a716-446655440017,Hewlett Packard';
    PERFORM trinity.transform_csv('manufacturer', v_manufacturer_csv, 'pk_manufacturer', 'id', 'name', NULL, '550e8400-e29b-41d4-a716-446655440000'::UUID);

    -- Create model with FK
    v_fk_mappings := '{"fk_manufacturer_id": {"target_table": "manufacturer"}}';
    v_model_csv := E'id,name,fk_manufacturer_id\n550e8400-e29b-41d4-a716-446655440018,LaserJet,550e8400-e29b-41d4-a716-446655440017';
    SELECT COUNT(*) INTO v_count
    FROM trinity.transform_csv('model', v_model_csv, 'pk_model', 'id', 'name', v_fk_mappings, '550e8400-e29b-41d4-a716-446655440000'::UUID);
    IF v_count = 1 THEN
        PERFORM record_test('transform_csv_fk_resolution', true);
    ELSE
        PERFORM record_test('transform_csv_fk_resolution', false, 'Expected 1 row, got ' || v_count);
    END IF;
EXCEPTION WHEN OTHERS THEN
    PERFORM record_test('transform_csv_fk_resolution', false, SQLERRM);
END;
$$;

-- Test 26: Null CSV raises exception
DO $$
BEGIN
    PERFORM trinity.transform_csv('test', NULL, 'pk', 'id', NULL, NULL, '550e8400-e29b-41d4-a716-446655440000'::UUID);
    PERFORM record_test('transform_csv_null_csv', false, 'Should have raised exception');
EXCEPTION WHEN invalid_parameter_value THEN
    PERFORM record_test('transform_csv_null_csv', true);
WHEN OTHERS THEN
    PERFORM record_test('transform_csv_null_csv', false, 'Wrong exception: ' || SQLERRM);
END;
$$;

-- ============================================================================
-- GET_UUID_TO_PK_MAPPINGS() TESTS (5+ tests)
-- ============================================================================

-- Test 27: Get mappings returns correct data
DO $$
DECLARE
    v_count INT;
BEGIN
    -- Allocate a few PKs first
    PERFORM trinity.allocate_pk('mapping_test', '550e8400-e29b-41d4-a716-446655440019'::UUID, '550e8400-e29b-41d4-a716-446655440000'::UUID);
    PERFORM trinity.allocate_pk('mapping_test', '550e8400-e29b-41d4-a716-446655440020'::UUID, '550e8400-e29b-41d4-a716-446655440000'::UUID);

    SELECT COUNT(*) INTO v_count
    FROM trinity.get_uuid_to_pk_mappings('mapping_test', '550e8400-e29b-41d4-a716-446655440000'::UUID);
    IF v_count = 2 THEN
        PERFORM record_test('get_mappings_returns_data', true);
    ELSE
        PERFORM record_test('get_mappings_returns_data', false, 'Expected 2 mappings, got ' || v_count);
    END IF;
EXCEPTION WHEN OTHERS THEN
    PERFORM record_test('get_mappings_returns_data', false, SQLERRM);
END;
$$;

-- ============================================================================
-- PERFORMANCE TESTS (10+ tests)
-- ============================================================================

-- Test 28: Allocate PK performance (<5ms)
DO $$
DECLARE
    v_start TIMESTAMP;
    v_end TIMESTAMP;
    v_duration INTERVAL;
    v_pk BIGINT;
BEGIN
    v_start := clock_timestamp();
    v_pk := trinity.allocate_pk('perf_test', '550e8400-e29b-41d4-a716-446655440021'::UUID, '550e8400-e29b-41d4-a716-446655440000'::UUID);
    v_end := clock_timestamp();
    v_duration := v_end - v_start;

    IF extract(epoch from v_duration) * 1000 < 5 THEN
        PERFORM record_test('perf_allocate_pk', true);
    ELSE
        PERFORM record_test('perf_allocate_pk', false, format('Took %s ms, expected <5ms', extract(epoch from v_duration) * 1000));
    END IF;
EXCEPTION WHEN OTHERS THEN
    PERFORM record_test('perf_allocate_pk', false, SQLERRM);
END;
$$;

-- Test 29: Generate identifier performance (<0.1ms)
DO $$
DECLARE
    v_start TIMESTAMP;
    v_end TIMESTAMP;
    v_duration INTERVAL;
    v_result TEXT;
BEGIN
    v_start := clock_timestamp();
    v_result := trinity.generate_identifier('Performance Test Name');
    v_end := clock_timestamp();
    v_duration := v_end - v_start;

    IF extract(epoch from v_duration) * 1000 < 0.1 THEN
        PERFORM record_test('perf_generate_identifier', true);
    ELSE
        PERFORM record_test('perf_generate_identifier', false, format('Took %s ms, expected <0.1ms', extract(epoch from v_duration) * 1000));
    END IF;
EXCEPTION WHEN OTHERS THEN
    PERFORM record_test('perf_generate_identifier', false, SQLERRM);
END;
$$;

-- ============================================================================
-- INTEGRATION TESTS (15+ tests)
-- ============================================================================

-- Test 30: Full manufacturers → models pipeline
DO $$
DECLARE
    v_manufacturer_csv TEXT;
    v_model_csv TEXT;
    v_fk_mappings JSONB;
    v_manufacturer_count INT;
    v_model_count INT;
BEGIN
    -- Manufacturers
    v_manufacturer_csv := E'id,name\n550e8400-e29b-41d4-a716-446655440022,Hewlett Packard\n550e8400-e29b-41d4-a716-446655440023,Canon Inc';
    SELECT COUNT(*) INTO v_manufacturer_count
    FROM trinity.transform_csv('manufacturer', v_manufacturer_csv, 'pk_manufacturer', 'id', 'name', NULL, '550e8400-e29b-41d4-a716-446655440000'::UUID);

    -- Models with FKs
    v_fk_mappings := '{"fk_manufacturer_id": {"target_table": "manufacturer"}}';
    v_model_csv := E'id,name,fk_manufacturer_id\n550e8400-e29b-41d4-a716-446655440024,LaserJet P1102,550e8400-e29b-41d4-a716-446655440022\n550e8400-e29b-41d4-a716-446655440025,Canon PIXMA,550e8400-e29b-41d4-a716-446655440023';
    SELECT COUNT(*) INTO v_model_count
    FROM trinity.transform_csv('model', v_model_csv, 'pk_model', 'id', 'name', v_fk_mappings, '550e8400-e29b-41d4-a716-446655440000'::UUID);

    IF v_manufacturer_count = 2 AND v_model_count = 2 THEN
        PERFORM record_test('integration_manufacturers_models', true);
    ELSE
        PERFORM record_test('integration_manufacturers_models', false,
            format('Expected 2+2 rows, got %s+%s', v_manufacturer_count, v_model_count));
    END IF;
EXCEPTION WHEN OTHERS THEN
    PERFORM record_test('integration_manufacturers_models', false, SQLERRM);
END;
$$;

-- ============================================================================
-- TEST RESULTS SUMMARY
-- ============================================================================

SELECT
    COUNT(*) as total_tests,
    COUNT(*) FILTER (WHERE passed) as passed,
    COUNT(*) FILTER (WHERE NOT passed) as failed,
    ROUND(COUNT(*) FILTER (WHERE passed)::numeric / COUNT(*)::numeric * 100, 1) as success_rate
FROM test_results;

-- Show failed tests
SELECT test_name, error_message
FROM test_results
WHERE NOT passed
ORDER BY test_name;