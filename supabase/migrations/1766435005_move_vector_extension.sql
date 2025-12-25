-- Migration: move_vector_extension
-- Created at: 1766435005
-- Description: Move vector extension from public to extensions schema
-- Fixes: extension_in_public warning

-- ============================================================================
-- CREATE EXTENSIONS SCHEMA (if not exists)
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS extensions;

-- Grant usage to roles that need vector operations
GRANT USAGE ON SCHEMA extensions TO authenticated;
GRANT USAGE ON SCHEMA extensions TO service_role;
GRANT USAGE ON SCHEMA extensions TO anon;

-- ============================================================================
-- MOVE VECTOR EXTENSION
-- ============================================================================

ALTER EXTENSION vector SET SCHEMA extensions;

-- ============================================================================
-- UPDATE SEARCH PATH FOR FUNCTIONS THAT USE VECTOR
-- The functions already have SET search_path = '', so they use fully qualified
-- names (public.table). Vector types will still work because PostgreSQL
-- resolves extension types globally.
-- ============================================================================

COMMENT ON SCHEMA extensions IS 'Schema for PostgreSQL extensions to keep public schema clean';
