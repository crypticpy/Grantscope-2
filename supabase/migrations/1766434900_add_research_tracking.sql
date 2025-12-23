-- Migration: add_research_tracking
-- Created at: 1766434900
-- Description: Add deep research timestamps, rate limiting, and research tasks table

-- ============================================================================
-- Add deep research columns to cards table
-- ============================================================================

-- Timestamp for when deep research was last performed
ALTER TABLE cards ADD COLUMN IF NOT EXISTS deep_research_at TIMESTAMPTZ;

-- Rate limiting columns (2 deep research per day per card)
ALTER TABLE cards ADD COLUMN IF NOT EXISTS deep_research_count_today INTEGER DEFAULT 0;
ALTER TABLE cards ADD COLUMN IF NOT EXISTS deep_research_reset_date DATE DEFAULT CURRENT_DATE;

-- ============================================================================
-- Create research_tasks table for tracking async research jobs
-- ============================================================================

CREATE TABLE IF NOT EXISTS research_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    card_id UUID REFERENCES cards(id) ON DELETE SET NULL,
    workstream_id UUID REFERENCES workstreams(id) ON DELETE SET NULL,

    -- Task configuration
    task_type TEXT NOT NULL CHECK (task_type IN ('update', 'deep_research', 'workstream_analysis')),
    query TEXT,

    -- Status tracking
    status TEXT DEFAULT 'queued' CHECK (status IN ('queued', 'processing', 'completed', 'failed')),

    -- Results
    result_summary JSONB DEFAULT '{}',
    error_message TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

-- ============================================================================
-- Enable RLS on research_tasks
-- ============================================================================

ALTER TABLE research_tasks ENABLE ROW LEVEL SECURITY;

-- Users can view their own research tasks
CREATE POLICY "Users can view own research tasks"
    ON research_tasks FOR SELECT
    USING (user_id = auth.uid());

-- Users can create research tasks (for themselves)
CREATE POLICY "Users can create own research tasks"
    ON research_tasks FOR INSERT
    WITH CHECK (user_id = auth.uid());

-- Users can update their own research tasks (for status updates)
CREATE POLICY "Users can update own research tasks"
    ON research_tasks FOR UPDATE
    USING (user_id = auth.uid());

-- Service role can do everything (for backend processing)
CREATE POLICY "Service role full access on research_tasks"
    ON research_tasks FOR ALL
    USING (auth.role() = 'service_role');

-- ============================================================================
-- Indexes for efficient queries
-- ============================================================================

-- Index for finding tasks by card and status (for checking active tasks)
CREATE INDEX IF NOT EXISTS idx_research_tasks_card_status
    ON research_tasks(card_id, status);

-- Index for listing user's tasks by creation date
CREATE INDEX IF NOT EXISTS idx_research_tasks_user_created
    ON research_tasks(user_id, created_at DESC);

-- Index for finding processing tasks (for background job monitoring)
CREATE INDEX IF NOT EXISTS idx_research_tasks_status
    ON research_tasks(status)
    WHERE status IN ('queued', 'processing');

-- ============================================================================
-- Function to increment deep research count (called via RPC)
-- ============================================================================

CREATE OR REPLACE FUNCTION increment_deep_research_count(p_card_id UUID)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_today DATE := CURRENT_DATE;
BEGIN
    UPDATE cards
    SET
        deep_research_count_today = CASE
            WHEN deep_research_reset_date = v_today THEN deep_research_count_today + 1
            ELSE 1
        END,
        deep_research_reset_date = v_today
    WHERE id = p_card_id;
END;
$$;

-- Grant execute permission to authenticated users
GRANT EXECUTE ON FUNCTION increment_deep_research_count(UUID) TO authenticated;

-- ============================================================================
-- Comments for documentation
-- ============================================================================

COMMENT ON TABLE research_tasks IS 'Tracks async research tasks triggered by users for cards or workstreams';
COMMENT ON COLUMN research_tasks.task_type IS 'Type of research: update (quick), deep_research (comprehensive), workstream_analysis';
COMMENT ON COLUMN research_tasks.status IS 'Task lifecycle: queued -> processing -> completed/failed';
COMMENT ON COLUMN research_tasks.result_summary IS 'JSON containing sources_found, sources_added, cost, etc.';

COMMENT ON COLUMN cards.deep_research_at IS 'Timestamp of last deep research performed on this card';
COMMENT ON COLUMN cards.deep_research_count_today IS 'Rate limiting: number of deep research runs today (max 2)';
COMMENT ON COLUMN cards.deep_research_reset_date IS 'Date when deep_research_count_today was last reset';
