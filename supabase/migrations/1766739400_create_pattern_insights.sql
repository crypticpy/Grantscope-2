-- Migration: create_pattern_insights
-- Created at: 1766739400
-- Cross-signal pattern detection: stores AI-detected connections across strategic pillars

CREATE TABLE IF NOT EXISTS pattern_insights (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    pattern_title TEXT NOT NULL,
    pattern_summary TEXT NOT NULL,
    opportunity TEXT,
    confidence NUMERIC(3,2) DEFAULT 0.5,
    affected_pillars TEXT[] DEFAULT '{}',
    urgency TEXT DEFAULT 'medium' CHECK (urgency IN ('high', 'medium', 'low')),
    related_card_ids UUID[] DEFAULT '{}',
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'dismissed', 'acted_on')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '30 days')
);

-- RLS
ALTER TABLE pattern_insights ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Authenticated users can read pattern insights"
    ON pattern_insights FOR SELECT
    USING (auth.role() = 'authenticated');

CREATE POLICY "Service role can manage pattern insights"
    ON pattern_insights FOR ALL
    USING (auth.role() = 'service_role');

-- Indexes for quick lookups
CREATE INDEX idx_pattern_insights_status ON pattern_insights(status);
CREATE INDEX idx_pattern_insights_urgency ON pattern_insights(urgency);
CREATE INDEX idx_pattern_insights_created_at ON pattern_insights(created_at DESC);

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_pattern_insights_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER pattern_insights_updated_at
    BEFORE UPDATE ON pattern_insights
    FOR EACH ROW
    EXECUTE FUNCTION update_pattern_insights_updated_at();
