-- Migration: create_sources_and_relationships
-- Created at: 1766434548

-- Sources table - articles/information that inform cards
CREATE TABLE sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    card_id UUID REFERENCES cards(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    url TEXT,
    content TEXT,
    summary TEXT,
    
    -- Source metadata
    source_type TEXT CHECK (source_type IN ('article', 'report', 'paper', 'news')),
    author TEXT,
    publisher TEXT,
    published_date TIMESTAMPTZ,
    fetched_date TIMESTAMPTZ DEFAULT NOW(),
    
    -- AI analysis
    relevance_score INTEGER CHECK (relevance_score BETWEEN 0 AND 100),
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Card timeline - events showing how cards evolve
CREATE TABLE card_timeline (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    card_id UUID REFERENCES cards(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL, -- 'created', 'source_added', 'stage_changed', 'updated'
    title TEXT NOT NULL,
    description TEXT,
    metadata JSONB DEFAULT '{}',
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Card follows - users tracking specific cards
CREATE TABLE card_follows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    card_id UUID REFERENCES cards(id) ON DELETE CASCADE,
    priority TEXT DEFAULT 'medium' CHECK (priority IN ('high', 'medium', 'low')),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, card_id)
);

-- Card notes - user comments on cards
CREATE TABLE card_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    card_id UUID REFERENCES cards(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    is_private BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Workstreams - user-defined research streams
CREATE TABLE workstreams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    
    -- Filters
    pillar_ids TEXT[], -- Array of pillar IDs
    goal_ids TEXT[], -- Array of goal IDs
    stage_ids TEXT[], -- Array of stage IDs
    horizon TEXT CHECK (horizon IN ('H1', 'H2', 'H3', 'ALL')),
    keywords TEXT[], -- Array of keywords
    
    -- Settings
    is_active BOOLEAN DEFAULT true,
    auto_add BOOLEAN DEFAULT false, -- Auto-add matching cards
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Workstream cards - cards assigned to workstreams
CREATE TABLE workstream_cards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workstream_id UUID REFERENCES workstreams(id) ON DELETE CASCADE,
    card_id UUID REFERENCES cards(id) ON DELETE CASCADE,
    added_by UUID REFERENCES users(id),
    added_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(workstream_id, card_id)
);

-- Enable RLS
ALTER TABLE sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE card_timeline ENABLE ROW LEVEL SECURITY;
ALTER TABLE card_follows ENABLE ROW LEVEL SECURITY;
ALTER TABLE card_notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE workstreams ENABLE ROW LEVEL SECURITY;
ALTER TABLE workstream_cards ENABLE ROW LEVEL SECURITY;;