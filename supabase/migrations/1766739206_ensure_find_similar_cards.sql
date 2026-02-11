-- Ensure find_similar_cards exists with correct vector type reference.
-- Earlier migrations (1766435000, 1766435003, 1766435006) were marked as
-- applied but may not have actually run due to vector type / CLI parser issues.

DROP FUNCTION IF EXISTS public.find_similar_cards(extensions.vector, UUID, FLOAT, INT);
DROP FUNCTION IF EXISTS public.find_similar_cards(vector, UUID, FLOAT, INT);

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
AS $fn$
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
$fn$;

GRANT EXECUTE ON FUNCTION public.find_similar_cards(extensions.vector(1536), UUID, FLOAT, INT) TO authenticated;
GRANT EXECUTE ON FUNCTION public.find_similar_cards(extensions.vector(1536), UUID, FLOAT, INT) TO service_role;
