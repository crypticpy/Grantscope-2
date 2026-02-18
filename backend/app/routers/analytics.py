"""Analytics and metrics router."""

import asyncio
import logging
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from datetime import date as date_type
from decimal import Decimal
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select, literal_column
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, get_current_user_hardcoded, _safe_error, openai_client
from app.openai_provider import get_chat_mini_deployment
from app.models.analytics import (
    VelocityDataPoint,
    VelocityResponse,
    PillarCoverageItem,
    PillarCoverageResponse,
    InsightItem,
    InsightsResponse,
    StageDistribution,
    HorizonDistribution,
    TrendingTopic,
    SourceStats,
    DiscoveryStats,
    WorkstreamEngagement,
    FollowStats,
    SystemWideStats,
    UserFollowItem,
    PopularCard,
    UserEngagementComparison,
    PillarAffinity,
    PersonalStats,
)
from app.models.processing_metrics import (
    ProcessingMetrics,
    SourceCategoryMetrics,
    DiscoveryRunMetrics,
    ResearchTaskMetrics,
    ClassificationMetrics,
)
from app.models.db.card import Card
from app.models.db.card_extras import CardFollow
from app.models.db.source import Source
from app.models.db.discovery import DiscoveryRun
from app.models.db.research import ResearchTask
from app.models.db.analytics import (
    CachedInsight,
    ClassificationValidation,
    DomainReputation,
)
from app.models.db.workstream import Workstream, WorkstreamCard
from app.models.db.search import SearchHistory
from app.models.db.user import User
from app.taxonomy import PILLAR_NAMES

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["analytics"])

# ============================================================================
# Constants
# ============================================================================

# Pillar definitions for analytics (canonical source: taxonomy.py)
ANALYTICS_PILLAR_DEFINITIONS = PILLAR_NAMES

# Stage name mapping
STAGE_NAMES = {
    "1": "Concept",
    "2": "Exploring",
    "3": "Pilot",
    "4": "PoC",
    "5": "Implementing",
    "6": "Scaling",
    "7": "Mature",
    "8": "Declining",
}

# Horizon labels
HORIZON_LABELS = {
    "H1": "Near-term (0-2 years)",
    "H2": "Mid-term (2-5 years)",
    "H3": "Long-term (5+ years)",
}

# Strategic Insights Prompt for AI Generation
INSIGHTS_GENERATION_PROMPT = """You are a strategic intelligence analyst for the City of Austin municipal government.

Based on the following top emerging trends from our horizon scanning system, generate concise strategic insights for city leadership.

TRENDS DATA:
{trends_data}

For each trend, provide a strategic insight that:
1. Explains the key implications for municipal operations
2. Identifies potential opportunities or risks
3. Suggests actionable next steps for city planners

Respond with JSON:
{{
  "insights": [
    {{
      "trend_name": "Name of the trend",
      "insight": "2-3 sentence strategic insight for city leadership"
    }}
  ]
}}

Keep each insight concise (2-3 sentences) and actionable. Focus on municipal relevance."""


# ============================================================================
# Helpers
# ============================================================================


def _compute_card_data_hash(cards: list) -> str:
    """Compute a hash of card data to detect changes for cache invalidation."""
    import hashlib

    data_str = "|".join(
        [
            f"{c.get('id', '')}:{c.get('velocity_score', 0)}:{c.get('impact_score', 0)}"
            for c in sorted(cards, key=lambda x: x.get("id", ""))
        ]
    )
    return hashlib.sha256(data_str.encode()).hexdigest()


def _row_to_dict(obj, skip_cols=None) -> dict:
    """Convert an ORM row to a JSON-safe dict."""
    skip = skip_cols or set()
    result = {}
    for col in obj.__table__.columns:
        if col.name in skip:
            continue
        value = getattr(obj, col.key, None)
        if isinstance(value, uuid.UUID):
            result[col.name] = str(value)
        elif isinstance(value, (datetime, date_type)):
            result[col.name] = value.isoformat()
        elif isinstance(value, Decimal):
            result[col.name] = float(value)
        else:
            result[col.name] = value
    return result


# ============================================================================
# Routes
# ============================================================================


@router.get("/metrics/processing", response_model=ProcessingMetrics)
async def get_processing_metrics(
    current_user: dict = Depends(get_current_user_hardcoded),
    days: int = 7,
    db: AsyncSession = Depends(get_db),
):
    """
    Get comprehensive processing metrics for monitoring dashboard.

    Returns aggregated metrics including:
    - Source diversity (sources fetched per category)
    - Discovery run statistics (completed, failed, cards generated)
    - Research task statistics (by status, avg processing time)
    - Classification accuracy metrics
    - Card generation summary

    Args:
        days: Number of days to look back for metrics (default: 7)

    Returns:
        ProcessingMetrics object with all aggregated metrics
    """
    # Calculate time range
    period_end = datetime.now(timezone.utc)
    period_start = period_end - timedelta(days=days)

    # -------------------------------------------------------------------------
    # Discovery Run Metrics
    # -------------------------------------------------------------------------
    try:
        dr_result = await db.execute(
            select(DiscoveryRun).where(DiscoveryRun.started_at >= period_start)
        )
        discovery_runs_list = list(dr_result.scalars().all())
    except Exception as e:
        logger.warning(f"Failed to fetch discovery runs: {e}")
        discovery_runs_list = []

    completed_runs = [r for r in discovery_runs_list if r.status == "completed"]
    failed_runs = [r for r in discovery_runs_list if r.status == "failed"]

    total_cards_created = sum((r.cards_created or 0) for r in discovery_runs_list)
    total_cards_enriched = sum((r.cards_enriched or 0) for r in discovery_runs_list)
    total_sources = sum((r.sources_found or 0) for r in discovery_runs_list)

    avg_cards_per_run = (
        total_cards_created / len(completed_runs) if completed_runs else 0.0
    )
    avg_sources_per_run = (
        total_sources / len(discovery_runs_list) if discovery_runs_list else 0.0
    )

    discovery_metrics = DiscoveryRunMetrics(
        total_runs=len(discovery_runs_list),
        completed_runs=len(completed_runs),
        failed_runs=len(failed_runs),
        avg_cards_per_run=round(avg_cards_per_run, 2),
        avg_sources_per_run=round(avg_sources_per_run, 2),
        total_cards_created=total_cards_created,
        total_cards_enriched=total_cards_enriched,
    )

    # Extract source category metrics from discovery run summary_report
    sources_by_category: Dict[str, SourceCategoryMetrics] = {}
    for run in discovery_runs_list:
        report = run.summary_report or {}
        categories_data = report.get("sources_by_category", {})
        for category, count in categories_data.items():
            if category not in sources_by_category:
                sources_by_category[category] = SourceCategoryMetrics(
                    category=category,
                    sources_fetched=0,
                    articles_processed=0,
                    cards_generated=0,
                    errors=0,
                )
            sources_by_category[category].sources_fetched += (
                count if isinstance(count, int) else 0
            )

    # -------------------------------------------------------------------------
    # Research Task Metrics
    # -------------------------------------------------------------------------
    try:
        rt_result = await db.execute(
            select(ResearchTask).where(ResearchTask.created_at >= period_start)
        )
        research_tasks_list = list(rt_result.scalars().all())
    except Exception as e:
        logger.warning(f"Failed to fetch research tasks: {e}")
        research_tasks_list = []

    completed_tasks = [t for t in research_tasks_list if t.status == "completed"]
    failed_tasks = [t for t in research_tasks_list if t.status == "failed"]
    queued_tasks = [t for t in research_tasks_list if t.status == "queued"]
    processing_tasks = [t for t in research_tasks_list if t.status == "processing"]

    # Calculate average processing time for completed tasks
    processing_times = []
    for task in completed_tasks:
        started = task.started_at
        completed = task.completed_at
        if started and completed:
            try:
                processing_times.append((completed - started).total_seconds())
            except (ValueError, TypeError):
                pass

    avg_processing_time = (
        sum(processing_times) / len(processing_times) if processing_times else None
    )

    research_metrics = ResearchTaskMetrics(
        total_tasks=len(research_tasks_list),
        completed_tasks=len(completed_tasks),
        failed_tasks=len(failed_tasks),
        queued_tasks=len(queued_tasks),
        processing_tasks=len(processing_tasks),
        avg_processing_time_seconds=(
            round(avg_processing_time, 2) if avg_processing_time else None
        ),
    )

    # -------------------------------------------------------------------------
    # Classification Accuracy Metrics
    # -------------------------------------------------------------------------
    try:
        cv_result = await db.execute(
            select(ClassificationValidation).where(
                ClassificationValidation.is_correct.is_not(None)
            )
        )
        validations_list = list(cv_result.scalars().all())
    except Exception as e:
        logger.warning(f"Failed to fetch classification validations: {e}")
        validations_list = []

    total_validations = len(validations_list)
    correct_count = sum(bool(v.is_correct) for v in validations_list)
    accuracy = (
        (correct_count / total_validations * 100) if total_validations > 0 else None
    )

    classification_metrics = ClassificationMetrics(
        total_validations=total_validations,
        correct_count=correct_count,
        accuracy_percentage=round(accuracy, 2) if accuracy else None,
        target_accuracy=85.0,
        meets_target=accuracy >= 85.0 if accuracy else False,
    )

    # -------------------------------------------------------------------------
    # Card Generation Summary
    # -------------------------------------------------------------------------
    try:
        cards_result = await db.execute(
            select(Card).where(Card.created_at >= period_start)
        )
        cards_list = list(cards_result.scalars().all())
    except Exception as e:
        logger.warning(f"Failed to fetch cards: {e}")
        cards_list = []

    cards_generated = len(cards_list)

    # Count cards with all 4 scoring dimensions
    cards_with_all_scores = sum(
        bool(
            c.impact_score is not None
            and c.velocity_score is not None
            and c.novelty_score is not None
            and c.risk_score is not None
        )
        for c in cards_list
    )

    # -------------------------------------------------------------------------
    # Error Summary
    # -------------------------------------------------------------------------
    total_errors = len(failed_runs) + len(failed_tasks)
    total_operations = len(discovery_runs_list) + len(research_tasks_list)
    error_rate = (
        (total_errors / total_operations * 100) if total_operations > 0 else None
    )

    # -------------------------------------------------------------------------
    # Build Response
    # -------------------------------------------------------------------------
    return ProcessingMetrics(
        period_start=period_start,
        period_end=period_end,
        period_days=days,
        sources_by_category=list(sources_by_category.values()),
        total_source_categories=len(sources_by_category),
        discovery_runs=discovery_metrics,
        research_tasks=research_metrics,
        classification=classification_metrics,
        cards_generated_in_period=cards_generated,
        cards_with_all_scores=cards_with_all_scores,
        total_errors=total_errors,
        error_rate_percentage=round(error_rate, 2) if error_rate else None,
    )


@router.get("/analytics/pillar-coverage", response_model=PillarCoverageResponse)
async def get_pillar_coverage(
    current_user: dict = Depends(get_current_user_hardcoded),
    start_date: Optional[str] = Query(
        None, description="Start date filter (ISO format)"
    ),
    end_date: Optional[str] = Query(None, description="End date filter (ISO format)"),
    stage_id: Optional[str] = Query(None, description="Filter by maturity stage"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get activity distribution across strategic pillars.

    Returns counts and percentages for all 6 strategic pillars (CH, EW, HG, HH, MC, PS),
    showing how cards are distributed across the organization's strategic focus areas.

    Args:
        start_date: Optional start date filter (ISO format)
        end_date: Optional end date filter (ISO format)
        stage_id: Optional maturity stage filter

    Returns:
        PillarCoverageResponse with pillar distribution data
    """
    try:
        # Build query for active cards with velocity_score for avg calculation
        stmt = select(Card.pillar_id, Card.velocity_score).where(
            Card.status == "active"
        )

        # Apply date filters if provided
        if start_date:
            stmt = stmt.where(Card.created_at >= start_date)
        if end_date:
            stmt = stmt.where(Card.created_at <= end_date)

        # Apply stage filter if provided
        if stage_id:
            stmt = stmt.where(Card.stage_id == stage_id)

        result = await db.execute(stmt)
        cards_data = result.all()

        # Count cards per pillar and sum velocity scores
        pillar_counts: Dict[str, int] = {}
        pillar_velocity_sums: Dict[str, float] = {}
        for pillar_code in ANALYTICS_PILLAR_DEFINITIONS.keys():
            pillar_counts[pillar_code] = 0
            pillar_velocity_sums[pillar_code] = 0.0

        # Also count cards with null/unknown pillar
        unassigned_count = 0
        for row in cards_data:
            pillar_id = row[0]
            velocity = row[1]
            if pillar_id and pillar_id in ANALYTICS_PILLAR_DEFINITIONS:
                pillar_counts[pillar_id] += 1
                if velocity is not None:
                    pillar_velocity_sums[pillar_id] += float(velocity)
            else:
                unassigned_count += 1

        total_cards = len(cards_data)

        # Build response data with percentages and average velocity
        coverage_data = []
        for pillar_code, pillar_name in ANALYTICS_PILLAR_DEFINITIONS.items():
            count = pillar_counts[pillar_code]
            percentage = (count / total_cards * 100) if total_cards > 0 else 0.0
            avg_velocity = (
                pillar_velocity_sums[pillar_code] / count if count > 0 else None
            )
            coverage_data.append(
                PillarCoverageItem(
                    pillar_code=pillar_code,
                    pillar_name=pillar_name,
                    count=count,
                    percentage=round(percentage, 2),
                    avg_velocity=(
                        round(avg_velocity, 2) if avg_velocity is not None else None
                    ),
                )
            )

        # Sort by count descending for better visualization
        coverage_data.sort(key=lambda x: x.count, reverse=True)

        logger.info(
            f"Pillar coverage: {total_cards} cards analyzed, "
            f"{unassigned_count} unassigned"
        )

        return PillarCoverageResponse(
            data=coverage_data,
            total_cards=total_cards,
            period_start=start_date,
            period_end=end_date,
        )

    except Exception as e:
        logger.error(f"Failed to get pillar coverage: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("pillar coverage retrieval", e),
        ) from e


@router.get("/analytics/insights", response_model=InsightsResponse)
async def get_analytics_insights(
    pillar_id: Optional[str] = Query(
        None, pattern=r"^[A-Z]{2}$", description="Filter by pillar code"
    ),
    limit: int = Query(5, ge=1, le=10, description="Number of insights to generate"),
    force_refresh: bool = Query(
        False, description="Force regeneration, bypassing cache"
    ),
    current_user: dict = Depends(get_current_user_hardcoded),
    db: AsyncSession = Depends(get_db),
):
    """
    Get AI-generated strategic insights for top emerging trends.

    Returns insights for the highest-scoring active cards, optionally filtered by pillar.
    Uses OpenAI to generate strategic insights based on trend data.

    Implements 24-hour caching to avoid redundant API calls:
    - Cache key: pillar_id + limit + date
    - Cache invalidated: when top card scores change significantly
    - Force refresh: use force_refresh=true to bypass cache

    If AI service is unavailable, returns an error message with empty insights list.
    """
    import json

    try:
        # -------------------------------------------------------------------------
        # Step 1: Fetch top cards (needed for both cache check and generation)
        # -------------------------------------------------------------------------
        stmt = select(Card).where(Card.status == "active")

        if pillar_id:
            stmt = stmt.where(Card.pillar_id == pillar_id)

        stmt = stmt.order_by(Card.velocity_score.desc().nullslast()).limit(limit * 2)

        result = await db.execute(stmt)
        card_rows = result.scalars().all()

        if not card_rows:
            return InsightsResponse(
                insights=[],
                generated_at=datetime.now(timezone.utc),
                ai_available=True,
                period_analyzed="No active cards found",
            )

        # Convert to dict-like for scoring
        cards_with_scores = []
        for card in card_rows:
            velocity = (
                float(card.velocity_score) if card.velocity_score is not None else 0
            )
            impact = card.impact_score or 0
            relevance = card.relevance_score or 0
            novelty = card.novelty_score or 0
            combined_score = (velocity + impact + relevance + novelty) / 4
            cards_with_scores.append(
                {
                    "id": str(card.id),
                    "name": card.name,
                    "slug": card.slug,
                    "summary": card.summary,
                    "pillar_id": card.pillar_id,
                    "horizon": card.horizon,
                    "velocity_score": velocity,
                    "impact_score": impact,
                    "relevance_score": relevance,
                    "novelty_score": novelty,
                    "combined_score": combined_score,
                }
            )

        cards_with_scores.sort(key=lambda x: x["combined_score"], reverse=True)
        top_cards = cards_with_scores[:limit]

        if not top_cards:
            return InsightsResponse(
                insights=[], generated_at=datetime.now(timezone.utc), ai_available=True
            )

        # Compute hash for cache validation
        current_hash = _compute_card_data_hash(top_cards)
        top_card_ids = [c["id"] for c in top_cards]

        # -------------------------------------------------------------------------
        # Step 2: Check cache (unless force_refresh)
        # -------------------------------------------------------------------------
        if not force_refresh:
            try:
                cache_stmt = (
                    select(CachedInsight)
                    .where(
                        CachedInsight.pillar_filter == pillar_id,
                        CachedInsight.insight_limit == limit,
                        CachedInsight.cache_date == date_type.today(),
                        CachedInsight.expires_at > datetime.now(timezone.utc),
                    )
                    .limit(1)
                )

                cache_result = await db.execute(cache_stmt)
                cached = cache_result.scalar_one_or_none()

                if cached and cached.card_data_hash == current_hash:
                    logger.info(
                        f"Serving cached insights for pillar={pillar_id}, limit={limit}"
                    )
                    cached_json = cached.insights_json

                    # Reconstruct response from cached JSON
                    cached_insights = [
                        InsightItem(**item) for item in cached_json.get("insights", [])
                    ]
                    generated_at = cached.generated_at
                    return InsightsResponse(
                        insights=cached_insights,
                        generated_at=generated_at,
                        ai_available=cached_json.get("ai_available", True),
                        period_analyzed=cached_json.get("period_analyzed"),
                        fallback_message=cached_json.get("fallback_message"),
                    )
                elif cached:
                    logger.info("Cache invalidated - card data changed")
            except Exception as cache_err:
                # Cache check failed - proceed to generate
                logger.warning(f"Cache lookup failed: {cache_err}")

        # -------------------------------------------------------------------------
        # Step 3: Generate new insights via AI
        # -------------------------------------------------------------------------
        start_time = datetime.now(timezone.utc)

        trends_data = "\n".join(
            [
                f"- {card['name']}: {card.get('summary', 'No summary available')[:200]} "
                f"(Pillar: {card.get('pillar_id', 'N/A')}, Horizon: {card.get('horizon', 'N/A')}, "
                f"Score: {card['combined_score']:.1f})"
                for card in top_cards
            ]
        )

        ai_available = True
        fallback_message = None
        insights = []

        try:
            prompt = INSIGHTS_GENERATION_PROMPT.format(trends_data=trends_data)

            ai_response = await asyncio.to_thread(
                openai_client.chat.completions.create,
                model=get_chat_mini_deployment(),
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=1000,
                timeout=30,
            )

            ai_result = json.loads(ai_response.choices[0].message.content)

            for i, insight_data in enumerate(ai_result.get("insights", [])):
                if i < len(top_cards):
                    card = top_cards[i]
                    insights.append(
                        InsightItem(
                            trend_name=insight_data.get("trend_name", card["name"]),
                            score=card["combined_score"],
                            insight=insight_data.get("insight", ""),
                            pillar_id=card.get("pillar_id"),
                            card_id=card.get("id"),
                            card_slug=card.get("slug"),
                            velocity_score=card.get("velocity_score"),
                        )
                    )

        except Exception as ai_error:
            logger.warning(f"AI insights generation failed: {str(ai_error)}")
            ai_available = False
            fallback_message = (
                "AI insights temporarily unavailable. Showing trend summaries instead."
            )

            insights = [
                InsightItem(
                    trend_name=card["name"],
                    score=card["combined_score"],
                    insight=(
                        card.get("summary", "No summary available")[:300]
                        if card.get("summary")
                        else "Strategic analysis pending."
                    ),
                    pillar_id=card.get("pillar_id"),
                    card_id=card.get("id"),
                    card_slug=card.get("slug"),
                    velocity_score=card.get("velocity_score"),
                )
                for card in top_cards
            ]

        generation_time_ms = int(
            (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        )
        generated_at = datetime.now(timezone.utc)
        period_analyzed = f"Top {len(top_cards)} trending cards" + (
            f" in {pillar_id}" if pillar_id else ""
        )

        # -------------------------------------------------------------------------
        # Step 4: Store in cache
        # -------------------------------------------------------------------------
        try:
            cache_json = {
                "insights": [i.dict() for i in insights],
                "ai_available": ai_available,
                "period_analyzed": period_analyzed,
                "fallback_message": fallback_message,
            }

            # Check if cache entry exists for upsert
            existing_cache_result = await db.execute(
                select(CachedInsight).where(
                    CachedInsight.pillar_filter == pillar_id,
                    CachedInsight.insight_limit == limit,
                    CachedInsight.cache_date == date_type.today(),
                )
            )
            existing_cache = existing_cache_result.scalar_one_or_none()

            if existing_cache:
                existing_cache.insights_json = cache_json
                existing_cache.top_card_ids = top_card_ids
                existing_cache.card_data_hash = current_hash
                existing_cache.ai_model_used = (
                    get_chat_mini_deployment() if ai_available else None
                )
                existing_cache.generation_time_ms = generation_time_ms
                existing_cache.generated_at = generated_at
                existing_cache.expires_at = generated_at + timedelta(hours=24)
            else:
                new_cache = CachedInsight(
                    pillar_filter=pillar_id,
                    insight_limit=limit,
                    cache_date=date_type.today(),
                    insights_json=cache_json,
                    top_card_ids=top_card_ids,
                    card_data_hash=current_hash,
                    ai_model_used=(
                        get_chat_mini_deployment() if ai_available else None
                    ),
                    generation_time_ms=generation_time_ms,
                    generated_at=generated_at,
                    expires_at=generated_at + timedelta(hours=24),
                )
                db.add(new_cache)

            await db.flush()

            logger.info(
                f"Cached insights for pillar={pillar_id}, limit={limit}, took {generation_time_ms}ms"
            )
        except Exception as cache_err:
            logger.warning(f"Failed to cache insights: {cache_err}")

        return InsightsResponse(
            insights=insights,
            generated_at=generated_at,
            ai_available=ai_available,
            period_analyzed=period_analyzed,
            fallback_message=fallback_message,
        )

    except Exception as e:
        logger.error(f"Analytics insights endpoint failed: {str(e)}")
        raise HTTPException(
            status_code=500, detail=_safe_error("analytics insights", e)
        ) from e


@router.get("/analytics/velocity", response_model=VelocityResponse)
async def get_trend_velocity(
    pillar_id: Optional[str] = None,
    stage_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user_hardcoded),
    db: AsyncSession = Depends(get_db),
):
    """
    Get trend velocity analytics over time.

    Returns time-series data showing trend momentum, including:
    - Daily/weekly velocity aggregations
    - Week-over-week comparison
    - Card counts per time period

    Query parameters:
    - pillar_id: Filter by strategic pillar code (CH, EW, HG, HH, MC, PS)
    - stage_id: Filter by maturity stage ID
    - start_date: Start date in ISO format (YYYY-MM-DD)
    - end_date: End date in ISO format (YYYY-MM-DD)

    Returns:
        VelocityResponse with time-series velocity data
    """
    try:
        # Default to last 30 days if no date range specified
        if not end_date:
            end_dt = datetime.now(timezone.utc)
            end_date = end_dt.strftime("%Y-%m-%d")
        else:
            end_dt = datetime.fromisoformat(end_date)

        if not start_date:
            start_dt = end_dt - timedelta(days=30)
            start_date = start_dt.strftime("%Y-%m-%d")
        else:
            start_dt = datetime.fromisoformat(start_date)

        # Validate date range
        if start_dt > end_dt:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_date must be before or equal to end_date",
            )

        # Build query for cards
        stmt = select(
            Card.id,
            Card.velocity_score,
            Card.created_at,
            Card.updated_at,
            Card.pillar_id,
            Card.stage_id,
        ).where(Card.status == "active")

        # Apply filters
        if pillar_id:
            if pillar_id not in ANALYTICS_PILLAR_DEFINITIONS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid pillar_id. Must be one of: {', '.join(ANALYTICS_PILLAR_DEFINITIONS.keys())}",
                )
            stmt = stmt.where(Card.pillar_id == pillar_id)

        if stage_id:
            stmt = stmt.where(Card.stage_id == stage_id)

        # Filter by date range on created_at
        stmt = stmt.where(Card.created_at >= f"{start_date}T00:00:00")
        stmt = stmt.where(Card.created_at <= f"{end_date}T23:59:59")

        stmt = stmt.order_by(Card.created_at.asc())

        result = await db.execute(stmt)
        cards = result.all()
        total_cards = len(cards)

        # Aggregate velocity data by date
        daily_data = defaultdict(lambda: {"velocity_sum": 0, "count": 0, "scores": []})

        for row in cards:
            created_at = row[2]  # Card.created_at
            if created_at:
                date_str = created_at.strftime("%Y-%m-%d")
                velocity = row[1]  # Card.velocity_score
                if velocity is not None:
                    vel_float = float(velocity)
                    daily_data[date_str]["velocity_sum"] += vel_float
                    daily_data[date_str]["scores"].append(vel_float)
                daily_data[date_str]["count"] += 1

        # Convert to VelocityDataPoint list
        velocity_data = []
        for date_str in sorted(daily_data.keys()):
            day_info = daily_data[date_str]
            avg_velocity = None
            if day_info["scores"]:
                avg_velocity = round(
                    sum(day_info["scores"]) / len(day_info["scores"]), 2
                )

            velocity_data.append(
                VelocityDataPoint(
                    date=date_str,
                    velocity=day_info["velocity_sum"],
                    count=day_info["count"],
                    avg_velocity_score=avg_velocity,
                )
            )

        # Calculate week-over-week change
        week_over_week_change = None
        if len(velocity_data) >= 14:
            # Get last 7 days and previous 7 days
            last_week_data = velocity_data[-7:]
            prev_week_data = velocity_data[-14:-7]

            last_week_total = sum(d.velocity for d in last_week_data)
            prev_week_total = sum(d.velocity for d in prev_week_data)

            if prev_week_total > 0:
                week_over_week_change = round(
                    ((last_week_total - prev_week_total) / prev_week_total) * 100, 2
                )
            elif last_week_total > 0:
                week_over_week_change = 100.0  # Infinite increase represented as 100%

        return VelocityResponse(
            data=velocity_data,
            count=len(velocity_data),
            period_start=start_date,
            period_end=end_date,
            week_over_week_change=week_over_week_change,
            total_cards_analyzed=total_cards,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch velocity analytics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("velocity analytics retrieval", e),
        ) from e


@router.get("/analytics/system-stats", response_model=SystemWideStats)
async def get_system_wide_stats(
    current_user: dict = Depends(get_current_user_hardcoded),
    db: AsyncSession = Depends(get_db),
):
    """
    Get comprehensive system-wide analytics.

    Returns aggregated statistics about:
    - Total cards, sources, and discovery activity
    - Distribution by pillar, stage, and horizon
    - Trending topics and hot categories
    - Workstream and follow engagement metrics
    """
    try:
        now = datetime.now(timezone.utc)
        one_week_ago = now - timedelta(days=7)
        one_month_ago = now - timedelta(days=30)

        # -------------------------------------------------------------------------
        # Core Card Stats
        # -------------------------------------------------------------------------
        total_cards_result = await db.execute(select(func.count()).select_from(Card))
        total_cards = total_cards_result.scalar() or 0

        active_cards_result = await db.execute(
            select(func.count()).select_from(Card).where(Card.status == "active")
        )
        active_cards = active_cards_result.scalar() or 0

        cards_week_result = await db.execute(
            select(func.count())
            .select_from(Card)
            .where(Card.created_at >= one_week_ago)
        )
        cards_this_week = cards_week_result.scalar() or 0

        cards_month_result = await db.execute(
            select(func.count())
            .select_from(Card)
            .where(Card.created_at >= one_month_ago)
        )
        cards_this_month = cards_month_result.scalar() or 0

        # -------------------------------------------------------------------------
        # Cards by Pillar (active cards with velocity)
        # -------------------------------------------------------------------------
        pillar_result = await db.execute(
            select(Card.pillar_id, Card.velocity_score).where(Card.status == "active")
        )
        pillar_data = pillar_result.all()

        pillar_counts = Counter()
        pillar_velocity: dict = {}
        for row in pillar_data:
            p = row[0]
            if p:
                pillar_counts[p] += 1
                if p not in pillar_velocity:
                    pillar_velocity[p] = []
                if row[1] is not None:
                    pillar_velocity[p].append(float(row[1]))

        cards_by_pillar = []
        for code, name in ANALYTICS_PILLAR_DEFINITIONS.items():
            count = pillar_counts.get(code, 0)
            pct = (count / active_cards * 100) if active_cards > 0 else 0
            avg_vel = None
            if pillar_velocity.get(code):
                avg_vel = round(
                    sum(pillar_velocity[code]) / len(pillar_velocity[code]), 1
                )
            cards_by_pillar.append(
                PillarCoverageItem(
                    pillar_code=code,
                    pillar_name=name,
                    count=count,
                    percentage=round(pct, 1),
                    avg_velocity=avg_vel,
                )
            )

        # -------------------------------------------------------------------------
        # Cards by Stage
        # -------------------------------------------------------------------------
        stage_result = await db.execute(
            select(Card.stage_id).where(Card.status == "active")
        )
        stage_data = stage_result.all()

        stage_counts = Counter()
        for row in stage_data:
            s = row[0]
            if s:
                # Normalize stage_id - extract number from formats like "4_proof", "5_implementing"
                stage_str = str(s)
                stage_num = (
                    stage_str.split("_")[0]
                    if "_" in stage_str
                    else stage_str.replace("Stage ", "").strip()
                )
                stage_counts[stage_num] += 1

        cards_by_stage = []
        for stage_id_key, stage_name in STAGE_NAMES.items():
            count = stage_counts.get(stage_id_key, 0)
            pct = (count / active_cards * 100) if active_cards > 0 else 0
            cards_by_stage.append(
                StageDistribution(
                    stage_id=stage_id_key,
                    stage_name=stage_name,
                    count=count,
                    percentage=round(pct, 1),
                )
            )

        # -------------------------------------------------------------------------
        # Cards by Horizon
        # -------------------------------------------------------------------------
        horizon_result = await db.execute(
            select(Card.horizon).where(Card.status == "active")
        )
        horizon_data = horizon_result.all()

        horizon_counts = Counter()
        for row in horizon_data:
            h = row[0]
            if h:
                horizon_counts[h] += 1

        cards_by_horizon = []
        for horizon, label in HORIZON_LABELS.items():
            count = horizon_counts.get(horizon, 0)
            pct = (count / active_cards * 100) if active_cards > 0 else 0
            cards_by_horizon.append(
                HorizonDistribution(
                    horizon=horizon, label=label, count=count, percentage=round(pct, 1)
                )
            )

        # -------------------------------------------------------------------------
        # Trending Pillars (based on recent card creation)
        # -------------------------------------------------------------------------
        recent_pillar_result = await db.execute(
            select(Card.pillar_id, Card.velocity_score).where(
                Card.created_at >= one_week_ago, Card.status == "active"
            )
        )
        recent_pillar_data = recent_pillar_result.all()

        recent_pillar_counts = Counter()
        recent_pillar_velocity: dict = {}
        for row in recent_pillar_data:
            p = row[0]
            if p:
                recent_pillar_counts[p] += 1
                if p not in recent_pillar_velocity:
                    recent_pillar_velocity[p] = []
                if row[1] is not None:
                    recent_pillar_velocity[p].append(float(row[1]))

        trending_pillars = []
        for code, count in recent_pillar_counts.most_common(6):
            name = ANALYTICS_PILLAR_DEFINITIONS.get(code, code)
            avg_vel = None
            if recent_pillar_velocity.get(code):
                avg_vel = round(
                    sum(recent_pillar_velocity[code])
                    / len(recent_pillar_velocity[code]),
                    1,
                )
            # Determine trend by comparing to historical average
            historical_count = pillar_counts.get(code, 0)
            weekly_avg = (
                historical_count / 4 if historical_count > 0 else 0
            )  # Rough 4-week avg
            trend = "stable"
            if count > weekly_avg * 1.5:
                trend = "up"
            elif count < weekly_avg * 0.5:
                trend = "down"
            trending_pillars.append(
                TrendingTopic(name=name, count=count, trend=trend, velocity_avg=avg_vel)
            )

        # -------------------------------------------------------------------------
        # Hot Topics (high velocity cards)
        # -------------------------------------------------------------------------
        hot_cards_result = await db.execute(
            select(Card.name, Card.velocity_score)
            .where(Card.status == "active", Card.velocity_score >= 70)
            .order_by(Card.velocity_score.desc())
            .limit(5)
        )
        hot_cards_data = hot_cards_result.all()

        hot_topics = [
            TrendingTopic(
                name=row[0] or "Unknown",
                count=1,
                trend="up",
                velocity_avg=float(row[1]) if row[1] is not None else None,
            )
            for row in hot_cards_data
        ]

        # -------------------------------------------------------------------------
        # Source Statistics
        # -------------------------------------------------------------------------
        try:
            total_sources_result = await db.execute(
                select(func.count()).select_from(Source)
            )
            total_sources = total_sources_result.scalar() or 0

            sources_data_result = await db.execute(
                select(Source.source_type, Source.created_at).limit(10000)
            )
            sources_data = sources_data_result.all()

            # Sources this week
            sources_week = sum(
                bool(row[1] and row[1] > one_week_ago) for row in sources_data
            )

            # Sources by type
            source_types = Counter()
            for row in sources_data:
                st = row[0] or "unknown"
                source_types[st] += 1

            source_stats = SourceStats(
                total_sources=total_sources,
                sources_this_week=sources_week,
                sources_by_type=dict(source_types),
            )
        except Exception as e:
            logger.warning(f"Could not fetch source stats: {e}")
            source_stats = SourceStats()

        # -------------------------------------------------------------------------
        # Discovery Statistics
        # -------------------------------------------------------------------------
        try:
            discovery_data_result = await db.execute(select(DiscoveryRun).limit(1000))
            discovery_data = list(discovery_data_result.scalars().all())

            total_runs = len(discovery_data)
            completed_runs_list = [r for r in discovery_data if r.status == "completed"]
            runs_week = sum(
                bool(r.started_at and r.started_at > one_week_ago)
                for r in discovery_data
            )

            total_discovered = sum((r.cards_created or 0) for r in completed_runs_list)
            avg_per_run = (
                total_discovered / len(completed_runs_list)
                if completed_runs_list
                else 0
            )

            try:
                total_searches_result = await db.execute(
                    select(func.count()).select_from(SearchHistory)
                )
                total_searches = total_searches_result.scalar() or 0

                search_data_result = await db.execute(
                    select(SearchHistory.executed_at).limit(1000)
                )
                search_data = search_data_result.all()
                searches_week = sum(
                    bool(row[0] and row[0] > one_week_ago) for row in search_data
                )
            except Exception:
                total_searches = 0
                searches_week = 0

            discovery_stats = DiscoveryStats(
                total_discovery_runs=total_runs,
                runs_this_week=runs_week,
                total_searches=total_searches,
                searches_this_week=searches_week,
                cards_discovered=total_discovered,
                avg_cards_per_run=round(avg_per_run, 1),
            )
        except Exception as e:
            logger.warning(f"Could not fetch discovery stats: {e}")
            discovery_stats = DiscoveryStats()

        # -------------------------------------------------------------------------
        # Workstream Engagement
        # -------------------------------------------------------------------------
        try:
            total_ws_result = await db.execute(
                select(func.count()).select_from(Workstream)
            )
            total_workstreams = total_ws_result.scalar() or 0

            ws_data_result = await db.execute(select(Workstream.updated_at))
            ws_data = ws_data_result.all()

            # Active workstreams (updated in last 30 days)
            active_workstreams = sum(
                bool(row[0] and row[0] > one_month_ago) for row in ws_data
            )

            ws_cards_result = await db.execute(select(WorkstreamCard.card_id))
            ws_cards_data = ws_cards_result.all()
            unique_cards_in_ws = len({row[0] for row in ws_cards_data if row[0]})

            avg_cards_per_ws = (
                len(ws_cards_data) / total_workstreams if total_workstreams > 0 else 0
            )

            workstream_engagement = WorkstreamEngagement(
                total_workstreams=total_workstreams,
                active_workstreams=active_workstreams,
                unique_cards_in_workstreams=unique_cards_in_ws,
                avg_cards_per_workstream=round(avg_cards_per_ws, 1),
            )
        except Exception as e:
            logger.warning(f"Could not fetch workstream stats: {e}")
            workstream_engagement = WorkstreamEngagement()

        # -------------------------------------------------------------------------
        # Follow Statistics
        # -------------------------------------------------------------------------
        try:
            follows_result = await db.execute(
                select(CardFollow.card_id, CardFollow.user_id)
            )
            follows_data = follows_result.all()

            total_follows = len(follows_data)
            unique_cards_followed = len({row[0] for row in follows_data if row[0]})
            unique_users_following = len({row[1] for row in follows_data if row[1]})

            # Most followed cards
            card_follow_counts = Counter(row[0] for row in follows_data if row[0])
            top_followed = card_follow_counts.most_common(5)

            # Get card names for top followed
            most_followed_cards = []
            if top_followed:
                top_card_ids = [c[0] for c in top_followed]
                cards_info_result = await db.execute(
                    select(Card.id, Card.name, Card.slug).where(
                        Card.id.in_(top_card_ids)
                    )
                )
                cards_info = cards_info_result.all()
                cards_map = {
                    row[0]: {"name": row[1], "slug": row[2]} for row in cards_info
                }

                for card_id, count in top_followed:
                    card_info = cards_map.get(
                        card_id, {"name": "Unknown", "slug": None}
                    )
                    most_followed_cards.append(
                        {
                            "card_id": (
                                str(card_id)
                                if isinstance(card_id, uuid.UUID)
                                else card_id
                            ),
                            "card_slug": card_info.get("slug"),
                            "card_name": card_info.get("name", "Unknown"),
                            "follower_count": count,
                        }
                    )

            follow_stats = FollowStats(
                total_follows=total_follows,
                unique_cards_followed=unique_cards_followed,
                unique_users_following=unique_users_following,
                most_followed_cards=most_followed_cards,
            )
        except Exception as e:
            logger.warning(f"Could not fetch follow stats: {e}")
            follow_stats = FollowStats()

        # -------------------------------------------------------------------------
        # Build Response
        # -------------------------------------------------------------------------

        return SystemWideStats(
            total_cards=total_cards,
            active_cards=active_cards,
            cards_this_week=cards_this_week,
            cards_this_month=cards_this_month,
            cards_by_pillar=cards_by_pillar,
            cards_by_stage=cards_by_stage,
            cards_by_horizon=cards_by_horizon,
            trending_pillars=trending_pillars,
            hot_topics=hot_topics,
            source_stats=source_stats,
            discovery_stats=discovery_stats,
            workstream_engagement=workstream_engagement,
            follow_stats=follow_stats,
            generated_at=now,
        )

    except Exception as e:
        logger.error(f"Failed to fetch system-wide stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("system-wide stats retrieval", e),
        ) from e


@router.get("/analytics/personal-stats", response_model=PersonalStats)
async def get_personal_stats(
    current_user: dict = Depends(get_current_user_hardcoded),
    db: AsyncSession = Depends(get_db),
):
    """
    Get personal analytics for the current user.

    Returns:
    - Cards the user is following
    - Comparison to community engagement
    - Pillar affinity analysis
    - Popular cards the user isn't following (social discovery)
    """
    try:
        user_id = current_user["id"]
        now = datetime.now(timezone.utc)
        one_week_ago = now - timedelta(days=7)

        # -------------------------------------------------------------------------
        # User's Follows -- fetch follows and join card data
        # -------------------------------------------------------------------------
        user_follows_result = await db.execute(
            select(CardFollow, Card)
            .outerjoin(Card, CardFollow.card_id == Card.id)
            .where(CardFollow.user_id == user_id)
        )
        user_follows_rows = user_follows_result.all()

        # All follows (for community stats)
        all_follows_result = await db.execute(
            select(CardFollow.card_id, CardFollow.user_id, CardFollow.created_at)
        )
        all_follows_data = all_follows_result.all()

        # Build follower counts from the all_follows query
        card_follower_counts = Counter(row[0] for row in all_follows_data if row[0])

        user_card_ids = set()
        following = []
        for follow, card in user_follows_rows:
            if not card:
                continue
            card_id = card.id
            user_card_ids.add(card_id)

            followed_at = follow.created_at or now

            following.append(
                UserFollowItem(
                    card_id=str(card_id),
                    card_slug=card.slug,
                    card_name=card.name or "Unknown",
                    pillar_id=card.pillar_id,
                    horizon=card.horizon,
                    velocity_score=(
                        float(card.velocity_score)
                        if card.velocity_score is not None
                        else None
                    ),
                    followed_at=followed_at,
                    priority=follow.priority or "medium",
                    follower_count=card_follower_counts.get(card_id, 1),
                )
            )

        total_following = len(following)

        # -------------------------------------------------------------------------
        # Engagement Comparison
        # -------------------------------------------------------------------------
        all_users_result = await db.execute(select(User.id))
        all_users = all_users_result.all()
        total_users = len(all_users)

        # User follow counts per user
        user_follow_counts = Counter(row[1] for row in all_follows_data if row[1])
        all_follow_counts = list(user_follow_counts.values()) or [0]
        avg_follows = (
            sum(all_follow_counts) / len(all_follow_counts) if all_follow_counts else 0
        )

        user_ws_result = await db.execute(
            select(func.count())
            .select_from(Workstream)
            .where(Workstream.user_id == user_id)
        )
        user_workstream_count = user_ws_result.scalar() or 0

        all_ws_result = await db.execute(select(Workstream.user_id))
        all_ws_data = all_ws_result.all()
        ws_per_user = Counter(row[0] for row in all_ws_data if row[0])
        all_ws_counts = list(ws_per_user.values()) or [0]
        avg_workstreams = (
            sum(all_ws_counts) / len(all_ws_counts) if all_ws_counts else 0
        )

        # Calculate percentiles
        user_id_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        user_follows_count = user_follow_counts.get(user_id_uuid, 0)
        follows_below = sum(bool(c < user_follows_count) for c in all_follow_counts)
        user_percentile_follows = (
            (follows_below / len(all_follow_counts) * 100) if all_follow_counts else 0
        )

        ws_below = sum(bool(c < user_workstream_count) for c in all_ws_counts)
        user_percentile_workstreams = (
            (ws_below / len(all_ws_counts) * 100) if all_ws_counts else 0
        )

        engagement = UserEngagementComparison(
            user_follow_count=user_follows_count,
            avg_community_follows=round(avg_follows, 1),
            user_workstream_count=user_workstream_count,
            avg_community_workstreams=round(avg_workstreams, 1),
            user_percentile_follows=round(user_percentile_follows, 1),
            user_percentile_workstreams=round(user_percentile_workstreams, 1),
        )

        # -------------------------------------------------------------------------
        # Pillar Affinity
        # -------------------------------------------------------------------------

        # User's pillar distribution
        user_pillar_counts = Counter()
        for f in following:
            if f.pillar_id:
                user_pillar_counts[f.pillar_id] += 1

        # Community pillar distribution from all follows
        community_pillar_counts = Counter()
        all_card_ids = list({row[0] for row in all_follows_data if row[0]})
        if all_card_ids:
            cards_pillar_result = await db.execute(
                select(Card.id, Card.pillar_id).where(Card.id.in_(all_card_ids))
            )
            card_pillars = {row[0]: row[1] for row in cards_pillar_result.all()}
            for row in all_follows_data:
                card_id = row[0]
                if pillar := card_pillars.get(card_id):
                    community_pillar_counts[pillar] += 1

        total_community_follows = sum(community_pillar_counts.values()) or 1

        pillar_affinity = []
        for code, name in ANALYTICS_PILLAR_DEFINITIONS.items():
            user_count = user_pillar_counts.get(code, 0)
            user_pct = (
                (user_count / total_following * 100) if total_following > 0 else 0
            )
            community_pct = (
                community_pillar_counts.get(code, 0) / total_community_follows * 100
            )
            affinity = user_pct - community_pct  # Positive = more interested than avg

            pillar_affinity.append(
                PillarAffinity(
                    pillar_code=code,
                    pillar_name=name,
                    user_count=user_count,
                    user_percentage=round(user_pct, 1),
                    community_percentage=round(community_pct, 1),
                    affinity_score=round(affinity, 1),
                )
            )

        # Sort by affinity score descending
        pillar_affinity.sort(key=lambda x: x.affinity_score, reverse=True)

        # -------------------------------------------------------------------------
        # Popular Cards Not Followed (Social Discovery)
        # -------------------------------------------------------------------------

        # Get most popular cards that user doesn't follow
        popular_card_ids = [
            cid
            for cid, count in card_follower_counts.most_common(20)
            if cid not in user_card_ids and count >= 2
        ][:10]

        popular_not_followed = []
        if popular_card_ids:
            popular_cards_result = await db.execute(
                select(Card).where(
                    Card.id.in_(popular_card_ids), Card.status == "active"
                )
            )
            popular_cards = popular_cards_result.scalars().all()

            for card in popular_cards:
                popular_not_followed.append(
                    PopularCard(
                        card_id=str(card.id),
                        card_slug=card.slug,
                        card_name=card.name or "Unknown",
                        summary=(card.summary or "")[:200],
                        pillar_id=card.pillar_id,
                        horizon=card.horizon,
                        velocity_score=(
                            float(card.velocity_score)
                            if card.velocity_score is not None
                            else None
                        ),
                        follower_count=card_follower_counts.get(card.id, 0),
                        is_followed_by_user=False,
                    )
                )

        # -------------------------------------------------------------------------
        # Recently Popular (new follows in last week)
        # -------------------------------------------------------------------------

        recent_card_counts = Counter()
        for row in all_follows_data:
            created_at = row[2]
            if created_at:
                try:
                    if created_at > one_week_ago:
                        recent_card_counts[row[0]] += 1
                except (ValueError, TypeError):
                    pass

        recently_popular_ids = [
            cid
            for cid, count in recent_card_counts.most_common(10)
            if cid not in user_card_ids and count >= 1
        ][:5]

        recently_popular = []
        if recently_popular_ids:
            recent_cards_result = await db.execute(
                select(Card).where(
                    Card.id.in_(recently_popular_ids), Card.status == "active"
                )
            )
            recent_cards = recent_cards_result.scalars().all()

            for card in recent_cards:
                recently_popular.append(
                    PopularCard(
                        card_id=str(card.id),
                        card_slug=card.slug,
                        card_name=card.name or "Unknown",
                        summary=(card.summary or "")[:200],
                        pillar_id=card.pillar_id,
                        horizon=card.horizon,
                        velocity_score=(
                            float(card.velocity_score)
                            if card.velocity_score is not None
                            else None
                        ),
                        follower_count=recent_card_counts.get(card.id, 0),
                        is_followed_by_user=False,
                    )
                )

        # -------------------------------------------------------------------------
        # User Workstream Stats
        # -------------------------------------------------------------------------

        user_ws_cards_result = await db.execute(
            select(WorkstreamCard.card_id)
            .join(Workstream, WorkstreamCard.workstream_id == Workstream.id)
            .where(Workstream.user_id == user_id)
        )
        user_ws_cards_data = user_ws_cards_result.all()
        cards_in_workstreams = len({row[0] for row in user_ws_cards_data if row[0]})

        # -------------------------------------------------------------------------
        # Build Response
        # -------------------------------------------------------------------------

        return PersonalStats(
            following=following,
            total_following=total_following,
            engagement=engagement,
            pillar_affinity=pillar_affinity,
            popular_not_followed=popular_not_followed,
            recently_popular=recently_popular,
            workstream_count=user_workstream_count,
            cards_in_workstreams=cards_in_workstreams,
            generated_at=now,
        )

    except Exception as e:
        logger.error(f"Failed to fetch personal stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("personal stats retrieval", e),
        ) from e


@router.get("/analytics/top-domains")
async def get_top_domains(
    limit: int = 20,
    category: Optional[str] = None,
    user=Depends(get_current_user_hardcoded),
    db: AsyncSession = Depends(get_db),
):
    """Top domains leaderboard by composite score."""
    try:
        stmt = select(DomainReputation).where(DomainReputation.is_active == True)
        if category:
            stmt = stmt.where(DomainReputation.category == category)
        stmt = stmt.order_by(DomainReputation.composite_score.desc()).limit(limit)

        result = await db.execute(stmt)
        rows = result.scalars().all()
        return [_row_to_dict(row, skip_cols={"notes"}) for row in rows]
    except Exception as e:
        logger.error(f"Failed to get top domains: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("top domains retrieval", e),
        ) from e
