-- Migration: enhance_card_timeline
-- Created at: 1766436102
-- Purpose: Add enhanced stage tracking columns to card_timeline table for trend visualization

-- ============================================================
-- CARD_TIMELINE TABLE - Enhanced Stage Tracking
-- ============================================================
-- These columns support the stage-history endpoint and StageProgressionTimeline
-- visualization component for tracking maturity stage transitions over time.

-- Add old_stage_id column (integer 1-8 representing maturity stage before change)
ALTER TABLE card_timeline ADD COLUMN IF NOT EXISTS old_stage_id INTEGER
    CHECK (old_stage_id IS NULL OR old_stage_id BETWEEN 1 AND 8);

-- Add new_stage_id column (integer 1-8 representing maturity stage after change)
ALTER TABLE card_timeline ADD COLUMN IF NOT EXISTS new_stage_id INTEGER
    CHECK (new_stage_id IS NULL OR new_stage_id BETWEEN 1 AND 8);

-- Add old_horizon column (horizon before stage change: H1, H2, or H3)
ALTER TABLE card_timeline ADD COLUMN IF NOT EXISTS old_horizon TEXT
    CHECK (old_horizon IS NULL OR old_horizon IN ('H1', 'H2', 'H3'));

-- Add new_horizon column (horizon after stage change: H1, H2, or H3)
ALTER TABLE card_timeline ADD COLUMN IF NOT EXISTS new_horizon TEXT
    CHECK (new_horizon IS NULL OR new_horizon IN ('H1', 'H2', 'H3'));

-- Add trigger column for tracking what caused the stage change
ALTER TABLE card_timeline ADD COLUMN IF NOT EXISTS trigger TEXT
    CHECK (trigger IS NULL OR trigger IN ('manual', 'auto-calculated', 'source-update', 'system'));

-- Add reason column for optional explanation of stage change
ALTER TABLE card_timeline ADD COLUMN IF NOT EXISTS reason TEXT;

-- ============================================================
-- CREATE INDEXES for Stage History Queries
-- ============================================================
-- Index for efficient stage-history queries (filtering by event_type='stage_changed')
CREATE INDEX IF NOT EXISTS idx_card_timeline_stage_changes
    ON card_timeline(card_id, created_at DESC)
    WHERE event_type = 'stage_changed';

-- ============================================================
-- COMMENTS for Documentation
-- ============================================================
COMMENT ON COLUMN card_timeline.old_stage_id IS 'Maturity stage (1-8) before this change event';
COMMENT ON COLUMN card_timeline.new_stage_id IS 'Maturity stage (1-8) after this change event';
COMMENT ON COLUMN card_timeline.old_horizon IS 'Horizon (H1/H2/H3) before change. Stages 1-2=H3, 3-5=H2, 6-8=H1';
COMMENT ON COLUMN card_timeline.new_horizon IS 'Horizon (H1/H2/H3) after change. Stages 1-2=H3, 3-5=H2, 6-8=H1';
COMMENT ON COLUMN card_timeline.trigger IS 'What triggered this stage change (manual, auto-calculated, source-update, system)';
COMMENT ON COLUMN card_timeline.reason IS 'Optional explanation for why the stage changed';

-- ============================================================
-- DONE
-- ============================================================
SELECT 'card_timeline enhanced with stage tracking columns' as status;
