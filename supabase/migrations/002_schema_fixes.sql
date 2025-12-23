-- ============================================================
-- FORESIGHT SCHEMA FIX - Run in Supabase SQL Editor
-- ============================================================

-- Enable vector extension if not already enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- CARDS TABLE - Add missing columns
-- ============================================================
ALTER TABLE cards ADD COLUMN IF NOT EXISTS triage_score INTEGER;
ALTER TABLE cards ADD COLUMN IF NOT EXISTS stage INTEGER;
ALTER TABLE cards ADD COLUMN IF NOT EXISTS follower_count INTEGER DEFAULT 0;
ALTER TABLE cards ADD COLUMN IF NOT EXISTS anchors TEXT[] DEFAULT '{}';
ALTER TABLE cards ADD COLUMN IF NOT EXISTS time_to_prepare_months INTEGER;
ALTER TABLE cards ADD COLUMN IF NOT EXISTS credibility_score NUMERIC(3,2);
ALTER TABLE cards ADD COLUMN IF NOT EXISTS is_archived BOOLEAN DEFAULT FALSE;
ALTER TABLE cards ADD COLUMN IF NOT EXISTS source_count INTEGER DEFAULT 0;
ALTER TABLE cards ADD COLUMN IF NOT EXISTS time_to_awareness_months INTEGER;
ALTER TABLE cards ADD COLUMN IF NOT EXISTS pillars TEXT[] DEFAULT '{}';
ALTER TABLE cards ADD COLUMN IF NOT EXISTS steep_categories TEXT[] DEFAULT '{}';
ALTER TABLE cards ADD COLUMN IF NOT EXISTS goals TEXT[] DEFAULT '{}';
ALTER TABLE cards ADD COLUMN IF NOT EXISTS likelihood_score NUMERIC(3,2);
ALTER TABLE cards ADD COLUMN IF NOT EXISTS novelty_score NUMERIC(3,2);
ALTER TABLE cards ADD COLUMN IF NOT EXISTS impact_score NUMERIC(3,2);
ALTER TABLE cards ADD COLUMN IF NOT EXISTS relevance_score NUMERIC(3,2);
ALTER TABLE cards ADD COLUMN IF NOT EXISTS velocity_score NUMERIC(5,2) DEFAULT 0;
ALTER TABLE cards ADD COLUMN IF NOT EXISTS top25_relevance TEXT[] DEFAULT '{}';
ALTER TABLE cards ADD COLUMN IF NOT EXISTS created_by UUID;

-- Add embedding column (may fail if vector extension not enabled)
DO $$
BEGIN
    ALTER TABLE cards ADD COLUMN IF NOT EXISTS embedding VECTOR(1536);
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'Could not add embedding column - vector extension may not be enabled';
END $$;

-- Migrate existing data from old columns to new (if applicable)
UPDATE cards SET stage = stage_id::INTEGER WHERE stage IS NULL AND stage_id IS NOT NULL;
UPDATE cards SET pillars = ARRAY[pillar_id::TEXT] WHERE pillars = '{}' AND pillar_id IS NOT NULL;
UPDATE cards SET goals = ARRAY[goal_id::TEXT] WHERE goals = '{}' AND goal_id IS NOT NULL;
UPDATE cards SET anchors = ARRAY[anchor_id::TEXT] WHERE anchors = '{}' AND anchor_id IS NOT NULL;

-- ============================================================
-- SOURCES TABLE - Add missing columns
-- ============================================================
ALTER TABLE sources ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS publication TEXT;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS full_text TEXT;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS ai_summary TEXT;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS relevance_to_card NUMERIC(3,2);
ALTER TABLE sources ADD COLUMN IF NOT EXISTS key_excerpts TEXT[];
ALTER TABLE sources ADD COLUMN IF NOT EXISTS api_source TEXT;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS ingested_at TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE sources ADD COLUMN IF NOT EXISTS relevance_score NUMERIC(3,2);
ALTER TABLE sources ADD COLUMN IF NOT EXISTS author TEXT;

-- Migrate existing data
UPDATE sources SET published_at = published_date WHERE published_at IS NULL AND published_date IS NOT NULL;
UPDATE sources SET publication = publisher WHERE publication IS NULL AND publisher IS NOT NULL;
UPDATE sources SET ai_summary = summary WHERE ai_summary IS NULL AND summary IS NOT NULL;
UPDATE sources SET ingested_at = fetched_date WHERE ingested_at IS NULL AND fetched_date IS NOT NULL;

-- Add embedding column
DO $$
BEGIN
    ALTER TABLE sources ADD COLUMN IF NOT EXISTS embedding VECTOR(1536);
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'Could not add embedding column to sources';
END $$;

-- ============================================================
-- CARD_TIMELINE TABLE - Add missing columns
-- ============================================================
ALTER TABLE card_timeline ADD COLUMN IF NOT EXISTS new_value JSONB;
ALTER TABLE card_timeline ADD COLUMN IF NOT EXISTS event_description TEXT;
ALTER TABLE card_timeline ADD COLUMN IF NOT EXISTS previous_value JSONB;
ALTER TABLE card_timeline ADD COLUMN IF NOT EXISTS triggered_by_source_id UUID;
ALTER TABLE card_timeline ADD COLUMN IF NOT EXISTS triggered_by_user_id UUID;

-- Migrate existing data
UPDATE card_timeline SET event_description = description WHERE event_description IS NULL AND description IS NOT NULL;

-- ============================================================
-- WORKSTREAMS TABLE - Add missing columns
-- ============================================================
ALTER TABLE workstreams ADD COLUMN IF NOT EXISTS horizons TEXT[] DEFAULT '{}';
ALTER TABLE workstreams ADD COLUMN IF NOT EXISTS min_stage INTEGER;
ALTER TABLE workstreams ADD COLUMN IF NOT EXISTS notification_enabled BOOLEAN DEFAULT TRUE;
ALTER TABLE workstreams ADD COLUMN IF NOT EXISTS anchors TEXT[] DEFAULT '{}';
ALTER TABLE workstreams ADD COLUMN IF NOT EXISTS max_stage INTEGER;
ALTER TABLE workstreams ADD COLUMN IF NOT EXISTS is_default BOOLEAN DEFAULT FALSE;
ALTER TABLE workstreams ADD COLUMN IF NOT EXISTS pillars TEXT[] DEFAULT '{}';
ALTER TABLE workstreams ADD COLUMN IF NOT EXISTS goals TEXT[] DEFAULT '{}';
ALTER TABLE workstreams ADD COLUMN IF NOT EXISTS keywords TEXT[] DEFAULT '{}';

-- Migrate existing data
UPDATE workstreams SET pillars = pillar_ids WHERE pillars = '{}' AND pillar_ids IS NOT NULL;
UPDATE workstreams SET goals = goal_ids WHERE goals = '{}' AND goal_ids IS NOT NULL;
UPDATE workstreams SET horizons = ARRAY[horizon] WHERE horizons = '{}' AND horizon IS NOT NULL;

-- ============================================================
-- CARD_FOLLOWS TABLE - Add missing columns
-- ============================================================
ALTER TABLE card_follows ADD COLUMN IF NOT EXISTS followed_at TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE card_follows ADD COLUMN IF NOT EXISTS workstream_id UUID;

-- ============================================================
-- PILLARS TABLE - Add code column
-- ============================================================
-- Add code column and populate from id if needed
ALTER TABLE pillars ADD COLUMN IF NOT EXISTS code TEXT;

-- Create unique index on code if it doesn't exist
DO $$
BEGIN
    UPDATE pillars SET code = id::text WHERE code IS NULL;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'Could not update pillars code';
END $$;

-- ============================================================
-- GOALS TABLE - Add code column
-- ============================================================
ALTER TABLE goals ADD COLUMN IF NOT EXISTS code TEXT;
ALTER TABLE goals ADD COLUMN IF NOT EXISTS sort_order INTEGER DEFAULT 0;

-- Populate code from id if needed
DO $$
BEGIN
    UPDATE goals SET code = id::text WHERE code IS NULL;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'Could not update goals code';
END $$;

-- ============================================================
-- STAGES TABLE - Add horizon column
-- ============================================================
ALTER TABLE stages ADD COLUMN IF NOT EXISTS horizon TEXT;

-- Populate horizon based on stage id
UPDATE stages SET horizon = 'H3' WHERE id IN (1, 2) AND horizon IS NULL;
UPDATE stages SET horizon = 'H2' WHERE id IN (3, 4, 5) AND horizon IS NULL;
UPDATE stages SET horizon = 'H1' WHERE id IN (6, 7, 8) AND horizon IS NULL;

-- ============================================================
-- CREATE MISSING TABLES
-- ============================================================

-- Implications Analyses
CREATE TABLE IF NOT EXISTS implications_analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    card_id UUID REFERENCES cards(id) ON DELETE CASCADE,
    perspective TEXT NOT NULL,
    perspective_detail TEXT,
    summary TEXT,
    created_by UUID,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analyses_card ON implications_analyses (card_id);

-- Implications (hierarchical)
CREATE TABLE IF NOT EXISTS implications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id UUID REFERENCES implications_analyses(id) ON DELETE CASCADE,
    parent_id UUID REFERENCES implications(id) ON DELETE CASCADE,
    order_level INTEGER NOT NULL CHECK (order_level BETWEEN 1 AND 3),
    content TEXT NOT NULL,
    likelihood_score INTEGER CHECK (likelihood_score BETWEEN 1 AND 9),
    desirability_score INTEGER CHECK (desirability_score BETWEEN -5 AND 5),
    flag TEXT CHECK (flag IN (
        'likely_strong_negative',
        'unlikely_strong_positive',
        'catastrophe',
        'triumph'
    )),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_implications_analysis ON implications (analysis_id);
CREATE INDEX IF NOT EXISTS idx_implications_parent ON implications (parent_id);

-- ============================================================
-- CARD_NOTES TABLE - Ensure columns exist
-- ============================================================
ALTER TABLE card_notes ADD COLUMN IF NOT EXISTS is_private BOOLEAN DEFAULT FALSE;
ALTER TABLE card_notes ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- ============================================================
-- CREATE INDEXES
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_cards_pillars ON cards USING GIN (pillars);
CREATE INDEX IF NOT EXISTS idx_cards_horizon ON cards (horizon);
CREATE INDEX IF NOT EXISTS idx_cards_stage ON cards (stage);
CREATE INDEX IF NOT EXISTS idx_cards_updated ON cards (updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_cards_status ON cards (status);
CREATE INDEX IF NOT EXISTS idx_sources_card ON sources (card_id);
CREATE INDEX IF NOT EXISTS idx_sources_ingested ON sources (ingested_at DESC);
CREATE INDEX IF NOT EXISTS idx_timeline_card ON card_timeline (card_id, created_at DESC);

-- ============================================================
-- RLS POLICIES
-- ============================================================

-- Enable RLS on new tables
ALTER TABLE implications_analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE implications ENABLE ROW LEVEL SECURITY;

-- Public read policies
DROP POLICY IF EXISTS implications_analyses_public_read ON implications_analyses;
CREATE POLICY implications_analyses_public_read ON implications_analyses FOR SELECT USING (true);

DROP POLICY IF EXISTS implications_public_read ON implications;
CREATE POLICY implications_public_read ON implications FOR SELECT USING (true);

-- Authenticated write
DROP POLICY IF EXISTS implications_analyses_auth_write ON implications_analyses;
CREATE POLICY implications_analyses_auth_write ON implications_analyses
    FOR INSERT WITH CHECK (auth.uid() IS NOT NULL);

DROP POLICY IF EXISTS implications_auth_write ON implications;
CREATE POLICY implications_auth_write ON implications
    FOR INSERT WITH CHECK (auth.uid() IS NOT NULL);

-- ============================================================
-- DONE
-- ============================================================
SELECT 'Schema migration complete!' as status;
