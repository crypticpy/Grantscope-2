-- Migration: create_card_relationships
-- Created at: 1766436101

-- Card relationships table - tracks relationships between cards for concept network visualization
CREATE TABLE card_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_card_id UUID NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    target_card_id UUID NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL CHECK (relationship_type IN ('related', 'similar', 'derived', 'parent', 'child', 'enables', 'blocks')),
    strength NUMERIC(3,2) CHECK (strength BETWEEN 0 AND 1),
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Prevent duplicate relationships between the same pair of cards with the same type
    UNIQUE(source_card_id, target_card_id, relationship_type),

    -- Prevent self-referential relationships
    CHECK (source_card_id != target_card_id)
);

-- Index for efficient queries by source card (for concept network visualization)
CREATE INDEX idx_card_relationships_source ON card_relationships(source_card_id);

-- Index for efficient queries by target card (for reverse lookups)
CREATE INDEX idx_card_relationships_target ON card_relationships(target_card_id);

-- Enable RLS
ALTER TABLE card_relationships ENABLE ROW LEVEL SECURITY;
