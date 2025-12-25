-- Migration: advanced_search_schema
-- Created at: 1766436000
-- Purpose: Add tables for saved searches and search history functionality

-- Saved searches - user-named search configurations for quick re-execution
CREATE TABLE saved_searches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    query_config JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_used_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Search history - tracks recent searches per user for quick re-execution
CREATE TABLE search_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    query_config JSONB NOT NULL DEFAULT '{}',
    executed_at TIMESTAMPTZ DEFAULT NOW(),
    result_count INTEGER DEFAULT 0
);

-- Indexes for performance
CREATE INDEX idx_saved_searches_user_id ON saved_searches(user_id);
CREATE INDEX idx_saved_searches_last_used ON saved_searches(user_id, last_used_at DESC);
CREATE INDEX idx_search_history_user_id ON search_history(user_id);
CREATE INDEX idx_search_history_executed_at ON search_history(user_id, executed_at DESC);

-- Enable Row Level Security
ALTER TABLE saved_searches ENABLE ROW LEVEL SECURITY;
ALTER TABLE search_history ENABLE ROW LEVEL SECURITY;

-- RLS Policies for saved_searches
-- Users can only see/manage their own saved searches
CREATE POLICY "Users can view own saved searches" ON saved_searches
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can create own saved searches" ON saved_searches
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own saved searches" ON saved_searches
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own saved searches" ON saved_searches
    FOR DELETE USING (auth.uid() = user_id);

-- RLS Policies for search_history
-- Users can only see/manage their own search history
CREATE POLICY "Users can view own search history" ON search_history
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can create own search history" ON search_history
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own search history" ON search_history
    FOR DELETE USING (auth.uid() = user_id);

-- Function to cleanup old search history entries (keep last 50 per user)
CREATE OR REPLACE FUNCTION cleanup_search_history()
RETURNS TRIGGER AS $$
BEGIN
    DELETE FROM search_history
    WHERE user_id = NEW.user_id
    AND id NOT IN (
        SELECT id FROM search_history
        WHERE user_id = NEW.user_id
        ORDER BY executed_at DESC
        LIMIT 50
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger to automatically cleanup old search history after insert
CREATE TRIGGER trigger_cleanup_search_history
    AFTER INSERT ON search_history
    FOR EACH ROW
    EXECUTE FUNCTION cleanup_search_history();
