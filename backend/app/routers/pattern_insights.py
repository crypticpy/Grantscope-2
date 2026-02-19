"""Pattern insights router."""

import asyncio
import logging
import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import (
    get_db,
    get_current_user_hardcoded,
    _safe_error,
    openai_client,
)
from app.models.db.analytics import PatternInsight
from app.models.db.card import Card

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["pattern_insights"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SKIP_COLUMNS = {"embedding", "search_vector"}


def _row_to_dict(obj, skip_cols=None) -> dict:
    skip = skip_cols or set()
    result = {}
    for col in obj.__table__.columns:
        if col.name in skip:
            continue
        value = getattr(obj, col.key, None)
        if isinstance(value, uuid.UUID):
            result[col.name] = str(value)
        elif isinstance(value, (datetime, date)):
            result[col.name] = value.isoformat()
        elif isinstance(value, Decimal):
            result[col.name] = float(value)
        elif isinstance(value, list):
            # Handle lists of UUIDs (e.g. related_card_ids)
            result[col.name] = [
                str(item) if isinstance(item, uuid.UUID) else item for item in value
            ]
        else:
            result[col.name] = value
    return result


@router.get("/pattern-insights")
async def get_pattern_insights(
    status_filter: str = Query("active", alias="status"),
    urgency: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_user_hardcoded),
    db: AsyncSession = Depends(get_db),
):
    """Get AI-detected cross-signal pattern insights."""
    try:
        stmt = select(PatternInsight).where(PatternInsight.status == status_filter)
        if urgency:
            stmt = stmt.where(PatternInsight.urgency == urgency)
        stmt = stmt.order_by(PatternInsight.created_at.desc()).limit(limit)

        result = await db.execute(stmt)
        rows = result.scalars().all()
        return [_row_to_dict(row) for row in rows]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("fetching pattern insights", e),
        ) from e


@router.get("/pattern-insights/{insight_id}")
async def get_pattern_insight_by_id(
    insight_id: str,
    current_user: dict = Depends(get_current_user_hardcoded),
    db: AsyncSession = Depends(get_db),
):
    """Get a single pattern insight by ID, including related card details."""
    try:
        result = await db.execute(
            select(PatternInsight).where(PatternInsight.id == insight_id)
        )
        row = result.scalar_one_or_none()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pattern insight not found",
            )
        insight = _row_to_dict(row)

        # Fetch related cards if any
        related_ids = row.related_card_ids or []
        if related_ids:
            cards_result = await db.execute(
                select(Card).where(Card.id.in_(related_ids))
            )
            cards = cards_result.scalars().all()
            insight["related_cards"] = [
                {
                    "id": str(c.id),
                    "name": c.name,
                    "summary": c.summary,
                    "pillar_id": c.pillar_id,
                    "stage_id": c.stage_id,
                    "horizon": c.horizon,
                    "pipeline_status": getattr(c, "pipeline_status", None),
                }
                for c in cards
            ]
        else:
            insight["related_cards"] = []

        return insight
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("fetching pattern insight", e),
        ) from e


@router.patch("/pattern-insights/{insight_id}")
async def update_pattern_insight_status(
    insight_id: str,
    body: dict,
    current_user: dict = Depends(get_current_user_hardcoded),
    db: AsyncSession = Depends(get_db),
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
        # Fetch the row first to verify it exists
        result = await db.execute(
            select(PatternInsight).where(PatternInsight.id == insight_id)
        )
        row = result.scalar_one_or_none()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pattern insight not found",
            )

        row.status = new_status
        await db.flush()
        await db.refresh(row)
        return _row_to_dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("updating pattern insight", e),
        ) from e


@router.post("/pattern-insights/generate")
async def generate_pattern_insights(
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Trigger cross-signal pattern detection. Runs in background."""
    from app.pattern_detection_service import PatternDetectionService

    async def _run_pattern_detection():
        try:
            from app.database import async_session_factory

            if not async_session_factory:
                logger.error("Cannot run pattern detection: database not configured")
                return
            async with async_session_factory() as session:
                service = PatternDetectionService(session, openai_client)
                result = await service.run_detection()
                logger.info("On-demand pattern detection completed: %s", result)
        except Exception as exc:
            logger.exception("On-demand pattern detection failed: %s", exc)

    asyncio.create_task(_run_pattern_detection())
    return {
        "status": "started",
        "message": "Pattern detection is running in the background.",
    }
