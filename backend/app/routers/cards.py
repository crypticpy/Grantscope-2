"""Cards router -- core CRUD, search, similar, blocked-topics, filter-preview.

Migrated from Supabase PostgREST to SQLAlchemy 2.0 async.
"""

import asyncio
import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select, func, and_, or_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import (
    get_db,
    get_current_user_hardcoded,
    _safe_error,
    azure_openai_embedding_client,
    get_embedding_deployment,
)
from app.card_analysis_service import queue_card_analysis
from app.models.core import Card as CardSchema, CardCreate, SimilarCard, BlockedTopic
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
from app.models.db.card import Card
from app.models.db.card_extras import CardFollow, CardScoreHistory, CardTimeline
from app.models.db.discovery import DiscoveryBlock
from app.helpers.db_utils import vector_search_cards
from app.helpers.search_utils import (
    _apply_search_filters,
    _apply_score_filters,
    _extract_highlights,
)
from app.taxonomy import VALID_PIPELINE_STATUSES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["cards"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SKIP_COLUMNS = {"embedding", "search_vector"}


def _card_to_dict(card: Card) -> dict[str, Any]:
    """Convert a Card ORM instance to a JSON-safe dictionary.

    Handles UUID -> str, datetime -> ISO string, and Decimal -> float
    conversions so the result can be returned directly from a FastAPI
    endpoint.
    """
    result: dict[str, Any] = {}
    for col in Card.__table__.columns:
        if col.name in _SKIP_COLUMNS:
            continue
        value = getattr(card, col.name, None)
        if value is None:
            result[col.name] = None
        elif isinstance(value, uuid.UUID):
            result[col.name] = str(value)
        elif isinstance(value, datetime):
            result[col.name] = value.isoformat()
        elif isinstance(value, date):
            result[col.name] = value.isoformat()
        elif isinstance(value, Decimal):
            result[col.name] = float(value)
        else:
            result[col.name] = value
    return result


def _parse_datetime_filter(
    value: Optional[str], *, end_of_day: bool = False
) -> Optional[datetime]:
    """Parse date/datetime query filters to timezone-aware datetimes.

    Accepts either full ISO datetime strings or YYYY-MM-DD dates.
    """
    if not value:
        return None

    # Date-only input: convert to UTC day boundary.
    if "T" not in value:
        parsed_date = date.fromisoformat(value)
        if end_of_day:
            return datetime(
                parsed_date.year,
                parsed_date.month,
                parsed_date.day,
                23,
                59,
                59,
                999999,
                tzinfo=timezone.utc,
            )
        return datetime(
            parsed_date.year,
            parsed_date.month,
            parsed_date.day,
            0,
            0,
            0,
            0,
            tzinfo=timezone.utc,
        )

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


# ============================================================================
# Cards endpoints
# ============================================================================


@router.get("/cards")
async def get_cards(
    limit: int = 50,
    offset: int = 0,
    pillar_id: Optional[str] = None,
    stage_id: Optional[str] = None,
    horizon: Optional[str] = None,
    pipeline_status: Optional[str] = None,
    search: Optional[str] = None,
    grant_type: Optional[str] = None,
    category_id: Optional[str] = None,
    created_after: Optional[str] = None,
    created_before: Optional[str] = None,
    updated_after: Optional[str] = None,
    updated_before: Optional[str] = None,
    deadline_after: Optional[str] = None,
    deadline_before: Optional[str] = None,
    impact_min: Optional[float] = None,
    relevance_min: Optional[float] = None,
    novelty_min: Optional[float] = None,
    funding_min: Optional[float] = None,
    funding_max: Optional[float] = None,
    following_only: bool = False,
    sort_by: Optional[str] = None,
    sort_asc: Optional[bool] = None,
    slug: Optional[str] = None,
    status: Optional[str] = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """Get cards with filtering and pagination.

    Returns { cards: [...], total_count, limit, offset, has_more }.
    """
    # Support both singular and repeated query params for filters like:
    # ?pillar_id=a&pillar_id=b
    # ?pipeline_status=discovered&pipeline_status=screening
    query_params = request.query_params if request is not None else None
    pillar_ids = (
        [p for p in query_params.getlist("pillar_id") if p] if query_params else []
    )
    pipeline_statuses = (
        [s for s in query_params.getlist("pipeline_status") if s]
        if query_params
        else []
    )
    if pillar_id and not pillar_ids:
        pillar_ids = [pillar_id]
    if pipeline_status and not pipeline_statuses:
        pipeline_statuses = [pipeline_status]

    invalid_pipeline_statuses = [
        s for s in pipeline_statuses if s not in VALID_PIPELINE_STATUSES
    ]
    if invalid_pipeline_statuses:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid pipeline_status '{invalid_pipeline_statuses[0]}'. "
                f"Must be one of: {', '.join(sorted(VALID_PIPELINE_STATUSES))}"
            ),
        )

    try:
        active_status = status or "active"
        base = select(Card).where(Card.status == active_status)

        # Parse date/datetime filter bounds.
        try:
            created_after_dt = _parse_datetime_filter(created_after)
            created_before_dt = _parse_datetime_filter(created_before, end_of_day=True)
            updated_after_dt = _parse_datetime_filter(updated_after)
            updated_before_dt = _parse_datetime_filter(updated_before, end_of_day=True)
            deadline_after_dt = _parse_datetime_filter(deadline_after)
            deadline_before_dt = _parse_datetime_filter(deadline_before, end_of_day=True)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid date filter: {e}") from e

        if following_only:
            if request is None:
                raise HTTPException(status_code=401, detail="Authentication required")
            current_user = await get_current_user_hardcoded(request)
            user_uuid = uuid.UUID(current_user["id"])
            base = base.join(CardFollow, CardFollow.card_id == Card.id).where(
                CardFollow.user_id == user_uuid
            )

        if slug:
            base = base.where(Card.slug == slug)
        if pillar_ids:
            base = base.where(Card.pillar_id.in_(pillar_ids))
        if pipeline_statuses:
            base = base.where(Card.pipeline_status.in_(pipeline_statuses))
        if stage_id:
            base = base.where(Card.stage_id == stage_id)
        if horizon:
            base = base.where(Card.horizon == horizon)
        if grant_type:
            base = base.where(Card.grant_type == grant_type)
        if category_id:
            base = base.where(Card.category_id == category_id)
        if search:
            pattern = f"%{search}%"
            base = base.where(
                or_(Card.name.ilike(pattern), Card.summary.ilike(pattern))
            )
        if created_after_dt:
            base = base.where(Card.created_at >= created_after_dt)
        if created_before_dt:
            base = base.where(Card.created_at <= created_before_dt)
        if updated_after_dt:
            base = base.where(Card.updated_at >= updated_after_dt)
        if updated_before_dt:
            base = base.where(Card.updated_at <= updated_before_dt)
        if deadline_after_dt:
            base = base.where(Card.deadline >= deadline_after_dt)
        if deadline_before_dt:
            base = base.where(Card.deadline <= deadline_before_dt)
        if impact_min is not None:
            base = base.where(Card.impact_score >= impact_min)
        if relevance_min is not None:
            base = base.where(Card.relevance_score >= relevance_min)
        if novelty_min is not None:
            base = base.where(Card.novelty_score >= novelty_min)
        if funding_min is not None:
            base = base.where(Card.funding_amount_max >= funding_min)
        if funding_max is not None:
            base = base.where(Card.funding_amount_min <= funding_max)

        # Total count (before pagination)
        count_result = await db.execute(
            select(func.count()).select_from(base.subquery())
        )
        total_count = count_result.scalar() or 0

        # Sorting
        sort_column = Card.created_at
        if sort_by == "name":
            sort_column = Card.name
        elif sort_by == "deadline":
            sort_column = Card.deadline
        elif sort_by == "funding_amount_max":
            sort_column = Card.funding_amount_max
        elif sort_by == "updated_at":
            sort_column = Card.updated_at
        elif sort_by == "signal_quality_score":
            sort_column = Card.signal_quality_score
        elif sort_by == "relevance_score":
            sort_column = Card.relevance_score
        elif sort_by == "opportunity_score":
            sort_column = Card.opportunity_score

        if sort_asc:
            base = base.order_by(sort_column.asc().nulls_last())
        else:
            base = base.order_by(sort_column.desc().nulls_last())

        stmt = base.offset(offset).limit(limit)
        result = await db.execute(stmt)
        cards = result.scalars().all()

        return {
            "cards": [_card_to_dict(c) for c in cards],
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total_count,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=_safe_error("get_cards", e)) from e


# NOTE: This route MUST be before /cards/{card_id} to avoid route matching issues
@router.get("/cards/pending-review")
async def get_pending_review_cards(
    current_user: dict = Depends(get_current_user_hardcoded),
    limit: int = 200,
    offset: int = 0,
    pillar_id: Optional[str] = None,
    sort: Optional[str] = Query(None, regex="^(confidence|date)$"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get cards pending review.

    Returns discovered cards that need human review.
    Default sort: newest first (discovered_at desc), with confidence as tiebreaker.
    Use sort=confidence for confidence-first ordering.
    """
    try:
        # Backward-compatible: include draft cards even if `review_status` wasn't set correctly.
        stmt = select(Card).where(
            Card.review_status != "rejected",
            or_(
                Card.review_status.in_(["discovered", "pending_review"]),
                Card.status == "draft",
            ),
        )

        if pillar_id:
            stmt = stmt.where(Card.pillar_id == pillar_id)

        if sort == "confidence":
            stmt = stmt.order_by(
                Card.ai_confidence.desc().nulls_last(),
                Card.discovered_at.desc().nulls_last(),
            )
        else:
            # Default: newest first
            stmt = stmt.order_by(
                Card.discovered_at.desc().nulls_last(),
                Card.ai_confidence.desc().nulls_last(),
            )

        stmt = stmt.order_by(Card.created_at.desc()).offset(offset).limit(limit)

        result = await db.execute(stmt)
        cards = result.scalars().all()

        return [_card_to_dict(c) for c in cards]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=_safe_error("get_pending_review_cards", e)
        ) from e


# NOTE: This route MUST be before /cards/{card_id} to avoid route matching issues
@router.get("/cards/compare", response_model=CardComparisonResponse)
async def compare_cards(
    card_ids: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: dict = Depends(get_current_user_hardcoded),
    db: AsyncSession = Depends(get_db),
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

    try:

        async def fetch_card_comparison_data(card_id: str) -> CardComparisonItem:
            # Fetch card data
            card_result = await db.execute(select(Card).where(Card.id == card_id))
            card_obj = card_result.scalar_one_or_none()

            if not card_obj:
                raise HTTPException(
                    status_code=404, detail=f"Card not found: {card_id}"
                )

            card_dict = _card_to_dict(card_obj)
            card_data = CardData(
                id=card_dict["id"],
                name=card_dict["name"],
                slug=card_dict["slug"],
                summary=card_dict.get("summary"),
                pillar_id=card_dict.get("pillar_id"),
                goal_id=card_dict.get("goal_id"),
                stage_id=card_dict.get("stage_id"),
                horizon=card_dict.get("horizon"),
                pipeline_status=card_dict.get("pipeline_status"),
                maturity_score=card_dict.get("maturity_score"),
                velocity_score=(
                    int(card_dict["velocity_score"])
                    if card_dict.get("velocity_score") is not None
                    else None
                ),
                novelty_score=card_dict.get("novelty_score"),
                impact_score=card_dict.get("impact_score"),
                relevance_score=card_dict.get("relevance_score"),
                risk_score=card_dict.get("risk_score"),
                opportunity_score=card_dict.get("opportunity_score"),
                created_at=card_dict.get("created_at"),
                updated_at=card_dict.get("updated_at"),
            )

            # Fetch score history
            score_stmt = select(CardScoreHistory).where(
                CardScoreHistory.card_id == card_id
            )
            if start_date:
                score_stmt = score_stmt.where(
                    CardScoreHistory.recorded_at >= start_date
                )
            if end_date:
                score_stmt = score_stmt.where(CardScoreHistory.recorded_at <= end_date)
            score_stmt = score_stmt.order_by(CardScoreHistory.recorded_at.desc())

            score_result = await db.execute(score_stmt)
            score_rows = score_result.scalars().all()

            score_history = [
                ScoreHistory(
                    id=str(row.id),
                    card_id=str(row.card_id),
                    recorded_at=row.recorded_at,
                    maturity_score=row.maturity_score,
                    velocity_score=row.velocity_score,
                    novelty_score=row.novelty_score,
                    impact_score=row.impact_score,
                    relevance_score=row.relevance_score,
                    risk_score=row.risk_score,
                    opportunity_score=row.opportunity_score,
                )
                for row in score_rows
            ]

            # Fetch stage history from card_timeline
            # Note: old_stage_id, new_stage_id, old_horizon, new_horizon, trigger,
            # reason are DB columns not on the ORM model, so use raw SQL.
            stage_sql = text(
                """
                SELECT id, card_id, created_at, old_stage_id, new_stage_id,
                       old_horizon, new_horizon, trigger, reason
                FROM card_timeline
                WHERE card_id = :card_id
                  AND event_type = 'stage_changed'
                ORDER BY created_at DESC
                """
            )
            stage_result = await db.execute(stage_sql, {"card_id": card_id})
            stage_rows = stage_result.mappings().all()

            stage_history = []
            for record in stage_rows:
                if record.get("new_stage_id") is None:
                    continue
                stage_history.append(
                    StageHistory(
                        id=str(record["id"]),
                        card_id=str(record["card_id"]),
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
                card=card_data,
                score_history=score_history,
                stage_history=stage_history,
            )

        # Fetch data for both cards sequentially (sharing the same session)
        card1_data = await fetch_card_comparison_data(card_id_1)
        card2_data = await fetch_card_comparison_data(card_id_2)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching comparison data: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch comparison data")

    return CardComparisonResponse(
        card1=card1_data,
        card2=card2_data,
        comparison_generated_at=datetime.now(timezone.utc),
    )


@router.get("/cards/{card_id}", response_model=CardSchema)
async def get_card(
    card_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get specific card"""
    try:
        result = await db.execute(select(Card).where(Card.id == card_id))
        card = result.scalar_one_or_none()
        if card:
            return CardSchema(**_card_to_dict(card))
        else:
            raise HTTPException(status_code=404, detail="Card not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=_safe_error("get_card", e)) from e


@router.post("/cards", response_model=CardSchema)
async def create_card(
    card_data: CardCreate,
    current_user: dict = Depends(get_current_user_hardcoded),
    db: AsyncSession = Depends(get_db),
):
    """Create new card"""
    try:
        # Generate slug from name
        slug = (
            card_data.name.lower().replace(" ", "-").replace(":", "").replace("/", "-")
        )

        now = datetime.now(timezone.utc)

        card_dict = card_data.dict()
        new_card = Card(
            name=card_dict["name"],
            slug=slug,
            summary=card_dict.get("summary"),
            description=card_dict.get("description"),
            pillar_id=card_dict.get("pillar_id"),
            goal_id=card_dict.get("goal_id"),
            anchor_id=card_dict.get("anchor_id"),
            stage_id=card_dict.get("stage_id"),
            horizon=card_dict.get("horizon"),
            pipeline_status=card_dict.get("pipeline_status", "discovered"),
            pipeline_status_changed_at=datetime.now(timezone.utc),
            grant_type=card_dict.get("grant_type"),
            funding_amount_min=card_dict.get("funding_amount_min"),
            funding_amount_max=card_dict.get("funding_amount_max"),
            deadline=card_dict.get("deadline"),
            grantor=card_dict.get("grantor"),
            category_id=card_dict.get("category_id"),
            source_url=card_dict.get("source_url"),
            created_by=current_user["id"],
            created_at=now,
            updated_at=now,
        )

        db.add(new_card)
        await db.flush()
        await db.refresh(new_card)

        # Queue background AI analysis for the new card
        try:
            await queue_card_analysis(db, str(new_card.id), current_user["id"])
        except Exception:
            logger.warning("Failed to queue card analysis for %s", new_card.id)

        return CardSchema(**_card_to_dict(new_card))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=_safe_error("create_card", e)
        ) from e


@router.post("/cards/search")
async def search_cards(
    request: AdvancedSearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Advanced search for intelligence cards with filtering and vector similarity.

    Supports:
    - Text query with optional vector (semantic) search
    - Filters: pillar_ids, stage_ids, date_range, score_thresholds
    - Pagination with limit and offset

    Returns cards sorted by relevance with search metadata.
    """
    try:
        results: list[dict[str, Any]] = []
        search_type = (
            "vector" if request.use_vector_search and request.query else "text"
        )

        # Vector search path
        if request.use_vector_search and request.query:
            try:
                # Get embedding for search query
                embedding_response = await asyncio.to_thread(
                    azure_openai_embedding_client.embeddings.create,
                    model=get_embedding_deployment(),
                    input=request.query,
                )
                query_embedding = embedding_response.data[0].embedding

                # Vector similarity search
                matched = await vector_search_cards(
                    db,
                    query_embedding,
                    match_threshold=0.5,
                    match_count=request.limit + request.offset + 100,
                )

                if matched:
                    similarity_map = {
                        item["id"]: item.get("similarity", 0.0) for item in matched
                    }
                    matched_ids = list(similarity_map.keys())

                    # Hydrate with full card data
                    hydrate_result = await db.execute(
                        select(Card).where(Card.id.in_(matched_ids))
                    )
                    hydrated_cards = hydrate_result.scalars().all()

                    results = [_card_to_dict(c) for c in hydrated_cards]
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
            stmt = select(Card)

            if request.query:
                # Text search on name and summary
                pattern = f"%{request.query}%"
                stmt = stmt.where(
                    or_(
                        Card.name.ilike(pattern),
                        Card.summary.ilike(pattern),
                    )
                )

            stmt = stmt.limit(request.limit + request.offset + 100)
            text_result = await db.execute(stmt)
            text_cards = text_result.scalars().all()
            results = [_card_to_dict(c) for c in text_cards]

            # Add placeholder relevance for text search
            for item in results:
                item["search_relevance"] = None

        # If no query provided, fetch all cards (for filter-only searches)
        if not request.query:
            search_type = "filter"
            stmt = select(Card).limit(request.limit + request.offset + 100)
            filter_result = await db.execute(stmt)
            filter_cards = filter_result.scalars().all()
            results = [_card_to_dict(c) for c in filter_cards]

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
                pipeline_status=item.get("pipeline_status"),
                novelty_score=item.get("novelty_score"),
                maturity_score=item.get("maturity_score"),
                impact_score=item.get("impact_score"),
                relevance_score=item.get("relevance_score"),
                velocity_score=(
                    int(item["velocity_score"])
                    if item.get("velocity_score") is not None
                    else None
                ),
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
        raise HTTPException(status_code=500, detail=_safe_error("search", e)) from e


# ============================================================================
# Similar cards & blocked topics
# ============================================================================


@router.get("/cards/{card_id}/similar", response_model=List[SimilarCard])
async def get_similar_cards(
    card_id: str,
    limit: int = 5,
    db: AsyncSession = Depends(get_db),
):
    """
    Get cards similar to the specified card.

    Uses vector similarity search via pgvector cosine distance
    to find semantically similar cards.

    Args:
        card_id: UUID of the source card
        limit: Maximum number of similar cards to return (default: 5)

    Returns:
        List of similar cards with similarity scores
    """
    try:
        # Get the source card's embedding via raw SQL (embedding is NullType in ORM)
        embed_sql = text("SELECT id, name, embedding FROM cards WHERE id = :card_id")
        embed_result = await db.execute(embed_sql, {"card_id": card_id})
        card_row = embed_result.mappings().first()

        if not card_row:
            raise HTTPException(status_code=404, detail="Card not found")

        if not card_row["embedding"]:
            # Fallback: return empty list if no embedding
            logger.warning(f"Card {card_id} has no embedding for similarity search")
            return []

        # Use vector_search_cards helper (replaces match_cards_by_embedding RPC)
        similar = await vector_search_cards(
            db,
            card_row["embedding"],
            match_threshold=0.7,
            match_count=limit + 1,  # +1 to exclude self
            require_active=True,
        )

        return [
            SimilarCard(
                id=c["id"],
                name=c["name"],
                summary=c.get("summary"),
                similarity=c["similarity"],
                pillar_id=c.get("pillar_id"),
            )
            for c in similar
            if c["id"] != card_id
        ][:limit]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Similar cards search failed: {str(e)}")
        # Fallback to empty list
        return []


@router.get("/discovery/blocked-topics", response_model=List[BlockedTopic])
async def list_blocked_topics(
    current_user: dict = Depends(get_current_user_hardcoded),
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
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
    try:
        stmt = (
            select(DiscoveryBlock)
            .order_by(DiscoveryBlock.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        result = await db.execute(stmt)
        blocks = result.scalars().all()

        return [
            BlockedTopic(
                id=str(block.id),
                topic_pattern=block.topic_name,
                reason=block.reason or "",
                blocked_by_count=block.blocked_by_count or 0,
                created_at=block.created_at,
            )
            for block in blocks
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=_safe_error("list_blocked_topics", e)
        ) from e


# ============================================================================
# Filter preview
# ============================================================================


@router.post("/cards/filter-preview", response_model=FilterPreviewResponse)
async def preview_filter_count(
    filters: FilterPreviewRequest,
    current_user: dict = Depends(get_current_user_hardcoded),
    db: AsyncSession = Depends(get_db),
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
    try:
        # Build base query for active cards
        stmt = select(Card).where(Card.status == "active")

        # Apply filters
        if filters.pillar_ids:
            stmt = stmt.where(Card.pillar_id.in_(filters.pillar_ids))

        if filters.goal_ids:
            stmt = stmt.where(Card.goal_id.in_(filters.goal_ids))

        if filters.horizon and filters.horizon != "ALL":
            stmt = stmt.where(Card.horizon == filters.horizon)

        # Apply pipeline_status filter if present
        if hasattr(filters, "pipeline_statuses") and filters.pipeline_statuses:
            stmt = stmt.where(Card.pipeline_status.in_(filters.pipeline_statuses))

        # Fetch cards (limit to reasonable amount for performance)
        stmt = stmt.order_by(Card.created_at.desc()).limit(500)
        result = await db.execute(stmt)
        cards_orm = result.scalars().all()
        cards = [_card_to_dict(c) for c in cards_orm]

        # Apply stage filtering client-side
        if filters.stage_ids:
            filtered_by_stage = []
            for card in cards:
                card_stage_id = card.get("stage_id") or ""
                stage_num = (
                    card_stage_id.split("_")[0]
                    if "_" in card_stage_id
                    else card_stage_id
                )
                if stage_num in filters.stage_ids:
                    filtered_by_stage.append(card)
            cards = filtered_by_stage

        # Apply keyword filtering
        if filters.keywords and cards:
            filtered_cards = []
            for card in cards:
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

        return FilterPreviewResponse(
            estimated_count=len(cards), sample_cards=sample_cards
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=_safe_error("filter_preview", e)
        ) from e
