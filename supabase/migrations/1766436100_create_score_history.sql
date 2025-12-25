-- Migration: create_score_history
-- Created at: 1766436100

-- Card score history table - tracks score changes over time for trend visualization
CREATE TABLE card_score_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    card_id UUID NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- AI-generated metrics (same as cards table, 0-100 range)
    maturity_score INTEGER CHECK (maturity_score BETWEEN 0 AND 100),
    velocity_score INTEGER CHECK (velocity_score BETWEEN 0 AND 100),
    novelty_score INTEGER CHECK (novelty_score BETWEEN 0 AND 100),
    impact_score INTEGER CHECK (impact_score BETWEEN 0 AND 100),
    relevance_score INTEGER CHECK (relevance_score BETWEEN 0 AND 100),
    risk_score INTEGER CHECK (risk_score BETWEEN 0 AND 100),
    opportunity_score INTEGER CHECK (opportunity_score BETWEEN 0 AND 100),

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for efficient queries on card_id and recorded_at (date range filtering)
CREATE INDEX idx_card_score_history_card_id_recorded_at
    ON card_score_history(card_id, recorded_at DESC);

-- Index for card_id only (for fetching all history for a card)
CREATE INDEX idx_card_score_history_card_id
    ON card_score_history(card_id);

-- Enable RLS
ALTER TABLE card_score_history ENABLE ROW LEVEL SECURITY;

-- RLS policies: Allow read access to all authenticated users
CREATE POLICY "Authenticated users can view score history"
    ON card_score_history
    FOR SELECT
    TO authenticated
    USING (true);

-- RLS policies: Allow insert for authenticated users (for recording score changes)
CREATE POLICY "Authenticated users can insert score history"
    ON card_score_history
    FOR INSERT
    TO authenticated
    WITH CHECK (true);

-- Service role full access (for backend operations)
CREATE POLICY "Service role full access on score history"
    ON card_score_history
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Comment on table for documentation
COMMENT ON TABLE card_score_history IS 'Tracks historical score changes for cards to enable trend visualization and analysis';
COMMENT ON COLUMN card_score_history.recorded_at IS 'Timestamp when this score snapshot was recorded';
