-- Discovery Schedule settings
-- Phase 3, Layer 2.3: Scheduled Discovery Runs

CREATE TABLE IF NOT EXISTS discovery_schedule (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL DEFAULT 'default',
    enabled BOOLEAN DEFAULT TRUE,
    cron_expression TEXT DEFAULT '0 6 * * *',  -- Daily at 6 AM (reference only)
    timezone TEXT DEFAULT 'America/Chicago',     -- Austin's timezone
    interval_hours INTEGER DEFAULT 24,           -- Run every N hours
    max_search_queries_per_run INTEGER DEFAULT 20,
    pillars_to_scan TEXT[] DEFAULT ARRAY['CH', 'MC', 'HS', 'EC', 'ES', 'CE'],
    process_rss_first BOOLEAN DEFAULT TRUE,
    last_run_at TIMESTAMPTZ,
    next_run_at TIMESTAMPTZ,
    last_run_status TEXT,
    last_run_summary JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert default schedule (next run = now, so it triggers on first worker cycle)
INSERT INTO discovery_schedule (name, enabled, cron_expression, timezone, next_run_at)
VALUES ('default', true, '0 6 * * *', 'America/Chicago', NOW() + INTERVAL '24 hours')
ON CONFLICT DO NOTHING;

-- Index for the worker polling query
CREATE INDEX IF NOT EXISTS idx_discovery_schedule_enabled_next
    ON discovery_schedule(next_run_at)
    WHERE enabled = TRUE;
