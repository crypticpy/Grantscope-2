"""Admin, taxonomy, source rating, quality, and domain reputation router."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.deps import supabase, get_current_user, _safe_error, limiter
from app.models.source_rating import (
    SourceRatingCreate,
    SourceRatingResponse,
    SourceRatingAggregate,
)
from app.models.domain_reputation import (
    DomainReputationCreate,
    DomainReputationUpdate,
)
from app import quality_service, domain_reputation_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["admin"])


# ============================================================================
# Taxonomy endpoints
# ============================================================================


@router.get("/taxonomy")
async def get_taxonomy():
    """Get all taxonomy data"""
    pillars = supabase.table("pillars").select("*").order("name").execute()
    goals = (
        supabase.table("goals").select("*").order("pillar_id", "sort_order").execute()
    )
    anchors = supabase.table("anchors").select("*").order("name").execute()
    stages = supabase.table("stages").select("*").order("sort_order").execute()

    return {
        "pillars": pillars.data,
        "goals": goals.data,
        "anchors": anchors.data,
        "stages": stages.data,
    }


# ============================================================================
# Admin scan
# ============================================================================


@router.post("/admin/scan")
@limiter.limit("3/minute")
async def trigger_manual_scan(
    request: Request, current_user: dict = Depends(get_current_user)
):
    """
    Manually trigger content scan for all active cards.

    This triggers a quick update research task for cards that haven't been
    updated in the last 24 hours. Limited to admin users.

    Note: In production, add admin role check here.
    """
    try:
        # Get cards that need updates (not updated in last 24 hours)
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

        cards_result = (
            supabase.table("cards")
            .select("id, name")
            .eq("status", "active")
            .lt("updated_at", cutoff)
            .limit(10)
            .execute()
        )

        if not cards_result.data:
            return {
                "status": "skipped",
                "message": "No cards need updating",
                "cards_queued": 0,
            }

        # Queue update tasks for each card
        tasks_created = 0
        for card in cards_result.data:
            task_record = {
                "user_id": current_user["id"],
                "card_id": card["id"],
                "task_type": "update",
                "status": "queued",
            }
            result = supabase.table("research_tasks").insert(task_record).execute()
            if result.data:
                tasks_created += 1
                logger.info(f"Queued update task for card: {card['name']}")

        return {
            "status": "scan_triggered",
            "message": f"Queued {tasks_created} update tasks",
            "cards_queued": tasks_created,
        }

    except Exception as e:
        logger.error(f"Manual scan failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("manual scan", e),
        ) from e


# ============================================================================
# Source Rating endpoints
# ============================================================================


@router.post("/sources/{source_id}/rate", response_model=SourceRatingResponse)
async def rate_source(
    source_id: str,
    rating: SourceRatingCreate,
    user=Depends(get_current_user),
):
    """Create or update user's rating for a source. Upserts on (source_id, user_id)."""
    try:
        data = {
            "source_id": source_id,
            "user_id": user["id"],
            "quality_rating": rating.quality_rating,
            "relevance_rating": rating.relevance_rating.value,
            "comment": rating.comment,
        }
        result = (
            supabase.table("source_ratings")
            .upsert(data, on_conflict="source_id,user_id")
            .execute()
        )
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to save rating",
            )

        # Trigger SQI recalculation for parent card(s) of this source.
        # Fire-and-forget: rating is saved even if recalculation fails.
        try:
            card_links = (
                supabase.table("card_sources")
                .select("card_id")
                .eq("source_id", source_id)
                .execute()
            )
            for link in card_links.data or []:
                if card_id := link.get("card_id"):
                    try:
                        quality_service.calculate_sqi(supabase, card_id)
                    except Exception as sqi_err:
                        logger.warning(
                            f"SQI recalc failed for card {card_id} after rating: {sqi_err}"
                        )
        except Exception as lookup_err:
            logger.warning(
                f"Failed to look up parent cards for source {source_id}: {lookup_err}"
            )

        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to rate source {source_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("rating save", e),
        ) from e


@router.get("/sources/{source_id}/ratings", response_model=SourceRatingAggregate)
async def get_source_ratings(source_id: str, user=Depends(get_current_user)):
    """Get aggregated ratings for a source plus current user's rating."""
    try:
        all_ratings = (
            supabase.table("source_ratings")
            .select("*")
            .eq("source_id", source_id)
            .execute()
        )

        ratings = all_ratings.data or []
        if not ratings:
            return SourceRatingAggregate(
                source_id=source_id,
                avg_quality=0,
                total_ratings=0,
                relevance_distribution={
                    "high": 0,
                    "medium": 0,
                    "low": 0,
                    "not_relevant": 0,
                },
            )

        avg_quality = sum(r["quality_rating"] for r in ratings) / len(ratings)
        relevance_dist = {"high": 0, "medium": 0, "low": 0, "not_relevant": 0}
        for r in ratings:
            if r["relevance_rating"] in relevance_dist:
                relevance_dist[r["relevance_rating"]] += 1

        current_user_rating = next(
            (r for r in ratings if r["user_id"] == user["id"]), None
        )

        return SourceRatingAggregate(
            source_id=source_id,
            avg_quality=round(avg_quality, 2),
            total_ratings=len(ratings),
            relevance_distribution=relevance_dist,
            current_user_rating=current_user_rating,
        )
    except Exception as e:
        logger.error(f"Failed to get source ratings for {source_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("source ratings retrieval", e),
        ) from e


@router.delete("/sources/{source_id}/rate")
async def delete_source_rating(source_id: str, user=Depends(get_current_user)):
    """Remove user's rating for a source."""
    try:
        supabase.table("source_ratings").delete().eq("source_id", source_id).eq(
            "user_id", user["id"]
        ).execute()
        return {"status": "deleted"}
    except Exception as e:
        logger.error(f"Failed to delete source rating for {source_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("rating deletion", e),
        ) from e


# ============================================================================
# Quality / SQI endpoints
# ============================================================================


@router.get("/cards/{card_id}/quality")
async def get_card_quality(card_id: str, user=Depends(get_current_user)):
    """Get full SQI breakdown for a card."""
    try:
        breakdown = quality_service.get_breakdown(
            supabase, card_id
        ) or quality_service.calculate_sqi(supabase, card_id)
        return breakdown
    except Exception as e:
        logger.error(f"Failed to get quality for card {card_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("card quality retrieval", e),
        ) from e


@router.post("/cards/{card_id}/quality/recalculate")
@limiter.limit("20/minute")
async def recalculate_card_quality(
    request: Request, card_id: str, user=Depends(get_current_user)
):
    """Force SQI recalculation for a card."""
    try:
        return quality_service.calculate_sqi(supabase, card_id)
    except Exception as e:
        logger.error(f"Failed to recalculate quality for card {card_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("card quality recalculation", e),
        ) from e


@router.post("/admin/quality/recalculate-all")
async def recalculate_all_quality(user=Depends(get_current_user)):
    """Batch recalculate SQI for all cards. Admin only."""
    try:
        return quality_service.recalculate_all_cards(supabase)
    except Exception as e:
        logger.error(f"Failed to batch recalculate quality: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("batch quality recalculation", e),
        ) from e


@router.get("/cards/{card_id}/quality-score")
async def get_signal_quality_score(card_id: str):
    """Get computed signal quality score for a card."""
    from app.signal_quality import compute_signal_quality_score

    return compute_signal_quality_score(supabase, card_id)


@router.post("/cards/{card_id}/quality-score/refresh")
async def refresh_signal_quality_score(card_id: str):
    """Recompute and store the signal quality score."""
    from app.signal_quality import update_signal_quality_score

    score = update_signal_quality_score(supabase, card_id)
    return {"card_id": card_id, "signal_quality_score": score}


# ============================================================================
# Domain Reputation endpoints
# ============================================================================


@router.get("/domain-reputation")
async def list_domain_reputations(
    page: int = 1,
    page_size: int = 50,
    tier: Optional[int] = None,
    category: Optional[str] = None,
    user=Depends(get_current_user),
):
    """List all domains with reputation data, paginated and filterable."""
    try:
        query = supabase.table("domain_reputation").select("*", count="exact")
        if tier:
            query = query.eq("curated_tier", tier)
        if category:
            query = query.eq("category", category)
        query = query.order("composite_score", desc=True)
        query = query.range((page - 1) * page_size, page * page_size - 1)
        result = query.execute()
        return {
            "items": result.data,
            "total": result.count,
            "page": page,
            "page_size": page_size,
        }
    except Exception as e:
        logger.error(f"Failed to list domain reputations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("domain reputations listing", e),
        ) from e


@router.get("/domain-reputation/{domain_id}")
async def get_domain_reputation(domain_id: str, user=Depends(get_current_user)):
    """Get single domain reputation detail."""
    try:
        result = (
            supabase.table("domain_reputation")
            .select("*")
            .eq("id", domain_id)
            .single()
            .execute()
        )
        return result.data
    except Exception as e:
        logger.error(f"Failed to get domain reputation {domain_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_safe_error("domain reputation lookup", e),
        ) from e


@router.post("/admin/domain-reputation")
async def create_domain_reputation(
    body: DomainReputationCreate, user=Depends(get_current_user)
):
    """Add a new domain to the reputation system. Admin only."""
    try:
        data = body.model_dump()
        # Calculate initial composite score based on tier
        tier_scores = {1: 85, 2: 60, 3: 35}
        tier_score = tier_scores.get(data.get("curated_tier"), 20)
        data["composite_score"] = tier_score * 0.50 + data.get(
            "texas_relevance_bonus", 0
        )
        result = supabase.table("domain_reputation").insert(data).execute()
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create domain reputation",
            )
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create domain reputation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("domain reputation creation", e),
        ) from e


@router.patch("/admin/domain-reputation/{domain_id}")
async def update_domain_reputation(
    domain_id: str,
    body: DomainReputationUpdate,
    user=Depends(get_current_user),
):
    """Update a domain's tier, category, or other fields. Admin only."""
    try:
        data = body.model_dump(exclude_none=True)
        if not data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields provided for update",
            )
        result = (
            supabase.table("domain_reputation")
            .update(data)
            .eq("id", domain_id)
            .execute()
        )
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Domain reputation not found",
            )
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update domain reputation {domain_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("domain reputation update", e),
        ) from e


@router.delete("/admin/domain-reputation/{domain_id}")
async def delete_domain_reputation(domain_id: str, user=Depends(get_current_user)):
    """Remove a domain from the reputation system. Admin only."""
    try:
        supabase.table("domain_reputation").delete().eq("id", domain_id).execute()
        return {"status": "deleted"}
    except Exception as e:
        logger.error(f"Failed to delete domain reputation {domain_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("domain reputation deletion", e),
        ) from e


@router.post("/admin/domain-reputation/recalculate")
async def recalculate_domain_reputations(user=Depends(get_current_user)):
    """Recalculate all composite scores from user ratings + pipeline stats."""
    try:
        return domain_reputation_service.recalculate_all(supabase)
    except Exception as e:
        logger.error(f"Failed to recalculate domain reputations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("domain reputations recalculation", e),
        ) from e


# NOTE: top-domains endpoint lives in analytics.py to avoid route duplication.


# ============================================================================
# Velocity calculation endpoint
# ============================================================================


@router.post("/admin/velocity/calculate")
async def trigger_velocity_calculation(
    current_user: dict = Depends(get_current_user),
):
    """Trigger velocity trend calculation for all active cards. Runs in background."""
    # Admin-only endpoint
    user_role = current_user.get("role", "")
    if user_role not in ("admin", "service_role"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    from app.velocity_service import calculate_velocity_trends

    async def _run_velocity():
        try:
            result = await calculate_velocity_trends(supabase)
            logger.info("On-demand velocity calculation completed: %s", result)
        except Exception as exc:
            logger.exception("On-demand velocity calculation failed: %s", exc)

    asyncio.create_task(_run_velocity())
    return {
        "status": "started",
        "message": "Velocity calculation is running in the background.",
    }
