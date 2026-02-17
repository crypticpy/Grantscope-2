"""
Embedding-based content deduplication for GrantScope sources.

Provides a two-tier deduplication check for incoming sources:

1. **URL dedup** (fast path): exact URL match on the same card.
2. **Embedding dedup** (semantic): cosine similarity via pgvector.

Decision thresholds
-------------------
- similarity > 0.95  ->  duplicate   -> ``action="skip"``
- 0.85 <= sim <= 0.95 -> related     -> ``action="store_as_related"`` (sets ``duplicate_of``)
- similarity < 0.85  ->  new content -> ``action="store"``

Usage
-----
    from app.deduplication import check_duplicate, DedupResult

    result = await check_duplicate(
        supabase=supabase,
        card_id=card_id,
        content=source_content,
        url=source_url,
        embedding=precomputed_embedding,   # optional
        ai_service=ai_service_instance,    # optional, used to generate embedding
    )

    if result.action == "skip":
        return None  # duplicate, don't insert
    elif result.action == "store_as_related":
        insert_data["duplicate_of"] = result.duplicate_of_id

Dependencies
------------
- ``sources`` table with ``embedding VECTOR(1536)`` and ``duplicate_of UUID`` columns.
- ``match_sources_by_embedding`` Postgres function (migration 20260213_dedup_similarity_function).
- ``ai_service.AIService.generate_embedding`` for on-the-fly embedding generation.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional

from supabase import Client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------
DUPLICATE_THRESHOLD = 0.95  # similarity above this -> skip (duplicate)
RELATED_THRESHOLD = 0.85  # similarity above this -> store as related


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------
@dataclass
class DedupResult:
    """Outcome of a deduplication check."""

    is_duplicate: bool  # True if similarity > DUPLICATE_THRESHOLD
    is_related: bool  # True if RELATED_THRESHOLD < similarity <= DUPLICATE_THRESHOLD
    duplicate_of_id: Optional[
        str
    ]  # source ID of the best match (if duplicate or related)
    similarity: float  # highest similarity score found (0.0 if no comparison)
    action: str  # "skip", "store_as_related", or "store"


# ---------------------------------------------------------------------------
# Helper: build a "no match" result
# ---------------------------------------------------------------------------
def _no_match_result() -> DedupResult:
    """Return a DedupResult indicating no duplicate was found."""
    return DedupResult(
        is_duplicate=False,
        is_related=False,
        duplicate_of_id=None,
        similarity=0.0,
        action="store",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
async def check_duplicate(
    supabase: Client,
    card_id: str,
    content: str,
    url: str,
    embedding: Optional[List[float]] = None,
    ai_service=None,  # Optional[AIService] — typed loosely to avoid circular import
) -> DedupResult:
    """
    Check whether a source is a duplicate of an existing source on the same card.

    Performs two checks in order:

    1. **URL dedup** (cheap): If the exact URL already exists on this card,
       return ``is_duplicate=True, action="skip"`` immediately.

    2. **Embedding dedup** (semantic): Compare the source embedding against
       existing source embeddings on the same card via the
       ``match_sources_by_embedding`` RPC function.

    Parameters
    ----------
    supabase : Client
        Authenticated Supabase client.
    card_id : str
        UUID of the card this source would be stored on.
    content : str
        Full text / content of the source (used to generate embedding if needed).
    url : str
        URL of the source.
    embedding : list[float] | None
        Pre-computed 1536-dim embedding vector.  If not provided and
        ``ai_service`` is available, one will be generated from ``content``.
    ai_service : AIService | None
        Optional AI service instance for embedding generation.

    Returns
    -------
    DedupResult
        Contains the dedup decision (action, similarity, duplicate_of_id, etc.)
    """
    try:
        return await _check_duplicate_inner(
            supabase=supabase,
            card_id=card_id,
            content=content,
            url=url,
            embedding=embedding,
            ai_service=ai_service,
        )
    except Exception as exc:
        # Dedup is NON-BLOCKING — if it fails, proceed with normal storage
        logger.warning(f"Deduplication check failed (proceeding with store): {exc}")
        return _no_match_result()


async def _check_duplicate_inner(
    supabase: Client,
    card_id: str,
    content: str,
    url: str,
    embedding: Optional[List[float]],
    ai_service,
) -> DedupResult:
    """Inner implementation that may raise; wrapped by check_duplicate."""

    # ------------------------------------------------------------------
    # 1. URL dedup (fast path)
    # ------------------------------------------------------------------
    if url:
        try:
            existing = (
                supabase.table("sources")
                .select("id")
                .eq("card_id", card_id)
                .eq("url", url)
                .execute()
            )
            if existing.data:
                logger.debug(f"Dedup: URL match on card {card_id}: {url[:80]}")
                return DedupResult(
                    is_duplicate=True,
                    is_related=False,
                    duplicate_of_id=existing.data[0]["id"],
                    similarity=1.0,
                    action="skip",
                )
        except Exception as exc:
            logger.warning(f"Dedup: URL check failed: {exc}")
            # Continue to embedding check

    # ------------------------------------------------------------------
    # 2. Resolve embedding
    # ------------------------------------------------------------------
    resolved_embedding = embedding

    if resolved_embedding is None and ai_service is not None and content:
        try:
            # Generate embedding from content (truncated by ai_service internally)
            embed_text = content[:8000]
            resolved_embedding = await ai_service.generate_embedding(embed_text)
        except Exception as exc:
            logger.warning(f"Dedup: Embedding generation failed: {exc}")

    if resolved_embedding is None:
        # No embedding available — fall back to URL-only (already checked above)
        logger.debug("Dedup: No embedding available, falling back to URL-only check")
        return _no_match_result()

    # ------------------------------------------------------------------
    # 3. Embedding similarity via RPC
    # ------------------------------------------------------------------
    try:
        rpc_result = supabase.rpc(
            "match_sources_by_embedding",
            {
                "query_embedding": resolved_embedding,
                "target_card_id": card_id,
                "match_threshold": RELATED_THRESHOLD,
                "match_count": 5,
            },
        ).execute()
    except Exception as exc:
        logger.warning(f"Dedup: RPC match_sources_by_embedding failed: {exc}")
        return _no_match_result()

    if not rpc_result.data:
        # No similar sources found above the RELATED_THRESHOLD
        return _no_match_result()

    # ------------------------------------------------------------------
    # 4. Decision logic based on top match
    # ------------------------------------------------------------------
    top_match = rpc_result.data[0]
    similarity = float(top_match.get("similarity", 0.0))
    match_id = str(top_match.get("id", ""))
    match_title = top_match.get("title", "")

    if similarity > DUPLICATE_THRESHOLD:
        logger.info(
            f"Dedup: DUPLICATE detected (sim={similarity:.4f}) — "
            f"source '{match_title[:50]}' (id={match_id}) on card {card_id}"
        )
        return DedupResult(
            is_duplicate=True,
            is_related=False,
            duplicate_of_id=match_id,
            similarity=similarity,
            action="skip",
        )

    if similarity >= RELATED_THRESHOLD:
        logger.info(
            f"Dedup: RELATED source detected (sim={similarity:.4f}) — "
            f"source '{match_title[:50]}' (id={match_id}) on card {card_id}"
        )
        return DedupResult(
            is_duplicate=False,
            is_related=True,
            duplicate_of_id=match_id,
            similarity=similarity,
            action="store_as_related",
        )

    # Below RELATED_THRESHOLD — this shouldn't happen because the RPC filters,
    # but handle it gracefully.
    return _no_match_result()
