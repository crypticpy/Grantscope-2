-- Migration: source_quality_dedup
-- Created at: 20260213
-- Phase 2, Layer 1.1: Source Quality Scoring & Deduplication
--
-- PURPOSE:
--   Adds quality scoring and deduplication columns to the sources table.
--   These columns support the source_quality.py module which computes a
--   composite quality score (0-100) for each individual source, and tracks
--   the extracted domain and duplicate relationships.
--
-- NEW COLUMNS:
--   quality_score (INTEGER 0-100):
--     Composite quality score computed from content richness (25%), relevance
--     (25%), domain reputation (25%), source credibility (15%), and recency
--     (10%).  Computed by source_quality.score_source() and stored by
--     compute_and_store_quality_score().  NULL = not yet scored.
--
--   domain (TEXT):
--     Registered domain extracted from the source URL (e.g., "austin.gov"
--     from "https://www.austin.gov/news/article").  Extracted by
--     source_quality.extract_domain().  Enables fast domain-level
--     aggregation without re-parsing URLs at query time.
--
--   duplicate_of (UUID FK -> sources.id):
--     Self-referential foreign key pointing to the canonical source when
--     this source has been identified as a duplicate.  SET NULL on delete
--     of the canonical source to prevent cascading deletions.  NULL = not
--     a duplicate (or not yet checked).
--
-- DEPENDS ON:
--   - 1766434548_create_sources_and_relationships.sql (sources table)
--
-- ROLLBACK:
--   DROP INDEX IF EXISTS idx_sources_duplicate_of;
--   DROP INDEX IF EXISTS idx_sources_domain;
--   DROP INDEX IF EXISTS idx_sources_quality_score;
--   ALTER TABLE sources DROP COLUMN IF EXISTS duplicate_of;
--   ALTER TABLE sources DROP COLUMN IF EXISTS domain;
--   ALTER TABLE sources DROP COLUMN IF EXISTS quality_score;
-- ============================================================================

-- ============================================================================
-- COLUMN ADDITIONS
-- ============================================================================

-- Composite quality score: 0-100, computed by source_quality.score_source().
-- NULL means the source has not been scored yet.
ALTER TABLE sources ADD COLUMN IF NOT EXISTS quality_score INTEGER
    CHECK (quality_score BETWEEN 0 AND 100);

-- Extracted registered domain from the source URL.
-- NULL for sources without a URL or where extraction failed.
ALTER TABLE sources ADD COLUMN IF NOT EXISTS domain TEXT;

-- Self-referential FK for deduplication. Points to the canonical source.
-- ON DELETE SET NULL prevents cascading when the canonical source is removed.
ALTER TABLE sources ADD COLUMN IF NOT EXISTS duplicate_of UUID
    REFERENCES sources(id) ON DELETE SET NULL;

-- ============================================================================
-- INDEXES (sparse / partial -- only index rows with non-NULL values)
-- ============================================================================

-- Quality score index for filtering and sorting (e.g., "top quality sources").
-- Partial index excludes unscored sources since they are the majority initially.
CREATE INDEX IF NOT EXISTS idx_sources_quality_score
    ON sources (quality_score)
    WHERE quality_score IS NOT NULL;

-- Domain index for aggregation queries (e.g., "all sources from austin.gov",
-- domain-level quality stats).  Partial index excludes sources without a domain.
CREATE INDEX IF NOT EXISTS idx_sources_domain
    ON sources (domain)
    WHERE domain IS NOT NULL;

-- Duplicate lookup index for deduplication queries (e.g., "find all duplicates
-- of a canonical source").  Partial index excludes non-duplicate sources.
CREATE INDEX IF NOT EXISTS idx_sources_duplicate_of
    ON sources (duplicate_of)
    WHERE duplicate_of IS NOT NULL;

-- ============================================================================
-- COLUMN COMMENTS
-- ============================================================================

COMMENT ON COLUMN sources.quality_score IS 'Composite quality score (0-100) from content richness, relevance, domain reputation, credibility, and recency. NULL=unscored.';
COMMENT ON COLUMN sources.domain IS 'Registered domain extracted from URL (e.g., austin.gov). Used for domain-level aggregation.';
COMMENT ON COLUMN sources.duplicate_of IS 'Self-referential FK to the canonical source when this source is a duplicate. NULL=not a duplicate.';

-- ============================================================================
-- VERIFICATION
-- ============================================================================

SELECT 'sources table extended with quality_score, domain, duplicate_of' AS status;
