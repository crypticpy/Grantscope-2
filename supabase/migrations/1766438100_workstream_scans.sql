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
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
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

-- Atomic rate limit check (2 scans per workstream per day)
-- Returns TRUE if under limit, FALSE if limit reached
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

-- Check if workstream has an active (queued or running) scan
-- Returns TRUE if there's an active scan, FALSE otherwise
CREATE OR REPLACE FUNCTION has_active_workstream_scan(
    p_workstream_id UUID
) RETURNS BOOLEAN AS $$
DECLARE
    active_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO active_count
    FROM workstream_scans
    WHERE workstream_id = p_workstream_id
      AND status IN ('queued', 'running');
    
    RETURN active_count > 0;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Atomic scan creation with rate limit and concurrency checks
-- Returns the new scan ID if successful, NULL if blocked
CREATE OR REPLACE FUNCTION create_workstream_scan_atomic(
    p_workstream_id UUID,
    p_user_id UUID,
    p_config JSONB
) RETURNS UUID AS $$
DECLARE
    new_scan_id UUID;
    daily_count INTEGER;
    active_count INTEGER;
BEGIN
    -- Lock the workstream row to prevent race conditions
    PERFORM id FROM workstreams WHERE id = p_workstream_id FOR UPDATE;
    
    -- Check for active scans
    SELECT COUNT(*) INTO active_count
    FROM workstream_scans
    WHERE workstream_id = p_workstream_id
      AND status IN ('queued', 'running');
    
    IF active_count > 0 THEN
        RETURN NULL;  -- Already has active scan
    END IF;
    
    -- Check daily rate limit
    SELECT COUNT(*) INTO daily_count
    FROM workstream_scans
    WHERE workstream_id = p_workstream_id
      AND created_at > NOW() - INTERVAL '24 hours';
    
    IF daily_count >= 2 THEN
        RETURN NULL;  -- Rate limit exceeded
    END IF;
    
    -- Create the scan
    INSERT INTO workstream_scans (workstream_id, user_id, status, config, created_at)
    VALUES (p_workstream_id, p_user_id, 'queued', p_config, NOW())
    RETURNING id INTO new_scan_id;
    
    RETURN new_scan_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON TABLE workstream_scans IS 
    'Tracks workstream-specific targeted discovery scans';
COMMENT ON FUNCTION check_workstream_scan_rate_limit IS 
    'Returns TRUE if workstream has fewer than 2 scans in last 24 hours';
COMMENT ON FUNCTION has_active_workstream_scan IS 
    'Returns TRUE if workstream has a queued or running scan';
COMMENT ON FUNCTION create_workstream_scan_atomic IS 
    'Atomically creates a scan with rate limit and concurrency checks. Returns NULL if blocked.';
