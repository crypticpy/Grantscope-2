-- Migration: add_velocity_trend
-- Created at: 1766739600
--
-- Add velocity trend tracking to cards.
-- Tracks the rate of new source additions over rolling windows
-- to surface accelerating, decelerating, emerging, and stale signals.

ALTER TABLE cards ADD COLUMN IF NOT EXISTS velocity_trend TEXT DEFAULT 'stable'
  CHECK (velocity_trend IN ('accelerating', 'stable', 'decelerating', 'emerging', 'stale'));

ALTER TABLE cards ADD COLUMN IF NOT EXISTS velocity_score NUMERIC(5,2) DEFAULT 0;

ALTER TABLE cards ADD COLUMN IF NOT EXISTS velocity_updated_at TIMESTAMPTZ;

COMMENT ON COLUMN cards.velocity_trend IS 'Signal momentum: accelerating, stable, decelerating, emerging, or stale';
COMMENT ON COLUMN cards.velocity_score IS 'Numeric velocity metric: positive = accelerating, negative = decelerating';
COMMENT ON COLUMN cards.velocity_updated_at IS 'When velocity was last calculated';
