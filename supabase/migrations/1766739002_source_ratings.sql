-- Migration: source_ratings
-- Created at: 1766739002
-- Task: 0.2 from DEV_PLAN_Information_Quality.md
--
-- PURPOSE:
--   Creates the source_ratings table for per-user quality and municipal
--   relevance ratings on individual sources. This enables users to rate sources
--   they encounter during card review, discovery triage, or workstream research.
--
-- Ratings serve two purposes:
--
--   1. Display: Shown alongside AI scores in the SourcesTab to provide human
--      context on source trustworthiness and municipal relevance.
--
--   2. Aggregation: A nightly job aggregates source_ratings by domain into the
--      domain_reputation table (user_quality_avg, user_relevance_avg,
--      user_rating_count), feeding the composite reputation score used by the
--      discovery pipeline's triage step and the Source Quality Index (SQI).
--
-- Relationship to domain_reputation:
--   source_ratings (per-source, per-user) --> aggregated into -->
--   domain_reputation (per-domain, system-wide averages)
--
-- ROLLBACK:
--   DROP TRIGGER IF EXISTS trigger_source_ratings_updated_at ON source_ratings;
--   DROP TABLE IF EXISTS source_ratings;
-- ============================================================================

-- ============================================================================
-- SOURCE RATINGS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS source_ratings (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Foreign keys
    source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Quality rating: 1-5 star scale
    -- 1 = Unreliable/propaganda, 2 = Poor quality, 3 = Acceptable,
    -- 4 = Good quality, 5 = Excellent/authoritative
    quality_rating INTEGER NOT NULL CHECK (quality_rating BETWEEN 1 AND 5),

    -- Municipal relevance assessment
    -- high: directly impacts Austin operations or policy
    -- medium: tangentially relevant to municipal concerns
    -- low: loosely related, worth monitoring
    -- not_relevant: no meaningful connection to municipal operations
    relevance_rating TEXT NOT NULL CHECK (relevance_rating IN ('high', 'medium', 'low', 'not_relevant')),

    -- Optional brief note (Twitter-length constraint for conciseness)
    comment TEXT CHECK (char_length(comment) <= 280),

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- One rating per user per source; upsert pattern expected
    UNIQUE (source_id, user_id)
);

-- ============================================================================
-- COLUMN COMMENTS
-- ============================================================================

COMMENT ON TABLE source_ratings IS 'Per-user quality and relevance ratings on individual sources, aggregated into domain_reputation';
COMMENT ON COLUMN source_ratings.source_id IS 'The source being rated';
COMMENT ON COLUMN source_ratings.user_id IS 'The user who submitted the rating';
COMMENT ON COLUMN source_ratings.quality_rating IS 'Quality star rating 1-5 (1=unreliable, 5=authoritative)';
COMMENT ON COLUMN source_ratings.relevance_rating IS 'Municipal relevance assessment: high, medium, low, not_relevant';
COMMENT ON COLUMN source_ratings.comment IS 'Optional brief note, max 280 characters';

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- Lookup all ratings for a source (for aggregate display and domain rollup)
CREATE INDEX IF NOT EXISTS idx_source_ratings_source
    ON source_ratings (source_id);

-- Lookup all ratings by a user (for user profile / history)
CREATE INDEX IF NOT EXISTS idx_source_ratings_user
    ON source_ratings (user_id);

-- Filter/sort by quality rating (for analytics and reporting)
CREATE INDEX IF NOT EXISTS idx_source_ratings_quality
    ON source_ratings (quality_rating);

-- ============================================================================
-- TRIGGER FOR UPDATED_AT
-- ============================================================================

-- Reuse the existing update_updated_at() function from 001_complete_schema.sql
DROP TRIGGER IF EXISTS trigger_source_ratings_updated_at ON source_ratings;

CREATE TRIGGER trigger_source_ratings_updated_at
    BEFORE UPDATE ON source_ratings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- ============================================================================
-- ROW LEVEL SECURITY
-- ============================================================================

-- Enable RLS
ALTER TABLE source_ratings ENABLE ROW LEVEL SECURITY;

-- SELECT: All authenticated users can read all ratings
-- Needed for aggregate display (average stars, relevance breakdown)
CREATE POLICY "Source ratings viewable by all authenticated users"
    ON source_ratings FOR SELECT
    TO authenticated
    USING (true);

-- INSERT: Users can only insert ratings for themselves
CREATE POLICY "Users can create their own source ratings"
    ON source_ratings FOR INSERT
    TO authenticated
    WITH CHECK (user_id = auth.uid());

-- UPDATE: Users can only update their own ratings
CREATE POLICY "Users can update their own source ratings"
    ON source_ratings FOR UPDATE
    TO authenticated
    USING (user_id = auth.uid());

-- DELETE: Users can only delete their own ratings
CREATE POLICY "Users can delete their own source ratings"
    ON source_ratings FOR DELETE
    TO authenticated
    USING (user_id = auth.uid());

-- Service role: full access for backend aggregation jobs
CREATE POLICY "Service role full access on source_ratings"
    ON source_ratings FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ============================================================================
-- VERIFICATION
-- ============================================================================

SELECT
    'source_ratings table created' AS status,
    (SELECT COUNT(*) FROM information_schema.tables
     WHERE table_name = 'source_ratings') AS table_exists,
    (SELECT COUNT(*) FROM information_schema.columns
     WHERE table_name = 'source_ratings') AS column_count;
