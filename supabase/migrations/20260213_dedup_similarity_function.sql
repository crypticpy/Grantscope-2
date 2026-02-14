-- Migration: dedup_similarity_function
-- Created at: 20260213
-- Phase 2, Layer 1.2: Embedding-based Content Deduplication
--
-- PURPOSE:
--   Creates a PostgreSQL function for pgvector-based source similarity search.
--   Used by the deduplication module (app/deduplication.py) to find semantically
--   similar sources on the same card before inserting a new source.
--
-- FUNCTION: match_sources_by_embedding(query_embedding, target_card_id, match_threshold, match_count)
--   Searches existing sources on a given card by cosine similarity (1 - cosine distance).
--   Only considers sources that:
--     - Belong to the specified card (card_id = target_card_id)
--     - Have a non-NULL embedding vector
--     - Are NOT already marked as duplicates (duplicate_of IS NULL)
--     - Exceed the similarity threshold
--
-- DEPENDS ON:
--   - pgvector extension (enabled in project)
--   - sources table with embedding VECTOR(1536) column
--   - 20260213_source_quality_dedup.sql (duplicate_of column)
--
-- ROLLBACK:
--   DROP FUNCTION IF EXISTS match_sources_by_embedding;
-- ============================================================================

-- Ensure pgvector extension is available (Supabase may have it in 'extensions' schema)
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;

-- Make vector type visible in public schema
DO $$ BEGIN
    EXECUTE 'SET search_path TO public, extensions';
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

CREATE OR REPLACE FUNCTION match_sources_by_embedding(
    query_embedding vector(1536),
    target_card_id uuid,
    match_threshold float DEFAULT 0.85,
    match_count int DEFAULT 5
)
RETURNS TABLE (
    id uuid,
    url text,
    title text,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        s.id,
        s.url,
        s.title,
        (1 - (s.embedding <=> query_embedding))::float AS similarity
    FROM sources s
    WHERE s.card_id = target_card_id
    AND s.embedding IS NOT NULL
    AND s.duplicate_of IS NULL
    AND (1 - (s.embedding <=> query_embedding)) > match_threshold
    ORDER BY s.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

SELECT 'match_sources_by_embedding function created' AS status;
