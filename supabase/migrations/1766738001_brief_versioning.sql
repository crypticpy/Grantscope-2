-- Migration: brief_versioning
-- Created at: 1766738001
-- Purpose: Add versioning support to executive_briefs table

-- ============================================================================
-- ADD VERSION COLUMN
-- ============================================================================

-- Add version column with default of 1 for existing records
ALTER TABLE executive_briefs
ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;

-- Add column to track new sources since previous version
ALTER TABLE executive_briefs
ADD COLUMN IF NOT EXISTS sources_since_previous JSONB DEFAULT NULL;

-- Add comment for documentation
COMMENT ON COLUMN executive_briefs.version IS 'Version number of the brief (1, 2, 3, etc.)';
COMMENT ON COLUMN executive_briefs.sources_since_previous IS 'Metadata about sources discovered since previous brief version';

-- ============================================================================
-- MODIFY CONSTRAINTS
-- ============================================================================

-- Drop the existing unique constraint on workstream_card_id
-- This allows multiple versions per workstream card
ALTER TABLE executive_briefs
DROP CONSTRAINT IF EXISTS executive_briefs_workstream_card_id_key;

-- Add new unique constraint on (workstream_card_id, version)
-- Ensures each version number is unique per workstream card
ALTER TABLE executive_briefs
ADD CONSTRAINT executive_briefs_workstream_card_version_key
UNIQUE (workstream_card_id, version);

-- ============================================================================
-- ADD INDEXES FOR PERFORMANCE
-- ============================================================================

-- Index for efficient lookup of latest version
-- Queries like "get latest brief for card" use this
CREATE INDEX IF NOT EXISTS idx_executive_briefs_workstream_card_version
ON executive_briefs (workstream_card_id, version DESC);

-- ============================================================================
-- VERIFICATION
-- ============================================================================

SELECT
    'brief_versioning migration applied' as status,
    (SELECT COUNT(*) FROM information_schema.columns
     WHERE table_name = 'executive_briefs' AND column_name = 'version') as version_column_exists,
    (SELECT COUNT(*) FROM information_schema.table_constraints
     WHERE table_name = 'executive_briefs'
     AND constraint_name = 'executive_briefs_workstream_card_version_key') as version_constraint_exists;
