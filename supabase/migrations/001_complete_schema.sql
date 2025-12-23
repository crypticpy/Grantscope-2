-- Foresight Complete Database Schema
-- Run this in Supabase SQL Editor

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- ============================================
-- REFERENCE TABLES
-- ============================================

-- Pillars (Strategic pillars)
CREATE TABLE IF NOT EXISTS pillars (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Goals (under pillars)
CREATE TABLE IF NOT EXISTS goals (
    code TEXT PRIMARY KEY,
    pillar_id TEXT REFERENCES pillars(code) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Anchors
CREATE TABLE IF NOT EXISTS anchors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Stages (maturity stages 1-8)
CREATE TABLE IF NOT EXISTS stages (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    horizon TEXT CHECK (horizon IN ('H1', 'H2', 'H3')),
    description TEXT,
    sort_order INTEGER DEFAULT 0
);

-- Top 25 Priorities
CREATE TABLE IF NOT EXISTS top25_priorities (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    pillar_code TEXT REFERENCES pillars(code),
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- CORE TABLES
-- ============================================

-- Users (extends Supabase auth.users)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    display_name TEXT,
    department TEXT,
    role TEXT DEFAULT 'user',
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Cards (core intelligence units)
CREATE TABLE IF NOT EXISTS cards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    description TEXT,
    summary TEXT,

    -- Classification
    horizon TEXT CHECK (horizon IN ('H1', 'H2', 'H3')),
    stage INTEGER CHECK (stage BETWEEN 1 AND 8),
    triage_score INTEGER CHECK (triage_score IN (1, 3, 5)),
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'archived', 'draft')),

    -- Taxonomy (arrays for multi-select)
    pillars TEXT[] DEFAULT '{}',
    goals TEXT[] DEFAULT '{}',
    steep_categories TEXT[] DEFAULT '{}',
    anchors TEXT[] DEFAULT '{}',
    top25_relevance TEXT[] DEFAULT '{}',

    -- Scoring (7 criteria)
    credibility_score NUMERIC(3,2),
    novelty_score NUMERIC(3,2),
    likelihood_score NUMERIC(3,2),
    impact_score NUMERIC(3,2),
    relevance_score NUMERIC(3,2),
    time_to_awareness_months INTEGER,
    time_to_prepare_months INTEGER,

    -- Computed
    velocity_score NUMERIC(5,2) DEFAULT 0,
    follower_count INTEGER DEFAULT 0,
    source_count INTEGER DEFAULT 0,

    -- Embedding for semantic search
    embedding VECTOR(1536),

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES users(id),
    is_archived BOOLEAN DEFAULT FALSE
);

-- Sources (articles, papers linked to cards)
CREATE TABLE IF NOT EXISTS sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    card_id UUID REFERENCES cards(id) ON DELETE CASCADE,

    -- Source info
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    publication TEXT,
    author TEXT,
    published_at TIMESTAMPTZ,

    -- Processing
    api_source TEXT,
    full_text TEXT,
    ai_summary TEXT,
    key_excerpts TEXT[],
    relevance_score NUMERIC(3,2),
    relevance_to_card NUMERIC(3,2),

    -- Embedding
    embedding VECTOR(1536),

    -- Metadata
    ingested_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(card_id, url)
);

-- Card Timeline (event log)
CREATE TABLE IF NOT EXISTS card_timeline (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    card_id UUID REFERENCES cards(id) ON DELETE CASCADE,

    event_type TEXT NOT NULL,
    event_description TEXT,
    previous_value JSONB,
    new_value JSONB,
    triggered_by_source_id UUID REFERENCES sources(id),
    triggered_by_user_id UUID REFERENCES users(id),

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Workstreams (user-defined filters/lenses)
CREATE TABLE IF NOT EXISTS workstreams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,

    name TEXT NOT NULL,
    description TEXT,

    -- Filter criteria
    pillars TEXT[] DEFAULT '{}',
    goals TEXT[] DEFAULT '{}',
    anchors TEXT[] DEFAULT '{}',
    keywords TEXT[] DEFAULT '{}',
    min_stage INTEGER,
    max_stage INTEGER,
    horizons TEXT[] DEFAULT '{}',

    -- Settings
    is_default BOOLEAN DEFAULT FALSE,
    notification_enabled BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Card Follows (user following cards)
CREATE TABLE IF NOT EXISTS card_follows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    card_id UUID REFERENCES cards(id) ON DELETE CASCADE,
    workstream_id UUID REFERENCES workstreams(id) ON DELETE SET NULL,

    followed_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(user_id, card_id)
);

-- Card Notes (user annotations)
CREATE TABLE IF NOT EXISTS card_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    card_id UUID REFERENCES cards(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,

    content TEXT NOT NULL,
    is_private BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- ANALYSIS TABLES
-- ============================================

-- Implications Analyses
CREATE TABLE IF NOT EXISTS implications_analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    card_id UUID REFERENCES cards(id) ON DELETE CASCADE,

    perspective TEXT NOT NULL,
    perspective_detail TEXT,
    summary TEXT,

    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

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

-- ============================================
-- RESEARCH PIPELINE TABLES
-- ============================================

-- Research Tasks (async research jobs)
CREATE TABLE IF NOT EXISTS research_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    card_id UUID REFERENCES cards(id) ON DELETE SET NULL,
    workstream_id UUID REFERENCES workstreams(id) ON DELETE SET NULL,

    -- Task configuration
    task_type TEXT NOT NULL CHECK (task_type IN (
        'update',
        'research_topic',
        'workstream_scan',
        'refresh_summary',
        'deep_research'
    )),
    research_topic TEXT,
    depth TEXT DEFAULT 'standard' CHECK (depth IN ('quick', 'standard', 'deep')),

    -- Status tracking
    status TEXT DEFAULT 'queued' CHECK (status IN (
        'queued',
        'processing',
        'completed',
        'failed'
    )),

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    -- Results
    result_summary JSONB,
    error_message TEXT
);

-- Entities (extracted from research)
CREATE TABLE IF NOT EXISTS entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    card_id UUID REFERENCES cards(id) ON DELETE CASCADE,
    source_id UUID REFERENCES sources(id) ON DELETE SET NULL,

    entity_type TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    metadata JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(card_id, entity_type, name)
);

-- ============================================
-- INDEXES
-- ============================================

-- Cards indexes
CREATE INDEX IF NOT EXISTS idx_cards_pillars ON cards USING GIN (pillars);
CREATE INDEX IF NOT EXISTS idx_cards_horizon ON cards (horizon);
CREATE INDEX IF NOT EXISTS idx_cards_stage ON cards (stage);
CREATE INDEX IF NOT EXISTS idx_cards_updated ON cards (updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_cards_status ON cards (status);
CREATE INDEX IF NOT EXISTS idx_cards_slug ON cards (slug);

-- Sources indexes
CREATE INDEX IF NOT EXISTS idx_sources_card ON sources (card_id);
CREATE INDEX IF NOT EXISTS idx_sources_ingested ON sources (ingested_at DESC);

-- Timeline indexes
CREATE INDEX IF NOT EXISTS idx_timeline_card ON card_timeline (card_id, created_at DESC);

-- Workstreams indexes
CREATE INDEX IF NOT EXISTS idx_workstreams_user ON workstreams (user_id);

-- Follows indexes
CREATE INDEX IF NOT EXISTS idx_follows_user ON card_follows (user_id);
CREATE INDEX IF NOT EXISTS idx_follows_card ON card_follows (card_id);

-- Notes indexes
CREATE INDEX IF NOT EXISTS idx_notes_card ON card_notes (card_id);
CREATE INDEX IF NOT EXISTS idx_notes_user ON card_notes (user_id);

-- Analysis indexes
CREATE INDEX IF NOT EXISTS idx_analyses_card ON implications_analyses (card_id);
CREATE INDEX IF NOT EXISTS idx_implications_analysis ON implications (analysis_id);
CREATE INDEX IF NOT EXISTS idx_implications_parent ON implications (parent_id);

-- Research tasks indexes
CREATE INDEX IF NOT EXISTS idx_research_tasks_user ON research_tasks (user_id);
CREATE INDEX IF NOT EXISTS idx_research_tasks_status ON research_tasks (status);
CREATE INDEX IF NOT EXISTS idx_research_tasks_card ON research_tasks (card_id);

-- Entities indexes
CREATE INDEX IF NOT EXISTS idx_entities_card ON entities (card_id);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities (entity_type);

-- ============================================
-- TRIGGERS & FUNCTIONS
-- ============================================

-- Update timestamp function
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to tables with updated_at
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS update_cards_updated_at ON cards;
CREATE TRIGGER update_cards_updated_at
    BEFORE UPDATE ON cards
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS update_workstreams_updated_at ON workstreams;
CREATE TRIGGER update_workstreams_updated_at
    BEFORE UPDATE ON workstreams
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS update_card_notes_updated_at ON card_notes;
CREATE TRIGGER update_card_notes_updated_at
    BEFORE UPDATE ON card_notes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Follower count trigger
CREATE OR REPLACE FUNCTION update_follower_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE cards SET follower_count = follower_count + 1
        WHERE id = NEW.card_id;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE cards SET follower_count = follower_count - 1
        WHERE id = OLD.card_id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_follower_count ON card_follows;
CREATE TRIGGER trg_follower_count
    AFTER INSERT OR DELETE ON card_follows
    FOR EACH ROW EXECUTE FUNCTION update_follower_count();

-- Source count trigger
CREATE OR REPLACE FUNCTION update_source_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE cards SET source_count = source_count + 1
        WHERE id = NEW.card_id;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE cards SET source_count = source_count - 1
        WHERE id = OLD.card_id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_source_count ON sources;
CREATE TRIGGER trg_source_count
    AFTER INSERT OR DELETE ON sources
    FOR EACH ROW EXECUTE FUNCTION update_source_count();

-- ============================================
-- ROW LEVEL SECURITY
-- ============================================

-- Enable RLS on user-scoped tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE workstreams ENABLE ROW LEVEL SECURITY;
ALTER TABLE card_follows ENABLE ROW LEVEL SECURITY;
ALTER TABLE card_notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_tasks ENABLE ROW LEVEL SECURITY;

-- Users policies
DROP POLICY IF EXISTS users_own ON users;
CREATE POLICY users_own ON users
    FOR ALL USING (auth.uid() = id);

-- Workstreams policies
DROP POLICY IF EXISTS workstreams_own ON workstreams;
CREATE POLICY workstreams_own ON workstreams
    FOR ALL USING (auth.uid() = user_id);

-- Follows policies
DROP POLICY IF EXISTS follows_own ON card_follows;
CREATE POLICY follows_own ON card_follows
    FOR ALL USING (auth.uid() = user_id);

-- Notes policies
DROP POLICY IF EXISTS notes_read ON card_notes;
CREATE POLICY notes_read ON card_notes
    FOR SELECT USING (NOT is_private OR auth.uid() = user_id);

DROP POLICY IF EXISTS notes_write ON card_notes;
CREATE POLICY notes_write ON card_notes
    FOR ALL USING (auth.uid() = user_id);

-- Research tasks policies
DROP POLICY IF EXISTS research_tasks_own ON research_tasks;
CREATE POLICY research_tasks_own ON research_tasks
    FOR ALL USING (auth.uid() = user_id);

-- Public read policies for cards, sources, analyses
ALTER TABLE cards ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS cards_public_read ON cards;
CREATE POLICY cards_public_read ON cards
    FOR SELECT USING (true);

DROP POLICY IF EXISTS cards_authenticated_write ON cards;
CREATE POLICY cards_authenticated_write ON cards
    FOR INSERT WITH CHECK (auth.uid() IS NOT NULL);

DROP POLICY IF EXISTS cards_authenticated_update ON cards;
CREATE POLICY cards_authenticated_update ON cards
    FOR UPDATE USING (auth.uid() IS NOT NULL);

ALTER TABLE sources ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS sources_public_read ON sources;
CREATE POLICY sources_public_read ON sources
    FOR SELECT USING (true);

DROP POLICY IF EXISTS sources_authenticated_write ON sources;
CREATE POLICY sources_authenticated_write ON sources
    FOR INSERT WITH CHECK (auth.uid() IS NOT NULL);

-- ============================================
-- SEED DATA
-- ============================================

-- Insert pillars if not exist
INSERT INTO pillars (code, name, description) VALUES
    ('CH', 'Community Health & Sustainability', 'Public health, parks, climate, preparedness'),
    ('EW', 'Economic & Workforce Development', 'Economic mobility, small business, creative economy'),
    ('HG', 'High-Performing Government', 'Fiscal, technology, workforce, engagement'),
    ('HH', 'Homelessness & Housing', 'Communities, affordable housing, homelessness reduction'),
    ('MC', 'Mobility & Critical Infrastructure', 'Transportation, transit, utilities, facilities'),
    ('PS', 'Public Safety', 'Relationships, fair delivery, disaster preparedness')
ON CONFLICT (code) DO NOTHING;

-- Insert goals
INSERT INTO goals (code, pillar_id, name, sort_order) VALUES
    ('CH.1', 'CH', 'Equitable public health services', 1),
    ('CH.2', 'CH', 'Parks, trails, recreation access', 2),
    ('CH.3', 'CH', 'Natural resources & climate mitigation', 3),
    ('CH.4', 'CH', 'Community preparedness & resiliency', 4),
    ('CH.5', 'CH', 'Animal Center operations', 5),
    ('EW.1', 'EW', 'Economic mobility', 1),
    ('EW.2', 'EW', 'Economic mobility', 2),
    ('EW.3', 'EW', 'Creative ecosystem', 3),
    ('HG.1', 'HG', 'Fiscal integrity', 1),
    ('HG.2', 'HG', 'Data & technology capabilities', 2),
    ('HG.3', 'HG', 'Workforce recruitment & retention', 3),
    ('HG.4', 'HG', 'Equitable outreach & engagement', 4),
    ('HH.1', 'HH', 'Complete communities', 1),
    ('HH.2', 'HH', 'Affordable housing', 2),
    ('HH.3', 'HH', 'Reduce homelessness', 3),
    ('MC.1', 'MC', 'Mobility safety', 1),
    ('MC.2', 'MC', 'Transit & airport expansion', 2),
    ('MC.3', 'MC', 'Sustainable transportation', 3),
    ('MC.4', 'MC', 'Safe, resilient facilities', 4),
    ('MC.5', 'MC', 'Utility infrastructure', 5),
    ('PS.1', 'PS', 'Community relationships', 1),
    ('PS.2', 'PS', 'Fair public safety delivery', 2),
    ('PS.3', 'PS', 'Hazard & disaster partnerships', 3)
ON CONFLICT (code) DO NOTHING;

-- Insert anchors
INSERT INTO anchors (name) VALUES
    ('Equity'),
    ('Affordability'),
    ('Innovation'),
    ('Sustainability & Resiliency'),
    ('Proactive Prevention'),
    ('Community Trust & Relationships')
ON CONFLICT (name) DO NOTHING;

-- Insert stages
INSERT INTO stages (id, name, horizon, description, sort_order) VALUES
    (1, 'Concept', 'H3', 'Academic/theoretical', 1),
    (2, 'Emerging', 'H3', 'Startups, patents, VC interest', 2),
    (3, 'Prototype', 'H2', 'Working demos', 3),
    (4, 'Pilot', 'H2', 'Real-world testing', 4),
    (5, 'Municipal Pilot', 'H2', 'Government testing', 5),
    (6, 'Early Adoption', 'H1', 'Multiple cities implementing', 6),
    (7, 'Mainstream', 'H1', 'Widespread adoption', 7),
    (8, 'Mature', 'H1', 'Established, commoditized', 8)
ON CONFLICT (id) DO NOTHING;

-- Done
SELECT 'Schema migration complete!' as status;
