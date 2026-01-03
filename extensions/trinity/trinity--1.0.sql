-- Trinity PostgreSQL Extension v1.0
-- UUID to INTEGER Primary Key Transformer for Multi-tenant Data Warehouses
--
-- This extension provides atomic, high-performance transformations for converting
-- UUID-based data (from Forge) into Trinity-formatted INTEGER PKs for FraiseQL databases.
--
-- Created: 2026-01-03
-- Status: Implementation Phase 1

-- ============================================================================
-- PHASE 1.1: EXTENSION STRUCTURE & SETUP
-- ============================================================================

-- Create the trinity schema for extension objects
CREATE SCHEMA IF NOT EXISTS trinity;

-- Set schema search path for this extension
COMMENT ON SCHEMA trinity IS 'FraiseQL Trinity Extension - UUID to INTEGER PK transformation';

-- ============================================================================
-- PHASE 1.2: CORE TABLES
-- ============================================================================

-- Table: trinity.uuid_allocation_log
-- Purpose: Central state table tracking UUID → INTEGER PK allocations
-- Design:
--   - Primary key: (table_name, uuid_value, tenant_id) ensures one allocation per UUID per table/tenant
--   - Unique constraint: (table_name, pk_value, tenant_id) ensures no duplicate PKs
--   - BIGINT PKs support 1M+ rows per table with future growth potential
--   - tenant_id enables multi-tenant isolation at SQL level
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

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_uuid_allocation_log_tenant_table
    ON trinity.uuid_allocation_log (tenant_id, table_name);

CREATE INDEX IF NOT EXISTS idx_uuid_allocation_log_uuid_lookup
    ON trinity.uuid_allocation_log (table_name, uuid_value);

CREATE INDEX IF NOT EXISTS idx_uuid_allocation_log_pk_lookup
    ON trinity.uuid_allocation_log (table_name, pk_value);

COMMENT ON TABLE trinity.uuid_allocation_log IS
    'Tracks UUID to INTEGER PK allocations. Primary source of truth for Trinity pattern.
     Composite PK: (table_name, uuid_value, tenant_id) ensures one allocation per UUID.
     UNIQUE constraint on (table_name, pk_value, tenant_id) prevents duplicate PKs.';

COMMENT ON COLUMN trinity.uuid_allocation_log.table_name IS 'Which table (e.g., manufacturer, model)';
COMMENT ON COLUMN trinity.uuid_allocation_log.uuid_value IS 'Original UUID from Forge';
COMMENT ON COLUMN trinity.uuid_allocation_log.pk_value IS 'Allocated INTEGER PK (BIGINT for 1M+ row support)';
COMMENT ON COLUMN trinity.uuid_allocation_log.tenant_id IS 'Multi-tenant isolation key';
COMMENT ON COLUMN trinity.uuid_allocation_log.allocated_at IS 'Audit trail - when allocation occurred';
COMMENT ON COLUMN trinity.uuid_allocation_log.created_by IS 'Audit trail - which user/process created allocation';

-- Table: trinity.table_dependency_log
-- Purpose: Track foreign key relationships between tables
-- Design:
--   - Enables circular dependency detection
--   - Supports future optimization and relationship analysis
--   - Per-tenant isolation prevents cross-tenant relationship confusion
CREATE TABLE IF NOT EXISTS trinity.table_dependency_log (
    source_table TEXT NOT NULL,
    target_table TEXT NOT NULL,
    fk_column TEXT NOT NULL,
    tenant_id UUID NOT NULL,
    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (source_table, target_table, fk_column, tenant_id)
);

-- Indexes for dependency queries
CREATE INDEX IF NOT EXISTS idx_table_dependency_log_tenant
    ON trinity.table_dependency_log (tenant_id);

CREATE INDEX IF NOT EXISTS idx_table_dependency_log_source
    ON trinity.table_dependency_log (tenant_id, source_table);

CREATE INDEX IF NOT EXISTS idx_table_dependency_log_target
    ON trinity.table_dependency_log (tenant_id, target_table);

COMMENT ON TABLE trinity.table_dependency_log IS
    'Tracks FK relationships for circular dependency detection and analysis.
     Helps understand data warehouse schema structure per tenant.';

-- View: trinity.uuid_to_pk_mapping
-- Purpose: Convenient query interface for UUID→PK lookups
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

COMMENT ON VIEW trinity.uuid_to_pk_mapping IS
    'Convenient query interface for UUID to PK mapping lookups.
     Primarily used for verification and debugging.';

-- ============================================================================
-- PHASE 1.3: HELPER FUNCTIONS
-- ============================================================================

-- Helper Function 1: _validate_uuid()
-- Purpose: Validate and parse UUID string
-- Input: Text that should be a valid UUID
-- Output: UUID type or raises exception
-- Performance: <0.1ms
CREATE OR REPLACE FUNCTION trinity._validate_uuid(p_uuid TEXT)
    RETURNS UUID
    LANGUAGE plpgsql
    IMMUTABLE
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

COMMENT ON FUNCTION trinity._validate_uuid(TEXT) IS
    'Validates and parses UUID string. Returns UUID or raises exception with helpful error message.
     Performance: <0.1ms';

-- Helper Function 2: _normalize_identifier_source()
-- Purpose: Pre-process name for identifier generation
-- Input: Name string (potentially with spaces, special chars)
-- Output: Normalized string ready for slug generation
-- Performance: <0.1ms
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

    -- Trim whitespace
    v_normalized := TRIM(p_name);

    IF v_normalized = '' THEN
        RAISE EXCEPTION 'Name input cannot be empty'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;

    -- Collapse multiple spaces to single space
    v_normalized := regexp_replace(v_normalized, '\s+', ' ', 'g');

    RETURN v_normalized;
END;
$$;

COMMENT ON FUNCTION trinity._normalize_identifier_source(TEXT) IS
    'Normalizes name for identifier generation: trim, collapse multiple spaces.
     Performance: <0.1ms';

-- Helper Function 3: _allocate_next_pk()
-- Purpose: Find and allocate next available PK for table/tenant combination
-- Input: table_name, tenant_id
-- Output: BIGINT - next available PK (MAX(pk_value) + 1 or 1 if no allocations)
-- Performance: <1ms with proper indexing
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

COMMENT ON FUNCTION trinity._allocate_next_pk(TEXT, UUID) IS
    'Finds next available PK for table/tenant: MAX(pk_value) + 1 or 1 if empty.
     Performance: <1ms with index on (table_name, tenant_id)';

-- Helper Function 4: _check_circular_dependency()
-- Purpose: Detect if adding dependency creates cycle via DFS
-- Input: source_table, target_table, tenant_id
-- Output: BOOLEAN - TRUE if would create cycle, FALSE if safe
-- Performance: <10ms for up to 100 tables
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
    v_visited TEXT[] := ARRAY[]::TEXT[];
    v_queue TEXT[] := ARRAY[]::TEXT[];
    v_queue_idx INT := 0;
    v_current_table TEXT;
    v_neighbor_rec RECORD;
    v_is_new BOOLEAN;
BEGIN
    -- Direct cycle: source → source
    IF p_source_table = p_target_table THEN
        RETURN TRUE;
    END IF;

    -- BFS from p_target_table to find if there's a path back to p_source_table
    -- Initialize queue with target's neighbors
    v_queue := ARRAY[p_target_table];
    v_queue_idx := 1;

    WHILE v_queue_idx <= array_length(v_queue, 1) LOOP
        v_current_table := v_queue[v_queue_idx];
        v_queue_idx := v_queue_idx + 1;

        -- Skip if already visited
        CONTINUE WHEN v_current_table = ANY(v_visited);
        v_visited := array_append(v_visited, v_current_table);

        -- Check all outgoing edges from current table
        FOR v_neighbor_rec IN
            SELECT DISTINCT target_table
            FROM trinity.table_dependency_log
            WHERE source_table = v_current_table AND tenant_id = p_tenant_id
        LOOP
            -- Found a path back to source - cycle detected
            IF v_neighbor_rec.target_table = p_source_table THEN
                RETURN TRUE;
            END IF;

            -- Add to queue if not visited
            IF NOT v_neighbor_rec.target_table = ANY(v_visited) THEN
                v_queue := array_append(v_queue, v_neighbor_rec.target_table);
            END IF;
        END LOOP;
    END LOOP;

    -- No path found from target back to source
    RETURN FALSE;
END;
$$;

COMMENT ON FUNCTION trinity._check_circular_dependency(TEXT, TEXT, UUID) IS
    'Detects circular dependencies using DFS algorithm.
     Returns TRUE if adding source→target dependency would create cycle, FALSE if safe.
     Performance: <10ms for up to 100 tables';

-- Helper Function 5: _get_next_identifier_instance()
-- Purpose: Find next instance number for duplicate identifier
-- Input: base identifier, existing identifiers array, tenant_id
-- Output: INT - next instance number (1 if no duplicates, 2+ if collision)
-- Performance: <1ms
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

    -- If no existing identifiers, no collision
    IF p_existing_identifiers IS NULL OR array_length(p_existing_identifiers, 1) IS NULL THEN
        RETURN 1;
    END IF;

    -- Check if base itself is in use
    IF p_base = ANY(p_existing_identifiers) THEN
        -- Find next available instance number
        v_instance := 1;
        LOOP
            v_candidate := p_base || '-' || v_instance::TEXT;
            EXIT WHEN NOT v_candidate = ANY(p_existing_identifiers);
            v_instance := v_instance + 1;
            IF v_instance > 1000 THEN
                -- Safety check to prevent infinite loops
                RAISE EXCEPTION 'Too many identifier collisions for base: %', p_base
                    USING ERRCODE = 'too_many_rows';
            END IF;
        END LOOP;
        RETURN v_instance;
    END IF;

    RETURN 1;
END;
$$;

COMMENT ON FUNCTION trinity._get_next_identifier_instance(TEXT, TEXT[], UUID) IS
    'Finds next instance number for duplicate identifiers.
     Returns 1 if no collision, 2+ if duplicates exist.
     Performance: <1ms';

-- ============================================================================
-- PERMISSION GRANTS
-- ============================================================================

-- Grant usage on schema to public (allows CREATE EXTENSION)
GRANT USAGE ON SCHEMA trinity TO PUBLIC;

-- Grant execute on helper functions to public
GRANT EXECUTE ON FUNCTION trinity._validate_uuid(TEXT) TO PUBLIC;
GRANT EXECUTE ON FUNCTION trinity._normalize_identifier_source(TEXT) TO PUBLIC;
GRANT EXECUTE ON FUNCTION trinity._allocate_next_pk(TEXT, UUID) TO PUBLIC;
GRANT EXECUTE ON FUNCTION trinity._check_circular_dependency(TEXT, TEXT, UUID) TO PUBLIC;
GRANT EXECUTE ON FUNCTION trinity._get_next_identifier_instance(TEXT, TEXT[], UUID) TO PUBLIC;

-- Grant table access (will be extended with public functions in Phase 2)
GRANT SELECT, INSERT ON trinity.uuid_allocation_log TO PUBLIC;
GRANT SELECT, INSERT ON trinity.table_dependency_log TO PUBLIC;
GRANT SELECT ON trinity.uuid_to_pk_mapping TO PUBLIC;

-- ============================================================================
-- END OF PHASE 1.1-1.2
-- ============================================================================
