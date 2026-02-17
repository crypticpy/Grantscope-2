#!/usr/bin/env python3
"""
One-time migration script to fix vector search_path issue.
Run this script to apply the migration: python run_migration.py
"""
import os
from supabase import create_client

# Load env
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("Error: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# The migration SQL
migration_sql = """
-- Migration: fix_vector_search_path
-- Fix vector operator access by adding extensions schema to search_path

-- Drop existing functions
DROP FUNCTION IF EXISTS public.find_similar_cards(extensions.vector, UUID, FLOAT, INT);
DROP FUNCTION IF EXISTS public.find_matching_blocks(extensions.vector, FLOAT);

-- Recreate find_similar_cards with proper search_path
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

-- Recreate find_matching_blocks with proper search_path
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

-- Grant permissions
GRANT EXECUTE ON FUNCTION public.find_similar_cards(extensions.vector(1536), UUID, FLOAT, INT) TO authenticated;
GRANT EXECUTE ON FUNCTION public.find_similar_cards(extensions.vector(1536), UUID, FLOAT, INT) TO service_role;
GRANT EXECUTE ON FUNCTION public.find_matching_blocks(extensions.vector(1536), FLOAT) TO authenticated;
GRANT EXECUTE ON FUNCTION public.find_matching_blocks(extensions.vector(1536), FLOAT) TO service_role;
"""

print("Applying migration: fix_vector_search_path")
print("=" * 50)

try:
    # Execute the migration using Supabase's raw SQL execution via the REST API
    # Note: Supabase Python client doesn't have direct SQL execution,
    # so we'll use the RPC to execute a helper function or use postgrest

    # Actually, we need to use the Supabase SQL editor or connect directly to postgres
    # The Python client doesn't support arbitrary SQL execution

    print("\nNote: The Supabase Python client doesn't support arbitrary SQL execution.")
    print("Please run the following SQL in the Supabase SQL Editor:")
    print("\n" + "=" * 50)
    print(migration_sql)
    print("=" * 50)
    print("\nAlternatively, the migration file has been saved to:")
    print(
        "/Users/aiml/Projects/grantscope-2/supabase/migrations/1766435006_fix_vector_search_path.sql"
    )

except Exception as e:
    print(f"Error: {e}")
    exit(1)
