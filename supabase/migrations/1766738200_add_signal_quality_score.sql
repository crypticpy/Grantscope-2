-- Migration: add_signal_quality_score
-- Created at: 1766738200
-- Description: Add signal quality score to cards for tracking data completeness and research depth

-- Add signal quality score to cards
ALTER TABLE cards ADD COLUMN IF NOT EXISTS signal_quality_score INTEGER
  CHECK (signal_quality_score >= 0 AND signal_quality_score <= 100);

CREATE INDEX IF NOT EXISTS idx_cards_signal_quality_score
  ON cards(signal_quality_score DESC NULLS LAST);

COMMENT ON COLUMN cards.signal_quality_score IS
  'Computed quality score (0-100) based on source count, diversity, research depth, and engagement';
