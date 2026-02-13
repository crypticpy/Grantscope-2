-- Migration: signal_sources junction table for many-to-many source-to-signal relationships
-- A source can belong to multiple signals; a signal can draw from many sources.

CREATE TABLE IF NOT EXISTS signal_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    card_id UUID NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,

    -- Relationship metadata
    relationship_type TEXT NOT NULL DEFAULT 'primary'
        CHECK (relationship_type IN ('primary', 'supporting', 'contextual', 'contrary')),
    confidence REAL CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    agent_reasoning TEXT,

    -- Tracking
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT DEFAULT 'signal_agent',

    UNIQUE(card_id, source_id)
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_signal_sources_card ON signal_sources(card_id);
CREATE INDEX IF NOT EXISTS idx_signal_sources_source ON signal_sources(source_id);
CREATE INDEX IF NOT EXISTS idx_signal_sources_type ON signal_sources(relationship_type);

-- RLS
ALTER TABLE signal_sources ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated users can view signal_sources"
    ON signal_sources FOR SELECT TO authenticated USING (true);

CREATE POLICY "Service role full access on signal_sources"
    ON signal_sources FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Track agent stats on discovery runs
ALTER TABLE discovery_runs ADD COLUMN IF NOT EXISTS signal_agent_stats JSONB DEFAULT '{}';
