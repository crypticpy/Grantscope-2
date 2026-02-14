-- Migration: card_snapshots table for version history of card fields
-- Stores snapshots of description and summary before they get overwritten
-- by deep research, profile refresh, or other automated processes.

CREATE TABLE IF NOT EXISTS card_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    card_id UUID NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    field_name TEXT NOT NULL DEFAULT 'description',
    content TEXT NOT NULL,
    content_length INT NOT NULL,
    trigger TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT DEFAULT 'system',

    CHECK (field_name IN ('description', 'summary')),
    CHECK (trigger IN ('deep_research', 'profile_refresh', 'enhance_research', 'manual_edit', 'restore'))
);

-- Fast lookup: "show me all versions of this card's description"
CREATE INDEX IF NOT EXISTS idx_card_snapshots_card_field
    ON card_snapshots(card_id, field_name, created_at DESC);

-- RLS
ALTER TABLE card_snapshots ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    CREATE POLICY "Authenticated users can view card_snapshots"
        ON card_snapshots FOR SELECT TO authenticated USING (true);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE POLICY "Service role full access on card_snapshots"
        ON card_snapshots FOR ALL TO service_role USING (true) WITH CHECK (true);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
