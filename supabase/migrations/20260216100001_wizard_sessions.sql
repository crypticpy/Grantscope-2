-- Migration: wizard_sessions
-- Created at: 20260216100001
-- Purpose: Add wizard_sessions table for guided grant application wizard.
--          Each session links to a chat conversation (for the AI interview),
--          optionally to a card (the grant opportunity), and optionally to a
--          proposal (the output). Also extends chat_conversations scope to
--          include 'wizard'.

-- ============================================================================
-- 1. TABLE: wizard_sessions
-- ============================================================================

CREATE TABLE wizard_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- References
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES chat_conversations(id) ON DELETE SET NULL,
    proposal_id UUID REFERENCES proposals(id) ON DELETE SET NULL,
    card_id UUID REFERENCES cards(id) ON DELETE SET NULL,

    -- Wizard state
    entry_path TEXT NOT NULL CHECK (entry_path IN ('have_grant', 'find_grant')),
    current_step INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'in_progress'
        CHECK (status IN ('in_progress', 'completed', 'abandoned')),

    -- Structured data collected during the wizard
    grant_context JSONB DEFAULT '{}'::jsonb,
    interview_data JSONB DEFAULT '{}'::jsonb,
    plan_data JSONB DEFAULT '{}'::jsonb,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE wizard_sessions IS 'Guided grant application wizard sessions tracking progress through AI-powered interviews';
COMMENT ON COLUMN wizard_sessions.entry_path IS 'How the user entered the wizard: have_grant (known opportunity) or find_grant (discovery)';
COMMENT ON COLUMN wizard_sessions.grant_context IS 'JSONB storing parsed grant requirements, dates, eligibility, etc.';
COMMENT ON COLUMN wizard_sessions.interview_data IS 'JSONB storing AI interview Q&A and extracted information';
COMMENT ON COLUMN wizard_sessions.plan_data IS 'JSONB storing generated plan: staffing, budget, timeline, metrics';

-- ============================================================================
-- 2. INDEXES
-- ============================================================================

CREATE INDEX idx_wizard_sessions_user ON wizard_sessions(user_id, status);
CREATE INDEX idx_wizard_sessions_updated ON wizard_sessions(updated_at DESC);

-- ============================================================================
-- 3. ROW LEVEL SECURITY
-- ============================================================================

ALTER TABLE wizard_sessions ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'wizard_sessions' AND policyname = 'wizard_sessions_select_own'
    ) THEN
        CREATE POLICY wizard_sessions_select_own
            ON wizard_sessions FOR SELECT
            TO authenticated
            USING (auth.uid() = user_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'wizard_sessions' AND policyname = 'wizard_sessions_insert_own'
    ) THEN
        CREATE POLICY wizard_sessions_insert_own
            ON wizard_sessions FOR INSERT
            TO authenticated
            WITH CHECK (auth.uid() = user_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'wizard_sessions' AND policyname = 'wizard_sessions_update_own'
    ) THEN
        CREATE POLICY wizard_sessions_update_own
            ON wizard_sessions FOR UPDATE
            TO authenticated
            USING (auth.uid() = user_id)
            WITH CHECK (auth.uid() = user_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'wizard_sessions' AND policyname = 'wizard_sessions_delete_own'
    ) THEN
        CREATE POLICY wizard_sessions_delete_own
            ON wizard_sessions FOR DELETE
            TO authenticated
            USING (auth.uid() = user_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'wizard_sessions' AND policyname = 'wizard_sessions_service_role_all'
    ) THEN
        CREATE POLICY wizard_sessions_service_role_all
            ON wizard_sessions FOR ALL
            TO service_role
            USING (true)
            WITH CHECK (true);
    END IF;
END $$;

-- ============================================================================
-- 4. EXTEND CHAT SCOPE
-- ============================================================================

-- Add 'wizard' to chat_conversations scope CHECK constraint
ALTER TABLE chat_conversations DROP CONSTRAINT IF EXISTS chat_conversations_scope_check;
ALTER TABLE chat_conversations ADD CONSTRAINT chat_conversations_scope_check
    CHECK (scope IN ('signal', 'workstream', 'global', 'wizard'));

-- ============================================================================
-- 5. TRIGGERS
-- ============================================================================

-- Reuse existing update_updated_at() function for wizard_sessions
DROP TRIGGER IF EXISTS trigger_wizard_sessions_updated_at ON wizard_sessions;

CREATE TRIGGER trigger_wizard_sessions_updated_at
    BEFORE UPDATE ON wizard_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- ============================================================================
-- 6. VERIFICATION
-- ============================================================================

SELECT 'wizard_sessions' AS table_name, COUNT(*) AS row_count FROM wizard_sessions;
