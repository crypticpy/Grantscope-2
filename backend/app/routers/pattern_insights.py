"""Pattern insights router."""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.deps import supabase, get_current_user, _safe_error, openai_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["pattern_insights"])


@router.get("/pattern-insights")
async def get_pattern_insights(
    status_filter: str = Query("active", alias="status"),
    urgency: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
):
    """Get AI-detected cross-signal pattern insights."""
    try:
        query = (
            supabase.table("pattern_insights").select("*").eq("status", status_filter)
        )
        if urgency:
            query = query.eq("urgency", urgency)
        result = query.order("created_at", desc=True).limit(limit).execute()
        return result.data or []
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("fetching pattern insights", e),
        )


@router.get("/pattern-insights/{insight_id}")
async def get_pattern_insight_by_id(
    insight_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get a single pattern insight by ID, including related card details."""
    try:
        result = (
            supabase.table("pattern_insights")
            .select("*")
            .eq("id", insight_id)
            .execute()
        )
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pattern insight not found",
            )
        insight = result.data[0]

        # Fetch related cards for richer context
        related_ids = insight.get("related_card_ids", [])
        if related_ids:
            cards_result = (
                supabase.table("cards")
                .select("id, name, summary, pillar_id, stage_id, horizon")
                .in_("id", related_ids)
                .execute()
            )
            insight["related_cards"] = cards_result.data or []
        else:
            insight["related_cards"] = []

        return insight
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("fetching pattern insight", e),
        )


@router.patch("/pattern-insights/{insight_id}")
async def update_pattern_insight_status(
    insight_id: str,
    body: dict,
    current_user: dict = Depends(get_current_user),
):
    """Update a pattern insight status (e.g., dismiss or mark as acted on)."""
    allowed_statuses = {"active", "dismissed", "acted_on"}
    new_status = body.get("status")
    if new_status not in allowed_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {', '.join(allowed_statuses)}",
        )
    try:
        result = (
            supabase.table("pattern_insights")
            .update({"status": new_status})
            .eq("id", insight_id)
            .execute()
        )
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pattern insight not found",
            )
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("updating pattern insight", e),
        )


@router.post("/pattern-insights/generate")
async def generate_pattern_insights(
    current_user: dict = Depends(get_current_user),
):
    """Trigger cross-signal pattern detection. Runs in background."""
    from app.pattern_detection_service import PatternDetectionService

    async def _run_pattern_detection():
        try:
            service = PatternDetectionService(supabase, openai_client)
            result = await service.run_detection()
            logger.info("On-demand pattern detection completed: %s", result)
        except Exception as exc:
            logger.exception("On-demand pattern detection failed: %s", exc)

    asyncio.create_task(_run_pattern_detection())
    return {
        "status": "started",
        "message": "Pattern detection is running in the background.",
    }
