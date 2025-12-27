-- Migration: workstream_kanban
-- Created at: 1766437000
-- Purpose: Add kanban board columns to workstream_cards table for research workflow tracking

-- ============================================================================
-- WORKSTREAM_CARDS TABLE ENHANCEMENTS
-- ============================================================================

-- Add status column for kanban column tracking
-- Values: inbox, screening, research, brief, watching, archived
ALTER TABLE workstream_cards
ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'inbox'
    CHECK (status IN ('inbox', 'screening', 'research', 'brief', 'watching', 'archived'));

-- Add position column for ordering cards within a column
ALTER TABLE workstream_cards
ADD COLUMN IF NOT EXISTS position INTEGER DEFAULT 0;

-- Add notes column for user annotations on cards within workstream context
ALTER TABLE workstream_cards
ADD COLUMN IF NOT EXISTS notes TEXT;

-- Add reminder_at column for setting reminders on cards
ALTER TABLE workstream_cards
ADD COLUMN IF NOT EXISTS reminder_at TIMESTAMPTZ;

-- Add added_from column to track how the card was added
-- manual: user explicitly added, auto: matched filters, follow: added when following card
ALTER TABLE workstream_cards
ADD COLUMN IF NOT EXISTS added_from TEXT DEFAULT 'manual'
    CHECK (added_from IN ('manual', 'auto', 'follow'));

-- Add updated_at column for tracking last modification
ALTER TABLE workstream_cards
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- Index for fetching cards by workstream and status (kanban columns)
CREATE INDEX IF NOT EXISTS idx_workstream_cards_status
ON workstream_cards(workstream_id, status);

-- Index for ordering within columns
CREATE INDEX IF NOT EXISTS idx_workstream_cards_position
ON workstream_cards(workstream_id, status, position);

-- Index for reminder queries
CREATE INDEX IF NOT EXISTS idx_workstream_cards_reminder
ON workstream_cards(reminder_at)
WHERE reminder_at IS NOT NULL;

-- ============================================================================
-- TRIGGER FOR UPDATED_AT
-- ============================================================================

-- Reuse the existing update_updated_at() function from 001_complete_schema.sql
-- This function is already used by users, cards, workstreams, and card_notes tables
-- No need to create a new function - just add the trigger

-- Drop existing trigger if exists and recreate
DROP TRIGGER IF EXISTS trigger_workstream_cards_updated_at ON workstream_cards;

CREATE TRIGGER trigger_workstream_cards_updated_at
    BEFORE UPDATE ON workstream_cards
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- ============================================================================
-- COMMENTS FOR DOCUMENTATION
-- ============================================================================

COMMENT ON COLUMN workstream_cards.status IS 'Kanban column: inbox (new), screening (triage), research (investigating), brief (ready for leadership), watching (monitoring), archived (done)';
COMMENT ON COLUMN workstream_cards.position IS 'Order of card within its column (0-indexed, lower = higher in column)';
COMMENT ON COLUMN workstream_cards.notes IS 'User notes specific to this card in this workstream context';
COMMENT ON COLUMN workstream_cards.reminder_at IS 'Optional reminder timestamp for this card';
COMMENT ON COLUMN workstream_cards.added_from IS 'How card was added: manual (user added), auto (matched filters), follow (added when following)';
COMMENT ON COLUMN workstream_cards.updated_at IS 'Last modification timestamp';

-- ============================================================================
-- VERIFICATION
-- ============================================================================

SELECT
    'workstream_cards kanban columns added' as status,
    (SELECT COUNT(*) FROM information_schema.columns
     WHERE table_name = 'workstream_cards'
     AND column_name IN ('status', 'position', 'notes', 'reminder_at', 'added_from', 'updated_at')) as columns_added;
