-- Migration: discovered_sources
-- Created at: 1766435002
-- Description: Persistent storage for all sources found during discovery runs
-- This ensures no data is lost even if card creation fails

-- ============================================================================
-- DISCOVERED SOURCES TABLE
-- Stores every source found during discovery, with full context and analysis
-- ============================================================================

CREATE TABLE IF NOT EXISTS discovered_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Link to discovery run
    discovery_run_id UUID NOT NULL REFERENCES discovery_runs(id) ON DELETE CASCADE,

    -- ========================================================================
    -- RAW SOURCE DATA (captured immediately on discovery)
    -- ========================================================================
    url TEXT NOT NULL,
    title TEXT,
    content_snippet TEXT,  -- First 2000 chars of content
    full_content TEXT,     -- Full content if available
    published_at TIMESTAMPTZ,
    source_type TEXT,      -- 'article', 'paper', 'news', 'blog', etc.
    domain TEXT,           -- Extracted domain from URL

    -- Search context
    search_query TEXT,     -- The query that found this source
    query_pillar TEXT,     -- Pillar the query was targeting
    query_priority TEXT,   -- Priority/goal the query was targeting (if any)

    -- ========================================================================
    -- TRIAGE RESULTS (from AI triage)
    -- ========================================================================
    triage_is_relevant BOOLEAN,
    triage_confidence REAL,  -- 0.0 to 1.0
    triage_primary_pillar TEXT,
    triage_reason TEXT,
    triaged_at TIMESTAMPTZ,

    -- ========================================================================
    -- FULL ANALYSIS RESULTS (from deep AI analysis)
    -- ========================================================================
    analysis_summary TEXT,
    analysis_key_excerpts TEXT[],

    -- Classification
    analysis_pillars TEXT[],
    analysis_goals TEXT[],
    analysis_steep_categories TEXT[],
    analysis_anchors TEXT[],
    analysis_horizon TEXT CHECK (analysis_horizon IN ('H1', 'H2', 'H3')),
    analysis_suggested_stage INTEGER,
    analysis_triage_score INTEGER,

    -- Scores (1-5 or 1-9 scale)
    analysis_credibility REAL,
    analysis_novelty REAL,
    analysis_likelihood REAL,
    analysis_impact REAL,
    analysis_relevance REAL,

    -- Timing estimates
    analysis_time_to_awareness_months INTEGER,
    analysis_time_to_prepare_months INTEGER,

    -- Card suggestion
    analysis_suggested_card_name TEXT,
    analysis_is_new_concept BOOLEAN,
    analysis_reasoning TEXT,

    -- Entities extracted
    analysis_entities JSONB DEFAULT '[]',

    analyzed_at TIMESTAMPTZ,

    -- ========================================================================
    -- DEDUPLICATION RESULTS
    -- ========================================================================
    dedup_status TEXT CHECK (dedup_status IN ('unique', 'duplicate', 'enrichment_candidate')),
    dedup_matched_card_id UUID,  -- If matched to existing card
    dedup_similarity_score REAL, -- Similarity to matched card
    deduplicated_at TIMESTAMPTZ,

    -- ========================================================================
    -- FINAL OUTCOME
    -- ========================================================================
    processing_status TEXT NOT NULL DEFAULT 'discovered'
        CHECK (processing_status IN (
            'discovered',      -- Just found
            'triaged',         -- Passed/failed triage
            'analyzed',        -- Full analysis complete
            'deduplicated',    -- Dedup check complete
            'card_created',    -- New card was created
            'card_enriched',   -- Added to existing card
            'filtered_triage', -- Filtered out at triage
            'filtered_blocked',-- Matched blocked topic
            'filtered_duplicate', -- Duplicate of existing
            'error'            -- Processing error
        )),

    -- Link to resulting card (if any)
    resulting_card_id UUID,
    resulting_source_id UUID,  -- Link to sources table entry

    -- Error tracking
    error_message TEXT,
    error_stage TEXT,

    -- Embeddings for future similarity searches
    content_embedding VECTOR(1536),

    -- ========================================================================
    -- METADATA
    -- ========================================================================
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Fast lookup by discovery run
CREATE INDEX IF NOT EXISTS idx_discovered_sources_run_id
    ON discovered_sources(discovery_run_id);

-- Find sources by URL (dedup across runs)
CREATE INDEX IF NOT EXISTS idx_discovered_sources_url
    ON discovered_sources(url);

-- Find sources by status
CREATE INDEX IF NOT EXISTS idx_discovered_sources_status
    ON discovered_sources(processing_status);

-- Find sources that became cards
CREATE INDEX IF NOT EXISTS idx_discovered_sources_card
    ON discovered_sources(resulting_card_id)
    WHERE resulting_card_id IS NOT NULL;

-- Find sources by pillar
CREATE INDEX IF NOT EXISTS idx_discovered_sources_pillar
    ON discovered_sources(triage_primary_pillar);

-- Time-based queries
CREATE INDEX IF NOT EXISTS idx_discovered_sources_created
    ON discovered_sources(created_at DESC);

-- Vector similarity search on content
CREATE INDEX IF NOT EXISTS idx_discovered_sources_embedding
    ON discovered_sources
    USING ivfflat (content_embedding vector_cosine_ops)
    WITH (lists = 100);

-- ============================================================================
-- ROW LEVEL SECURITY
-- ============================================================================

ALTER TABLE discovered_sources ENABLE ROW LEVEL SECURITY;

-- Authenticated users can view discovered sources
CREATE POLICY "Authenticated users can view discovered_sources"
    ON discovered_sources FOR SELECT
    TO authenticated
    USING (true);

-- Service role has full access
CREATE POLICY "Service role full access on discovered_sources"
    ON discovered_sources FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE discovered_sources IS 'Persistent storage for all sources found during discovery runs - ensures no data loss';
COMMENT ON COLUMN discovered_sources.content_snippet IS 'First 2000 chars for quick preview';
COMMENT ON COLUMN discovered_sources.full_content IS 'Complete content for re-analysis if needed';
COMMENT ON COLUMN discovered_sources.processing_status IS 'Current stage in the discovery pipeline';
COMMENT ON COLUMN discovered_sources.content_embedding IS 'Vector embedding for cross-run deduplication';

-- ============================================================================
-- TRIGGER FOR UPDATED_AT
-- ============================================================================

CREATE OR REPLACE FUNCTION update_discovered_sources_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_discovered_sources_updated_at
    BEFORE UPDATE ON discovered_sources
    FOR EACH ROW
    EXECUTE FUNCTION update_discovered_sources_updated_at();
