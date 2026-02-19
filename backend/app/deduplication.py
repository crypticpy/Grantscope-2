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
        db=db,
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
- ``app.helpers.db_utils.vector_search_sources`` for embedding similarity search.
- ``ai_service.AIService.generate_embedding`` for on-the-fly embedding generation.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.source import Source
from app.helpers.db_utils import vector_search_sources
from app.helpers.settings_reader import get_setting

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thresholds (defaults — overridable via admin system_settings)
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
    db: AsyncSession,
    card_id: str,
    content: str,
    url: str,
    embedding: Optional[List[float]] = None,
    ai_service=None,  # Optional[AIService] -- typed loosely to avoid circular import
) -> DedupResult:
    """
    Check whether a source is a duplicate of an existing source on the same card.

    Performs two checks in order:

    1. **URL dedup** (cheap): If the exact URL already exists on this card,
       return ``is_duplicate=True, action="skip"`` immediately.

    2. **Embedding dedup** (semantic): Compare the source embedding against
       existing source embeddings on the same card via the
       ``vector_search_sources`` utility function.

    Parameters
    ----------
    db : AsyncSession
        SQLAlchemy async session.
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
            db=db,
            card_id=card_id,
            content=content,
            url=url,
            embedding=embedding,
            ai_service=ai_service,
        )
    except Exception as exc:
        # Dedup is NON-BLOCKING -- if it fails, proceed with normal storage
        logger.warning(f"Deduplication check failed (proceeding with store): {exc}")
        return _no_match_result()


async def _check_duplicate_inner(
    db: AsyncSession,
    card_id: str,
    content: str,
    url: str,
    embedding: Optional[List[float]],
    ai_service,
) -> DedupResult:
    """Inner implementation that may raise; wrapped by check_duplicate."""

    # Read admin-configurable thresholds (cached, 60s TTL)
    dedup_thresholds = await get_setting(db, "dedup_thresholds", None)
    if isinstance(dedup_thresholds, dict):
        dup_threshold = float(dedup_thresholds.get("duplicate", DUPLICATE_THRESHOLD))
        rel_threshold = float(dedup_thresholds.get("related", RELATED_THRESHOLD))
    else:
        dup_threshold = DUPLICATE_THRESHOLD
        rel_threshold = RELATED_THRESHOLD

    # ------------------------------------------------------------------
    # 1. URL dedup (fast path)
    # ------------------------------------------------------------------
    if url:
        try:
            result = await db.execute(
                select(Source.id)
                .where(Source.card_id == card_id)
                .where(Source.url == url)
            )
            existing_row = result.first()
            if existing_row:
                logger.debug(f"Dedup: URL match on card {card_id}: {url[:80]}")
                return DedupResult(
                    is_duplicate=True,
                    is_related=False,
                    duplicate_of_id=str(existing_row[0]),
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
        # No embedding available -- fall back to URL-only (already checked above)
        logger.debug("Dedup: No embedding available, falling back to URL-only check")
        return _no_match_result()

    # ------------------------------------------------------------------
    # 3. Embedding similarity via vector_search_sources
    # ------------------------------------------------------------------
    try:
        matches = await vector_search_sources(
            db,
            resolved_embedding,
            target_card_id=card_id,
            match_threshold=rel_threshold,
            match_count=5,
        )
    except Exception as exc:
        logger.warning(f"Dedup: vector_search_sources failed: {exc}")
        return _no_match_result()

    if not matches:
        # No similar sources found above the RELATED_THRESHOLD
        return _no_match_result()

    # ------------------------------------------------------------------
    # 4. Decision logic based on top match
    # ------------------------------------------------------------------
    top_match = matches[0]
    similarity = float(top_match.get("similarity", 0.0))
    match_id = str(top_match.get("id", ""))
    match_title = top_match.get("title", "")

    if similarity > dup_threshold:
        logger.info(
            f"Dedup: DUPLICATE detected (sim={similarity:.4f}) -- "
            f"source '{match_title[:50]}' (id={match_id}) on card {card_id}"
        )
        return DedupResult(
            is_duplicate=True,
            is_related=False,
            duplicate_of_id=match_id,
            similarity=similarity,
            action="skip",
        )

    if similarity >= rel_threshold:
        logger.info(
            f"Dedup: RELATED source detected (sim={similarity:.4f}) -- "
            f"source '{match_title[:50]}' (id={match_id}) on card {card_id}"
        )
        return DedupResult(
            is_duplicate=False,
            is_related=True,
            duplicate_of_id=match_id,
            similarity=similarity,
            action="store_as_related",
        )

    # Below RELATED_THRESHOLD -- this shouldn't happen because the search filters,
    # but handle it gracefully.
    return _no_match_result()
