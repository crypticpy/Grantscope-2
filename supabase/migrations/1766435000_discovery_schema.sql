-- Migration: discovery_schema
-- Created at: 1766435000
-- Description: Discovery System - automated weekly scans, blocked topics, user dismissals, and card review workflow

-- ============================================================================
-- DISCOVERY RUNS TABLE
-- Tracks automated discovery scan sessions (weekly or triggered)
-- ============================================================================

CREATE TABLE IF NOT EXISTS discovery_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Timing
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,

    -- Status tracking
    status TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),

    -- Scope of the scan
    pillars_scanned TEXT[] DEFAULT '{}',
    priorities_scanned TEXT[] DEFAULT '{}',

    -- Generation metrics
    queries_generated INTEGER DEFAULT 0,

    -- Results metrics
    sources_found INTEGER DEFAULT 0,
    sources_relevant INTEGER DEFAULT 0,
    cards_created INTEGER DEFAULT 0,
    cards_enriched INTEGER DEFAULT 0,
    cards_deduplicated INTEGER DEFAULT 0,

    -- Cost tracking (OpenAI API costs)
    estimated_cost NUMERIC(10,4) DEFAULT 0,

    -- Error handling
    error_message TEXT,
    error_details JSONB,

    -- Detailed summary for review
    summary_report JSONB DEFAULT '{}',

    -- Trigger context
    triggered_by TEXT DEFAULT 'scheduled' CHECK (triggered_by IN ('scheduled', 'manual', 'api')),
    triggered_by_user UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add comments for documentation
COMMENT ON TABLE discovery_runs IS 'Tracks automated discovery scans that find and process new intelligence sources';
COMMENT ON COLUMN discovery_runs.status IS 'Scan lifecycle: running -> completed/failed/cancelled';
COMMENT ON COLUMN discovery_runs.pillars_scanned IS 'Array of pillar IDs that were included in this scan';
COMMENT ON COLUMN discovery_runs.priorities_scanned IS 'Array of priority/goal IDs targeted in this scan';
COMMENT ON COLUMN discovery_runs.sources_relevant IS 'Number of sources that passed relevance threshold after AI scoring';
COMMENT ON COLUMN discovery_runs.cards_deduplicated IS 'Number of potential cards that were merged with existing cards';
COMMENT ON COLUMN discovery_runs.summary_report IS 'JSON containing detailed breakdown by pillar, top discoveries, etc.';

-- ============================================================================
-- DISCOVERY BLOCKS TABLE (Ignored Topics)
-- Tracks topics that users have marked as irrelevant or to be excluded
-- ============================================================================

CREATE TABLE IF NOT EXISTS discovery_blocks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Topic identification
    topic_name TEXT NOT NULL,
    topic_embedding VECTOR(1536),
    keywords TEXT[] DEFAULT '{}',

    -- Usage tracking
    blocked_by_count INTEGER DEFAULT 1,
    first_blocked_at TIMESTAMPTZ DEFAULT NOW(),
    last_blocked_at TIMESTAMPTZ DEFAULT NOW(),

    -- Context
    reason TEXT,
    example_sources TEXT[],

    -- Status
    is_active BOOLEAN DEFAULT true,

    -- Categorization
    block_type TEXT DEFAULT 'topic' CHECK (block_type IN ('topic', 'domain', 'keyword', 'source')),

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Unique constraint on topic name to prevent duplicates
CREATE UNIQUE INDEX IF NOT EXISTS idx_discovery_blocks_topic_name ON discovery_blocks (lower(topic_name));

-- Add comments for documentation
COMMENT ON TABLE discovery_blocks IS 'Topics, domains, or keywords to exclude from discovery scans';
COMMENT ON COLUMN discovery_blocks.topic_embedding IS 'Vector embedding for semantic similarity matching against new content';
COMMENT ON COLUMN discovery_blocks.blocked_by_count IS 'Number of users who have blocked this topic (for prioritization)';
COMMENT ON COLUMN discovery_blocks.keywords IS 'Array of keywords/phrases associated with this blocked topic';
COMMENT ON COLUMN discovery_blocks.block_type IS 'Type of block: topic (semantic), domain (URL), keyword (exact), source (specific)';

-- ============================================================================
-- USER CARD DISMISSALS TABLE
-- Tracks when users dismiss cards from their discovery queue
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_card_dismissals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- References
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    card_id UUID NOT NULL REFERENCES cards(id) ON DELETE CASCADE,

    -- Dismissal context
    dismissed_at TIMESTAMPTZ DEFAULT NOW(),
    reason TEXT,
    dismiss_type TEXT DEFAULT 'not_relevant' CHECK (dismiss_type IN (
        'not_relevant', 'already_known', 'not_interested', 'wrong_pillar', 'duplicate', 'other'
    )),

    -- Feedback for improving discovery
    feedback_notes TEXT,
    suggest_block_topic BOOLEAN DEFAULT false,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Prevent duplicate dismissals
    UNIQUE(user_id, card_id)
);

-- Add comments for documentation
COMMENT ON TABLE user_card_dismissals IS 'Tracks user-level card dismissals for personalized discovery filtering';
COMMENT ON COLUMN user_card_dismissals.dismiss_type IS 'Categorized reason for dismissal to improve future discovery';
COMMENT ON COLUMN user_card_dismissals.suggest_block_topic IS 'User suggests this topic should be globally blocked';

-- ============================================================================
-- ADD REVIEW STATUS COLUMNS TO CARDS TABLE
-- Extends cards with discovery workflow fields
-- ============================================================================

-- Review status for discovery workflow
ALTER TABLE cards ADD COLUMN IF NOT EXISTS review_status TEXT
    DEFAULT 'active'
    CHECK (review_status IN ('discovered', 'pending_review', 'active', 'rejected'));

-- When the card was first discovered by automated scan
ALTER TABLE cards ADD COLUMN IF NOT EXISTS discovered_at TIMESTAMPTZ;

-- Link to the discovery run that created this card
ALTER TABLE cards ADD COLUMN IF NOT EXISTS discovery_run_id UUID REFERENCES discovery_runs(id) ON DELETE SET NULL;

-- AI confidence score for the card's relevance (0.00 to 1.00)
ALTER TABLE cards ADD COLUMN IF NOT EXISTS ai_confidence NUMERIC(3,2)
    CHECK (ai_confidence IS NULL OR (ai_confidence >= 0 AND ai_confidence <= 1));

-- Rejection tracking
ALTER TABLE cards ADD COLUMN IF NOT EXISTS rejected_at TIMESTAMPTZ;
ALTER TABLE cards ADD COLUMN IF NOT EXISTS rejected_by UUID REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE cards ADD COLUMN IF NOT EXISTS rejection_reason TEXT;

-- Discovery metadata (for debugging and analytics)
ALTER TABLE cards ADD COLUMN IF NOT EXISTS discovery_metadata JSONB DEFAULT '{}';

-- Add comments for documentation
COMMENT ON COLUMN cards.review_status IS 'Discovery workflow: discovered -> pending_review -> active/rejected';
COMMENT ON COLUMN cards.discovered_at IS 'Timestamp when card was created by automated discovery (null for manual cards)';
COMMENT ON COLUMN cards.discovery_run_id IS 'Reference to the discovery run that created this card';
COMMENT ON COLUMN cards.ai_confidence IS 'AI confidence score 0-1 for relevance to organizational priorities';
COMMENT ON COLUMN cards.rejected_at IS 'Timestamp when card was rejected during review';
COMMENT ON COLUMN cards.rejected_by IS 'User who rejected the card during review';
COMMENT ON COLUMN cards.rejection_reason IS 'Reason provided when rejecting a discovered card';
COMMENT ON COLUMN cards.discovery_metadata IS 'JSON with discovery context: queries matched, sources, dedup attempts';

-- ============================================================================
-- FIND SIMILAR CARDS FUNCTION (for deduplication)
-- Used during discovery to prevent duplicate card creation
-- ============================================================================

CREATE OR REPLACE FUNCTION find_similar_cards(
    query_embedding VECTOR(1536),
    exclude_card_id UUID DEFAULT NULL,
    match_threshold FLOAT DEFAULT 0.75,
    match_count INT DEFAULT 10
)
RETURNS TABLE (
    id UUID,
    name TEXT,
    summary TEXT,
    pillar_id TEXT,
    horizon TEXT,
    similarity FLOAT
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        c.name,
        c.summary,
        c.pillar_id,
        c.horizon,
        1 - (c.embedding <=> query_embedding) AS similarity
    FROM cards c
    WHERE
        c.embedding IS NOT NULL
        -- Exclude rejected cards from deduplication matching
        AND c.review_status != 'rejected'
        -- Exclude the card we're comparing against (for updates)
        AND (exclude_card_id IS NULL OR c.id != exclude_card_id)
        -- Only return matches above threshold
        AND 1 - (c.embedding <=> query_embedding) > match_threshold
    ORDER BY c.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Grant execute permission
GRANT EXECUTE ON FUNCTION find_similar_cards(VECTOR(1536), UUID, FLOAT, INT) TO authenticated;
GRANT EXECUTE ON FUNCTION find_similar_cards(VECTOR(1536), UUID, FLOAT, INT) TO service_role;

COMMENT ON FUNCTION find_similar_cards IS 'Find cards similar to a query embedding for deduplication during discovery';

-- ============================================================================
-- FIND BLOCKED TOPICS FUNCTION (for discovery filtering)
-- Checks if content matches any blocked topics
-- ============================================================================

CREATE OR REPLACE FUNCTION find_matching_blocks(
    content_embedding VECTOR(1536),
    match_threshold FLOAT DEFAULT 0.80
)
RETURNS TABLE (
    id UUID,
    topic_name TEXT,
    similarity FLOAT
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT
        db.id,
        db.topic_name,
        1 - (db.topic_embedding <=> content_embedding) AS similarity
    FROM discovery_blocks db
    WHERE
        db.is_active = true
        AND db.topic_embedding IS NOT NULL
        AND 1 - (db.topic_embedding <=> content_embedding) > match_threshold
    ORDER BY db.topic_embedding <=> content_embedding
    LIMIT 5;
END;
$$;

-- Grant execute permission
GRANT EXECUTE ON FUNCTION find_matching_blocks(VECTOR(1536), FLOAT) TO authenticated;
GRANT EXECUTE ON FUNCTION find_matching_blocks(VECTOR(1536), FLOAT) TO service_role;

COMMENT ON FUNCTION find_matching_blocks IS 'Check if content embedding matches any blocked topics';

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- Discovery runs indexes
CREATE INDEX IF NOT EXISTS idx_discovery_runs_status
    ON discovery_runs(status);

CREATE INDEX IF NOT EXISTS idx_discovery_runs_started
    ON discovery_runs(started_at DESC);

CREATE INDEX IF NOT EXISTS idx_discovery_runs_status_started
    ON discovery_runs(status, started_at DESC)
    WHERE status IN ('running', 'completed');

-- Discovery blocks indexes
CREATE INDEX IF NOT EXISTS idx_discovery_blocks_embedding
    ON discovery_blocks
    USING ivfflat (topic_embedding vector_cosine_ops)
    WITH (lists = 50);

CREATE INDEX IF NOT EXISTS idx_discovery_blocks_active
    ON discovery_blocks(is_active)
    WHERE is_active = true;

CREATE INDEX IF NOT EXISTS idx_discovery_blocks_keywords
    ON discovery_blocks
    USING gin (keywords);

-- User card dismissals indexes
CREATE INDEX IF NOT EXISTS idx_user_dismissals_user
    ON user_card_dismissals(user_id);

CREATE INDEX IF NOT EXISTS idx_user_dismissals_card
    ON user_card_dismissals(card_id);

CREATE INDEX IF NOT EXISTS idx_user_dismissals_user_dismissed
    ON user_card_dismissals(user_id, dismissed_at DESC);

-- Cards table indexes for discovery workflow
CREATE INDEX IF NOT EXISTS idx_cards_review_status
    ON cards(review_status);

CREATE INDEX IF NOT EXISTS idx_cards_discovered_at
    ON cards(discovered_at DESC)
    WHERE discovered_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_cards_discovery_run
    ON cards(discovery_run_id)
    WHERE discovery_run_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_cards_pending_review
    ON cards(review_status, discovered_at DESC)
    WHERE review_status IN ('discovered', 'pending_review');

CREATE INDEX IF NOT EXISTS idx_cards_ai_confidence
    ON cards(ai_confidence DESC)
    WHERE review_status IN ('discovered', 'pending_review');

-- ============================================================================
-- ROW LEVEL SECURITY POLICIES
-- ============================================================================

-- Enable RLS on new tables
ALTER TABLE discovery_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE discovery_blocks ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_card_dismissals ENABLE ROW LEVEL SECURITY;

-- Discovery Runs: viewable by authenticated users, full access for service_role
CREATE POLICY "Discovery runs viewable by authenticated users"
    ON discovery_runs FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Service role full access on discovery_runs"
    ON discovery_runs FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Discovery Blocks: viewable by authenticated users, full access for service_role
CREATE POLICY "Discovery blocks viewable by authenticated users"
    ON discovery_blocks FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Service role full access on discovery_blocks"
    ON discovery_blocks FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Allow authenticated users to suggest blocks (insert only)
CREATE POLICY "Authenticated users can suggest blocks"
    ON discovery_blocks FOR INSERT
    TO authenticated
    WITH CHECK (true);

-- User Card Dismissals: users manage their own
CREATE POLICY "Users can view own dismissals"
    ON user_card_dismissals FOR SELECT
    TO authenticated
    USING (user_id = auth.uid());

CREATE POLICY "Users can create own dismissals"
    ON user_card_dismissals FOR INSERT
    TO authenticated
    WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users can update own dismissals"
    ON user_card_dismissals FOR UPDATE
    TO authenticated
    USING (user_id = auth.uid());

CREATE POLICY "Users can delete own dismissals"
    ON user_card_dismissals FOR DELETE
    TO authenticated
    USING (user_id = auth.uid());

CREATE POLICY "Service role full access on user_card_dismissals"
    ON user_card_dismissals FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to get discovery queue for a user (cards pending review, excluding dismissed)
CREATE OR REPLACE FUNCTION get_discovery_queue(
    p_user_id UUID,
    p_limit INT DEFAULT 20,
    p_offset INT DEFAULT 0
)
RETURNS TABLE (
    id UUID,
    name TEXT,
    summary TEXT,
    pillar_id TEXT,
    horizon TEXT,
    ai_confidence NUMERIC(3,2),
    discovered_at TIMESTAMPTZ,
    discovery_run_id UUID
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        c.name,
        c.summary,
        c.pillar_id,
        c.horizon,
        c.ai_confidence,
        c.discovered_at,
        c.discovery_run_id
    FROM cards c
    WHERE
        c.review_status IN ('discovered', 'pending_review')
        -- Exclude cards the user has dismissed
        AND NOT EXISTS (
            SELECT 1 FROM user_card_dismissals ucd
            WHERE ucd.card_id = c.id AND ucd.user_id = p_user_id
        )
    ORDER BY
        c.ai_confidence DESC NULLS LAST,
        c.discovered_at DESC
    LIMIT p_limit
    OFFSET p_offset;
END;
$$;

GRANT EXECUTE ON FUNCTION get_discovery_queue(UUID, INT, INT) TO authenticated;
GRANT EXECUTE ON FUNCTION get_discovery_queue(UUID, INT, INT) TO service_role;

COMMENT ON FUNCTION get_discovery_queue IS 'Get cards pending review for a user, excluding their dismissed cards';

-- Function to approve a discovered card (move to active)
CREATE OR REPLACE FUNCTION approve_discovered_card(
    p_card_id UUID,
    p_user_id UUID
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    UPDATE cards
    SET
        review_status = 'active',
        status = 'active',
        updated_at = NOW()
    WHERE
        id = p_card_id
        AND review_status IN ('discovered', 'pending_review');

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Card not found or not in reviewable state';
    END IF;
END;
$$;

GRANT EXECUTE ON FUNCTION approve_discovered_card(UUID, UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION approve_discovered_card(UUID, UUID) TO service_role;

COMMENT ON FUNCTION approve_discovered_card IS 'Approve a discovered card, moving it to active status';

-- Function to reject a discovered card
CREATE OR REPLACE FUNCTION reject_discovered_card(
    p_card_id UUID,
    p_user_id UUID,
    p_reason TEXT DEFAULT NULL
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    UPDATE cards
    SET
        review_status = 'rejected',
        status = 'archived',
        rejected_at = NOW(),
        rejected_by = p_user_id,
        rejection_reason = p_reason,
        updated_at = NOW()
    WHERE
        id = p_card_id
        AND review_status IN ('discovered', 'pending_review');

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Card not found or not in reviewable state';
    END IF;
END;
$$;

GRANT EXECUTE ON FUNCTION reject_discovered_card(UUID, UUID, TEXT) TO authenticated;
GRANT EXECUTE ON FUNCTION reject_discovered_card(UUID, UUID, TEXT) TO service_role;

COMMENT ON FUNCTION reject_discovered_card IS 'Reject a discovered card with optional reason';

-- Function to increment block count when a topic is blocked again
CREATE OR REPLACE FUNCTION increment_block_count(p_topic_name TEXT)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_block_id UUID;
BEGIN
    -- Try to update existing block
    UPDATE discovery_blocks
    SET
        blocked_by_count = blocked_by_count + 1,
        last_blocked_at = NOW(),
        updated_at = NOW()
    WHERE lower(topic_name) = lower(p_topic_name)
    RETURNING id INTO v_block_id;

    -- If no existing block found, return null (caller should insert new)
    RETURN v_block_id;
END;
$$;

GRANT EXECUTE ON FUNCTION increment_block_count(TEXT) TO authenticated;
GRANT EXECUTE ON FUNCTION increment_block_count(TEXT) TO service_role;

COMMENT ON FUNCTION increment_block_count IS 'Increment block count for an existing blocked topic';

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Update updated_at timestamp for discovery_blocks
CREATE OR REPLACE FUNCTION update_discovery_blocks_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER discovery_blocks_updated_at
    BEFORE UPDATE ON discovery_blocks
    FOR EACH ROW
    EXECUTE FUNCTION update_discovery_blocks_updated_at();

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================
