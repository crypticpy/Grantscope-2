-- Migration: cards_quality_and_origin
-- Created at: 1766739003
-- Task: 0.3 from DEV_PLAN_Information_Quality.md
--
-- PURPOSE:
--   Adds Source Quality Index (SQI) fields, card origin tracking, and an
--   exploratory flag to the existing cards table.
--
-- WHAT DEPENDS ON THESE FIELDS:
--   - quality_score / quality_breakdown: Populated by the SQI calculation engine
--     (quality_service.py). Displayed in CardDetailPanel, used for sorting/filtering
--     in discovery queue and dashboard analytics. quality_breakdown stores the five
--     SQI sub-scores: source_authority, source_diversity, corroboration, recency,
--     municipal_specificity, plus a calculated_at timestamp.
--   - origin: Displayed as a provenance badge on card detail views. Used by
--     analytics to segment cards by creation method (discovery pipeline vs.
--     workstream scan vs. user-created vs. manual import).
--   - is_exploratory: Flags cards that don't align with any predefined strategic
--     pillar. Surfaced in a dedicated "Exploratory" filter on the Discover page
--     and included in executive brief "emerging signals" sections.
--
-- ROLLBACK:
--   ALTER TABLE cards DROP COLUMN IF EXISTS quality_score;
--   ALTER TABLE cards DROP COLUMN IF EXISTS quality_breakdown;
--   ALTER TABLE cards DROP COLUMN IF EXISTS origin;
--   ALTER TABLE cards DROP COLUMN IF EXISTS is_exploratory;
--   DROP INDEX IF EXISTS idx_cards_quality_score;
--   DROP INDEX IF EXISTS idx_cards_origin;
--   DROP INDEX IF EXISTS idx_cards_exploratory;
-- ============================================================================

-- ============================================================================
-- ADD COLUMNS
-- ============================================================================

-- Source Quality Index composite score (0-100). Recalculated by backend service
-- whenever a card's sources change. Higher = more credible / better sourced.
ALTER TABLE cards ADD COLUMN IF NOT EXISTS quality_score INTEGER DEFAULT 0
    CHECK (quality_score BETWEEN 0 AND 100);

-- Breakdown of the five SQI sub-component scores as JSONB.
-- Expected shape:
--   {
--     "source_authority": <0-100>,      -- Domain reputation tier weighting
--     "source_diversity": <0-100>,      -- Variety of source types
--     "corroboration": <0-100>,         -- Multiple independent sources agreeing
--     "recency": <0-100>,              -- Freshness of source material
--     "municipal_specificity": <0-100>, -- Relevance to municipal operations
--     "calculated_at": "<ISO 8601>"     -- When the score was last computed
--   }
ALTER TABLE cards ADD COLUMN IF NOT EXISTS quality_breakdown JSONB DEFAULT '{}';

-- How this card was originally created. Used for provenance tracking and
-- analytics segmentation.
--   discovery       = automated discovery pipeline
--   workstream_scan = workstream-triggered research scan
--   user_created    = manually created by a user through the UI
--   manual          = imported via admin tools or bulk upload
ALTER TABLE cards ADD COLUMN IF NOT EXISTS origin TEXT DEFAULT 'discovery'
    CHECK (origin IN ('discovery', 'workstream_scan', 'user_created', 'manual'));

-- Flag for cards that don't align with any predefined strategic pillar.
-- These represent emerging signals that may warrant new pillar consideration.
ALTER TABLE cards ADD COLUMN IF NOT EXISTS is_exploratory BOOLEAN DEFAULT FALSE;

-- ============================================================================
-- BACKFILL EXISTING DATA
-- ============================================================================

-- All existing cards were created by the discovery pipeline, so set origin
-- explicitly. The DEFAULT handles new rows, but existing NULLs (if any from
-- the ADD COLUMN) need to be set.
UPDATE cards SET origin = 'discovery' WHERE origin IS NULL;

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Sort by quality score descending (highest quality first in listings)
CREATE INDEX IF NOT EXISTS idx_cards_quality_score ON cards (quality_score DESC);

-- Filter cards by creation method
CREATE INDEX IF NOT EXISTS idx_cards_origin ON cards (origin);

-- Sparse/partial index for exploratory cards -- only indexes rows where
-- is_exploratory = TRUE, keeping the index small and fast
CREATE INDEX IF NOT EXISTS idx_cards_exploratory ON cards (is_exploratory) WHERE is_exploratory = TRUE;

-- ============================================================================
-- COLUMN COMMENTS
-- ============================================================================

COMMENT ON COLUMN cards.quality_score IS 'Source Quality Index (SQI) composite score 0-100. Recalculated when sources change.';
COMMENT ON COLUMN cards.quality_breakdown IS 'JSONB breakdown of SQI sub-scores: source_authority, source_diversity, corroboration, recency, municipal_specificity, calculated_at';
COMMENT ON COLUMN cards.origin IS 'How the card was created: discovery, workstream_scan, user_created, or manual';
COMMENT ON COLUMN cards.is_exploratory IS 'True for cards that do not align with any predefined strategic pillar';

-- ============================================================================
-- DONE
-- ============================================================================
SELECT 'cards table extended with quality_score, quality_breakdown, origin, is_exploratory' AS status;
