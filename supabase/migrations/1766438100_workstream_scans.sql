-- ============================================================================
-- Workstream Targeted Scans
-- ============================================================================
-- Enables users to run lightweight, focused discovery scans scoped to their
-- workstream's metadata (keywords, pillars, horizon). Discovered cards are
-- added to the global pool and auto-added to the user's workstream inbox.

-- Tracking table for workstream scan jobs
CREATE TABLE IF NOT EXISTS workstream_scans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workstream_id UUID NOT NULL REFERENCES workstreams(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    
    -- Job status
    status TEXT NOT NULL DEFAULT 'queued' 
        CHECK (status IN ('queued', 'running', 'completed', 'failed')),
    
    -- Configuration snapshot (keywords, pillars, horizon at scan time)
    config JSONB NOT NULL DEFAULT '{}',
    
    -- Results summary
    results JSONB DEFAULT NULL,
    -- Expected structure:
    -- {
    --   "queries_executed": 12,
    --   "sources_fetched": 45,
    --   "sources_by_category": {"news": 15, "tech_blog": 12, ...},
    --   "cards_created": 4,
    --   "cards_enriched": 2,
    --   "cards_added_to_workstream": 6,
    --   "duplicates_skipped": 8
    -- }
    
    -- Timestamps
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Error handling
    error_message TEXT
);

-- Indexes for efficient querying
CREATE INDEX idx_workstream_scans_status ON workstream_scans(status);
CREATE INDEX idx_workstream_scans_workstream ON workstream_scans(workstream_id);
CREATE INDEX idx_workstream_scans_user ON workstream_scans(user_id);
CREATE INDEX idx_workstream_scans_created ON workstream_scans(created_at DESC);

-- Index for rate limiting query (scans per workstream per day)
CREATE INDEX idx_workstream_scans_rate_limit 
    ON workstream_scans(workstream_id, created_at DESC);

-- ============================================================================
-- Row Level Security
-- ============================================================================

ALTER TABLE workstream_scans ENABLE ROW LEVEL SECURITY;

-- Users can view scans for workstreams they own
CREATE POLICY "Users can view own workstream scans"
    ON workstream_scans FOR SELECT
    USING (
        user_id = auth.uid() OR
        workstream_id IN (
            SELECT id FROM workstreams WHERE user_id = auth.uid()
        )
    );

-- Users can create scans for their own workstreams
CREATE POLICY "Users can create scans for own workstreams"
    ON workstream_scans FOR INSERT
    WITH CHECK (
        user_id = auth.uid() AND
        workstream_id IN (
            SELECT id FROM workstreams WHERE user_id = auth.uid()
        )
    );

-- Service role can do everything (for worker)
CREATE POLICY "Service role full access to workstream_scans"
    ON workstream_scans FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- ============================================================================
-- Helper function: Check rate limit (2 scans per workstream per day)
-- ============================================================================

CREATE OR REPLACE FUNCTION check_workstream_scan_rate_limit(
    p_workstream_id UUID
) RETURNS BOOLEAN AS $$
DECLARE
    scan_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO scan_count
    FROM workstream_scans
    WHERE workstream_id = p_workstream_id
      AND created_at > NOW() - INTERVAL '24 hours';
    
    RETURN scan_count < 2;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON TABLE workstream_scans IS 
    'Tracks workstream-specific targeted discovery scans';
COMMENT ON FUNCTION check_workstream_scan_rate_limit IS 
    'Returns TRUE if workstream has fewer than 2 scans in last 24 hours';
