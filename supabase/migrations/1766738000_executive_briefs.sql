-- Migration: executive_briefs
-- Created at: 1766738000
-- Purpose: Add executive_briefs table for storing AI-generated leadership briefs

-- ============================================================================
-- EXECUTIVE BRIEFS TABLE
-- ============================================================================

-- Executive briefs are comprehensive leadership documents generated from cards
-- in the "brief" column of workstream kanban boards. They synthesize card data,
-- user notes, related cards, and source materials into actionable intelligence
-- for City of Austin decision-makers.

CREATE TABLE IF NOT EXISTS executive_briefs (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Foreign keys
    workstream_card_id UUID NOT NULL REFERENCES workstream_cards(id) ON DELETE CASCADE,
    card_id UUID NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    created_by UUID NOT NULL REFERENCES auth.users(id),

    -- Status tracking
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'generating', 'completed', 'failed')),

    -- Brief content
    content JSONB, -- Structured brief content (sections as JSON for programmatic access)
    content_markdown TEXT, -- Full brief as markdown for display/export
    summary TEXT, -- Executive summary extracted for quick display/preview

    -- Generation metadata
    generated_at TIMESTAMPTZ, -- When generation completed
    generation_time_ms INTEGER, -- How long generation took
    model_used TEXT, -- Which AI model was used (e.g., 'gpt-4o')
    prompt_tokens INTEGER, -- Token usage for cost tracking
    completion_tokens INTEGER,

    -- Error handling
    error_message TEXT, -- Error details if generation failed

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    UNIQUE(workstream_card_id) -- One brief per workstream card
);

-- Add comments for documentation
COMMENT ON TABLE executive_briefs IS 'AI-generated executive briefs for workstream cards in the brief column';
COMMENT ON COLUMN executive_briefs.workstream_card_id IS 'The workstream card this brief was generated for';
COMMENT ON COLUMN executive_briefs.card_id IS 'The underlying intelligence card (for cross-workstream queries)';
COMMENT ON COLUMN executive_briefs.created_by IS 'User who triggered the brief generation';
COMMENT ON COLUMN executive_briefs.status IS 'Generation status: pending, generating, completed, or failed';
COMMENT ON COLUMN executive_briefs.content IS 'Structured JSON with brief sections for programmatic access';
COMMENT ON COLUMN executive_briefs.content_markdown IS 'Full brief as markdown for rendering and export';
COMMENT ON COLUMN executive_briefs.summary IS 'Executive summary section for quick preview';
COMMENT ON COLUMN executive_briefs.generated_at IS 'Timestamp when brief generation completed';
COMMENT ON COLUMN executive_briefs.generation_time_ms IS 'Time taken to generate brief in milliseconds';
COMMENT ON COLUMN executive_briefs.model_used IS 'AI model used for generation (e.g., gpt-4o)';

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- Primary lookup: get brief for a workstream card
CREATE INDEX IF NOT EXISTS idx_executive_briefs_workstream_card
    ON executive_briefs(workstream_card_id);

-- Cross-workstream lookup: find all briefs for a card
CREATE INDEX IF NOT EXISTS idx_executive_briefs_card
    ON executive_briefs(card_id);

-- Status queries: find pending/generating briefs
CREATE INDEX IF NOT EXISTS idx_executive_briefs_status
    ON executive_briefs(status)
    WHERE status IN ('pending', 'generating');

-- User's briefs: find briefs created by a user
CREATE INDEX IF NOT EXISTS idx_executive_briefs_created_by
    ON executive_briefs(created_by);

-- Recent briefs: sorted by generation time
CREATE INDEX IF NOT EXISTS idx_executive_briefs_generated_at
    ON executive_briefs(generated_at DESC)
    WHERE generated_at IS NOT NULL;

-- ============================================================================
-- TRIGGER FOR UPDATED_AT
-- ============================================================================

-- Reuse the existing update_updated_at() function from 001_complete_schema.sql
DROP TRIGGER IF EXISTS trigger_executive_briefs_updated_at ON executive_briefs;

CREATE TRIGGER trigger_executive_briefs_updated_at
    BEFORE UPDATE ON executive_briefs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- ============================================================================
-- ROW LEVEL SECURITY
-- ============================================================================

-- Enable RLS
ALTER TABLE executive_briefs ENABLE ROW LEVEL SECURITY;

-- Policy: Briefs are viewable by all authenticated users
-- Briefs are considered shareable assets within the organization
CREATE POLICY "Briefs are viewable by all authenticated users"
    ON executive_briefs FOR SELECT
    TO authenticated
    USING (true);

-- Policy: Users can create briefs for cards in their own workstreams
CREATE POLICY "Users can create briefs for their workstream cards"
    ON executive_briefs FOR INSERT
    TO authenticated
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM workstream_cards wc
            JOIN workstreams w ON wc.workstream_id = w.id
            WHERE wc.id = workstream_card_id
            AND w.user_id = auth.uid()
        )
    );

-- Policy: Users can update briefs they created (or briefs in their workstreams)
CREATE POLICY "Users can update their own briefs"
    ON executive_briefs FOR UPDATE
    TO authenticated
    USING (
        created_by = auth.uid()
        OR EXISTS (
            SELECT 1 FROM workstream_cards wc
            JOIN workstreams w ON wc.workstream_id = w.id
            WHERE wc.id = workstream_card_id
            AND w.user_id = auth.uid()
        )
    );

-- Policy: Users can delete briefs in their own workstreams
CREATE POLICY "Users can delete briefs in their workstreams"
    ON executive_briefs FOR DELETE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM workstream_cards wc
            JOIN workstreams w ON wc.workstream_id = w.id
            WHERE wc.id = workstream_card_id
            AND w.user_id = auth.uid()
        )
    );

-- ============================================================================
-- VERIFICATION
-- ============================================================================

SELECT
    'executive_briefs table created' as status,
    (SELECT COUNT(*) FROM information_schema.tables
     WHERE table_name = 'executive_briefs') as table_exists,
    (SELECT COUNT(*) FROM information_schema.columns
     WHERE table_name = 'executive_briefs') as column_count;
