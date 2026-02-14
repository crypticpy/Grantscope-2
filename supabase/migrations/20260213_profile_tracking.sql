-- Track profile generation metadata on cards
ALTER TABLE cards ADD COLUMN IF NOT EXISTS profile_generated_at TIMESTAMPTZ;
ALTER TABLE cards ADD COLUMN IF NOT EXISTS profile_source_count INTEGER DEFAULT 0;
ALTER TABLE cards ADD COLUMN IF NOT EXISTS trend_direction TEXT
    CHECK (trend_direction IN ('accelerating', 'stable', 'emerging', 'declining', 'unknown'))
    DEFAULT 'unknown';

CREATE INDEX IF NOT EXISTS idx_cards_trend_direction ON cards(trend_direction);
