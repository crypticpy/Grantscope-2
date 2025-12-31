-- Migration: security_search_path_fix
-- Created at: 1766435003
-- Description: Fix function_search_path_mutable security warnings
-- Sets explicit search_path on all functions to prevent search path injection attacks

-- ============================================================================
-- DROP EXISTING FUNCTIONS FIRST (required to change parameter names)
-- ============================================================================

DROP FUNCTION IF EXISTS public.increment_deep_research_count(UUID);
DROP FUNCTION IF EXISTS public.find_similar_cards(VECTOR(1536), UUID, FLOAT, INT);
DROP FUNCTION IF EXISTS public.find_matching_blocks(VECTOR(1536), FLOAT);
DROP FUNCTION IF EXISTS public.get_discovery_queue(UUID, INT, INT);
DROP FUNCTION IF EXISTS public.approve_discovered_card(UUID, UUID);
DROP FUNCTION IF EXISTS public.reject_discovered_card(UUID, UUID, TEXT);
DROP FUNCTION IF EXISTS public.increment_block_count(TEXT);
-- Note: Trigger functions don't need to be dropped, CREATE OR REPLACE works

-- ============================================================================
-- FIX: increment_deep_research_count
-- ============================================================================

CREATE OR REPLACE FUNCTION public.increment_deep_research_count(p_card_id UUID)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_today DATE := CURRENT_DATE;
BEGIN
    UPDATE public.cards
    SET
        deep_research_count_today = CASE
            WHEN deep_research_reset_date = v_today THEN COALESCE(deep_research_count_today, 0) + 1
            ELSE 1
        END,
        deep_research_reset_date = v_today
    WHERE id = p_card_id;
END;
$$;

-- ============================================================================
-- FIX: find_similar_cards
-- ============================================================================

CREATE OR REPLACE FUNCTION public.find_similar_cards(
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
SET search_path = ''
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
    FROM public.cards c
    WHERE
        c.embedding IS NOT NULL
        AND c.review_status != 'rejected'
        AND (exclude_card_id IS NULL OR c.id != exclude_card_id)
        AND 1 - (c.embedding <=> query_embedding) > match_threshold
    ORDER BY c.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- ============================================================================
-- FIX: find_matching_blocks
-- ============================================================================

CREATE OR REPLACE FUNCTION public.find_matching_blocks(
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
SET search_path = ''
AS $$
BEGIN
    RETURN QUERY
    SELECT
        db.id,
        db.topic_name,
        1 - (db.topic_embedding <=> content_embedding) AS similarity
    FROM public.discovery_blocks db
    WHERE
        db.is_active = true
        AND db.topic_embedding IS NOT NULL
        AND 1 - (db.topic_embedding <=> content_embedding) > match_threshold
    ORDER BY db.topic_embedding <=> content_embedding
    LIMIT 5;
END;
$$;

-- ============================================================================
-- FIX: get_discovery_queue
-- ============================================================================

CREATE OR REPLACE FUNCTION public.get_discovery_queue(
    p_user_id UUID,
    p_limit INTEGER DEFAULT 20,
    p_offset INTEGER DEFAULT 0
)
RETURNS TABLE (
    id UUID,
    name TEXT,
    summary TEXT,
    pillar_id TEXT,
    horizon TEXT,
    ai_confidence NUMERIC,
    discovered_at TIMESTAMPTZ,
    discovery_run_id UUID
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
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
    FROM public.cards c
    WHERE
        c.review_status IN ('discovered', 'pending_review')
        AND NOT EXISTS (
            SELECT 1 FROM public.user_card_dismissals ucd
            WHERE ucd.card_id = c.id AND ucd.user_id = p_user_id
        )
    ORDER BY
        c.ai_confidence DESC NULLS LAST,
        c.discovered_at DESC
    LIMIT p_limit
    OFFSET p_offset;
END;
$$;

-- ============================================================================
-- FIX: approve_discovered_card
-- ============================================================================

CREATE OR REPLACE FUNCTION public.approve_discovered_card(
    p_card_id UUID,
    p_reviewer_id UUID DEFAULT NULL
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
    UPDATE public.cards
    SET
        review_status = 'active',
        status = 'active',
        reviewed_at = NOW(),
        reviewed_by = p_reviewer_id,
        updated_at = NOW()
    WHERE id = p_card_id
    AND review_status IN ('discovered', 'pending_review');
END;
$$;

-- ============================================================================
-- FIX: reject_discovered_card
-- ============================================================================

CREATE OR REPLACE FUNCTION public.reject_discovered_card(
    p_card_id UUID,
    p_reviewer_id UUID DEFAULT NULL,
    p_reason TEXT DEFAULT NULL
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
    UPDATE public.cards
    SET
        review_status = 'rejected',
        status = 'archived',
        rejected_at = NOW(),
        rejected_by = p_reviewer_id,
        rejection_reason = p_reason,
        updated_at = NOW()
    WHERE id = p_card_id
    AND review_status IN ('discovered', 'pending_review');
END;
$$;

-- ============================================================================
-- FIX: increment_block_count
-- ============================================================================

CREATE OR REPLACE FUNCTION public.increment_block_count(p_topic_name TEXT)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
    UPDATE public.discovery_blocks
    SET
        blocked_by_count = blocked_by_count + 1,
        last_blocked_at = NOW(),
        updated_at = NOW()
    WHERE lower(topic_name) = lower(p_topic_name);
END;
$$;

-- ============================================================================
-- FIX: update_discovery_blocks_updated_at (trigger function)
-- ============================================================================

CREATE OR REPLACE FUNCTION public.update_discovery_blocks_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

-- ============================================================================
-- FIX: update_discovered_sources_updated_at (trigger function)
-- ============================================================================

CREATE OR REPLACE FUNCTION public.update_discovered_sources_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

-- ============================================================================
-- GRANT PERMISSIONS (required after dropping and recreating)
-- ============================================================================

GRANT EXECUTE ON FUNCTION public.increment_deep_research_count(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION public.increment_deep_research_count(UUID) TO service_role;

GRANT EXECUTE ON FUNCTION public.find_similar_cards(VECTOR(1536), UUID, FLOAT, INT) TO authenticated;
GRANT EXECUTE ON FUNCTION public.find_similar_cards(VECTOR(1536), UUID, FLOAT, INT) TO service_role;

GRANT EXECUTE ON FUNCTION public.find_matching_blocks(VECTOR(1536), FLOAT) TO authenticated;
GRANT EXECUTE ON FUNCTION public.find_matching_blocks(VECTOR(1536), FLOAT) TO service_role;

GRANT EXECUTE ON FUNCTION public.get_discovery_queue(UUID, INT, INT) TO authenticated;
GRANT EXECUTE ON FUNCTION public.get_discovery_queue(UUID, INT, INT) TO service_role;

GRANT EXECUTE ON FUNCTION public.approve_discovered_card(UUID, UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION public.approve_discovered_card(UUID, UUID) TO service_role;

GRANT EXECUTE ON FUNCTION public.reject_discovered_card(UUID, UUID, TEXT) TO authenticated;
GRANT EXECUTE ON FUNCTION public.reject_discovered_card(UUID, UUID, TEXT) TO service_role;

GRANT EXECUTE ON FUNCTION public.increment_block_count(TEXT) TO authenticated;
GRANT EXECUTE ON FUNCTION public.increment_block_count(TEXT) TO service_role;

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON FUNCTION public.increment_deep_research_count IS 'Increment deep research count with secure search_path';
COMMENT ON FUNCTION public.find_similar_cards IS 'Find cards similar to embedding with secure search_path';
COMMENT ON FUNCTION public.find_matching_blocks IS 'Check content against blocked topics with secure search_path';
COMMENT ON FUNCTION public.get_discovery_queue IS 'Get pending discovery cards for review with secure search_path';
COMMENT ON FUNCTION public.approve_discovered_card IS 'Approve a discovered card with secure search_path';
COMMENT ON FUNCTION public.reject_discovered_card IS 'Reject a discovered card with secure search_path';
COMMENT ON FUNCTION public.increment_block_count IS 'Increment block count for topic with secure search_path';
