-- Migration: proposals
-- Created at: 20260216000003
-- Purpose: Add proposals table for AI-assisted grant proposal drafts with
--          section-based editing. Each proposal links to a card, workstream,
--          and optionally a grant_application.

-- ============================================================================
-- 1. TABLE: proposals
-- ============================================================================

CREATE TABLE IF NOT EXISTS proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- References
    card_id UUID NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    workstream_id UUID NOT NULL REFERENCES workstreams(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    application_id UUID REFERENCES grant_applications(id) ON DELETE SET NULL,

    -- Proposal content
    title TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft', 'in_review', 'final', 'submitted', 'archived'
    )),

    -- Section-based content (each section is independently editable)
    -- Example structure:
    -- {
    --   "executive_summary": {"content": "...", "ai_draft": "...", "last_edited": "..."},
    --   "needs_statement": {"content": "...", "ai_draft": "...", "last_edited": "..."},
    --   "project_description": {"content": "...", "ai_draft": "...", "last_edited": "..."},
    --   "budget_narrative": {"content": "...", "ai_draft": "...", "last_edited": "..."},
    --   "timeline": {"content": "...", "ai_draft": "...", "last_edited": "..."},
    --   "evaluation_plan": {"content": "...", "ai_draft": "...", "last_edited": "..."}
    -- }
    sections JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- AI generation metadata
    ai_model TEXT,
    ai_generation_metadata JSONB DEFAULT '{}'::jsonb,

    -- Review
    reviewer_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    review_notes TEXT,
    reviewed_at TIMESTAMPTZ,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE proposals IS 'AI-assisted grant proposal drafts with section-based editing';
COMMENT ON COLUMN proposals.sections IS 'JSONB storing proposal sections (executive_summary, needs_statement, etc.) with content and AI drafts';

-- ============================================================================
-- 2. INDEXES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_proposals_card_id
    ON proposals(card_id);

CREATE INDEX IF NOT EXISTS idx_proposals_workstream_id
    ON proposals(workstream_id);

CREATE INDEX IF NOT EXISTS idx_proposals_user_id
    ON proposals(user_id);

CREATE INDEX IF NOT EXISTS idx_proposals_status
    ON proposals(status);

CREATE INDEX IF NOT EXISTS idx_proposals_card_workstream
    ON proposals(card_id, workstream_id);

-- ============================================================================
-- 3. ROW LEVEL SECURITY
-- ============================================================================

ALTER TABLE proposals ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'proposals' AND policyname = 'proposals_select_own'
    ) THEN
        CREATE POLICY proposals_select_own
            ON proposals FOR SELECT
            TO authenticated
            USING (auth.uid() = user_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'proposals' AND policyname = 'proposals_insert_own'
    ) THEN
        CREATE POLICY proposals_insert_own
            ON proposals FOR INSERT
            TO authenticated
            WITH CHECK (auth.uid() = user_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'proposals' AND policyname = 'proposals_update_own'
    ) THEN
        CREATE POLICY proposals_update_own
            ON proposals FOR UPDATE
            TO authenticated
            USING (auth.uid() = user_id)
            WITH CHECK (auth.uid() = user_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'proposals' AND policyname = 'proposals_delete_own'
    ) THEN
        CREATE POLICY proposals_delete_own
            ON proposals FOR DELETE
            TO authenticated
            USING (auth.uid() = user_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'proposals' AND policyname = 'proposals_service_role_all'
    ) THEN
        CREATE POLICY proposals_service_role_all
            ON proposals FOR ALL
            TO service_role
            USING (true)
            WITH CHECK (true);
    END IF;
END $$;

-- ============================================================================
-- 4. TRIGGERS
-- ============================================================================

-- Reuse existing update_updated_at() function for proposals
DROP TRIGGER IF EXISTS trigger_proposals_updated_at ON proposals;

CREATE TRIGGER trigger_proposals_updated_at
    BEFORE UPDATE ON proposals
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- ============================================================================
-- 5. VERIFICATION
-- ============================================================================

SELECT 'proposals' AS table_name, COUNT(*) AS row_count FROM proposals;
