-- Migration: enhanced_research_schema
-- Created at: 1766434901
-- Description: Enhance sources schema, add entities table for graph, add vector matching

-- ============================================================================
-- Enable pgvector extension (if not already enabled)
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- Enhance sources table with full schema
-- ============================================================================

-- Add new columns for full source processing
ALTER TABLE sources ADD COLUMN IF NOT EXISTS publication TEXT;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS full_text TEXT;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS ai_summary TEXT;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS key_excerpts TEXT[] DEFAULT '{}';
ALTER TABLE sources ADD COLUMN IF NOT EXISTS relevance_to_card NUMERIC(3,2);
ALTER TABLE sources ADD COLUMN IF NOT EXISTS api_source TEXT DEFAULT 'manual';
ALTER TABLE sources ADD COLUMN IF NOT EXISTS ingested_at TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE sources ADD COLUMN IF NOT EXISTS embedding VECTOR(1536);

-- Add index for vector similarity search on sources
CREATE INDEX IF NOT EXISTS idx_sources_embedding ON sources
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ============================================================================
-- Add embedding column to cards (if not exists)
-- ============================================================================

ALTER TABLE cards ADD COLUMN IF NOT EXISTS embedding VECTOR(1536);

-- Add index for vector similarity search on cards
CREATE INDEX IF NOT EXISTS idx_cards_embedding ON cards
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ============================================================================
-- Create entities table for graph building
-- ============================================================================

CREATE TABLE IF NOT EXISTS entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Entity identification
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL CHECK (entity_type IN (
        'technology', 'organization', 'concept', 'person', 'location'
    )),

    -- Context and relationships
    context TEXT,

    -- Associations
    source_id UUID REFERENCES sources(id) ON DELETE CASCADE,
    card_id UUID REFERENCES cards(id) ON DELETE SET NULL,

    -- For deduplication and merging
    canonical_name TEXT,  -- Normalized version for matching

    -- Embedding for entity resolution
    embedding VECTOR(1536),

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for entity queries
CREATE INDEX IF NOT EXISTS idx_entities_name ON entities (name);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities (entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_card ON entities (card_id);
CREATE INDEX IF NOT EXISTS idx_entities_source ON entities (source_id);
CREATE INDEX IF NOT EXISTS idx_entities_canonical ON entities (canonical_name);

-- ============================================================================
-- Create entity_relationships table for graph edges
-- ============================================================================

CREATE TABLE IF NOT EXISTS entity_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Relationship endpoints
    source_entity_id UUID REFERENCES entities(id) ON DELETE CASCADE,
    target_entity_id UUID REFERENCES entities(id) ON DELETE CASCADE,

    -- Relationship type
    relationship_type TEXT NOT NULL CHECK (relationship_type IN (
        'implements', 'develops', 'partners_with', 'competes_with',
        'regulates', 'located_in', 'acquired_by', 'spun_off_from',
        'uses', 'provides', 'researches', 'funds'
    )),

    -- Confidence and context
    confidence NUMERIC(3,2) DEFAULT 0.7,
    context TEXT,

    -- Source tracking
    source_id UUID REFERENCES sources(id) ON DELETE SET NULL,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Prevent duplicate relationships
    UNIQUE(source_entity_id, target_entity_id, relationship_type)
);

-- Indexes for relationship queries
CREATE INDEX IF NOT EXISTS idx_relationships_source ON entity_relationships (source_entity_id);
CREATE INDEX IF NOT EXISTS idx_relationships_target ON entity_relationships (target_entity_id);
CREATE INDEX IF NOT EXISTS idx_relationships_type ON entity_relationships (relationship_type);

-- ============================================================================
-- Create vector matching function for cards
-- ============================================================================

CREATE OR REPLACE FUNCTION match_cards_by_embedding(
    query_embedding VECTOR(1536),
    match_threshold FLOAT DEFAULT 0.82,
    match_count INT DEFAULT 5
)
RETURNS TABLE (
    id UUID,
    name TEXT,
    summary TEXT,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        c.name,
        c.summary,
        1 - (c.embedding <=> query_embedding) AS similarity
    FROM cards c
    WHERE
        c.embedding IS NOT NULL
        AND c.status = 'active'
        AND 1 - (c.embedding <=> query_embedding) > match_threshold
    ORDER BY c.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- ============================================================================
-- Create vector matching function for sources
-- ============================================================================

CREATE OR REPLACE FUNCTION match_sources_by_embedding(
    query_embedding VECTOR(1536),
    match_threshold FLOAT DEFAULT 0.80,
    match_count INT DEFAULT 10
)
RETURNS TABLE (
    id UUID,
    card_id UUID,
    title TEXT,
    ai_summary TEXT,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        s.id,
        s.card_id,
        s.title,
        s.ai_summary,
        1 - (s.embedding <=> query_embedding) AS similarity
    FROM sources s
    WHERE
        s.embedding IS NOT NULL
        AND 1 - (s.embedding <=> query_embedding) > match_threshold
    ORDER BY s.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- ============================================================================
-- Create function to find similar entities (for deduplication/merging)
-- ============================================================================

CREATE OR REPLACE FUNCTION find_similar_entities(
    entity_name TEXT,
    entity_type_filter TEXT DEFAULT NULL,
    match_count INT DEFAULT 5
)
RETURNS TABLE (
    id UUID,
    name TEXT,
    entity_type TEXT,
    card_id UUID,
    match_score FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        e.id,
        e.name,
        e.entity_type,
        e.card_id,
        similarity(lower(e.name), lower(entity_name)) AS match_score
    FROM entities e
    WHERE
        (entity_type_filter IS NULL OR e.entity_type = entity_type_filter)
        AND similarity(lower(e.name), lower(entity_name)) > 0.5
    ORDER BY similarity(lower(e.name), lower(entity_name)) DESC
    LIMIT match_count;
END;
$$;

-- Enable trigram extension for fuzzy matching
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Index for trigram matching on entity names
CREATE INDEX IF NOT EXISTS idx_entities_name_trgm ON entities
    USING gin (name gin_trgm_ops);

-- ============================================================================
-- Update timeline table to support source references
-- ============================================================================

ALTER TABLE card_timeline ADD COLUMN IF NOT EXISTS triggered_by_source_id UUID REFERENCES sources(id);
ALTER TABLE card_timeline ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';

-- ============================================================================
-- RLS Policies for new tables
-- ============================================================================

-- Entities are readable by all authenticated users
ALTER TABLE entities ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Entities are viewable by all authenticated users"
    ON entities FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Service role full access on entities"
    ON entities FOR ALL
    USING (auth.role() = 'service_role');

-- Entity relationships same policy
ALTER TABLE entity_relationships ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Entity relationships viewable by all authenticated users"
    ON entity_relationships FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Service role full access on entity_relationships"
    ON entity_relationships FOR ALL
    USING (auth.role() = 'service_role');

-- ============================================================================
-- Comments for documentation
-- ============================================================================

COMMENT ON TABLE entities IS 'Extracted entities (technologies, orgs, concepts) for graph building';
COMMENT ON COLUMN entities.entity_type IS 'Type: technology, organization, concept, person, location';
COMMENT ON COLUMN entities.canonical_name IS 'Normalized name for deduplication and entity resolution';

COMMENT ON TABLE entity_relationships IS 'Relationships between entities for knowledge graph';
COMMENT ON COLUMN entity_relationships.relationship_type IS 'Edge type: implements, develops, partners_with, etc.';

COMMENT ON FUNCTION match_cards_by_embedding IS 'Vector similarity search against cards using embedding';
COMMENT ON FUNCTION match_sources_by_embedding IS 'Vector similarity search against sources using embedding';
COMMENT ON FUNCTION find_similar_entities IS 'Fuzzy text matching to find similar entity names';
