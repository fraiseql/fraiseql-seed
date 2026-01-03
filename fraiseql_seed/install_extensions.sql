-- FraiseQL-Seed Extension Installation
-- Automatically installs required PostgreSQL extensions when seeding a database
--
-- This file is executed during fraiseql-seed setup to ensure all required
-- extensions are available for the seeding process.

-- ============================================================================
-- TRINITY EXTENSION INSTALLATION
-- ============================================================================

-- Install the Trinity extension for UUID→INTEGER PK transformations
-- This is required for PrintOptim Forge → FraiseQL data pipelines

DO $$
DECLARE
    v_extension_exists BOOLEAN := FALSE;
    v_version TEXT;
BEGIN
    -- Check if extension already exists
    SELECT EXISTS(
        SELECT 1 FROM pg_extension WHERE extname = 'trinity'
    ) INTO v_extension_exists;

    IF v_extension_exists THEN
        -- Get current version
        SELECT extversion INTO v_version
        FROM pg_extension
        WHERE extname = 'trinity';

        RAISE NOTICE 'Trinity extension already installed (version %)', v_version;
    ELSE
        -- Install the extension
        CREATE EXTENSION trinity;

        RAISE NOTICE 'Trinity extension installed successfully';
    END IF;

    -- Verify installation by testing a simple function
    BEGIN
        PERFORM trinity._validate_uuid('550e8400-e29b-41d4-a716-446655440000'::TEXT);
        RAISE NOTICE 'Trinity extension verification successful';
    EXCEPTION WHEN OTHERS THEN
        RAISE EXCEPTION 'Trinity extension installation failed: %', SQLERRM;
    END;

END;
$$;

-- ============================================================================
-- ADDITIONAL EXTENSIONS (Future)
-- ============================================================================

-- Add other required extensions here as needed
-- For example:
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
-- CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- ============================================================================
-- INSTALLATION COMPLETE
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE 'FraiseQL-Seed extension installation completed successfully';
    RAISE NOTICE 'All required PostgreSQL extensions are now available';
END;
$$;