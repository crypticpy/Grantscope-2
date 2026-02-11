-- Migration: discovery_quality_stats
-- Created at: 1766739005
-- Task: 0.5 from DEV_PLAN_Information_Quality.md
--
-- PURPOSE:
--   Add quality_stats JSONB column to discovery_runs for tracking
--   information quality metrics during discovery pipeline execution.
--
-- BACKGROUND:
--   The discovery pipeline applies multiple quality filters (content length,
--   freshness, domain reputation, story clustering) before promoting sources
--   into cards. Previously these filter outcomes were not persisted, making it
--   impossible to audit or trend quality over time. This migration adds a
--   dedicated quality_stats column so every run records exactly how many
--   sources were filtered and why.
--
-- quality_stats JSONB keys (documented here; not enforced by schema):
--   content_filter_count     (integer) - Sources rejected for insufficient content (<100 chars)
--   freshness_filter_count   (integer) - Sources rejected for being too old
--   preprint_count           (integer) - Academic sources identified as pre-prints
--   story_cluster_count      (integer) - Unique story clusters identified across sources
--   domain_reputation_lookups(integer) - Number of domains looked up during triage
--   tier1_source_count       (integer) - Sources originating from Tier 1 (authoritative) domains
--   tier2_source_count       (integer) - Sources originating from Tier 2 (credible) domains
--   tier3_source_count       (integer) - Sources originating from Tier 3 (general) domains
--   untiered_source_count    (integer) - Sources from domains with no tier classification
--   confidence_adjustments   (integer) - Number of AI confidence scores adjusted by domain reputation
--
-- cards.discovery_metadata JSONB will also receive a new key written by the
-- pipeline (no schema change required since the column is already JSONB):
--   scores_are_defaults      (boolean) - True when AI scores are parse-error fallbacks
--
-- ROLLBACK:
--   ALTER TABLE discovery_runs DROP COLUMN IF EXISTS quality_stats;
-- ============================================================================

-- Add quality_stats JSONB column to discovery_runs
ALTER TABLE discovery_runs ADD COLUMN IF NOT EXISTS quality_stats JSONB DEFAULT '{}';

-- Document the column purpose
COMMENT ON COLUMN discovery_runs.quality_stats IS
    'Per-run quality metrics: content/freshness filter counts, domain tier distribution, '
    'story cluster count, confidence adjustments. Written by the discovery pipeline at completion.';

-- Update the comment on cards.discovery_metadata to reflect the new key
COMMENT ON COLUMN cards.discovery_metadata IS
    'JSON with discovery context: queries matched, sources, dedup attempts, '
    'scores_are_defaults (boolean, true when AI scores are parse-error fallbacks)';

-- ============================================================================
-- VERIFICATION
-- ============================================================================

SELECT 'discovery_runs.quality_stats column added successfully' AS status;
