"""Search tools for the grant discovery assistant.

Provides tools to search the internal grant database, Grants.gov,
SAM.gov, and the web for grant opportunities.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.tools import ToolDefinition, registry
from app.models.db.card import Card

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool 1: search_internal_grants
# ---------------------------------------------------------------------------


async def _handle_search_internal_grants(
    db: AsyncSession, user_id: str, **kwargs: Any
) -> dict:
    """Search the internal grant/card database using hybrid search.

    Generates an embedding for the query text enriched with the user's
    profile context (department, program, priorities), then runs hybrid
    (full-text + vector) search over the cards table.  Results are
    optionally post-filtered by pillar, category, funding range, and
    deadline.

    Args:
        db: Async database session.
        user_id: Authenticated user UUID string.
        **kwargs: Tool call arguments (query, pillar_filter, etc.).

    Returns:
        Dict with ``results`` list and ``count`` integer.
    """
    try:
        query: str = kwargs.get("query", "")
        if not query:
            return {"error": "A 'query' parameter is required."}

        pillar_filter: Optional[str] = kwargs.get("pillar_filter")
        category_filter: Optional[str] = kwargs.get("category_filter")
        funding_min: Optional[float] = kwargs.get("funding_min")
        funding_max: Optional[float] = kwargs.get("funding_max")
        deadline_after: Optional[str] = kwargs.get("deadline_after")

        logger.info(
            "search_internal_grants called: query=%r user_id=%s filters(pillar=%s cat=%s fmin=%s fmax=%s deadline=%s)",
            query,
            user_id,
            pillar_filter,
            category_filter,
            funding_min,
            funding_max,
            deadline_after,
        )

        # Enrich query with user profile context for better search recall.
        # The LLM's query may be generic (e.g. "grants for my division") so we
        # append department, program, and priority keywords.  The enriched text
        # is used for embedding generation (semantic match) while an OR-enhanced
        # variant is used for full-text search (FTS) so that profile terms like
        # "Information Technology" can match cards even when the LLM's phrasing
        # doesn't share exact stems with the card's search_vector.
        enriched_query = query
        fts_query = query  # OR-enhanced version for full-text search
        profile: Optional[dict] = None
        fts_parts: List[str] = []
        try:
            import uuid as _uuid

            from app.chat.profile_utils import load_user_profile

            profile = await load_user_profile(db, _uuid.UUID(user_id))
            if profile:
                # --- Build embedding enrichment (AND-concatenated) ---
                context_parts: List[str] = []
                if profile.get("department"):
                    context_parts.append(str(profile["department"]))
                if profile.get("program_name"):
                    context_parts.append(str(profile["program_name"]))
                if profile.get("program_mission"):
                    context_parts.append(str(profile["program_mission"])[:200])
                if profile.get("priorities") and isinstance(
                    profile["priorities"], list
                ):
                    context_parts.append(" ".join(profile["priorities"][:5]))
                if profile.get("custom_priorities"):
                    context_parts.append(str(profile["custom_priorities"])[:200])
                if context_parts:
                    enriched_query = f"{query} {' '.join(context_parts)}"

                # --- Build FTS query with OR semantics ---
                # websearch_to_tsquery treats unquoted "or" as the OR operator,
                # so "grants for programs or APH" yields
                # ('grant' & 'program') | 'aph'.
                #
                # We only include department and program_name as OR branches.
                # Mission and priorities are intentionally excluded from FTS
                # because they add too many generic terms (e.g. "training",
                # "equipment") that match hundreds of cards and drown out
                # specific matches.  The enriched embedding (which includes
                # mission + priorities) handles semantic matching instead.
                fts_parts: List[str] = []
                if profile.get("department"):
                    fts_parts.append(str(profile["department"]))
                if profile.get("program_name"):
                    fts_parts.append(str(profile["program_name"]))
                if fts_parts:
                    fts_query = f"{query} or {' or '.join(fts_parts)}"
        except Exception as e:
            logger.debug("Could not enrich query with user profile: %s", e)

        # LLMs often generate comma-separated lists (e.g. "health IT,
        # software, training, equipment") which websearch_to_tsquery treats
        # as AND — requiring ALL terms to match.  Replace commas with "or"
        # so each phrase becomes a separate OR branch, matching cards that
        # contain ANY of the listed terms.
        fts_query = fts_query.replace(",", " or ")

        # Generate embedding for the enriched query
        from app.openai_provider import (
            azure_openai_async_embedding_client,
            get_embedding_deployment,
        )

        embed_response = await azure_openai_async_embedding_client.embeddings.create(
            model=get_embedding_deployment(),
            input=enriched_query[:8000],
        )
        embedding: List[float] = embed_response.data[0].embedding

        # Run hybrid search (OR-enhanced FTS query + enriched embedding)
        from app.helpers.db_utils import hybrid_search_cards, vector_search_cards

        # Determine vector pool size dynamically.  For small corpora
        # (< 1000 cards) we scan all cards so every row receives a
        # vector rank in the RRF fusion.  For larger corpora the default
        # match_count * 2 window is more performant; at that scale a
        # pgvector HNSW index should be added for sub-linear search.
        from sqlalchemy import text as sa_text

        pool_result = await db.execute(
            sa_text(
                "SELECT count(*) FROM cards "
                "WHERE status = 'active' AND embedding IS NOT NULL"
            )
        )
        total_cards = pool_result.scalar() or 0
        # Cover the full corpus up to 1000; beyond that use a fixed cap
        # that balances recall vs. query latency.
        vector_pool = max(total_cards, 120) if total_cards <= 1000 else 1000

        raw_results = await hybrid_search_cards(
            db,
            fts_query,
            embedding,
            match_count=60,
            status_filter="active",
            # Weight vector similarity 2x over FTS to favour semantic
            # matches from the enriched embedding.  The embedding carries
            # the full user profile context (mission, priorities) while
            # FTS only has query + department/program abbreviations.
            vector_weight=2.0,
            # Expand the vector candidate pool to cover the entire corpus.
            # The default pool (match_count * 2) can exclude cards with
            # strong FTS signal from getting any vector contribution in
            # the RRF fusion.
            vector_pool_size=vector_pool,
        )

        logger.info(
            "hybrid_search returned %d results for fts=%r",
            len(raw_results),
            fts_query[:80],
        )

        # ---- Supplemental profile-focused search ----
        # The LLM's queries may use terms that don't match cards directly
        # relevant to the user's department (e.g. "health IT infrastructure"
        # misses LEAP grants because 'infrastructure' isn't in their tsvector).
        # Run a second search using ONLY the user's profile keywords as the
        # FTS query with the same enriched embedding.  This guarantees cards
        # tagged with the user's department/program always surface.
        if profile and fts_parts:
            profile_fts = " or ".join(fts_parts)
            try:
                profile_results = await hybrid_search_cards(
                    db,
                    profile_fts,
                    embedding,
                    match_count=15,
                    status_filter="active",
                    vector_weight=2.0,
                    vector_pool_size=vector_pool,
                )
                existing_ids = {str(r.get("id", "")) for r in raw_results}
                added = 0
                for pr in profile_results:
                    pid = str(pr.get("id", ""))
                    if pid not in existing_ids:
                        raw_results.append(pr)
                        existing_ids.add(pid)
                        added += 1
                if added:
                    logger.info(
                        "Profile supplemental search added %d new results (profile_fts=%r)",
                        added,
                        profile_fts,
                    )
            except Exception as e:
                logger.debug("Profile supplemental search failed: %s", e)

        # Fallback: if hybrid search returned very few results, supplement
        # with vector-only search at a lower similarity threshold.  This
        # handles cases where FTS terms don't match any card but the
        # semantic embedding is still close.
        if len(raw_results) < 3:
            logger.info(
                "Hybrid search returned %d results; supplementing with vector-only fallback",
                len(raw_results),
            )
            vec_results = await vector_search_cards(
                db,
                embedding,
                match_threshold=0.4,
                match_count=25,
                require_active=True,
            )
            existing_ids = {str(r.get("id", "")) for r in raw_results}
            for vr in vec_results:
                if str(vr.get("id", "")) not in existing_ids:
                    raw_results.append({**vr, "rrf_score": vr.get("similarity", 0)})

        # Batch-fetch full cards to avoid N+1 queries
        card_ids = [row.get("id") for row in raw_results if row.get("id")]
        cards_by_id: Dict[str, Any] = {}
        if card_ids:
            cards_result = await db.execute(select(Card).where(Card.id.in_(card_ids)))
            cards_by_id = {str(c.id): c for c in cards_result.scalars().all()}

        # Post-filter by grant-specific fields
        filtered: List[Dict[str, Any]] = []
        for row in raw_results:
            card_id = str(row.get("id", ""))
            card = cards_by_id.get(card_id)
            if card is None:
                continue

            # Apply optional filters
            if pillar_filter and card.pillar_id != pillar_filter:
                continue

            if category_filter and card.category_id != category_filter:
                continue

            if funding_min is not None and card.funding_amount_max is not None:
                if float(card.funding_amount_max) < funding_min:
                    continue

            if funding_max is not None and card.funding_amount_min is not None:
                if float(card.funding_amount_min) > funding_max:
                    continue

            if deadline_after and card.deadline:
                try:
                    cutoff = datetime.fromisoformat(deadline_after)
                    # Normalise both to UTC-aware datetimes for safe comparison
                    card_dl = (
                        card.deadline
                        if card.deadline.tzinfo
                        else card.deadline.replace(tzinfo=timezone.utc)
                    )
                    cutoff = (
                        cutoff if cutoff.tzinfo else cutoff.replace(tzinfo=timezone.utc)
                    )
                    if card_dl < cutoff:
                        continue
                except (ValueError, TypeError):
                    pass

            filtered.append(
                {
                    "card_id": card_id,
                    "name": card.name,
                    "slug": card.slug,
                    "grantor": card.grantor,
                    "funding_amount_min": (
                        float(card.funding_amount_min)
                        if card.funding_amount_min is not None
                        else None
                    ),
                    "funding_amount_max": (
                        float(card.funding_amount_max)
                        if card.funding_amount_max is not None
                        else None
                    ),
                    "deadline": (card.deadline.isoformat() if card.deadline else None),
                    "grant_type": card.grant_type,
                    "summary": card.summary,
                    "pillar_id": card.pillar_id,
                    "source_url": card.source_url,
                    "similarity": float(row.get("rrf_score", 0)),
                }
            )

        logger.info(
            "search_internal_grants post-filter: %d → %d results",
            len(raw_results),
            len(filtered),
        )

        # Safety net: if post-filtering removed ALL results, return
        # unfiltered results.  The LLM often over-applies filters from the
        # user profile (pillar, funding range, deadline) even when the user
        # didn't explicitly request them, causing 0 results.  Returning
        # the full set lets the model evaluate relevance itself.
        if len(filtered) == 0 and len(raw_results) > 0:
            logger.warning(
                "Post-filter reduced %d results to 0; returning unfiltered results",
                len(raw_results),
            )
            # Build result dicts for ALL cards (no filters applied)
            unfiltered: List[Dict[str, Any]] = []
            for row in raw_results:
                card_id = str(row.get("id", ""))
                card = cards_by_id.get(card_id)
                if card is None:
                    continue
                unfiltered.append(
                    {
                        "card_id": card_id,
                        "name": card.name,
                        "slug": card.slug,
                        "grantor": card.grantor,
                        "funding_amount_min": (
                            float(card.funding_amount_min)
                            if card.funding_amount_min is not None
                            else None
                        ),
                        "funding_amount_max": (
                            float(card.funding_amount_max)
                            if card.funding_amount_max is not None
                            else None
                        ),
                        "deadline": (
                            card.deadline.isoformat() if card.deadline else None
                        ),
                        "grant_type": card.grant_type,
                        "summary": card.summary,
                        "pillar_id": card.pillar_id,
                        "source_url": card.source_url,
                        "similarity": float(row.get("rrf_score", 0)),
                    }
                )
            return {
                "results": unfiltered,
                "count": len(unfiltered),
                "note": "No results matched the exact filters. Showing all search results — please evaluate relevance.",
            }

        return {"results": filtered, "count": len(filtered)}

    except Exception as exc:
        logger.exception("search_internal_grants failed: %s", exc)
        return {
            "error": "Internal grant search is temporarily unavailable. Please try again."
        }


registry.register(
    ToolDefinition(
        name="search_internal_grants",
        description=(
            "Search the internal GrantScope database for grant opportunities "
            "matching a text query. The search automatically incorporates the "
            "user's profile (department, program, priorities) for better results. "
            "Supports optional filters for strategic pillar, grant category, "
            "funding range, and application deadline."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Short, focused search query (3-7 words) for the grant "
                        "topic or area. Use specific domain terms, not laundry "
                        "lists. Example: 'health information technology grants' "
                        "not 'health IT, equipment, software, training, EMR'. "
                        "The user's profile context is automatically added. "
                        "Call this tool multiple times with different queries "
                        "to cover different aspects."
                    ),
                },
                "pillar_filter": {
                    "type": "string",
                    "description": (
                        "ONLY use if the user explicitly asks to filter by pillar. "
                        "Do NOT infer from the user's profile. "
                        "Values: 'CH', 'MC', 'HS', 'EC', 'ES', 'CE'."
                    ),
                },
                "category_filter": {
                    "type": "string",
                    "description": (
                        "ONLY use if the user explicitly asks to filter by category. "
                        "Do NOT infer from the user's profile."
                    ),
                },
                "funding_min": {
                    "type": "number",
                    "description": (
                        "ONLY use if the user explicitly specifies a minimum "
                        "funding amount. Do NOT infer from the user's profile."
                    ),
                },
                "funding_max": {
                    "type": "number",
                    "description": (
                        "ONLY use if the user explicitly specifies a maximum "
                        "funding amount. Do NOT infer from the user's profile."
                    ),
                },
                "deadline_after": {
                    "type": "string",
                    "description": (
                        "ONLY use if the user explicitly asks for grants with "
                        "deadlines after a specific date. Do NOT automatically "
                        "filter by today's date."
                    ),
                },
            },
            "required": ["query"],
        },
        handler=_handle_search_internal_grants,
        requires_online=False,
    )
)


# ---------------------------------------------------------------------------
# Tool 2: get_grant_details
# ---------------------------------------------------------------------------


async def _handle_get_grant_details(
    db: AsyncSession, user_id: str, **kwargs: Any
) -> dict:
    """Retrieve full details for a specific grant/card by ID or slug.

    Args:
        db: Async database session.
        user_id: Authenticated user UUID string.
        **kwargs: Must include ``card_id`` or ``slug`` (or both).

    Returns:
        Dict with the grant's full details, or an error dict.
    """
    try:
        card_id: Optional[str] = kwargs.get("card_id")
        slug: Optional[str] = kwargs.get("slug")

        if not card_id and not slug:
            return {"error": "At least one of 'card_id' or 'slug' is required."}

        if card_id:
            import uuid as _uuid

            try:
                uid = _uuid.UUID(card_id)
            except ValueError:
                return {"error": f"Invalid card_id format: {card_id}"}
            result = await db.execute(select(Card).where(Card.id == uid))
        else:
            result = await db.execute(select(Card).where(Card.slug == slug))

        card = result.scalar_one_or_none()
        if card is None:
            return {"error": "Grant not found."}

        return {
            "card_id": str(card.id),
            "name": card.name,
            "slug": card.slug,
            "summary": card.summary,
            "description": card.description,
            "pillar_id": card.pillar_id,
            "stage_id": card.stage_id,
            "horizon": card.horizon,
            "status": card.status,
            "grantor": card.grantor,
            "grant_type": card.grant_type,
            "cfda_number": card.cfda_number,
            "grants_gov_id": card.grants_gov_id,
            "sam_opportunity_id": card.sam_opportunity_id,
            "funding_amount_min": (
                float(card.funding_amount_min)
                if card.funding_amount_min is not None
                else None
            ),
            "funding_amount_max": (
                float(card.funding_amount_max)
                if card.funding_amount_max is not None
                else None
            ),
            "deadline": card.deadline.isoformat() if card.deadline else None,
            "eligibility_text": card.eligibility_text,
            "match_requirement": card.match_requirement,
            "source_url": card.source_url,
            "category_id": card.category_id,
            "alignment_score": card.alignment_score,
            "readiness_score": card.readiness_score,
            "competition_score": card.competition_score,
            "urgency_score": card.urgency_score,
            "probability_score": card.probability_score,
            "impact_score": (
                float(card.impact_score) if card.impact_score is not None else None
            ),
            "relevance_score": (
                float(card.relevance_score)
                if card.relevance_score is not None
                else None
            ),
            "created_at": (card.created_at.isoformat() if card.created_at else None),
        }

    except Exception as exc:
        logger.exception("get_grant_details failed: %s", exc)
        return {"error": "Failed to retrieve grant details. Please try again."}


registry.register(
    ToolDefinition(
        name="get_grant_details",
        description=(
            "Retrieve full details for a specific grant opportunity from "
            "the internal database, including funding amounts, deadlines, "
            "eligibility, scores, and metadata."
        ),
        parameters={
            "type": "object",
            "properties": {
                "card_id": {
                    "type": "string",
                    "description": "UUID of the card/grant to retrieve.",
                },
                "slug": {
                    "type": "string",
                    "description": "URL slug of the card/grant to retrieve.",
                },
            },
            "required": [],
        },
        handler=_handle_get_grant_details,
        requires_online=False,
    )
)


# ---------------------------------------------------------------------------
# Tool 3: search_grants_gov (online)
# ---------------------------------------------------------------------------


async def _handle_search_grants_gov(
    db: AsyncSession, user_id: str, **kwargs: Any
) -> dict:
    """Search the Grants.gov federal grants database.

    Args:
        db: Async database session (unused but kept for interface consistency).
        user_id: Authenticated user UUID string (unused).
        **kwargs: ``topics`` (list of strings), ``max_results`` (int, optional).

    Returns:
        Dict with ``results`` list and ``total_results`` integer.
    """
    try:
        topics: List[str] = kwargs.get("topics", [])
        if not topics:
            return {"error": "At least one topic string is required."}

        max_results: int = kwargs.get("max_results", 10)

        from app.source_fetchers.grants_gov_fetcher import (
            fetch_grants_gov_opportunities,
        )

        result = await fetch_grants_gov_opportunities(
            topics=topics,
            max_results=max_results,
            posted_only=True,
            filter_relevant=False,
        )

        formatted: List[Dict[str, Any]] = []
        for opp in result.opportunities:
            formatted.append(
                {
                    "title": opp.title,
                    "agency": opp.agency,
                    "description": (opp.description or "")[:500],
                    "close_date": (
                        opp.close_date.isoformat() if opp.close_date else None
                    ),
                    "estimated_funding": opp.estimated_funding,
                    "award_floor": opp.award_floor,
                    "award_ceiling": opp.award_ceiling,
                    "opportunity_url": opp.opportunity_url,
                    "cfda_numbers": opp.cfda_numbers,
                }
            )

        return {
            "results": formatted,
            "total_results": result.total_results,
            "errors": result.errors[:3] if result.errors else [],
        }

    except Exception as exc:
        logger.exception("search_grants_gov failed: %s", exc)
        return {
            "error": "Grants.gov search is temporarily unavailable. Please try again."
        }


registry.register(
    ToolDefinition(
        name="search_grants_gov",
        description=(
            "Search the federal Grants.gov database for grant "
            "opportunities matching given topics. Returns titles, "
            "agencies, funding amounts, deadlines, and CFDA numbers."
        ),
        parameters={
            "type": "object",
            "properties": {
                "topics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "List of keyword topics to search for "
                        "(e.g. ['municipal infrastructure', 'public health'])."
                    ),
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default 10).",
                },
            },
            "required": ["topics"],
        },
        handler=_handle_search_grants_gov,
        requires_online=True,
    )
)


# ---------------------------------------------------------------------------
# Tool 4: search_sam_gov (online)
# ---------------------------------------------------------------------------


async def _handle_search_sam_gov(db: AsyncSession, user_id: str, **kwargs: Any) -> dict:
    """Search the SAM.gov federal opportunities database.

    Args:
        db: Async database session (unused).
        user_id: Authenticated user UUID string (unused).
        **kwargs: ``topics`` (list of strings), ``max_results`` (int, optional).

    Returns:
        Dict with ``results`` list and ``total_results`` integer.
    """
    try:
        topics: List[str] = kwargs.get("topics", [])
        if not topics:
            return {"error": "At least one topic string is required."}

        max_results: int = kwargs.get("max_results", 10)

        from app.source_fetchers.sam_gov_fetcher import (
            fetch_sam_gov_opportunities,
        )

        result = await fetch_sam_gov_opportunities(
            topics=topics,
            max_results=max_results,
            include_grants=True,
            include_contracts=False,
            filter_relevant=False,
        )

        formatted: List[Dict[str, Any]] = []
        for opp in result.opportunities:
            formatted.append(
                {
                    "title": opp.title,
                    "department": opp.department,
                    "description": (opp.description or "")[:500],
                    "response_deadline": (
                        opp.response_deadline.isoformat()
                        if opp.response_deadline
                        else None
                    ),
                    "posted_date": (
                        opp.posted_date.isoformat() if opp.posted_date else None
                    ),
                    "notice_id": opp.notice_id,
                    "solicitation_number": opp.solicitation_number,
                    "opportunity_url": opp.opportunity_url,
                    "is_grant": opp.is_grant,
                }
            )

        return {
            "results": formatted,
            "total_results": result.total_results,
            "errors": result.errors[:3] if result.errors else [],
        }

    except Exception as exc:
        logger.exception("search_sam_gov failed: %s", exc)
        return {"error": "SAM.gov search is temporarily unavailable. Please try again."}


registry.register(
    ToolDefinition(
        name="search_sam_gov",
        description=(
            "Search the SAM.gov federal opportunities database for "
            "grant opportunities matching given topics. Returns titles, "
            "departments, deadlines, and links."
        ),
        parameters={
            "type": "object",
            "properties": {
                "topics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "List of keyword topics to search for "
                        "(e.g. ['affordable housing', 'climate resilience'])."
                    ),
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default 10).",
                },
            },
            "required": ["topics"],
        },
        handler=_handle_search_sam_gov,
        requires_online=True,
    )
)


# ---------------------------------------------------------------------------
# Tool 5: web_search (online)
# ---------------------------------------------------------------------------


async def _handle_web_search(db: AsyncSession, user_id: str, **kwargs: Any) -> dict:
    """Search the web for grant-related information.

    Args:
        db: Async database session (unused).
        user_id: Authenticated user UUID string (unused).
        **kwargs: ``query`` (str), ``num_results`` (int, optional).

    Returns:
        Dict with ``results`` list.
    """
    try:
        query: str = kwargs.get("query", "")
        if not query:
            return {"error": "A 'query' parameter is required."}

        num_results: int = kwargs.get("num_results", 5)

        from app.search_provider import search_web

        results = await search_web(query, num_results)

        formatted: List[Dict[str, Any]] = []
        for r in results:
            formatted.append(
                {
                    "title": r.title,
                    "url": r.url,
                    "snippet": r.snippet,
                }
            )

        return {"results": formatted, "count": len(formatted)}

    except Exception as exc:
        logger.exception("web_search failed: %s", exc)
        return {"error": "Web search is temporarily unavailable. Please try again."}


registry.register(
    ToolDefinition(
        name="web_search",
        description=(
            "Search the web for grant opportunities, funding news, "
            "or related information. Returns titles, URLs, and snippets."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The web search query string.",
                },
                "num_results": {
                    "type": "integer",
                    "description": "Number of results to return (default 5).",
                },
            },
            "required": ["query"],
        },
        handler=_handle_web_search,
        requires_online=True,
    )
)


# ---------------------------------------------------------------------------
# Tool 6: search_all_sources (online)
# ---------------------------------------------------------------------------


async def _handle_search_all_sources(
    db: AsyncSession, user_id: str, **kwargs: Any
) -> dict:
    """Search across all configured source types for grant opportunities.

    Uses the multi-source search module which queries Grants.gov, SAM.gov,
    web (SearXNG/Serper/Tavily), news, government documents, and optionally
    academic papers in parallel. Results are merged using Reciprocal Rank
    Fusion for optimal ranking.
    """
    try:
        from app.multi_source_search import search_all_sources

        query = kwargs.get("query", "")
        if not query:
            return {"error": "A 'query' parameter is required."}

        # Parse source_types filter if provided
        source_types = kwargs.get("source_types")
        include_flags: Dict[str, bool] = {}
        if source_types and isinstance(source_types, list):
            all_sources = {
                "grants_gov",
                "sam_gov",
                "web",
                "news",
                "government",
                "academic",
            }
            requested = set(source_types)
            for src in all_sources:
                include_flags[f"include_{src}"] = src in requested

        max_per_source = kwargs.get("max_per_source", 5)
        if not isinstance(max_per_source, int):
            try:
                max_per_source = int(max_per_source)
            except (ValueError, TypeError):
                max_per_source = 5
        max_per_source = max(1, min(max_per_source, 20))

        results = await search_all_sources(
            query,
            max_results_per_source=max_per_source,
            **include_flags,
        )

        # Format results for the chat assistant
        formatted: List[Dict[str, Any]] = []
        for r in results:
            item: Dict[str, Any] = {
                "title": r.title,
                "url": r.url,
                "snippet": r.snippet,
                "source_type": r.source_type,
                "rrf_score": r.rrf_score,
            }
            # Include selected metadata
            if r.metadata.get("agency"):
                item["agency"] = r.metadata["agency"]
            if r.metadata.get("close_date"):
                item["deadline"] = r.metadata["close_date"]
            if r.metadata.get("response_deadline"):
                item["deadline"] = r.metadata["response_deadline"]
            if r.metadata.get("source_types"):
                item["found_in_sources"] = r.metadata["source_types"]
            formatted.append(item)

        return {
            "results": formatted,
            "count": len(formatted),
            "query": query,
        }

    except Exception as exc:
        logger.exception("search_all_sources tool failed: %s", exc)
        return {"error": "Search failed. Please try again."}


registry.register(
    ToolDefinition(
        name="search_all_sources",
        description=(
            "Search across all available source types (Grants.gov, SAM.gov, web, "
            "news, government publications, academic papers) for grant opportunities "
            "and related information. Results are ranked using Reciprocal Rank Fusion. "
            "Use this for broad searches when the user wants to explore opportunities "
            "beyond the internal database."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query text.",
                },
                "source_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Optional filter: only search these source types. "
                        "Values: grants_gov, sam_gov, web, news, government, academic. "
                        "If omitted, searches all available sources."
                    ),
                },
                "max_per_source": {
                    "type": "integer",
                    "description": "Maximum results per source (1-20, default 5).",
                },
            },
            "required": ["query"],
        },
        handler=_handle_search_all_sources,
        requires_online=True,
    )
)
