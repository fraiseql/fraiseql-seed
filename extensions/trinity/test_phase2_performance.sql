-- Trinity Extension Performance Benchmarks
-- Tests performance targets for Phase 2 functions

-- Setup
SET trinity.tenant_id = '550e8400-e29b-41d4-a716-446655440000'::UUID;

-- Benchmark 1: allocate_pk performance (<5ms per call)
DO $$
DECLARE
    v_start TIMESTAMP;
    v_end TIMESTAMP;
    v_duration INTERVAL;
    v_pk BIGINT;
    v_total_time FLOAT := 0;
    v_iterations INT := 100;
BEGIN
    RAISE NOTICE 'Testing allocate_pk performance with % iterations...', v_iterations;

    FOR i IN 1..v_iterations LOOP
        v_start := clock_timestamp();
        v_pk := trinity.allocate_pk('perf_test', gen_random_uuid(), '550e8400-e29b-41d4-a716-446655440000'::UUID);
        v_end := clock_timestamp();
        v_duration := v_end - v_start;
        v_total_time := v_total_time + extract(epoch from v_duration);
    END LOOP;

    RAISE NOTICE 'Total time: % seconds', v_total_time;
    RAISE NOTICE 'Average time per call: % ms', (v_total_time / v_iterations) * 1000;
    RAISE NOTICE 'Target: <5ms per call';

    IF (v_total_time / v_iterations) * 1000 < 5 THEN
        RAISE NOTICE '✓ PASSED: Performance target met';
    ELSE
        RAISE NOTICE '✗ FAILED: Performance target not met';
    END IF;
END;
$$;

-- Benchmark 2: generate_identifier performance (<0.1ms per call)
DO $$
DECLARE
    v_start TIMESTAMP;
    v_end TIMESTAMP;
    v_duration INTERVAL;
    v_result TEXT;
    v_total_time FLOAT := 0;
    v_iterations INT := 1000;
BEGIN
    RAISE NOTICE 'Testing generate_identifier performance with % iterations...', v_iterations;

    FOR i IN 1..v_iterations LOOP
        v_start := clock_timestamp();
        v_result := trinity.generate_identifier('Performance Test Name ' || i);
        v_end := clock_timestamp();
        v_duration := v_end - v_start;
        v_total_time := v_total_time + extract(epoch from v_duration);
    END LOOP;

    RAISE NOTICE 'Total time: % seconds', v_total_time;
    RAISE NOTICE 'Average time per call: % ms', (v_total_time / v_iterations) * 1000;
    RAISE NOTICE 'Target: <0.1ms per call';

    IF (v_total_time / v_iterations) * 1000 < 0.1 THEN
        RAISE NOTICE '✓ PASSED: Performance target met';
    ELSE
        RAISE NOTICE '✗ FAILED: Performance target not met';
    END IF;
END;
$$;

-- Benchmark 3: resolve_fk performance (<1ms per lookup)
DO $$
DECLARE
    v_start TIMESTAMP;
    v_end TIMESTAMP;
    v_duration INTERVAL;
    v_result BIGINT;
    v_total_time FLOAT := 0;
    v_iterations INT := 100;
BEGIN
    RAISE NOTICE 'Testing resolve_fk performance with % iterations...', v_iterations;

    -- First allocate some PKs to resolve
    FOR i IN 1..10 LOOP
        PERFORM trinity.allocate_pk('fk_test', gen_random_uuid(), '550e8400-e29b-41d4-a716-446655440000'::UUID);
    END LOOP;

    -- Now test lookups
    FOR i IN 1..v_iterations LOOP
        v_start := clock_timestamp();
        v_result := trinity.resolve_fk('source_test', 'fk_test',
            (SELECT uuid_value FROM trinity.uuid_allocation_log
             WHERE table_name = 'fk_test' LIMIT 1),
            '550e8400-e29b-41d4-a716-446655440000'::UUID);
        v_end := clock_timestamp();
        v_duration := v_end - v_start;
        v_total_time := v_total_time + extract(epoch from v_duration);
    END LOOP;

    RAISE NOTICE 'Total time: % seconds', v_total_time;
    RAISE NOTICE 'Average time per lookup: % ms', (v_total_time / v_iterations) * 1000;
    RAISE NOTICE 'Target: <1ms per lookup';

    IF (v_total_time / v_iterations) * 1000 < 1 THEN
        RAISE NOTICE '✓ PASSED: Performance target met';
    ELSE
        RAISE NOTICE '✗ FAILED: Performance target not met';
    END IF;
END;
$$;

-- Benchmark 4: Small CSV transformation
DO $$
DECLARE
    v_start TIMESTAMP;
    v_end TIMESTAMP;
    v_duration INTERVAL;
    v_csv TEXT;
    v_count INT;
BEGIN
    RAISE NOTICE 'Testing small CSV transformation...';

    v_csv := E'id,name\n550e8400-e29b-41d4-a716-446655440100,test1\n550e8400-e29b-41d4-a716-446655440101,test2';

    v_start := clock_timestamp();
    SELECT COUNT(*) INTO v_count
    FROM trinity.transform_csv('csv_test', v_csv, 'pk', 'id', 'name', NULL, '550e8400-e29b-41d4-a716-446655440000'::UUID);
    v_end := clock_timestamp();
    v_duration := v_end - v_start;

    RAISE NOTICE 'Processed % rows in % seconds', v_count, extract(epoch from v_duration);
    RAISE NOTICE 'Target: <2s for 1M rows (this test: % rows)', v_count;
END;
$$;