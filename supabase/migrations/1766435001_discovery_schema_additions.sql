-- Discovery Schema Additions
-- Migration: 1766435001_discovery_schema_additions.sql
-- Adds missing review tracking columns to cards table

-- Add review tracking columns to cards table
-- These columns track when cards are reviewed, by whom, and any notes

ALTER TABLE cards
ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS reviewed_by UUID REFERENCES auth.users(id),
ADD COLUMN IF NOT EXISTS review_notes TEXT,
ADD COLUMN IF NOT EXISTS auto_approved_at TIMESTAMPTZ;

-- Add comments for documentation
COMMENT ON COLUMN cards.reviewed_at IS 'Timestamp when the card was reviewed by a human';
COMMENT ON COLUMN cards.reviewed_by IS 'User ID of the reviewer who approved/rejected the card';
COMMENT ON COLUMN cards.review_notes IS 'Optional notes from the reviewer about the card';
COMMENT ON COLUMN cards.auto_approved_at IS 'Timestamp when the card was automatically approved by the system';

-- Create index for efficient queries on review status
CREATE INDEX IF NOT EXISTS idx_cards_reviewed_at ON cards(reviewed_at) WHERE reviewed_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_cards_reviewed_by ON cards(reviewed_by) WHERE reviewed_by IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_cards_auto_approved_at ON cards(auto_approved_at) WHERE auto_approved_at IS NOT NULL;
