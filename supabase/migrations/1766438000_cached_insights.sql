-- Migration: cached_insights
-- Created at: 1766438000
-- Description: Cache table for AI-generated strategic insights to avoid redundant API calls

-- ============================================================================
-- CACHED INSIGHTS TABLE
-- Stores AI-generated insights with TTL-based invalidation
-- ============================================================================

CREATE TABLE IF NOT EXISTS cached_insights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Cache key components
    pillar_filter TEXT,  -- NULL for "all pillars", or pillar code like "CH"
    insight_limit INTEGER DEFAULT 5,
    cache_date DATE NOT NULL DEFAULT CURRENT_DATE,  -- Date the insights were generated for
    
    -- Cached content
    insights_json JSONB NOT NULL,  -- Full InsightsResponse as JSON
    
    -- Metadata for cache validation
    top_card_ids TEXT[] NOT NULL,  -- IDs of cards used to generate insights (for invalidation)
    card_data_hash TEXT NOT NULL,  -- Hash of card scores for change detection
    
    -- AI generation metadata
    ai_model_used TEXT,
    generation_time_ms INTEGER,  -- How long AI generation took
    
    -- Timestamps
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '24 hours'),
    
    -- Ensure one cache entry per filter combination per day
    UNIQUE(pillar_filter, insight_limit, cache_date)
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Fast lookup by cache key
CREATE INDEX IF NOT EXISTS idx_cached_insights_lookup
    ON cached_insights(pillar_filter, insight_limit, cache_date)
    WHERE expires_at > NOW();

-- Clean up expired entries
CREATE INDEX IF NOT EXISTS idx_cached_insights_expires
    ON cached_insights(expires_at);

-- ============================================================================
-- ROW LEVEL SECURITY
-- ============================================================================

ALTER TABLE cached_insights ENABLE ROW LEVEL SECURITY;

-- All authenticated users can read cached insights
CREATE POLICY "Authenticated users can read cached insights"
    ON cached_insights FOR SELECT
    TO authenticated
    USING (true);

-- Service role can manage cache
CREATE POLICY "Service role full access on cached_insights"
    ON cached_insights FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ============================================================================
-- CACHE CLEANUP FUNCTION
-- Removes expired cache entries (can be called periodically)
-- ============================================================================

CREATE OR REPLACE FUNCTION cleanup_expired_insights()
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM public.cached_insights
    WHERE expires_at < NOW();
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$;

GRANT EXECUTE ON FUNCTION cleanup_expired_insights() TO service_role;

-- ============================================================================
-- HELPER FUNCTION: Check if cache is valid
-- Returns cached insights if valid, NULL if cache miss or stale
-- ============================================================================

CREATE OR REPLACE FUNCTION get_cached_insights(
    p_pillar_filter TEXT DEFAULT NULL,
    p_limit INTEGER DEFAULT 5
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    cached_data JSONB;
BEGIN
    SELECT insights_json INTO cached_data
    FROM public.cached_insights
    WHERE 
        (pillar_filter IS NOT DISTINCT FROM p_pillar_filter)
        AND insight_limit = p_limit
        AND cache_date = CURRENT_DATE
        AND expires_at > NOW()
    LIMIT 1;
    
    RETURN cached_data;
END;
$$;

GRANT EXECUTE ON FUNCTION get_cached_insights(TEXT, INTEGER) TO authenticated;
GRANT EXECUTE ON FUNCTION get_cached_insights(TEXT, INTEGER) TO service_role;

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE cached_insights IS 'Cache for AI-generated strategic insights with 24-hour TTL';
COMMENT ON COLUMN cached_insights.pillar_filter IS 'NULL for all pillars, or pillar code (CH, EW, etc.)';
COMMENT ON COLUMN cached_insights.card_data_hash IS 'Hash of input card data to detect when regeneration is needed';
COMMENT ON COLUMN cached_insights.top_card_ids IS 'Card IDs used for generation - for cache invalidation on card updates';

-- ============================================================================
-- DONE
-- ============================================================================

SELECT 'cached_insights table created' as status;
