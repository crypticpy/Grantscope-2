-- Migration: hybrid_search
-- Created at: 2026-02-11
-- Description: Add hybrid search infrastructure combining PostgreSQL full-text
--   search (FTS) with pgvector similarity search via Reciprocal Rank Fusion (RRF).
--
--   This migration adds:
--     1. tsvector columns and auto-update triggers on cards and sources
--     2. Backfill of search_vector for existing rows
--     3. GIN indexes for fast FTS queries
--     4. hybrid_search_cards() — RRF-fused FTS + vector search over cards
--     5. hybrid_search_sources() — RRF-fused FTS + vector search over sources
--
--   Both hybrid functions accept tunable weights for FTS vs vector ranking and
--   use a FULL OUTER JOIN so results found by only one method are still returned.

-- ============================================================================
-- 1. Add tsvector columns
-- ============================================================================

-- Cards: weighted FTS across name (A), summary (B), description (C)
ALTER TABLE cards ADD COLUMN IF NOT EXISTS search_vector tsvector;

-- Sources: weighted FTS across title (A), ai_summary (B), full_text (C)
ALTER TABLE sources ADD COLUMN IF NOT EXISTS search_vector tsvector;

-- ============================================================================
-- 2. Auto-update triggers
-- ============================================================================

-- --- Cards trigger function ---

CREATE OR REPLACE FUNCTION cards_search_vector_update() RETURNS trigger AS $$
BEGIN
  NEW.search_vector :=
    setweight(to_tsvector('english', coalesce(NEW.name, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(NEW.summary, '')), 'B') ||
    setweight(to_tsvector('english', coalesce(NEW.description, '')), 'C');
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS cards_search_vector_trigger ON cards;
CREATE TRIGGER cards_search_vector_trigger
  BEFORE INSERT OR UPDATE OF name, summary, description ON cards
  FOR EACH ROW EXECUTE FUNCTION cards_search_vector_update();

-- --- Sources trigger function ---

CREATE OR REPLACE FUNCTION sources_search_vector_update() RETURNS trigger AS $$
BEGIN
  NEW.search_vector :=
    setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(NEW.ai_summary, '')), 'B') ||
    setweight(to_tsvector('english', coalesce(NEW.full_text, '')), 'C');
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS sources_search_vector_trigger ON sources;
CREATE TRIGGER sources_search_vector_trigger
  BEFORE INSERT OR UPDATE OF title, ai_summary, full_text ON sources
  FOR EACH ROW EXECUTE FUNCTION sources_search_vector_update();

-- ============================================================================
-- 3. Backfill existing rows
-- ============================================================================

UPDATE cards
SET search_vector =
  setweight(to_tsvector('english', coalesce(name, '')), 'A') ||
  setweight(to_tsvector('english', coalesce(summary, '')), 'B') ||
  setweight(to_tsvector('english', coalesce(description, '')), 'C')
WHERE search_vector IS NULL;

UPDATE sources
SET search_vector =
  setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
  setweight(to_tsvector('english', coalesce(ai_summary, '')), 'B') ||
  setweight(to_tsvector('english', coalesce(full_text, '')), 'C')
WHERE search_vector IS NULL;

-- ============================================================================
-- 4. GIN indexes for full-text search
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_cards_search_vector ON cards USING gin(search_vector);
CREATE INDEX IF NOT EXISTS idx_sources_search_vector ON sources USING gin(search_vector);

-- ============================================================================
-- 5. Hybrid search function for cards (FTS + vector via RRF)
-- ============================================================================

CREATE OR REPLACE FUNCTION hybrid_search_cards(
  query_text TEXT,
  query_embedding extensions.vector(1536),
  match_count INT DEFAULT 20,
  fts_weight FLOAT DEFAULT 1.0,
  vector_weight FLOAT DEFAULT 1.0,
  rrf_k INT DEFAULT 60,
  scope_card_ids UUID[] DEFAULT NULL,
  status_filter TEXT DEFAULT 'active'
)
RETURNS TABLE(
  id UUID,
  name TEXT,
  slug TEXT,
  summary TEXT,
  description TEXT,
  pillar_id TEXT,
  horizon TEXT,
  stage_id TEXT,
  impact_score NUMERIC,
  relevance_score NUMERIC,
  velocity_score NUMERIC,
  risk_score INTEGER,
  signal_quality_score INTEGER,
  fts_rank REAL,
  vector_similarity FLOAT,
  rrf_score FLOAT
)
LANGUAGE sql STABLE
SET search_path = extensions, public
AS $$
  WITH fts_results AS (
    -- Full-text search leg: ts_rank_cd with normalization 32 (divides rank by itself + 1)
    SELECT
      c.id,
      ts_rank_cd(c.search_vector, websearch_to_tsquery('english', query_text), 32) AS rank
    FROM cards c
    WHERE c.search_vector @@ websearch_to_tsquery('english', query_text)
      AND (status_filter IS NULL OR c.status = status_filter)
      AND (scope_card_ids IS NULL OR c.id = ANY(scope_card_ids))
      AND c.search_vector IS NOT NULL
    ORDER BY rank DESC
    LIMIT match_count * 2
  ),
  vector_results AS (
    -- Vector similarity leg: cosine similarity (1 - cosine distance)
    SELECT
      c.id,
      1 - (c.embedding <=> query_embedding) AS similarity
    FROM cards c
    WHERE c.embedding IS NOT NULL
      AND (status_filter IS NULL OR c.status = status_filter)
      AND (scope_card_ids IS NULL OR c.id = ANY(scope_card_ids))
    ORDER BY c.embedding <=> query_embedding
    LIMIT match_count * 2
  ),
  fts_ranked AS (
    SELECT id, rank AS score, ROW_NUMBER() OVER (ORDER BY rank DESC) AS rank_pos
    FROM fts_results
  ),
  vector_ranked AS (
    SELECT id, similarity AS score, ROW_NUMBER() OVER (ORDER BY similarity DESC) AS rank_pos
    FROM vector_results
  ),
  combined AS (
    -- Reciprocal Rank Fusion: score = w_fts/(k + rank_fts) + w_vec/(k + rank_vec)
    -- FULL OUTER JOIN ensures results from only one leg are still included
    SELECT
      COALESCE(f.id, v.id) AS id,
      COALESCE(f.score, 0.0)::REAL AS fts_rank,
      COALESCE(v.score, 0.0)::FLOAT AS vector_similarity,
      (COALESCE(fts_weight / (rrf_k + f.rank_pos), 0.0) +
       COALESCE(vector_weight / (rrf_k + v.rank_pos), 0.0))::FLOAT AS rrf_score
    FROM fts_ranked f
    FULL OUTER JOIN vector_ranked v ON f.id = v.id
  )
  SELECT
    c.id,
    c.name,
    c.slug,
    c.summary,
    c.description,
    c.pillar_id,
    c.horizon,
    c.stage_id,
    c.impact_score,
    c.relevance_score,
    c.velocity_score,
    c.risk_score,
    c.signal_quality_score,
    comb.fts_rank,
    comb.vector_similarity,
    comb.rrf_score
  FROM combined comb
  JOIN cards c ON c.id = comb.id
  ORDER BY comb.rrf_score DESC
  LIMIT match_count;
$$;

-- ============================================================================
-- 6. Hybrid search function for sources (FTS + vector via RRF)
-- ============================================================================

CREATE OR REPLACE FUNCTION hybrid_search_sources(
  query_text TEXT,
  query_embedding extensions.vector(1536),
  match_count INT DEFAULT 20,
  fts_weight FLOAT DEFAULT 1.0,
  vector_weight FLOAT DEFAULT 1.0,
  rrf_k INT DEFAULT 60,
  scope_card_ids UUID[] DEFAULT NULL
)
RETURNS TABLE(
  id UUID,
  card_id UUID,
  card_name TEXT,
  card_slug TEXT,
  title TEXT,
  url TEXT,
  ai_summary TEXT,
  key_excerpts TEXT[],
  published_date TIMESTAMPTZ,
  full_text TEXT,
  fts_rank REAL,
  vector_similarity FLOAT,
  rrf_score FLOAT
)
LANGUAGE sql STABLE
SET search_path = extensions, public
AS $$
  WITH fts_results AS (
    -- Full-text search leg
    SELECT
      s.id,
      ts_rank_cd(s.search_vector, websearch_to_tsquery('english', query_text), 32) AS rank
    FROM sources s
    WHERE s.search_vector @@ websearch_to_tsquery('english', query_text)
      AND (scope_card_ids IS NULL OR s.card_id = ANY(scope_card_ids))
      AND s.search_vector IS NOT NULL
    ORDER BY rank DESC
    LIMIT match_count * 2
  ),
  vector_results AS (
    -- Vector similarity leg
    SELECT
      s.id,
      1 - (s.embedding <=> query_embedding) AS similarity
    FROM sources s
    WHERE s.embedding IS NOT NULL
      AND (scope_card_ids IS NULL OR s.card_id = ANY(scope_card_ids))
    ORDER BY s.embedding <=> query_embedding
    LIMIT match_count * 2
  ),
  fts_ranked AS (
    SELECT id, rank AS score, ROW_NUMBER() OVER (ORDER BY rank DESC) AS rank_pos
    FROM fts_results
  ),
  vector_ranked AS (
    SELECT id, similarity AS score, ROW_NUMBER() OVER (ORDER BY similarity DESC) AS rank_pos
    FROM vector_results
  ),
  combined AS (
    SELECT
      COALESCE(f.id, v.id) AS id,
      COALESCE(f.score, 0.0)::REAL AS fts_rank,
      COALESCE(v.score, 0.0)::FLOAT AS vector_similarity,
      (COALESCE(fts_weight / (rrf_k + f.rank_pos), 0.0) +
       COALESCE(vector_weight / (rrf_k + v.rank_pos), 0.0))::FLOAT AS rrf_score
    FROM fts_ranked f
    FULL OUTER JOIN vector_ranked v ON f.id = v.id
  )
  SELECT
    s.id,
    s.card_id,
    c.name AS card_name,
    c.slug AS card_slug,
    s.title,
    s.url,
    s.ai_summary,
    s.key_excerpts,
    s.published_date,
    s.full_text,
    comb.fts_rank,
    comb.vector_similarity,
    comb.rrf_score
  FROM combined comb
  JOIN sources s ON s.id = comb.id
  LEFT JOIN cards c ON c.id = s.card_id
  ORDER BY comb.rrf_score DESC
  LIMIT match_count;
$$;

-- ============================================================================
-- 7. Permissions
-- ============================================================================

GRANT EXECUTE ON FUNCTION hybrid_search_cards(TEXT, extensions.vector(1536), INT, FLOAT, FLOAT, INT, UUID[], TEXT) TO authenticated;
GRANT EXECUTE ON FUNCTION hybrid_search_cards(TEXT, extensions.vector(1536), INT, FLOAT, FLOAT, INT, UUID[], TEXT) TO service_role;

GRANT EXECUTE ON FUNCTION hybrid_search_sources(TEXT, extensions.vector(1536), INT, FLOAT, FLOAT, INT, UUID[]) TO authenticated;
GRANT EXECUTE ON FUNCTION hybrid_search_sources(TEXT, extensions.vector(1536), INT, FLOAT, FLOAT, INT, UUID[]) TO service_role;

-- ============================================================================
-- 8. Documentation
-- ============================================================================

COMMENT ON FUNCTION hybrid_search_cards IS
  'Hybrid search over cards combining PostgreSQL full-text search and pgvector '
  'cosine similarity via Reciprocal Rank Fusion (RRF). Supports tunable '
  'fts_weight/vector_weight, optional card-ID scoping, and status filtering.';

COMMENT ON FUNCTION hybrid_search_sources IS
  'Hybrid search over sources combining PostgreSQL full-text search and pgvector '
  'cosine similarity via Reciprocal Rank Fusion (RRF). Supports tunable '
  'fts_weight/vector_weight and optional scoping by parent card IDs. Includes '
  'parent card name and slug for source-map building.';

COMMENT ON COLUMN cards.search_vector IS
  'Auto-maintained tsvector for full-text search: name(A) + summary(B) + description(C)';

COMMENT ON COLUMN sources.search_vector IS
  'Auto-maintained tsvector for full-text search: title(A) + ai_summary(B) + full_text(C)';
