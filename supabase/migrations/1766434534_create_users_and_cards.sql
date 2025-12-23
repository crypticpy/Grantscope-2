-- Migration: create_users_and_cards
-- Created at: 1766434534

-- Users table (extends Supabase auth.users)
CREATE TABLE users (
    id UUID PRIMARY KEY REFERENCES auth.users(id),
    email TEXT NOT NULL,
    display_name TEXT,
    department TEXT,
    role TEXT,
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Main cards table - atomic units of intelligence
CREATE TABLE cards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    summary TEXT,
    description TEXT,
    
    -- Classification
    pillar_id TEXT REFERENCES pillars(id),
    goal_id TEXT REFERENCES goals(id),
    anchor_id TEXT REFERENCES anchors(id),
    stage_id TEXT REFERENCES stages(id),
    horizon TEXT CHECK (horizon IN ('H1', 'H2', 'H3')), -- 0-2yr, 2-5yr, 5+yr
    
    -- AI-generated metrics
    novelty_score INTEGER CHECK (novelty_score BETWEEN 0 AND 100),
    maturity_score INTEGER CHECK (maturity_score BETWEEN 0 AND 100),
    impact_score INTEGER CHECK (impact_score BETWEEN 0 AND 100),
    relevance_score INTEGER CHECK (relevance_score BETWEEN 0 AND 100),
    velocity_score INTEGER CHECK (velocity_score BETWEEN 0 AND 100),
    risk_score INTEGER CHECK (risk_score BETWEEN 0 AND 100),
    opportunity_score INTEGER CHECK (opportunity_score BETWEEN 0 AND 100),
    
    -- Metadata
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'archived', 'draft')),
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE cards ENABLE ROW LEVEL SECURITY;;