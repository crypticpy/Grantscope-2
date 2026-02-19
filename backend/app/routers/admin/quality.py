"""Quality / SQI endpoints -- signal quality index management.

Includes per-card quality endpoints (any authenticated user) and admin-only
endpoints for score distribution, SQI weight configuration, and batch
recalculation.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, get_current_user, _safe_error, limiter
from app.chat.admin_deps import require_admin
from app.models.db.system_settings import SystemSetting
from app import quality_service

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SQI_WEIGHTS_KEY = "signal_quality_weights"

# Default weights (must match quality_service.py constants)
DEFAULT_SQI_WEIGHTS: Dict[str, float] = {
    "source_authority": 0.30,
    "source_diversity": 0.20,
    "content_depth": 0.20,
    "recency": 0.15,
    "corroboration": 0.15,
}


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class SQIWeightsUpdate(BaseModel):
    """Request body for updating SQI weights.

    All five component weights must be provided and must sum to
    approximately 1.0 (tolerance: +/- 0.01).
    """

    source_authority: float = Field(..., ge=0.0, le=1.0)
    source_diversity: float = Field(..., ge=0.0, le=1.0)
    content_depth: float = Field(..., ge=0.0, le=1.0)
    recency: float = Field(..., ge=0.0, le=1.0)
    corroboration: float = Field(..., ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# Per-card quality endpoints (authenticated users)
# ---------------------------------------------------------------------------


@router.get("/cards/{card_id}/quality")
async def get_card_quality(
    card_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get full SQI breakdown for a card."""
    try:
        breakdown = await quality_service.get_breakdown(
            db, card_id
        ) or await quality_service.calculate_sqi(db, card_id)
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
    request: Request,
    card_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Force SQI recalculation for a card."""
    try:
        return await quality_service.calculate_sqi(db, card_id)
    except Exception as e:
        logger.error(f"Failed to recalculate quality for card {card_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("card quality recalculation", e),
        ) from e


@router.post("/admin/quality/recalculate-all")
async def recalculate_all_quality(
    db: AsyncSession = Depends(get_db),
    user=Depends(require_admin),
):
    """Batch recalculate SQI for all cards. Admin only."""
    try:
        return await quality_service.recalculate_all_cards(db)
    except Exception as e:
        logger.error(f"Failed to batch recalculate quality: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("batch quality recalculation", e),
        ) from e


@router.get("/cards/{card_id}/quality-score")
async def get_signal_quality_score(
    card_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Get computed signal quality score for a card."""
    try:
        from app.signal_quality import compute_signal_quality_score

        return await compute_signal_quality_score(db, card_id)
    except Exception as e:
        logger.error(f"Failed to get signal quality score for card {card_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("signal quality score retrieval", e),
        ) from e


@router.post("/cards/{card_id}/quality-score/refresh")
async def refresh_signal_quality_score(
    card_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_admin),
):
    """Recompute and store the signal quality score."""
    try:
        from app.signal_quality import update_signal_quality_score

        score = await update_signal_quality_score(db, card_id)
        return {"card_id": card_id, "signal_quality_score": score}
    except Exception as e:
        logger.error(
            f"Failed to refresh signal quality score for card {card_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("signal quality score refresh", e),
        ) from e


# ---------------------------------------------------------------------------
# Admin quality endpoints
# ---------------------------------------------------------------------------


@router.get("/admin/quality/distribution")
async def quality_score_distribution(
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(require_admin),
):
    """Quality score distribution across tiers: high, moderate, low, unscored.

    Returns a flat object matching the frontend QualityDistribution type.
    """
    try:
        distribution_sql = text(
            """
            SELECT
                count(*) FILTER (WHERE signal_quality_score >= 70) AS high,
                count(*) FILTER (WHERE signal_quality_score >= 40 AND signal_quality_score < 70) AS moderate,
                count(*) FILTER (WHERE signal_quality_score > 0 AND signal_quality_score < 40) AS low,
                count(*) FILTER (WHERE signal_quality_score IS NULL OR signal_quality_score = 0) AS unscored,
                count(*) AS total,
                coalesce(avg(signal_quality_score) FILTER (WHERE signal_quality_score IS NOT NULL), 0) AS avg_score
            FROM cards
        """
        )
        row = (await db.execute(distribution_sql)).one()

        return {
            "high": row._mapping["high"],
            "moderate": row._mapping["moderate"],
            "low": row._mapping["low"],
            "unscored": row._mapping["unscored"],
            "total": row._mapping["total"],
            "avg_score": round(float(row._mapping["avg_score"]), 2),
        }

    except Exception as e:
        logger.error("Failed to get quality distribution: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("quality distribution", e),
        ) from e


@router.get("/admin/quality/weights")
async def get_sqi_weights(
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(require_admin),
):
    """Return current SQI component weights from system_settings.

    If no custom weights have been saved, returns the defaults from
    quality_service.py.
    """
    try:
        result = await db.execute(
            select(SystemSetting).where(SystemSetting.key == _SQI_WEIGHTS_KEY)
        )
        setting = result.scalar_one_or_none()

        if setting and isinstance(setting.value, dict):
            weights = setting.value
        else:
            weights = dict(DEFAULT_SQI_WEIGHTS)

        return weights

    except Exception as e:
        logger.error("Failed to get SQI weights: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("SQI weights retrieval", e),
        ) from e


@router.put("/admin/quality/weights")
async def update_sqi_weights(
    body: SQIWeightsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Update SQI component weights.

    Validates that all five weights are present and sum to approximately
    1.0 (tolerance: +/- 0.01).  Persists to ``system_settings`` under
    the ``signal_quality_weights`` key.
    """
    try:
        weights = body.model_dump()
        total = sum(weights.values())

        if abs(total - 1.0) > 0.01:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Weights must sum to approximately 1.0 (got {total:.4f})",
            )

        now = datetime.now(timezone.utc)

        stmt = pg_insert(SystemSetting).values(
            key=_SQI_WEIGHTS_KEY,
            value=weights,
            description="SQI component weights for quality scoring",
            updated_by=current_user["id"],
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["key"],
            set_={
                "value": weights,
                "updated_by": current_user["id"],
                "updated_at": now,
            },
        )
        await db.execute(stmt)
        await db.commit()

        logger.info(
            "SQI weights updated by user %s: %s",
            current_user["id"],
            weights,
        )

        return {
            "weights": weights,
            "defaults": DEFAULT_SQI_WEIGHTS,
            "is_custom": True,
            "message": "SQI weights updated successfully. Run 'Recalculate All' to apply to existing cards.",
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("Failed to update SQI weights: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("SQI weights update", e),
        ) from e
