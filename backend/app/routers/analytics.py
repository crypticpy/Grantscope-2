"""Analytics and metrics router."""

import asyncio
import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from datetime import date as date_type
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.deps import supabase, get_current_user, _safe_error, openai_client
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

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["analytics"])

# ============================================================================
# Constants
# ============================================================================

# Pillar definitions for analytics (matches database pillars table)
ANALYTICS_PILLAR_DEFINITIONS = {
    "CH": "Community Health & Sustainability",
    "EW": "Economic & Workforce Development",
    "HG": "High-Performing Government",
    "HH": "Homelessness & Housing",
    "MC": "Mobility & Critical Infrastructure",
    "PS": "Public Safety",
}

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
INSIGHTS_GENERATION_PROMPT = """You are a strategic foresight analyst for the City of Austin municipal government.

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


# ============================================================================
# Routes
# ============================================================================


@router.get("/metrics/processing", response_model=ProcessingMetrics)
async def get_processing_metrics(
    current_user: dict = Depends(get_current_user), days: int = 7
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
    period_start_iso = period_start.isoformat()

    # -------------------------------------------------------------------------
    # Discovery Run Metrics
    # -------------------------------------------------------------------------
    discovery_runs_response = (
        supabase.table("discovery_runs")
        .select(
            "id, status, cards_created, cards_enriched, sources_found, sources_relevant, summary_report, started_at, completed_at"
        )
        .gte("started_at", period_start_iso)
        .execute()
    )

    discovery_runs_data = discovery_runs_response.data or []

    completed_runs = [r for r in discovery_runs_data if r.get("status") == "completed"]
    failed_runs = [r for r in discovery_runs_data if r.get("status") == "failed"]

    total_cards_created = sum(
        r.get("cards_created", 0) or 0 for r in discovery_runs_data
    )
    total_cards_enriched = sum(
        r.get("cards_enriched", 0) or 0 for r in discovery_runs_data
    )
    total_sources = sum(r.get("sources_found", 0) or 0 for r in discovery_runs_data)

    avg_cards_per_run = (
        total_cards_created / len(completed_runs) if completed_runs else 0.0
    )
    avg_sources_per_run = (
        total_sources / len(discovery_runs_data) if discovery_runs_data else 0.0
    )

    discovery_metrics = DiscoveryRunMetrics(
        total_runs=len(discovery_runs_data),
        completed_runs=len(completed_runs),
        failed_runs=len(failed_runs),
        avg_cards_per_run=round(avg_cards_per_run, 2),
        avg_sources_per_run=round(avg_sources_per_run, 2),
        total_cards_created=total_cards_created,
        total_cards_enriched=total_cards_enriched,
    )

    # Extract source category metrics from discovery run summary_report
    sources_by_category: Dict[str, SourceCategoryMetrics] = {}
    for run in discovery_runs_data:
        report = run.get("summary_report") or {}
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
    research_tasks_response = (
        supabase.table("research_tasks")
        .select("id, status, started_at, completed_at")
        .gte("created_at", period_start_iso)
        .execute()
    )

    research_tasks_data = research_tasks_response.data or []

    completed_tasks = [t for t in research_tasks_data if t.get("status") == "completed"]
    failed_tasks = [t for t in research_tasks_data if t.get("status") == "failed"]
    queued_tasks = [t for t in research_tasks_data if t.get("status") == "queued"]
    processing_tasks = [
        t for t in research_tasks_data if t.get("status") == "processing"
    ]

    # Calculate average processing time for completed tasks
    processing_times = []
    for task in completed_tasks:
        started = task.get("started_at")
        completed = task.get("completed_at")
        if started and completed:
            try:
                start_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(completed.replace("Z", "+00:00"))
                processing_times.append((end_dt - start_dt).total_seconds())
            except (ValueError, TypeError):
                pass

    avg_processing_time = (
        sum(processing_times) / len(processing_times) if processing_times else None
    )

    research_metrics = ResearchTaskMetrics(
        total_tasks=len(research_tasks_data),
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
    validations_response = (
        supabase.table("classification_validations")
        .select("is_correct")
        .not_.is_("is_correct", "null")
        .execute()
    )

    validations_data = validations_response.data or []
    total_validations = len(validations_data)
    correct_count = sum(bool(v.get("is_correct")) for v in validations_data)
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
    cards_response = (
        supabase.table("cards")
        .select(
            "id, impact_score, velocity_score, novelty_score, risk_score", count="exact"
        )
        .gte("created_at", period_start_iso)
        .execute()
    )

    cards_data = cards_response.data or []
    cards_generated = len(cards_data)

    # Count cards with all 4 scoring dimensions
    cards_with_all_scores = sum(
        bool(
            c.get("impact_score") is not None
            and c.get("velocity_score") is not None
            and c.get("novelty_score") is not None
            and c.get("risk_score") is not None
        )
        for c in cards_data
    )

    # -------------------------------------------------------------------------
    # Error Summary
    # -------------------------------------------------------------------------
    total_errors = len(failed_runs) + len(failed_tasks)
    total_operations = len(discovery_runs_data) + len(research_tasks_data)
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
    current_user: dict = Depends(get_current_user),
    start_date: Optional[str] = Query(
        None, description="Start date filter (ISO format)"
    ),
    end_date: Optional[str] = Query(None, description="End date filter (ISO format)"),
    stage_id: Optional[str] = Query(None, description="Filter by maturity stage"),
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
        query = (
            supabase.table("cards")
            .select("pillar_id, velocity_score")
            .eq("status", "active")
        )

        # Apply date filters if provided
        if start_date:
            query = query.gte("created_at", start_date)
        if end_date:
            query = query.lte("created_at", end_date)

        # Apply stage filter if provided
        if stage_id:
            query = query.eq("stage_id", stage_id)

        response = query.execute()
        cards_data = response.data or []

        # Count cards per pillar and sum velocity scores
        pillar_counts: Dict[str, int] = {}
        pillar_velocity_sums: Dict[str, float] = {}
        for pillar_code in ANALYTICS_PILLAR_DEFINITIONS.keys():
            pillar_counts[pillar_code] = 0
            pillar_velocity_sums[pillar_code] = 0.0

        # Also count cards with null/unknown pillar
        unassigned_count = 0
        for card in cards_data:
            pillar_id = card.get("pillar_id")
            if pillar_id and pillar_id in ANALYTICS_PILLAR_DEFINITIONS:
                pillar_counts[pillar_id] += 1
                velocity = card.get("velocity_score")
                if velocity is not None:
                    pillar_velocity_sums[pillar_id] += velocity
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
    current_user: dict = Depends(get_current_user),
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
        query = (
            supabase.table("cards")
            .select(
                "id, name, slug, summary, pillar_id, horizon, velocity_score, impact_score, relevance_score, novelty_score"
            )
            .eq("status", "active")
        )

        if pillar_id:
            query = query.eq("pillar_id", pillar_id)

        response = query.order("velocity_score", desc=True).limit(limit * 2).execute()

        if not response.data:
            return InsightsResponse(
                insights=[],
                generated_at=datetime.now(timezone.utc),
                ai_available=True,
                period_analyzed="No active cards found",
            )

        # Calculate combined scores and sort
        cards_with_scores = []
        for card in response.data:
            velocity = card.get("velocity_score") or 0
            impact = card.get("impact_score") or 0
            relevance = card.get("relevance_score") or 0
            novelty = card.get("novelty_score") or 0
            combined_score = (velocity + impact + relevance + novelty) / 4
            cards_with_scores.append({**card, "combined_score": combined_score})

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
                cache_response = (
                    supabase.table("cached_insights")
                    .select("insights_json, generated_at, card_data_hash")
                    .eq("pillar_filter", pillar_id)
                    .eq("insight_limit", limit)
                    .eq("cache_date", date_type.today().isoformat())
                    .gt("expires_at", datetime.now(timezone.utc).isoformat())
                    .limit(1)
                    .execute()
                )

                if cache_response.data:
                    cached = cache_response.data[0]
                    # Validate cache - check if underlying data changed
                    if cached.get("card_data_hash") == current_hash:
                        logger.info(
                            f"Serving cached insights for pillar={pillar_id}, limit={limit}"
                        )
                        cached_json = cached["insights_json"]

                        # Reconstruct response from cached JSON
                        cached_insights = [
                            InsightItem(**item)
                            for item in cached_json.get("insights", [])
                        ]
                        return InsightsResponse(
                            insights=cached_insights,
                            generated_at=datetime.fromisoformat(
                                cached["generated_at"].replace("Z", "+00:00")
                            ),
                            ai_available=cached_json.get("ai_available", True),
                            period_analyzed=cached_json.get("period_analyzed"),
                            fallback_message=cached_json.get("fallback_message"),
                        )
                    else:
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

            ai_response = openai_client.chat.completions.create(
                model=get_chat_mini_deployment(),
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=1000,
                timeout=30,
            )

            result = json.loads(ai_response.choices[0].message.content)

            for i, insight_data in enumerate(result.get("insights", [])):
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

            # Upsert cache entry
            supabase.table("cached_insights").upsert(
                {
                    "pillar_filter": pillar_id,
                    "insight_limit": limit,
                    "cache_date": date_type.today().isoformat(),
                    "insights_json": cache_json,
                    "top_card_ids": top_card_ids,
                    "card_data_hash": current_hash,
                    "ai_model_used": (
                        get_chat_mini_deployment() if ai_available else None
                    ),
                    "generation_time_ms": generation_time_ms,
                    "generated_at": generated_at.isoformat(),
                    "expires_at": (generated_at + timedelta(hours=24)).isoformat(),
                },
                on_conflict="pillar_filter,insight_limit,cache_date",
            ).execute()

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
    current_user: dict = Depends(get_current_user),
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
        query = (
            supabase.table("cards")
            .select("id, velocity_score, created_at, updated_at, pillar_id, stage_id")
            .eq("status", "active")
        )

        # Apply filters
        if pillar_id:
            if pillar_id not in ANALYTICS_PILLAR_DEFINITIONS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid pillar_id. Must be one of: {', '.join(ANALYTICS_PILLAR_DEFINITIONS.keys())}",
                )
            query = query.eq("pillar_id", pillar_id)

        if stage_id:
            query = query.eq("stage_id", stage_id)

        # Filter by date range on created_at
        query = query.gte("created_at", f"{start_date}T00:00:00")
        query = query.lte("created_at", f"{end_date}T23:59:59")

        response = query.order("created_at", desc=False).execute()

        cards = response.data or []
        total_cards = len(cards)

        # Aggregate velocity data by date
        daily_data = defaultdict(lambda: {"velocity_sum": 0, "count": 0, "scores": []})

        for card in cards:
            if created_at := card.get("created_at", ""):
                date_str = created_at[:10]  # YYYY-MM-DD
                velocity = card.get("velocity_score")
                if velocity is not None:
                    daily_data[date_str]["velocity_sum"] += velocity
                    daily_data[date_str]["scores"].append(velocity)
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
async def get_system_wide_stats(current_user: dict = Depends(get_current_user)):
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
        # Batch 1: All independent count & distribution queries in parallel
        # -------------------------------------------------------------------------

        (
            total_cards_resp,
            active_cards_resp,
            cards_week_resp,
            cards_month_resp,
            pillar_resp,
            stage_resp,
            horizon_resp,
            recent_pillar_resp,
            hot_cards_resp,
            sources_resp,
            discovery_resp,
            search_resp,
            ws_resp,
            ws_cards_resp,
            follows_resp,
        ) = await asyncio.gather(
            # Core card counts
            asyncio.to_thread(
                lambda: supabase.table("cards").select("id", count="exact").execute()
            ),
            asyncio.to_thread(
                lambda: supabase.table("cards")
                .select("id", count="exact")
                .eq("status", "active")
                .execute()
            ),
            asyncio.to_thread(
                lambda: supabase.table("cards")
                .select("id", count="exact")
                .gte("created_at", one_week_ago.isoformat())
                .execute()
            ),
            asyncio.to_thread(
                lambda: supabase.table("cards")
                .select("id", count="exact")
                .gte("created_at", one_month_ago.isoformat())
                .execute()
            ),
            # Distribution queries
            asyncio.to_thread(
                lambda: supabase.table("cards")
                .select("pillar_id, velocity_score")
                .eq("status", "active")
                .execute()
            ),
            asyncio.to_thread(
                lambda: supabase.table("cards")
                .select("stage_id")
                .eq("status", "active")
                .execute()
            ),
            asyncio.to_thread(
                lambda: supabase.table("cards")
                .select("horizon")
                .eq("status", "active")
                .execute()
            ),
            # Trending pillars
            asyncio.to_thread(
                lambda: supabase.table("cards")
                .select("pillar_id, velocity_score")
                .gte("created_at", one_week_ago.isoformat())
                .eq("status", "active")
                .execute()
            ),
            # Hot topics
            asyncio.to_thread(
                lambda: supabase.table("cards")
                .select("name, velocity_score")
                .eq("status", "active")
                .gte("velocity_score", 70)
                .order("velocity_score", desc=True)
                .limit(5)
                .execute()
            ),
            # Sources (bounded)
            asyncio.to_thread(
                lambda: supabase.table("sources")
                .select("id, source_type, created_at", count="exact")
                .limit(10000)
                .execute()
            ),
            # Discovery runs (bounded)
            asyncio.to_thread(
                lambda: supabase.table("discovery_runs")
                .select("id, cards_created, started_at, status")
                .limit(1000)
                .execute()
            ),
            # Search history (bounded)
            asyncio.to_thread(
                lambda: supabase.table("search_history")
                .select("id, executed_at", count="exact")
                .limit(1000)
                .execute()
            ),
            # Workstreams
            asyncio.to_thread(
                lambda: supabase.table("workstreams")
                .select("id, updated_at", count="exact")
                .execute()
            ),
            # Workstream cards
            asyncio.to_thread(
                lambda: supabase.table("workstream_cards").select("card_id").execute()
            ),
            # Follows
            asyncio.to_thread(
                lambda: supabase.table("card_follows")
                .select("card_id, user_id")
                .execute()
            ),
        )

        # -------------------------------------------------------------------------
        # Core Card Stats
        # -------------------------------------------------------------------------

        total_cards = total_cards_resp.count or 0
        active_cards = active_cards_resp.count or 0
        cards_this_week = cards_week_resp.count or 0
        cards_this_month = cards_month_resp.count or 0

        # -------------------------------------------------------------------------
        # Cards by Pillar
        # -------------------------------------------------------------------------

        pillar_data = pillar_resp.data or []

        pillar_counts = Counter()
        pillar_velocity = {}
        for card in pillar_data:
            if p := card.get("pillar_id"):
                pillar_counts[p] += 1
                if p not in pillar_velocity:
                    pillar_velocity[p] = []
                if card.get("velocity_score"):
                    pillar_velocity[p].append(card["velocity_score"])

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

        stage_data = stage_resp.data or []

        stage_counts = Counter()
        for card in stage_data:
            if s := card.get("stage_id"):
                # Normalize stage_id - extract number from formats like "4_proof", "5_implementing"
                stage_str = str(s)
                stage_num = (
                    stage_str.split("_")[0]
                    if "_" in stage_str
                    else stage_str.replace("Stage ", "").strip()
                )
                stage_counts[stage_num] += 1

        cards_by_stage = []
        for stage_id, stage_name in STAGE_NAMES.items():
            count = stage_counts.get(stage_id, 0)
            pct = (count / active_cards * 100) if active_cards > 0 else 0
            cards_by_stage.append(
                StageDistribution(
                    stage_id=stage_id,
                    stage_name=stage_name,
                    count=count,
                    percentage=round(pct, 1),
                )
            )

        # -------------------------------------------------------------------------
        # Cards by Horizon
        # -------------------------------------------------------------------------

        horizon_data = horizon_resp.data or []

        horizon_counts = Counter()
        for card in horizon_data:
            if h := card.get("horizon"):
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

        recent_pillar_data = recent_pillar_resp.data or []

        recent_pillar_counts = Counter()
        recent_pillar_velocity = {}
        for card in recent_pillar_data:
            if p := card.get("pillar_id"):
                recent_pillar_counts[p] += 1
                if p not in recent_pillar_velocity:
                    recent_pillar_velocity[p] = []
                if card.get("velocity_score"):
                    recent_pillar_velocity[p].append(card["velocity_score"])

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
        # Hot Topics (high velocity cards recently updated)
        # -------------------------------------------------------------------------

        hot_cards_data = hot_cards_resp.data or []

        hot_topics = [
            TrendingTopic(
                name=card.get("name", "Unknown"),
                count=1,
                trend="up",
                velocity_avg=card.get("velocity_score"),
            )
            for card in hot_cards_data
        ]

        # -------------------------------------------------------------------------
        # Source Statistics
        # -------------------------------------------------------------------------

        try:
            total_sources = sources_resp.count or 0
            sources_data = sources_resp.data or []

            # Sources this week
            sources_week = sum(
                bool(
                    s.get("created_at")
                    and datetime.fromisoformat(
                        s["created_at"].replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                    > one_week_ago
                )
                for s in sources_data
            )

            # Sources by type
            source_types = Counter()
            for s in sources_data:
                st = s.get("source_type") or "unknown"
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
            discovery_data = discovery_resp.data or []

            total_runs = len(discovery_data)
            completed_runs = [
                r for r in discovery_data if r.get("status") == "completed"
            ]
            runs_week = sum(
                bool(
                    r.get("started_at")
                    and datetime.fromisoformat(
                        r["started_at"].replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                    > one_week_ago
                )
                for r in discovery_data
            )

            total_discovered = sum(r.get("cards_created", 0) for r in completed_runs)
            avg_per_run = (
                total_discovered / len(completed_runs) if completed_runs else 0
            )

            try:
                total_searches = search_resp.count or 0
                search_data = search_resp.data or []
                searches_week = sum(
                    bool(
                        s.get("executed_at")
                        and datetime.fromisoformat(
                            s["executed_at"].replace("Z", "+00:00")
                        ).replace(tzinfo=None)
                        > one_week_ago
                    )
                    for s in search_data
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
            total_workstreams = ws_resp.count or 0
            ws_data = ws_resp.data or []

            # Active workstreams (updated in last 30 days)
            active_workstreams = sum(
                bool(
                    w.get("updated_at")
                    and datetime.fromisoformat(
                        w["updated_at"].replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                    > one_month_ago
                )
                for w in ws_data
            )

            ws_cards_data = ws_cards_resp.data or []
            unique_cards_in_ws = len(
                {c.get("card_id") for c in ws_cards_data if c.get("card_id")}
            )

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
            follows_data = follows_resp.data or []

            total_follows = len(follows_data)
            unique_cards_followed = len(
                {f.get("card_id") for f in follows_data if f.get("card_id")}
            )
            unique_users_following = len(
                {f.get("user_id") for f in follows_data if f.get("user_id")}
            )

            # Most followed cards
            card_follow_counts = Counter(
                f.get("card_id") for f in follows_data if f.get("card_id")
            )
            top_followed = card_follow_counts.most_common(5)

            # Get card names for top followed
            most_followed_cards = []
            if top_followed:
                top_card_ids = [c[0] for c in top_followed]
                cards_info = await asyncio.to_thread(
                    lambda: supabase.table("cards")
                    .select("id, name, slug")
                    .in_("id", top_card_ids)
                    .execute()
                )
                cards_map = {
                    c["id"]: {"name": c["name"], "slug": c.get("slug")}
                    for c in (cards_info.data or [])
                }

                for card_id, count in top_followed:
                    card_info = cards_map.get(
                        card_id, {"name": "Unknown", "slug": None}
                    )
                    most_followed_cards.append(
                        {
                            "card_id": card_id,
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
async def get_personal_stats(current_user: dict = Depends(get_current_user)):
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
        # Batch 1: All independent queries in parallel
        # -------------------------------------------------------------------------

        (
            user_follows_resp,
            all_follows_resp,
            users_resp,
            user_ws_resp,
            all_ws_resp,
            user_ws_cards_resp,
        ) = await asyncio.gather(
            # User's follows with card join
            asyncio.to_thread(
                lambda: supabase.table("card_follows")
                .select(
                    "card_id, priority, created_at, cards(id, name, slug, pillar_id, horizon, velocity_score)"
                )
                .eq("user_id", user_id)
                .execute()
            ),
            # All follows (card_id, user_id, created_at) - single fetch for
            # follower counts, engagement comparison, and recently popular
            asyncio.to_thread(
                lambda: supabase.table("card_follows")
                .select("card_id, user_id, created_at")
                .execute()
            ),
            # All users for engagement percentile
            asyncio.to_thread(lambda: supabase.table("users").select("id").execute()),
            # User's workstreams count
            asyncio.to_thread(
                lambda: supabase.table("workstreams")
                .select("id", count="exact")
                .eq("user_id", user_id)
                .execute()
            ),
            # All workstreams per user
            asyncio.to_thread(
                lambda: supabase.table("workstreams").select("user_id").execute()
            ),
            # User workstream cards
            asyncio.to_thread(
                lambda: supabase.table("workstream_cards")
                .select("card_id, workstreams!inner(user_id)")
                .eq("workstreams.user_id", user_id)
                .execute()
            ),
        )

        # -------------------------------------------------------------------------
        # User's Follows
        # -------------------------------------------------------------------------

        user_follows_data = user_follows_resp.data or []
        all_follows_data = all_follows_resp.data or []

        # Build follower counts from the single all_follows query
        card_follower_counts = Counter(
            f.get("card_id") for f in all_follows_data if f.get("card_id")
        )

        user_card_ids = set()
        following = []
        for f in user_follows_data:
            card = f.get("cards", {})
            if not card:
                continue
            card_id = card.get("id") or f.get("card_id")
            user_card_ids.add(card_id)

            followed_at = f.get("created_at")
            if followed_at:
                try:
                    followed_at = datetime.fromisoformat(
                        followed_at.replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    followed_at = now
            else:
                followed_at = now

            following.append(
                UserFollowItem(
                    card_id=card_id,
                    card_slug=card.get("slug"),
                    card_name=card.get("name", "Unknown"),
                    pillar_id=card.get("pillar_id"),
                    horizon=card.get("horizon"),
                    velocity_score=card.get("velocity_score"),
                    followed_at=followed_at,
                    priority=f.get("priority", "medium"),
                    follower_count=card_follower_counts.get(card_id, 1),
                )
            )

        total_following = len(following)

        # -------------------------------------------------------------------------
        # Engagement Comparison
        # -------------------------------------------------------------------------

        all_users = users_resp.data or []
        total_users = len(all_users)

        # User follow counts per user
        user_follow_counts = Counter(
            f.get("user_id") for f in all_follows_data if f.get("user_id")
        )
        all_follow_counts = list(user_follow_counts.values()) or [0]
        avg_follows = (
            sum(all_follow_counts) / len(all_follow_counts) if all_follow_counts else 0
        )

        user_workstream_count = user_ws_resp.count or 0

        ws_per_user = Counter(
            w.get("user_id") for w in (all_ws_resp.data or []) if w.get("user_id")
        )
        all_ws_counts = list(ws_per_user.values()) or [0]
        avg_workstreams = (
            sum(all_ws_counts) / len(all_ws_counts) if all_ws_counts else 0
        )

        # Calculate percentiles
        user_follows_count = user_follow_counts.get(user_id, 0)
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
        all_card_ids = list(
            {f.get("card_id") for f in all_follows_data if f.get("card_id")}
        )
        if all_card_ids:
            cards_pillar_resp = await asyncio.to_thread(
                lambda: supabase.table("cards")
                .select("id, pillar_id")
                .in_("id", all_card_ids)
                .execute()
            )
            card_pillars = {
                c["id"]: c.get("pillar_id") for c in (cards_pillar_resp.data or [])
            }
            for f in all_follows_data:
                card_id = f.get("card_id")
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
            popular_cards_resp = await asyncio.to_thread(
                lambda: supabase.table("cards")
                .select("id, name, slug, summary, pillar_id, horizon, velocity_score")
                .in_("id", popular_card_ids)
                .eq("status", "active")
                .execute()
            )

            for card in popular_cards_resp.data or []:
                card_id = card.get("id")
                popular_not_followed.append(
                    PopularCard(
                        card_id=card_id,
                        card_slug=card.get("slug"),
                        card_name=card.get("name", "Unknown"),
                        summary=card.get("summary", "")[:200],
                        pillar_id=card.get("pillar_id"),
                        horizon=card.get("horizon"),
                        velocity_score=card.get("velocity_score"),
                        follower_count=card_follower_counts.get(card_id, 0),
                        is_followed_by_user=False,
                    )
                )

        # -------------------------------------------------------------------------
        # Recently Popular (new follows in last week)
        # -------------------------------------------------------------------------

        # Reuse the all_follows_data already fetched (includes created_at)
        recent_card_counts = Counter()
        for f in all_follows_data:
            if created_at := f.get("created_at"):
                try:
                    dt = datetime.fromisoformat(
                        created_at.replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                    if dt > one_week_ago:
                        recent_card_counts[f.get("card_id")] += 1
                except (ValueError, TypeError):
                    pass

        recently_popular_ids = [
            cid
            for cid, count in recent_card_counts.most_common(10)
            if cid not in user_card_ids and count >= 1
        ][:5]

        recently_popular = []
        if recently_popular_ids:
            recent_cards_resp = await asyncio.to_thread(
                lambda: supabase.table("cards")
                .select("id, name, slug, summary, pillar_id, horizon, velocity_score")
                .in_("id", recently_popular_ids)
                .eq("status", "active")
                .execute()
            )

            for card in recent_cards_resp.data or []:
                card_id = card.get("id")
                recently_popular.append(
                    PopularCard(
                        card_id=card_id,
                        card_slug=card.get("slug"),
                        card_name=card.get("name", "Unknown"),
                        summary=card.get("summary", "")[:200],
                        pillar_id=card.get("pillar_id"),
                        horizon=card.get("horizon"),
                        velocity_score=card.get("velocity_score"),
                        follower_count=recent_card_counts.get(card_id, 0),
                        is_followed_by_user=False,
                    )
                )

        # -------------------------------------------------------------------------
        # User Workstream Stats
        # -------------------------------------------------------------------------

        cards_in_workstreams = len(
            {
                c.get("card_id")
                for c in (user_ws_cards_resp.data or [])
                if c.get("card_id")
            }
        )

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
    user=Depends(get_current_user),
):
    """Top domains leaderboard by composite score."""
    try:
        query = supabase.table("domain_reputation").select(
            "id,domain_pattern,organization_name,category,curated_tier,"
            "composite_score,user_quality_avg,user_rating_count,triage_pass_rate"
        )
        query = query.eq("is_active", True)
        if category:
            query = query.eq("category", category)
        query = query.order("composite_score", desc=True).limit(limit)
        result = query.execute()
        return result.data
    except Exception as e:
        logger.error(f"Failed to get top domains: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("top domains retrieval", e),
        ) from e
