-- Migration: create_reference_tables
-- Created at: 1766434524

-- Reference tables for taxonomy

-- Strategic pillars (6 total from Austin CSP)
CREATE TABLE pillars (
    id TEXT PRIMARY KEY, -- e.g., 'CH', 'MC', etc.
    name TEXT NOT NULL,
    description TEXT,
    color TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Goals under each pillar (23 total)
CREATE TABLE goals (
    id TEXT PRIMARY KEY, -- e.g., 'CH-01', 'MC-05', etc.
    pillar_id TEXT REFERENCES pillars(id),
    name TEXT NOT NULL,
    description TEXT,
    sort_order INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Anchors (6 total)
CREATE TABLE anchors (
    id TEXT PRIMARY KEY, -- e.g., 'equity', 'innovation', etc.
    name TEXT NOT NULL,
    description TEXT,
    color TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Maturity stages (8 total)
CREATE TABLE stages (
    id TEXT PRIMARY KEY, -- e.g., '1_concept', '2_exploring', etc.
    name TEXT NOT NULL,
    description TEXT,
    sort_order INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- CMO Top 25 priorities (for future use)
CREATE TABLE priorities (
    id TEXT PRIMARY KEY, -- e.g., 'P01', 'P25', etc.
    name TEXT NOT NULL,
    description TEXT,
    category TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);;