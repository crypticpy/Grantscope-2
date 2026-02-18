"""Database utility functions for vector search and hybrid search.

These replace the Supabase RPC functions that relied on pgvector operators
and tsvector-based full-text search.  All functions accept an
``AsyncSession`` and return lists of dicts (matching the original RPC
return types).
"""

import logging
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def vector_search_cards(
    db: AsyncSession,
    query_embedding: list[float],
    *,
    match_threshold: float = 0.75,
    match_count: int = 10,
    exclude_card_id: Optional[str] = None,
    require_active: bool = False,
) -> list[dict[str, Any]]:
    """Find cards similar to *query_embedding* using pgvector cosine distance.

    Replaces the ``find_similar_cards`` and ``match_cards_by_embedding``
    Supabase RPC functions.

    Parameters
    ----------
    require_active:
        If True, filter by ``status = 'active'`` (match_cards_by_embedding
        behaviour).  If False, filter by ``review_status != 'rejected'``
        (find_similar_cards behaviour).
    """
    embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    if require_active:
        status_clause = "AND c.status = 'active'"
    else:
        status_clause = "AND c.review_status != 'rejected'"

    exclude_clause = ""
    params: dict[str, Any] = {
        "embedding": embedding_str,
        "threshold": match_threshold,
        "limit": match_count,
    }

    if exclude_card_id:
        exclude_clause = "AND c.id != :exclude_id"
        params["exclude_id"] = exclude_card_id

    sql = text(
        f"""
        SELECT
            c.id, c.name, c.summary, c.pillar_id, c.horizon,
            1 - (c.embedding <=> CAST(:embedding AS vector)) AS similarity
        FROM cards c
        WHERE
            c.embedding IS NOT NULL
            {status_clause}
            {exclude_clause}
            AND 1 - (c.embedding <=> CAST(:embedding AS vector)) > :threshold
        ORDER BY c.embedding <=> CAST(:embedding AS vector)
        LIMIT :limit
    """
    )

    result = await db.execute(sql, params)
    rows = result.mappings().all()
    return [
        {
            "id": str(r["id"]),
            "name": r["name"],
            "summary": r["summary"],
            "pillar_id": r["pillar_id"],
            "horizon": r["horizon"],
            "similarity": float(r["similarity"]),
        }
        for r in rows
    ]


async def vector_search_sources(
    db: AsyncSession,
    query_embedding: list[float],
    *,
    target_card_id: Optional[str] = None,
    match_threshold: float = 0.85,
    match_count: int = 5,
) -> list[dict[str, Any]]:
    """Find sources similar to *query_embedding*.

    Replaces the ``match_sources_by_embedding`` Supabase RPC function.

    If *target_card_id* is given, scopes the search to that card's sources
    (the card-scoped deduplication variant).
    """
    embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    params: dict[str, Any] = {
        "embedding": embedding_str,
        "threshold": match_threshold,
        "limit": match_count,
    }

    card_clause = ""
    if target_card_id:
        card_clause = "AND s.card_id = :card_id"
        params["card_id"] = target_card_id

    sql = text(
        f"""
        SELECT
            s.id, s.url, s.title, s.card_id, s.ai_summary,
            CAST(1 - (s.embedding <=> CAST(:embedding AS vector)) AS float) AS similarity
        FROM sources s
        WHERE
            s.embedding IS NOT NULL
            AND s.duplicate_of IS NULL
            {card_clause}
            AND (1 - (s.embedding <=> CAST(:embedding AS vector))) > :threshold
        ORDER BY s.embedding <=> CAST(:embedding AS vector)
        LIMIT :limit
    """
    )

    result = await db.execute(sql, params)
    rows = result.mappings().all()
    return [
        {
            "id": str(r["id"]),
            "url": r["url"],
            "title": r["title"],
            "card_id": str(r["card_id"]) if r["card_id"] else None,
            "ai_summary": r["ai_summary"],
            "similarity": float(r["similarity"]),
        }
        for r in rows
    ]


async def hybrid_search_cards(
    db: AsyncSession,
    query_text: str,
    query_embedding: list[float],
    *,
    match_count: int = 20,
    fts_weight: float = 1.0,
    vector_weight: float = 1.0,
    rrf_k: int = 60,
    scope_card_ids: Optional[list[str]] = None,
    status_filter: str = "active",
) -> list[dict[str, Any]]:
    """Hybrid full-text + vector search over cards using RRF fusion.

    Replaces the ``hybrid_search_cards`` Supabase RPC function.
    """
    embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    params: dict[str, Any] = {
        "query_text": query_text,
        "embedding": embedding_str,
        "match_count": match_count,
        "fts_weight": fts_weight,
        "vector_weight": vector_weight,
        "rrf_k": rrf_k,
        "status_filter": status_filter,
    }

    scope_clause_fts = ""
    scope_clause_vec = ""
    if scope_card_ids:
        params["scope_ids"] = scope_card_ids
        scope_clause_fts = "AND c.id = ANY(:scope_ids)"
        scope_clause_vec = "AND c.id = ANY(:scope_ids)"

    sql = text(
        f"""
        WITH fts AS (
            SELECT
                c.id,
                ROW_NUMBER() OVER (ORDER BY ts_rank_cd(c.search_vector, websearch_to_tsquery('english', :query_text)) DESC) AS rank_pos,
                ts_rank_cd(c.search_vector, websearch_to_tsquery('english', :query_text)) AS fts_rank
            FROM cards c
            WHERE
                c.search_vector @@ websearch_to_tsquery('english', :query_text)
                AND c.status = :status_filter
                {scope_clause_fts}
        ),
        vec AS (
            SELECT
                c.id,
                ROW_NUMBER() OVER (ORDER BY c.embedding <=> CAST(:embedding AS vector)) AS rank_pos,
                1 - (c.embedding <=> CAST(:embedding AS vector)) AS vector_similarity
            FROM cards c
            WHERE
                c.embedding IS NOT NULL
                AND c.status = :status_filter
                {scope_clause_vec}
            ORDER BY c.embedding <=> CAST(:embedding AS vector)
            LIMIT :match_count * 2
        ),
        rrf AS (
            SELECT
                COALESCE(fts.id, vec.id) AS id,
                COALESCE(fts.fts_rank, 0) AS fts_rank,
                COALESCE(vec.vector_similarity, 0) AS vector_similarity,
                COALESCE(:fts_weight / (:rrf_k + fts.rank_pos), 0) +
                COALESCE(:vector_weight / (:rrf_k + vec.rank_pos), 0) AS rrf_score
            FROM fts
            FULL OUTER JOIN vec ON fts.id = vec.id
        )
        SELECT
            c.id, c.name, c.slug, c.summary, c.description,
            c.pillar_id, c.horizon, c.stage_id,
            c.impact_score, c.relevance_score, c.velocity_score,
            c.risk_score, c.signal_quality_score,
            rrf.fts_rank, rrf.vector_similarity, rrf.rrf_score
        FROM rrf
        JOIN cards c ON c.id = rrf.id
        ORDER BY rrf.rrf_score DESC
        LIMIT :match_count
    """
    )

    result = await db.execute(sql, params)
    rows = result.mappings().all()
    return [dict(r) for r in rows]


async def hybrid_search_sources(
    db: AsyncSession,
    query_text: str,
    query_embedding: list[float],
    *,
    match_count: int = 20,
    fts_weight: float = 1.0,
    vector_weight: float = 1.0,
    rrf_k: int = 60,
    scope_card_ids: Optional[list[str]] = None,
) -> list[dict[str, Any]]:
    """Hybrid full-text + vector search over sources using RRF fusion.

    Replaces the ``hybrid_search_sources`` Supabase RPC function.
    """
    embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    params: dict[str, Any] = {
        "query_text": query_text,
        "embedding": embedding_str,
        "match_count": match_count,
        "fts_weight": fts_weight,
        "vector_weight": vector_weight,
        "rrf_k": rrf_k,
    }

    scope_clause_fts = ""
    scope_clause_vec = ""
    if scope_card_ids:
        params["scope_ids"] = scope_card_ids
        scope_clause_fts = "AND s.card_id = ANY(:scope_ids)"
        scope_clause_vec = "AND s.card_id = ANY(:scope_ids)"

    sql = text(
        f"""
        WITH fts AS (
            SELECT
                s.id,
                ROW_NUMBER() OVER (ORDER BY ts_rank_cd(s.search_vector, websearch_to_tsquery('english', :query_text)) DESC) AS rank_pos,
                ts_rank_cd(s.search_vector, websearch_to_tsquery('english', :query_text)) AS fts_rank
            FROM sources s
            WHERE
                s.search_vector @@ websearch_to_tsquery('english', :query_text)
                {scope_clause_fts}
        ),
        vec AS (
            SELECT
                s.id,
                ROW_NUMBER() OVER (ORDER BY s.embedding <=> CAST(:embedding AS vector)) AS rank_pos,
                1 - (s.embedding <=> CAST(:embedding AS vector)) AS vector_similarity
            FROM sources s
            WHERE
                s.embedding IS NOT NULL
                {scope_clause_vec}
            ORDER BY s.embedding <=> CAST(:embedding AS vector)
            LIMIT :match_count * 2
        ),
        rrf AS (
            SELECT
                COALESCE(fts.id, vec.id) AS id,
                COALESCE(fts.fts_rank, 0) AS fts_rank,
                COALESCE(vec.vector_similarity, 0) AS vector_similarity,
                COALESCE(:fts_weight / (:rrf_k + fts.rank_pos), 0) +
                COALESCE(:vector_weight / (:rrf_k + vec.rank_pos), 0) AS rrf_score
            FROM fts
            FULL OUTER JOIN vec ON fts.id = vec.id
        )
        SELECT
            s.id, s.card_id, c.name AS card_name, c.slug AS card_slug,
            s.title, s.url, s.ai_summary, s.key_excerpts,
            s.published_date, s.full_text,
            rrf.fts_rank, rrf.vector_similarity, rrf.rrf_score
        FROM rrf
        JOIN sources s ON s.id = rrf.id
        LEFT JOIN cards c ON c.id = s.card_id
        ORDER BY rrf.rrf_score DESC
        LIMIT :match_count
    """
    )

    result = await db.execute(sql, params)
    rows = result.mappings().all()
    return [dict(r) for r in rows]


async def increment_deep_research_count(
    db: AsyncSession,
    card_id: str,
) -> None:
    """Atomically increment the daily deep research counter for a card.

    Replaces the ``increment_deep_research_count`` Supabase RPC function.
    """
    sql = text(
        """
        UPDATE cards
        SET
            deep_research_count_today = CASE
                WHEN deep_research_reset_date = CURRENT_DATE
                THEN COALESCE(deep_research_count_today, 0) + 1
                ELSE 1
            END,
            deep_research_reset_date = CURRENT_DATE
        WHERE id = :card_id
    """
    )
    await db.execute(sql, {"card_id": card_id})


async def create_workstream_scan_atomic(
    db: AsyncSession,
    workstream_id: str,
    user_id: str,
    config: dict,
) -> Optional[str]:
    """Atomically create a workstream scan with rate limiting.

    Replaces the ``create_workstream_scan_atomic`` Supabase RPC function.
    Returns the new scan ID on success, None if blocked.
    """
    import json

    sql = text(
        """
        WITH locked AS (
            SELECT id FROM workstreams WHERE id = :wid FOR UPDATE
        ),
        active_check AS (
            SELECT COUNT(*) AS cnt
            FROM workstream_scans
            WHERE workstream_id = :wid AND status IN ('queued', 'running')
        ),
        rate_check AS (
            SELECT COUNT(*) AS cnt
            FROM workstream_scans
            WHERE workstream_id = :wid AND created_at > NOW() - INTERVAL '24 hours'
        )
        INSERT INTO workstream_scans (workstream_id, user_id, status, config, created_at)
        SELECT :wid, :uid, 'queued', :config::jsonb, NOW()
        FROM active_check, rate_check
        WHERE active_check.cnt = 0 AND rate_check.cnt < 2
        RETURNING id
    """
    )

    result = await db.execute(
        sql,
        {
            "wid": workstream_id,
            "uid": user_id,
            "config": json.dumps(config),
        },
    )
    row = result.scalar_one_or_none()
    return str(row) if row else None


async def has_active_workstream_scan(
    db: AsyncSession,
    workstream_id: str,
) -> bool:
    """Check if a workstream has any active (queued/running) scans.

    Replaces the ``has_active_workstream_scan`` Supabase RPC function.
    """
    sql = text(
        """
        SELECT COUNT(*) FROM workstream_scans
        WHERE workstream_id = :wid AND status IN ('queued', 'running')
    """
    )
    result = await db.execute(sql, {"wid": workstream_id})
    count = result.scalar() or 0
    return count > 0
