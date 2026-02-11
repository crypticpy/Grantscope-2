-- Migration: source_preferences
-- Created at: 1766739100
-- Purpose: Add source preferences to cards and user signal preferences table

-- Source preferences on cards (for steering discovery/research)
ALTER TABLE cards ADD COLUMN IF NOT EXISTS source_preferences JSONB DEFAULT '{}';
-- Structure:
-- {
--   "enabled_categories": ["news", "academic", "government", "tech_blog", "rss"],
--   "preferred_type": "federal",
--   "priority_domains": ["gartner.com", "mckinsey.com"],
--   "custom_rss_feeds": ["https://..."],
--   "keywords": ["smart city", "municipal AI"]
-- }

COMMENT ON COLUMN cards.source_preferences IS 'JSON config for steering which sources to use during discovery/research scans';

-- User signal preferences (pins, custom sort order for personal hub)
CREATE TABLE IF NOT EXISTS user_signal_preferences (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  card_id UUID NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
  is_pinned BOOLEAN DEFAULT FALSE,
  custom_sort_order INTEGER,
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, card_id)
);

ALTER TABLE user_signal_preferences ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users manage own signal preferences"
  ON user_signal_preferences FOR ALL
  USING (auth.uid() = user_id);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_user_signal_prefs_user ON user_signal_preferences (user_id);
CREATE INDEX IF NOT EXISTS idx_user_signal_prefs_card ON user_signal_preferences (card_id);
CREATE INDEX IF NOT EXISTS idx_user_signal_prefs_pinned ON user_signal_preferences (user_id, is_pinned) WHERE is_pinned = TRUE;
