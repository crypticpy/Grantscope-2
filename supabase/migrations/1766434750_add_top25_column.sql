-- Migration: add_top25_column
-- Created at: 1766434750
-- Description: Adds top25_relevance column to cards table for CMO Top 25 priority alignment

-- Add top25_relevance column as JSONB array
ALTER TABLE cards ADD COLUMN IF NOT EXISTS top25_relevance JSONB DEFAULT '[]'::jsonb;

-- Create index for querying cards by Top 25 priority
CREATE INDEX IF NOT EXISTS idx_cards_top25 ON cards USING GIN (top25_relevance);
