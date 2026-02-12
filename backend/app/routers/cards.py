"""Cards router -- core CRUD, search, similar, blocked-topics, filter-preview."""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.deps import (
    supabase,
    get_current_user,
    _safe_error,
    azure_openai_embedding_client,
    get_embedding_deployment,
)
from app.models.core import Card, CardCreate, SimilarCard, BlockedTopic
from app.models.search import (
    AdvancedSearchRequest,
    AdvancedSearchResponse,
    SearchResultItem,
)
from app.models.history import (
    ScoreHistory,
    StageHistory,
    CardData,
    CardComparisonItem,
    CardComparisonResponse,
)
from app.models.workstream import FilterPreviewRequest, FilterPreviewResponse
from app.helpers.search_utils import (
    _apply_search_filters,
    _apply_score_filters,
    _extract_highlights,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["cards"])


# ============================================================================
# Cards endpoints
# ============================================================================


@router.get("/cards", response_model=List[Card])
async def get_cards(
    limit: int = 20,
    offset: int = 0,
    pillar_id: Optional[str] = None,
    stage_id: Optional[str] = None,
    horizon: Optional[str] = None,
    search: Optional[str] = None,
):
    """Get cards with filtering"""
    query = supabase.table("cards").select("*").eq("status", "active")

    if pillar_id:
        query = query.eq("pillar_id", pillar_id)
    if stage_id:
        query = query.eq("stage_id", stage_id)
    if horizon:
        query = query.eq("horizon", horizon)

    response = (
        query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    )

    return [Card(**card) for card in response.data]


# NOTE: This route MUST be before /cards/{card_id} to avoid route matching issues
@router.get("/cards/pending-review")
async def get_pending_review_cards(
    current_user: dict = Depends(get_current_user),
    limit: int = 20,
    offset: int = 0,
    pillar_id: Optional[str] = None,
):
    """
    Get cards pending review.

    Returns discovered cards that need human review, ordered by AI confidence
    (descending) and discovery date.
    """
    # Backward-compatible: include draft cards even if `review_status` wasn't set correctly.
    query = (
        supabase.table("cards")
        .select("*")
        .neq("review_status", "rejected")
        .or_("review_status.in.(discovered,pending_review),status.eq.draft")
    )

    if pillar_id:
        query = query.eq("pillar_id", pillar_id)

    response = (
        query.order("ai_confidence", desc=True)
        .order("discovered_at", desc=True)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )

    return response.data


# NOTE: This route MUST be before /cards/{card_id} to avoid route matching issues
@router.get("/cards/compare", response_model=CardComparisonResponse)
async def compare_cards(
    card_ids: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: dict = Depends(get_current_user),
):
    """
    Compare two cards side-by-side with their historical data.

    Returns parallel data for both cards including metadata, score history,
    and stage history to enable synchronized timeline charts and comparative
    metrics visualization.

    Args:
        card_ids: Comma-separated list of exactly 2 card UUIDs (e.g., "id1,id2")
        start_date: Optional filter for score history start date
        end_date: Optional filter for score history end date

    Returns:
        CardComparisonResponse with parallel data for both cards

    Raises:
        400: If card_ids doesn't contain exactly 2 IDs
        404: If either card is not found
    """
    # Parse and validate card_ids
    ids = [id.strip() for id in card_ids.split(",") if id.strip()]
    if len(ids) != 2:
        raise HTTPException(
            status_code=400,
            detail="Exactly 2 card IDs must be provided (comma-separated)",
        )

    card_id_1, card_id_2 = ids

    # Helper function to fetch all data for a single card (synchronous)
    def fetch_card_comparison_data(card_id: str) -> CardComparisonItem:
        # Fetch card data
        card_response = (
            supabase.table("cards")
            .select(
                "id, name, slug, summary, pillar_id, goal_id, stage_id, horizon, "
                "maturity_score, velocity_score, novelty_score, impact_score, "
                "relevance_score, risk_score, opportunity_score, created_at, updated_at"
            )
            .eq("id", card_id)
            .execute()
        )

        if not card_response.data:
            raise HTTPException(status_code=404, detail=f"Card not found: {card_id}")

        card_data = CardData(**card_response.data[0])

        # Fetch score history
        score_query = (
            supabase.table("card_score_history").select("*").eq("card_id", card_id)
        )
        if start_date:
            score_query = score_query.gte("recorded_at", start_date.isoformat())
        if end_date:
            score_query = score_query.lte("recorded_at", end_date.isoformat())
        score_response = score_query.order("recorded_at", desc=True).execute()

        score_history = (
            [ScoreHistory(**record) for record in score_response.data]
            if score_response.data
            else []
        )

        # Fetch stage history from card_timeline
        stage_response = (
            supabase.table("card_timeline")
            .select(
                "id, card_id, created_at, old_stage_id, new_stage_id, old_horizon, new_horizon, trigger, reason"
            )
            .eq("card_id", card_id)
            .eq("event_type", "stage_changed")
            .order("created_at", desc=True)
            .execute()
        )

        stage_history = []
        if stage_response.data:
            for record in stage_response.data:
                if record.get("new_stage_id") is None:
                    continue
                stage_history.append(
                    StageHistory(
                        id=record["id"],
                        card_id=record["card_id"],
                        changed_at=record["created_at"],
                        old_stage_id=record.get("old_stage_id"),
                        new_stage_id=record["new_stage_id"],
                        old_horizon=record.get("old_horizon"),
                        new_horizon=record.get("new_horizon", "H3"),
                        trigger=record.get("trigger"),
                        reason=record.get("reason"),
                    )
                )

        return CardComparisonItem(
            card=card_data, score_history=score_history, stage_history=stage_history
        )

    # Fetch data for both cards in parallel using asyncio.gather with to_thread
    try:
        card1_data, card2_data = await asyncio.gather(
            asyncio.to_thread(fetch_card_comparison_data, card_id_1),
            asyncio.to_thread(fetch_card_comparison_data, card_id_2),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching comparison data: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch comparison data")

    return CardComparisonResponse(
        card1=card1_data, card2=card2_data, comparison_generated_at=datetime.now()
    )


@router.get("/cards/{card_id}", response_model=Card)
async def get_card(card_id: uuid.UUID):
    """Get specific card"""
    response = supabase.table("cards").select("*").eq("id", str(card_id)).execute()
    if response.data:
        return Card(**response.data[0])
    else:
        raise HTTPException(status_code=404, detail="Card not found")


@router.post("/cards", response_model=Card)
async def create_card(
    card_data: CardCreate, current_user: dict = Depends(get_current_user)
):
    """Create new card"""
    # Generate slug from name
    slug = card_data.name.lower().replace(" ", "-").replace(":", "").replace("/", "-")

    card_dict = card_data.dict()
    card_dict.update(
        {
            "slug": slug,
            "created_by": current_user["id"],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
    )

    response = supabase.table("cards").insert(card_dict).execute()
    if response.data:
        return Card(**response.data[0])
    else:
        raise HTTPException(status_code=400, detail="Failed to create card")


@router.post("/cards/search")
async def search_cards(request: AdvancedSearchRequest):
    """
    Advanced search for intelligence cards with filtering and vector similarity.

    Supports:
    - Text query with optional vector (semantic) search
    - Filters: pillar_ids, stage_ids, date_range, score_thresholds
    - Pagination with limit and offset

    Returns cards sorted by relevance with search metadata.
    """
    try:
        results = []
        search_type = (
            "vector" if request.use_vector_search and request.query else "text"
        )

        # Vector search path
        if request.use_vector_search and request.query:
            try:
                # Get embedding for search query (uses embedding client with specific API version)
                embedding_response = azure_openai_embedding_client.embeddings.create(
                    model=get_embedding_deployment(), input=request.query
                )
                query_embedding = embedding_response.data[0].embedding

                # Vector similarity search returns id, name, summary,
                # pillar_id, horizon, similarity.  We hydrate the matched
                # IDs with only the columns needed for SearchResultItem.
                search_response = supabase.rpc(
                    "find_similar_cards",
                    {
                        "query_embedding": query_embedding,
                        "match_threshold": 0.5,
                        "match_count": request.limit
                        + request.offset
                        + 100,  # Get extra for filtering
                    },
                ).execute()

                matched = search_response.data or []
                if matched:
                    similarity_map = {
                        item["id"]: item.get("similarity", 0.0) for item in matched
                    }
                    matched_ids = list(similarity_map.keys())
                    _SEARCH_HYDRATE_COLS = (
                        "id, name, slug, summary, description, pillar_id, goal_id, "
                        "anchor_id, stage_id, horizon, novelty_score, maturity_score, "
                        "impact_score, relevance_score, velocity_score, risk_score, "
                        "opportunity_score, status, created_at, updated_at, "
                        "signal_quality_score, top25_relevance, origin, is_exploratory"
                    )
                    cards_response = (
                        supabase.table("cards")
                        .select(_SEARCH_HYDRATE_COLS)
                        .in_("id", matched_ids)
                        .execute()
                    )
                    results = cards_response.data or []
                    for item in results:
                        item["search_relevance"] = similarity_map.get(item["id"], 0.0)
                    # Preserve similarity ordering
                    results.sort(
                        key=lambda x: x.get("search_relevance", 0), reverse=True
                    )

            except Exception as vector_error:
                logger.warning(
                    f"Vector search failed, falling back to text: {vector_error}"
                )
                search_type = "text"
                results = []

        # Text search path (or fallback)
        if search_type == "text" or (not request.use_vector_search and request.query):
            search_type = "text"
            query_builder = supabase.table("cards").select("*")

            if request.query:
                # Text search on name and summary
                query_builder = query_builder.or_(
                    f"name.ilike.%{request.query}%,summary.ilike.%{request.query}%"
                )

            response = query_builder.limit(
                request.limit + request.offset + 100
            ).execute()
            results = response.data or []

            # Add placeholder relevance for text search
            for item in results:
                item["search_relevance"] = None

        # If no query provided, fetch all cards (for filter-only searches)
        if not request.query:
            search_type = "filter"
            response = (
                supabase.table("cards")
                .select("*")
                .limit(request.limit + request.offset + 100)
                .execute()
            )
            results = response.data or []

        # Apply filters
        if request.filters:
            results = _apply_search_filters(results, request.filters)

        # Get total count before pagination
        total_count = len(results)

        # Apply pagination
        results = results[request.offset : request.offset + request.limit]

        # Convert to response format
        result_items = [
            SearchResultItem(
                id=item.get("id", ""),
                name=item.get("name", ""),
                slug=item.get("slug", ""),
                summary=item.get("summary"),
                description=item.get("description"),
                pillar_id=item.get("pillar_id"),
                goal_id=item.get("goal_id"),
                anchor_id=item.get("anchor_id"),
                stage_id=item.get("stage_id"),
                horizon=item.get("horizon"),
                novelty_score=item.get("novelty_score"),
                maturity_score=item.get("maturity_score"),
                impact_score=item.get("impact_score"),
                relevance_score=item.get("relevance_score"),
                velocity_score=item.get("velocity_score"),
                risk_score=item.get("risk_score"),
                opportunity_score=item.get("opportunity_score"),
                status=item.get("status"),
                created_at=item.get("created_at"),
                updated_at=item.get("updated_at"),
                search_relevance=item.get("search_relevance"),
                match_highlights=(
                    _extract_highlights(item, request.query) if request.query else None
                ),
            )
            for item in results
        ]

        return AdvancedSearchResponse(
            results=result_items,
            total_count=total_count,
            query=request.query,
            filters_applied=request.filters,
            search_type=search_type,
        )

    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=_safe_error("search", e))


# ============================================================================
# Similar cards & blocked topics
# ============================================================================


@router.get("/cards/{card_id}/similar", response_model=List[SimilarCard])
async def get_similar_cards(card_id: str, limit: int = 5):
    """
    Get cards similar to the specified card.

    Uses vector similarity search via the find_similar_cards RPC function
    to find semantically similar cards.

    Args:
        card_id: UUID of the source card
        limit: Maximum number of similar cards to return (default: 5)

    Returns:
        List of similar cards with similarity scores
    """
    # Get the source card's embedding
    card_check = (
        supabase.table("cards")
        .select("id, name, embedding")
        .eq("id", card_id)
        .execute()
    )
    if not card_check.data:
        raise HTTPException(status_code=404, detail="Card not found")

    card = card_check.data[0]

    if not card.get("embedding"):
        # Fallback: return empty list if no embedding
        logger.warning(f"Card {card_id} has no embedding for similarity search")
        return []

    try:
        # Use RPC function for vector similarity search
        response = supabase.rpc(
            "match_cards_by_embedding",
            {
                "query_embedding": card["embedding"],
                "match_threshold": 0.7,
                "match_count": limit + 1,  # +1 to exclude self
            },
        ).execute()

        # Filter out the source card itself
        similar_cards = [
            SimilarCard(
                id=c["id"],
                name=c["name"],
                summary=c.get("summary"),
                similarity=c["similarity"],
                pillar_id=c.get("pillar_id"),
            )
            for c in response.data
            if c["id"] != card_id
        ][:limit]

        return similar_cards

    except Exception as e:
        logger.error(f"Similar cards search failed: {str(e)}")
        # Fallback to simple text-based similarity
        return []


@router.get("/discovery/blocked-topics", response_model=List[BlockedTopic])
async def list_blocked_topics(
    current_user: dict = Depends(get_current_user), limit: int = 50, offset: int = 0
):
    """
    List blocked discovery topics.

    Returns topics that have been blocked from discovery, either due to
    multiple user dismissals or manual blocking.

    Args:
        limit: Maximum number of blocked topics to return (default: 50)
        offset: Number of topics to skip for pagination

    Returns:
        List of blocked topic records
    """
    response = (
        supabase.table("discovery_blocks")
        .select("*")
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )

    return [BlockedTopic(**block) for block in response.data]


# ============================================================================
# Filter preview
# ============================================================================


@router.post("/cards/filter-preview", response_model=FilterPreviewResponse)
async def preview_filter_count(
    filters: FilterPreviewRequest, current_user: dict = Depends(get_current_user)
):
    """
    Preview how many cards match the given filter criteria.

    This is a lightweight endpoint for showing estimated matches while
    creating/editing workstreams. Does not modify any data.

    Args:
        filters: Filter criteria (pillars, goals, stages, horizon, keywords)
        current_user: Authenticated user (injected)

    Returns:
        FilterPreviewResponse with estimated count and sample cards
    """
    # Build base query for active cards
    query = (
        supabase.table("cards")
        .select("id, name, pillar_id, horizon, stage_id")
        .eq("status", "active")
    )

    # Apply filters
    if filters.pillar_ids:
        query = query.in_("pillar_id", filters.pillar_ids)

    if filters.goal_ids:
        query = query.in_("goal_id", filters.goal_ids)

    if filters.horizon and filters.horizon != "ALL":
        query = query.eq("horizon", filters.horizon)

    # Fetch cards (limit to reasonable amount for performance)
    response = query.order("created_at", desc=True).limit(500).execute()
    cards = response.data or []

    # Apply stage filtering client-side
    if filters.stage_ids:
        filtered_by_stage = []
        for card in cards:
            card_stage_id = card.get("stage_id") or ""
            stage_num = (
                card_stage_id.split("_")[0] if "_" in card_stage_id else card_stage_id
            )
            if stage_num in filters.stage_ids:
                filtered_by_stage.append(card)
        cards = filtered_by_stage

    # Apply keyword filtering (need to fetch full text for this)
    if filters.keywords:
        # Fetch full card data for keyword matching
        if cards:
            card_ids = [c["id"] for c in cards]
            full_response = (
                supabase.table("cards")
                .select("id, name, summary, description, pillar_id, horizon, stage_id")
                .in_("id", card_ids)
                .execute()
            )
            full_cards = full_response.data or []

            filtered_cards = []
            for card in full_cards:
                card_text = " ".join(
                    [
                        (card.get("name") or "").lower(),
                        (card.get("summary") or "").lower(),
                        (card.get("description") or "").lower(),
                    ]
                )
                if any(keyword.lower() in card_text for keyword in filters.keywords):
                    filtered_cards.append(card)
            cards = filtered_cards

    # Build response
    sample_cards = [
        {
            "id": c["id"],
            "name": c["name"],
            "pillar_id": c.get("pillar_id"),
            "horizon": c.get("horizon"),
        }
        for c in cards[:5]
    ]

    return FilterPreviewResponse(estimated_count=len(cards), sample_cards=sample_cards)
