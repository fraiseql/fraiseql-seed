-- Trinity Extension Phase 1 Foundation Tests (Development Version)
-- This version loads the extension source directly without system installation
-- Suitable for development and testing
--
-- Run with: psql -U postgres -d trinity_test -f test_phase1_dev.sql

-- ============================================================================
-- STEP 1: LOAD EXTENSION SOURCE DIRECTLY
-- ============================================================================

\echo '=== Loading Trinity Extension Source ==='

-- Create schema
CREATE SCHEMA IF NOT EXISTS trinity;

-- Create uuid_allocation_log table
CREATE TABLE IF NOT EXISTS trinity.uuid_allocation_log (
    table_name TEXT NOT NULL,
    uuid_value UUID NOT NULL,
    pk_value BIGINT NOT NULL,
    tenant_id UUID NOT NULL,
    allocated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT DEFAULT SESSION_USER,
    PRIMARY KEY (table_name, uuid_value, tenant_id),
    UNIQUE (table_name, pk_value, tenant_id)
);

CREATE INDEX IF NOT EXISTS idx_uuid_allocation_log_tenant_table
    ON trinity.uuid_allocation_log (tenant_id, table_name);

CREATE INDEX IF NOT EXISTS idx_uuid_allocation_log_uuid_lookup
    ON trinity.uuid_allocation_log (table_name, uuid_value);

CREATE INDEX IF NOT EXISTS idx_uuid_allocation_log_pk_lookup
    ON trinity.uuid_allocation_log (table_name, pk_value);

-- Create table_dependency_log table
CREATE TABLE IF NOT EXISTS trinity.table_dependency_log (
    source_table TEXT NOT NULL,
    target_table TEXT NOT NULL,
    fk_column TEXT NOT NULL,
    tenant_id UUID NOT NULL,
    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (source_table, target_table, fk_column, tenant_id)
);

CREATE INDEX IF NOT EXISTS idx_table_dependency_log_tenant
    ON trinity.table_dependency_log (tenant_id);

CREATE INDEX IF NOT EXISTS idx_table_dependency_log_source
    ON trinity.table_dependency_log (tenant_id, source_table);

CREATE INDEX IF NOT EXISTS idx_table_dependency_log_target
    ON trinity.table_dependency_log (tenant_id, target_table);

-- Create view
CREATE OR REPLACE VIEW trinity.uuid_to_pk_mapping AS
    SELECT
        table_name,
        uuid_value,
        pk_value,
        tenant_id,
        allocated_at,
        created_by
    FROM trinity.uuid_allocation_log
    ORDER BY table_name, pk_value;

-- Create helper functions

CREATE OR REPLACE FUNCTION trinity._validate_uuid(p_uuid TEXT)
    RETURNS UUID
    LANGUAGE plpgsql
    IMMUTABLE STRICT
    PARALLEL SAFE
AS $$
DECLARE
    v_uuid UUID;
BEGIN
    IF p_uuid IS NULL THEN
        RAISE EXCEPTION 'UUID input cannot be NULL'
            USING ERRCODE = 'null_value_not_allowed';
    END IF;

    IF p_uuid = '' THEN
        RAISE EXCEPTION 'UUID input cannot be empty'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;

    BEGIN
        v_uuid := p_uuid::UUID;
    EXCEPTION WHEN OTHERS THEN
        RAISE EXCEPTION 'Invalid UUID format: %', p_uuid
            USING ERRCODE = 'invalid_parameter_value',
                  HINT = 'UUID must be in format: 550e8400-e29b-41d4-a716-446655440000';
    END;

    RETURN v_uuid;
END;
$$;

CREATE OR REPLACE FUNCTION trinity._normalize_identifier_source(p_name TEXT)
    RETURNS TEXT
    LANGUAGE plpgsql
    IMMUTABLE STRICT
    PARALLEL SAFE
AS $$
DECLARE
    v_normalized TEXT;
BEGIN
    IF p_name IS NULL THEN
        RAISE EXCEPTION 'Name input cannot be NULL'
            USING ERRCODE = 'null_value_not_allowed';
    END IF;

    v_normalized := TRIM(p_name);

    IF v_normalized = '' THEN
        RAISE EXCEPTION 'Name input cannot be empty'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;

    v_normalized := regexp_replace(v_normalized, '\s+', ' ', 'g');

    RETURN v_normalized;
END;
$$;

CREATE OR REPLACE FUNCTION trinity._allocate_next_pk(
    p_table_name TEXT,
    p_tenant_id UUID
)
    RETURNS BIGINT
    LANGUAGE plpgsql
    STABLE STRICT
    PARALLEL SAFE
AS $$
DECLARE
    v_next_pk BIGINT;
BEGIN
    IF p_table_name IS NULL OR p_table_name = '' THEN
        RAISE EXCEPTION 'Table name cannot be NULL or empty'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;

    IF p_tenant_id IS NULL THEN
        RAISE EXCEPTION 'Tenant ID cannot be NULL'
            USING ERRCODE = 'null_value_not_allowed';
    END IF;

    SELECT COALESCE(MAX(pk_value), 0) + 1 INTO v_next_pk
    FROM trinity.uuid_allocation_log
    WHERE table_name = p_table_name
        AND tenant_id = p_tenant_id;

    RETURN v_next_pk;
END;
$$;

CREATE OR REPLACE FUNCTION trinity._check_circular_dependency(
    p_source_table TEXT,
    p_target_table TEXT,
    p_tenant_id UUID
)
    RETURNS BOOLEAN
    LANGUAGE plpgsql
    STABLE STRICT
    PARALLEL SAFE
AS $$
DECLARE
    v_has_cycle BOOLEAN := FALSE;
    v_visited TEXT[] := ARRAY[]::TEXT[];
    v_rec_stack TEXT[] := ARRAY[]::TEXT[];

    FUNCTION dfs(p_table TEXT) RETURNS BOOLEAN AS $inner$
    DECLARE
        v_neighbor TEXT;
        v_neighbor_rec RECORD;
    BEGIN
        v_visited := array_append(v_visited, p_table);
        v_rec_stack := array_append(v_rec_stack, p_table);

        FOR v_neighbor_rec IN
            SELECT DISTINCT target_table
            FROM trinity.table_dependency_log
            WHERE source_table = p_table AND tenant_id = p_tenant_id
        LOOP
            v_neighbor := v_neighbor_rec.target_table;

            IF v_neighbor = p_source_table THEN
                RETURN TRUE;
            END IF;

            IF NOT v_neighbor = ANY(v_visited) THEN
                IF dfs(v_neighbor) THEN
                    RETURN TRUE;
                END IF;
            END IF;
        END LOOP;

        v_rec_stack := v_rec_stack[1:array_length(v_rec_stack, 1) - 1];
        RETURN FALSE;
    END;
    $inner$ LANGUAGE plpgsql;
BEGIN
    IF p_source_table = p_target_table THEN
        RETURN TRUE;
    END IF;

    RESET v_visited;
    RESET v_rec_stack;
    v_has_cycle := dfs(p_target_table);

    RETURN v_has_cycle;
END;
$$;

CREATE OR REPLACE FUNCTION trinity._get_next_identifier_instance(
    p_base TEXT,
    p_existing_identifiers TEXT[],
    p_tenant_id UUID
)
    RETURNS INT
    LANGUAGE plpgsql
    STABLE STRICT
    PARALLEL SAFE
AS $$
DECLARE
    v_instance INT := 1;
    v_candidate TEXT;
BEGIN
    IF p_base IS NULL OR p_base = '' THEN
        RAISE EXCEPTION 'Base identifier cannot be NULL or empty'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;

    IF p_tenant_id IS NULL THEN
        RAISE EXCEPTION 'Tenant ID cannot be NULL'
            USING ERRCODE = 'null_value_not_allowed';
    END IF;

    IF p_existing_identifiers IS NULL OR array_length(p_existing_identifiers, 1) IS NULL THEN
        RETURN 1;
    END IF;

    IF p_base = ANY(p_existing_identifiers) THEN
        v_instance := 1;
        LOOP
            v_candidate := p_base || '-' || v_instance::TEXT;
            EXIT WHEN NOT v_candidate = ANY(p_existing_identifiers);
            v_instance := v_instance + 1;
            IF v_instance > 1000 THEN
                RAISE EXCEPTION 'Too many identifier collisions for base: %', p_base
                    USING ERRCODE = 'too_many_rows';
            END IF;
        END LOOP;
        RETURN v_instance;
    END IF;

    RETURN 1;
END;
$$;

\echo '✓ Extension source loaded successfully'

-- ============================================================================
-- STEP 2: RUN TESTS
-- ============================================================================

\echo ''
\echo '=== Running Phase 1 Foundation Tests ==='

-- Test utilities
CREATE TEMP TABLE test_results (
    test_num INT,
    test_name TEXT,
    status TEXT,
    message TEXT
);

CREATE OR REPLACE FUNCTION log_test(
    p_num INT,
    p_test_name TEXT,
    p_status TEXT,
    p_message TEXT DEFAULT ''
) RETURNS VOID AS $$
BEGIN
    INSERT INTO test_results (test_num, test_name, status, message)
    VALUES (p_num, p_test_name, p_status, p_message);

    IF p_status = 'PASS' THEN
        RAISE NOTICE '[%] ✓ %', p_num, p_test_name;
    ELSE
        RAISE NOTICE '[%] ✗ % - %', p_num, p_test_name, p_message;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Test 1: Schema exists
DO $$
BEGIN
    DECLARE v_count INT;
    BEGIN
        SELECT COUNT(*) INTO v_count FROM information_schema.schemata
        WHERE schema_name = 'trinity';
        PERFORM log_test(1, 'Schema trinity exists', CASE WHEN v_count > 0 THEN 'PASS' ELSE 'FAIL' END);
    END;
END;
$$ LANGUAGE plpgsql;

-- Test 2: uuid_allocation_log table exists
DO $$
BEGIN
    DECLARE v_count INT;
    BEGIN
        SELECT COUNT(*) INTO v_count FROM information_schema.tables
        WHERE table_schema = 'trinity' AND table_name = 'uuid_allocation_log';
        PERFORM log_test(2, 'Table uuid_allocation_log exists', CASE WHEN v_count > 0 THEN 'PASS' ELSE 'FAIL' END);
    END;
END;
$$ LANGUAGE plpgsql;

-- Test 3: table_dependency_log table exists
DO $$
BEGIN
    DECLARE v_count INT;
    BEGIN
        SELECT COUNT(*) INTO v_count FROM information_schema.tables
        WHERE table_schema = 'trinity' AND table_name = 'table_dependency_log';
        PERFORM log_test(3, 'Table table_dependency_log exists', CASE WHEN v_count > 0 THEN 'PASS' ELSE 'FAIL' END);
    END;
END;
$$ LANGUAGE plpgsql;

-- Test 4: Insert and retrieve allocation
DO $$
DECLARE
    v_test_uuid UUID := '550e8400-e29b-41d4-a716-446655440000'::UUID;
    v_test_tenant UUID := 'a0000000-0000-0000-0000-000000000001'::UUID;
    v_inserted_pk BIGINT;
    v_retrieved_pk BIGINT;
BEGIN
    INSERT INTO trinity.uuid_allocation_log
        (table_name, uuid_value, pk_value, tenant_id)
    VALUES ('test_table', v_test_uuid, 1, v_test_tenant);

    SELECT pk_value INTO v_retrieved_pk
    FROM trinity.uuid_allocation_log
    WHERE table_name = 'test_table'
        AND uuid_value = v_test_uuid
        AND tenant_id = v_test_tenant;

    PERFORM log_test(
        4,
        'Insert and retrieve allocation',
        CASE WHEN v_retrieved_pk = 1 THEN 'PASS' ELSE 'FAIL' END,
        'Retrieved PK: ' || v_retrieved_pk::TEXT
    );

    DELETE FROM trinity.uuid_allocation_log WHERE table_name = 'test_table';
END;
$$ LANGUAGE plpgsql;

-- Test 5: Tenant isolation
DO $$
DECLARE
    v_test_uuid UUID := '550e8400-e29b-41d4-a716-446655440001'::UUID;
    v_tenant1 UUID := 'a0000000-0000-0000-0000-000000000001'::UUID;
    v_tenant2 UUID := 'a0000000-0000-0000-0000-000000000002'::UUID;
    v_pk1 BIGINT;
    v_pk2 BIGINT;
BEGIN
    INSERT INTO trinity.uuid_allocation_log
        (table_name, uuid_value, pk_value, tenant_id)
    VALUES ('test_table', v_test_uuid, 1, v_tenant1),
           ('test_table', v_test_uuid, 2, v_tenant2);

    SELECT pk_value INTO v_pk1
    FROM trinity.uuid_allocation_log
    WHERE table_name = 'test_table' AND uuid_value = v_test_uuid AND tenant_id = v_tenant1;

    SELECT pk_value INTO v_pk2
    FROM trinity.uuid_allocation_log
    WHERE table_name = 'test_table' AND uuid_value = v_test_uuid AND tenant_id = v_tenant2;

    PERFORM log_test(
        5,
        'Tenant isolation - different PKs for same UUID',
        CASE WHEN v_pk1 = 1 AND v_pk2 = 2 THEN 'PASS' ELSE 'FAIL' END,
        'Tenant 1 PK: ' || v_pk1::TEXT || ', Tenant 2 PK: ' || v_pk2::TEXT
    );

    DELETE FROM trinity.uuid_allocation_log WHERE table_name = 'test_table';
END;
$$ LANGUAGE plpgsql;

-- Test 6: Unique constraint on PK
DO $$
DECLARE
    v_error_raised BOOLEAN := FALSE;
    v_test_uuid1 UUID := '550e8400-e29b-41d4-a716-446655440002'::UUID;
    v_test_uuid2 UUID := '550e8400-e29b-41d4-a716-446655440003'::UUID;
    v_test_tenant UUID := 'a0000000-0000-0000-0000-000000000001'::UUID;
BEGIN
    INSERT INTO trinity.uuid_allocation_log
        (table_name, uuid_value, pk_value, tenant_id)
    VALUES ('test_table', v_test_uuid1, 1, v_test_tenant);

    BEGIN
        INSERT INTO trinity.uuid_allocation_log
            (table_name, uuid_value, pk_value, tenant_id)
        VALUES ('test_table', v_test_uuid2, 1, v_test_tenant);
    EXCEPTION WHEN unique_violation THEN
        v_error_raised := TRUE;
    END;

    PERFORM log_test(
        6,
        'Unique constraint prevents duplicate PKs',
        CASE WHEN v_error_raised THEN 'PASS' ELSE 'FAIL' END
    );

    DELETE FROM trinity.uuid_allocation_log WHERE table_name = 'test_table';
END;
$$ LANGUAGE plpgsql;

-- Test 7: Primary key idempotency
DO $$
DECLARE
    v_error_raised BOOLEAN := FALSE;
    v_test_uuid UUID := '550e8400-e29b-41d4-a716-446655440004'::UUID;
    v_test_tenant UUID := 'a0000000-0000-0000-0000-000000000001'::UUID;
BEGIN
    INSERT INTO trinity.uuid_allocation_log
        (table_name, uuid_value, pk_value, tenant_id)
    VALUES ('test_table', v_test_uuid, 1, v_test_tenant);

    BEGIN
        INSERT INTO trinity.uuid_allocation_log
            (table_name, uuid_value, pk_value, tenant_id)
        VALUES ('test_table', v_test_uuid, 100, v_test_tenant);
    EXCEPTION WHEN unique_violation THEN
        v_error_raised := TRUE;
    END;

    PERFORM log_test(
        7,
        'Primary key prevents duplicate UUID',
        CASE WHEN v_error_raised THEN 'PASS' ELSE 'FAIL' END
    );

    DELETE FROM trinity.uuid_allocation_log WHERE table_name = 'test_table';
END;
$$ LANGUAGE plpgsql;

-- Test 8: _validate_uuid - valid UUID
DO $$
DECLARE
    v_result UUID;
    v_pass BOOLEAN := FALSE;
BEGIN
    v_result := trinity._validate_uuid('550e8400-e29b-41d4-a716-446655440000');
    v_pass := (v_result = '550e8400-e29b-41d4-a716-446655440000'::UUID);
    PERFORM log_test(8, '_validate_uuid - valid UUID', CASE WHEN v_pass THEN 'PASS' ELSE 'FAIL' END);
END;
$$ LANGUAGE plpgsql;

-- Test 9: _validate_uuid - invalid format
DO $$
DECLARE
    v_error_raised BOOLEAN := FALSE;
BEGIN
    BEGIN
        PERFORM trinity._validate_uuid('not-a-uuid');
    EXCEPTION WHEN OTHERS THEN
        v_error_raised := TRUE;
    END;
    PERFORM log_test(9, '_validate_uuid - invalid format raises exception', CASE WHEN v_error_raised THEN 'PASS' ELSE 'FAIL' END);
END;
$$ LANGUAGE plpgsql;

-- Test 10: _validate_uuid - NULL input
DO $$
DECLARE
    v_error_raised BOOLEAN := FALSE;
BEGIN
    BEGIN
        PERFORM trinity._validate_uuid(NULL);
    EXCEPTION WHEN OTHERS THEN
        v_error_raised := TRUE;
    END;
    PERFORM log_test(10, '_validate_uuid - NULL input raises exception', CASE WHEN v_error_raised THEN 'PASS' ELSE 'FAIL' END);
END;
$$ LANGUAGE plpgsql;

-- Test 11: _normalize_identifier_source - simple name
DO $$
DECLARE
    v_result TEXT;
    v_pass BOOLEAN;
BEGIN
    v_result := trinity._normalize_identifier_source('Acme Corp');
    v_pass := (v_result = 'Acme Corp');
    PERFORM log_test(11, '_normalize_identifier_source - simple name', CASE WHEN v_pass THEN 'PASS' ELSE 'FAIL' END, 'Result: ' || v_result);
END;
$$ LANGUAGE plpgsql;

-- Test 12: _normalize_identifier_source - trim whitespace
DO $$
DECLARE
    v_result TEXT;
    v_pass BOOLEAN;
BEGIN
    v_result := trinity._normalize_identifier_source('  Acme  ');
    v_pass := (v_result = 'Acme');
    PERFORM log_test(12, '_normalize_identifier_source - trim whitespace', CASE WHEN v_pass THEN 'PASS' ELSE 'FAIL' END, 'Result: ' || v_result);
END;
$$ LANGUAGE plpgsql;

-- Test 13: _normalize_identifier_source - collapse spaces
DO $$
DECLARE
    v_result TEXT;
    v_pass BOOLEAN;
BEGIN
    v_result := trinity._normalize_identifier_source('Multi   Space   Name');
    v_pass := (v_result = 'Multi Space Name');
    PERFORM log_test(13, '_normalize_identifier_source - collapse spaces', CASE WHEN v_pass THEN 'PASS' ELSE 'FAIL' END, 'Result: ' || v_result);
END;
$$ LANGUAGE plpgsql;

-- Test 14: _allocate_next_pk - first allocation
DO $$
DECLARE
    v_result BIGINT;
    v_test_tenant UUID := 'a0000000-0000-0000-0000-000000000001'::UUID;
BEGIN
    v_result := trinity._allocate_next_pk('new_table_1', v_test_tenant);
    PERFORM log_test(14, '_allocate_next_pk - first allocation is 1', CASE WHEN v_result = 1 THEN 'PASS' ELSE 'FAIL' END, 'Result: ' || v_result::TEXT);
END;
$$ LANGUAGE plpgsql;

-- Test 15: _allocate_next_pk - sequential allocation
DO $$
DECLARE
    v_result BIGINT;
    v_test_tenant UUID := 'a0000000-0000-0000-0000-000000000001'::UUID;
BEGIN
    INSERT INTO trinity.uuid_allocation_log
        (table_name, uuid_value, pk_value, tenant_id)
    VALUES ('seq_test', '550e8400-e29b-41d4-a716-446655440010'::UUID, 1, v_test_tenant),
           ('seq_test', '550e8400-e29b-41d4-a716-446655440011'::UUID, 2, v_test_tenant),
           ('seq_test', '550e8400-e29b-41d4-a716-446655440012'::UUID, 3, v_test_tenant);

    v_result := trinity._allocate_next_pk('seq_test', v_test_tenant);
    PERFORM log_test(15, '_allocate_next_pk - sequential allocation', CASE WHEN v_result = 4 THEN 'PASS' ELSE 'FAIL' END, 'Result: ' || v_result::TEXT);

    DELETE FROM trinity.uuid_allocation_log WHERE table_name = 'seq_test';
END;
$$ LANGUAGE plpgsql;

-- Test 16: _check_circular_dependency - direct cycle
DO $$
DECLARE
    v_result BOOLEAN;
    v_test_tenant UUID := 'a0000000-0000-0000-0000-000000000001'::UUID;
BEGIN
    v_result := trinity._check_circular_dependency('table_a', 'table_a', v_test_tenant);
    PERFORM log_test(16, '_check_circular_dependency - direct cycle', CASE WHEN v_result = TRUE THEN 'PASS' ELSE 'FAIL' END);
END;
$$ LANGUAGE plpgsql;

-- Test 17: _check_circular_dependency - no cycle in empty graph
DO $$
DECLARE
    v_result BOOLEAN;
    v_test_tenant UUID := 'a0000000-0000-0000-0000-000000000001'::UUID;
BEGIN
    v_result := trinity._check_circular_dependency('table_a', 'table_b', v_test_tenant);
    PERFORM log_test(17, '_check_circular_dependency - no cycle in empty graph', CASE WHEN v_result = FALSE THEN 'PASS' ELSE 'FAIL' END);
END;
$$ LANGUAGE plpgsql;

-- Test 18: _get_next_identifier_instance - no collision
DO $$
DECLARE
    v_result INT;
    v_test_tenant UUID := 'a0000000-0000-0000-0000-000000000001'::UUID;
BEGIN
    v_result := trinity._get_next_identifier_instance('acme-corp', ARRAY[]::TEXT[], v_test_tenant);
    PERFORM log_test(18, '_get_next_identifier_instance - no collision', CASE WHEN v_result = 1 THEN 'PASS' ELSE 'FAIL' END, 'Result: ' || v_result::TEXT);
END;
$$ LANGUAGE plpgsql;

-- Test 19: _get_next_identifier_instance - collision
DO $$
DECLARE
    v_result INT;
    v_test_tenant UUID := 'a0000000-0000-0000-0000-000000000001'::UUID;
BEGIN
    v_result := trinity._get_next_identifier_instance(
        'acme-corp',
        ARRAY['acme-corp']::TEXT[],
        v_test_tenant
    );
    PERFORM log_test(19, '_get_next_identifier_instance - collision with base', CASE WHEN v_result = 1 THEN 'PASS' ELSE 'FAIL' END, 'Result: ' || v_result::TEXT);
END;
$$ LANGUAGE plpgsql;

-- Test 20: _get_next_identifier_instance - multiple collisions
DO $$
DECLARE
    v_result INT;
    v_test_tenant UUID := 'a0000000-0000-0000-0000-000000000001'::UUID;
BEGIN
    v_result := trinity._get_next_identifier_instance(
        'acme-corp',
        ARRAY['acme-corp', 'acme-corp-1', 'acme-corp-2']::TEXT[],
        v_test_tenant
    );
    PERFORM log_test(20, '_get_next_identifier_instance - multiple collisions', CASE WHEN v_result = 3 THEN 'PASS' ELSE 'FAIL' END, 'Result: ' || v_result::TEXT);
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- TEST SUMMARY
-- ============================================================================

\echo ''
\echo '=== Test Summary ==='

SELECT
    COUNT(*) as "Total Tests",
    SUM(CASE WHEN status = 'PASS' THEN 1 ELSE 0 END) as "Passed",
    SUM(CASE WHEN status = 'FAIL' THEN 1 ELSE 0 END) as "Failed"
FROM test_results;

\echo ''
\echo 'Detailed Results:'
SELECT test_num, test_name, status, message FROM test_results ORDER BY test_num;

\echo ''
\echo '✓ Phase 1 Foundation Tests Complete'
