-- Migration: fix_vector_search_path
-- Created at: 1766435006
-- Description: Fix vector operator access by adding extensions schema to search_path
-- Fixes: "operator does not exist: extensions.vector <=> extensions.vector" error
--
-- The previous migration moved the vector extension to the extensions schema,
-- but functions with SET search_path = '' cannot access the <=> operator.
-- Solution: Set search_path to 'extensions, public' so operators are found.

-- ============================================================================
-- DROP EXISTING FUNCTIONS (required to change search_path)
-- ============================================================================

DROP FUNCTION IF EXISTS public.find_similar_cards(extensions.vector, UUID, FLOAT, INT);
DROP FUNCTION IF EXISTS public.find_matching_blocks(extensions.vector, FLOAT);

-- ============================================================================
-- FIX: find_similar_cards with proper search_path
-- ============================================================================

CREATE OR REPLACE FUNCTION public.find_similar_cards(
    query_embedding extensions.vector(1536),
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
SET search_path = extensions, public
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
-- FIX: find_matching_blocks with proper search_path
-- ============================================================================

CREATE OR REPLACE FUNCTION public.find_matching_blocks(
    content_embedding extensions.vector(1536),
    match_threshold FLOAT DEFAULT 0.80
)
RETURNS TABLE (
    id UUID,
    topic_name TEXT,
    similarity FLOAT
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = extensions, public
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
-- GRANT PERMISSIONS
-- ============================================================================

GRANT EXECUTE ON FUNCTION public.find_similar_cards(extensions.vector(1536), UUID, FLOAT, INT) TO authenticated;
GRANT EXECUTE ON FUNCTION public.find_similar_cards(extensions.vector(1536), UUID, FLOAT, INT) TO service_role;

GRANT EXECUTE ON FUNCTION public.find_matching_blocks(extensions.vector(1536), FLOAT) TO authenticated;
GRANT EXECUTE ON FUNCTION public.find_matching_blocks(extensions.vector(1536), FLOAT) TO service_role;

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON FUNCTION public.find_similar_cards IS 'Find cards similar to embedding with extensions schema in search_path for vector operators';
COMMENT ON FUNCTION public.find_matching_blocks IS 'Check content against blocked topics with extensions schema in search_path for vector operators';
