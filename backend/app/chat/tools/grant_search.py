"""Search tools for the grant discovery assistant.

Provides tools to search the internal grant database, Grants.gov,
SAM.gov, and the web for grant opportunities.
"""

from __future__ import annotations

import logging
from datetime import datetime
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

    Generates an embedding for the query text, then runs hybrid
    (full-text + vector) search over the cards table.  Results
    are optionally post-filtered by pillar, category, funding range,
    and deadline.

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

        # Generate embedding for the query
        from app.openai_provider import (
            azure_openai_async_embedding_client,
            get_embedding_deployment,
        )

        embed_response = await azure_openai_async_embedding_client.embeddings.create(
            model=get_embedding_deployment(),
            input=query[:8000],
        )
        embedding: List[float] = embed_response.data[0].embedding

        # Run hybrid search
        from app.helpers.db_utils import hybrid_search_cards

        raw_results = await hybrid_search_cards(
            db,
            query,
            embedding,
            match_count=15,
            status_filter="active",
        )

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
                    if card.deadline.replace(tzinfo=None) < cutoff.replace(tzinfo=None):
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
                    "similarity": float(row.get("rrf_score", 0)),
                }
            )

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
            "matching a text query. Supports optional filters for strategic "
            "pillar, grant category, funding range, and application deadline."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Free-text search query describing the grant "
                        "opportunity or topic of interest."
                    ),
                },
                "pillar_filter": {
                    "type": "string",
                    "description": (
                        "Strategic pillar ID to filter by "
                        "(e.g. 'CH', 'MC', 'HS', 'EC', 'ES', 'CE')."
                    ),
                },
                "category_filter": {
                    "type": "string",
                    "description": "Grant category ID to filter by.",
                },
                "funding_min": {
                    "type": "number",
                    "description": "Minimum funding amount in USD.",
                },
                "funding_max": {
                    "type": "number",
                    "description": "Maximum funding amount in USD.",
                },
                "deadline_after": {
                    "type": "string",
                    "description": (
                        "ISO 8601 date string; only return grants with "
                        "deadlines after this date."
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
