-- Migration: sources_quality_fields
-- Created at: 1766739004
-- Task: 0.4 from DEV_PLAN_Information_Quality.md
--
-- PURPOSE:
--   Add quality-tracking columns to the sources table for peer-review
--   status, story clustering, and domain reputation linkage.
--
-- ============================================================================
-- WHAT THIS ENABLES
-- ============================================================================
--
-- is_peer_reviewed:
--   Tracks whether a source is from a peer-reviewed journal or preprint server.
--   NULL = unknown (default for all existing rows). TRUE = confirmed peer-reviewed.
--   FALSE = pre-print, blog, news, or other non-academic source.
--   Set by academic source fetchers during the discovery pipeline. Used by the
--   Source Quality Index (SQI) calculation to weight academic rigor.
--
-- story_cluster_id:
--   Groups multiple sources that report on the same underlying event or story.
--   Assigned by StoryClusteringService after discovery to detect when several
--   articles all cover the same news. Enables corroboration counting in SQI
--   (many independent sources = higher confidence) and deduplication in the
--   discovery queue (show one representative per cluster, not N duplicates).
--   NULL = source has not yet been clustered.
--
-- domain_reputation_id:
--   Foreign key linking each source to its domain's entry in the domain_reputation
--   table. Set during triage when the domain reputation lookup occurs. Allows
--   efficient joins for domain-level analytics and avoids repeated domain pattern
--   matching at query time.
--
-- ============================================================================
-- MIGRATION ORDERING DEPENDENCY
-- ============================================================================
--
-- The domain_reputation_id column references domain_reputation(id). This requires
-- migration 1766739001_domain_reputation.sql to have been applied first to create
-- the domain_reputation table. Supabase applies migrations in filename-sort order,
-- and 1766739001 < 1766739004, so the dependency is satisfied.
--
-- ============================================================================
-- ROLLBACK STRATEGY
-- ============================================================================
--
-- To undo this migration, run:
--
--   DROP INDEX IF EXISTS idx_sources_domain_reputation;
--   DROP INDEX IF EXISTS idx_sources_story_cluster;
--   DROP INDEX IF EXISTS idx_sources_peer_reviewed;
--   ALTER TABLE sources DROP COLUMN IF EXISTS domain_reputation_id;
--   ALTER TABLE sources DROP COLUMN IF EXISTS story_cluster_id;
--   ALTER TABLE sources DROP COLUMN IF EXISTS is_peer_reviewed;
--
-- ============================================================================

-- --------------------------------------------------------------------------
-- COLUMN ADDITIONS
-- --------------------------------------------------------------------------

-- Peer-review flag: NULL = unknown, TRUE = confirmed peer-reviewed,
-- FALSE = pre-print or non-academic source.
ALTER TABLE sources ADD COLUMN IF NOT EXISTS is_peer_reviewed BOOLEAN;

-- Story cluster identifier: groups sources covering the same underlying event.
-- Assigned by StoryClusteringService. NULL = not yet clustered.
ALTER TABLE sources ADD COLUMN IF NOT EXISTS story_cluster_id UUID;

-- Link to the domain's reputation entry. Set during triage when the domain
-- reputation lookup is performed.
-- NOTE: Requires domain_reputation table from migration 1766739001.
ALTER TABLE sources ADD COLUMN IF NOT EXISTS domain_reputation_id UUID
    REFERENCES domain_reputation(id);

-- --------------------------------------------------------------------------
-- INDEXES (sparse / partial -- only index rows with non-NULL values)
-- --------------------------------------------------------------------------

-- Sparse index on peer-review status. Only rows where is_peer_reviewed has been
-- explicitly set (TRUE or FALSE) are indexed. Queries filtering for peer-reviewed
-- sources avoid scanning the majority of rows that are still NULL (unknown).
CREATE INDEX IF NOT EXISTS idx_sources_peer_reviewed
    ON sources (is_peer_reviewed)
    WHERE is_peer_reviewed IS NOT NULL;

-- Sparse index on story cluster membership. Enables fast lookup of all sources
-- within a given cluster for corroboration counting and cluster-level aggregation.
CREATE INDEX IF NOT EXISTS idx_sources_story_cluster
    ON sources (story_cluster_id)
    WHERE story_cluster_id IS NOT NULL;

-- Sparse index on domain reputation linkage. Enables efficient domain-level
-- analytics (e.g., aggregate SQI by domain, find all sources from a domain).
CREATE INDEX IF NOT EXISTS idx_sources_domain_reputation
    ON sources (domain_reputation_id)
    WHERE domain_reputation_id IS NOT NULL;

-- --------------------------------------------------------------------------
-- COLUMN COMMENTS
-- --------------------------------------------------------------------------

COMMENT ON COLUMN sources.is_peer_reviewed IS 'Whether source is peer-reviewed: NULL=unknown, TRUE=peer-reviewed, FALSE=preprint/non-academic';
COMMENT ON COLUMN sources.story_cluster_id IS 'UUID grouping sources that cover the same story/event. Set by StoryClusteringService.';
COMMENT ON COLUMN sources.domain_reputation_id IS 'FK to domain_reputation table. Set during triage for efficient domain-level joins.';

-- --------------------------------------------------------------------------
-- VERIFICATION
-- --------------------------------------------------------------------------

SELECT 'sources table extended with is_peer_reviewed, story_cluster_id, domain_reputation_id' AS status;
