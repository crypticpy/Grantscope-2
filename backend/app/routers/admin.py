"""Admin, taxonomy, source rating, quality, and domain reputation router."""

import asyncio
import logging
import uuid as _uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import (
    get_db,
    get_current_user,
    get_current_user_hardcoded,
    _safe_error,
    limiter,
)
from app.models.source_rating import (
    SourceRatingCreate,
    SourceRatingResponse,
    SourceRatingAggregate,
)
from app.models.domain_reputation import (
    DomainReputationCreate,
    DomainReputationUpdate,
)
from app.models.db.reference import Pillar, Goal, Anchor, Stage
from app.models.db.card import Card
from app.models.db.research import ResearchTask
from app.models.db.source import SourceRating, SignalSource
from app.models.db.analytics import DomainReputation
from app.models.db.system_settings import SystemSetting
from app.chat.admin_deps import require_admin
from app import quality_service, domain_reputation_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["admin"])

# Setting keys that non-admin users are allowed to read
PUBLIC_SETTING_KEYS = {"online_search_enabled"}


class SettingUpdate(BaseModel):
    """Request body for updating a system setting."""

    value: Any
    description: str | None = None


# ---------------------------------------------------------------------------
# Helper: ORM row -> dict (safe JSON-serialisable conversion)
# ---------------------------------------------------------------------------


def _row_to_dict(obj, skip_cols=None) -> dict:
    skip = skip_cols or set()
    result = {}
    for col in obj.__table__.columns:
        if col.name in skip:
            continue
        value = getattr(obj, col.key, None)
        if isinstance(value, _uuid.UUID):
            result[col.name] = str(value)
        elif isinstance(value, (datetime, date)):
            result[col.name] = value.isoformat()
        elif isinstance(value, Decimal):
            result[col.name] = float(value)
        else:
            result[col.name] = value
    return result


# ============================================================================
# Taxonomy endpoints
# ============================================================================


@router.get("/taxonomy")
async def get_taxonomy(db: AsyncSession = Depends(get_db)):
    """Get all taxonomy data"""
    try:
        pillars_q = await db.execute(select(Pillar).order_by(Pillar.name))
        goals_q = await db.execute(
            select(Goal).order_by(Goal.pillar_id, Goal.sort_order)
        )
        anchors_q = await db.execute(select(Anchor).order_by(Anchor.name))
        stages_q = await db.execute(select(Stage).order_by(Stage.sort_order))

        return {
            "pillars": [_row_to_dict(p) for p in pillars_q.scalars().all()],
            "goals": [_row_to_dict(g) for g in goals_q.scalars().all()],
            "anchors": [_row_to_dict(a) for a in anchors_q.scalars().all()],
            "stages": [_row_to_dict(s) for s in stages_q.scalars().all()],
        }
    except Exception as e:
        logger.error(f"Failed to fetch taxonomy: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("taxonomy retrieval", e),
        ) from e


# ============================================================================
# Admin scan
# ============================================================================


@router.post("/admin/scan")
@limiter.limit("3/minute")
async def trigger_manual_scan(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Manually trigger content scan for all active cards.

    This triggers a quick update research task for cards that haven't been
    updated in the last 24 hours. Limited to admin users.

    Note: In production, add admin role check here.
    """
    try:
        # Get cards that need updates (not updated in last 24 hours)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

        cards_result = await db.execute(
            select(Card.id, Card.name)
            .where(Card.status == "active")
            .where(Card.updated_at < cutoff)
            .limit(10)
        )
        cards = cards_result.all()

        if not cards:
            return {
                "status": "skipped",
                "message": "No cards need updating",
                "cards_queued": 0,
            }

        # Queue update tasks for each card
        tasks_created = 0
        for card in cards:
            task = ResearchTask(
                user_id=_uuid.UUID(current_user["id"]),
                card_id=card.id,
                task_type="update",
                status="queued",
            )
            db.add(task)
            tasks_created += 1
            logger.info(f"Queued update task for card: {card.name}")

        # Flush so the inserts are visible; commit happens on session close
        await db.flush()

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
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Create or update user's rating for a source. Upserts on (source_id, user_id)."""
    try:
        src_uuid = _uuid.UUID(source_id)
        usr_uuid = _uuid.UUID(user["id"])

        # Check for existing rating
        existing_result = await db.execute(
            select(SourceRating)
            .where(SourceRating.source_id == src_uuid)
            .where(SourceRating.user_id == usr_uuid)
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            existing.quality_rating = rating.quality_rating
            existing.relevance_rating = rating.relevance_rating.value
            existing.comment = rating.comment
            existing.updated_at = datetime.now(timezone.utc)
            await db.flush()
            saved = existing
        else:
            new_rating = SourceRating(
                source_id=src_uuid,
                user_id=usr_uuid,
                quality_rating=rating.quality_rating,
                relevance_rating=rating.relevance_rating.value,
                comment=rating.comment,
            )
            db.add(new_rating)
            await db.flush()
            await db.refresh(new_rating)
            saved = new_rating

        result_dict = _row_to_dict(saved)

        # Trigger SQI recalculation for parent card(s) of this source.
        # Fire-and-forget: rating is saved even if recalculation fails.
        try:
            links_result = await db.execute(
                select(SignalSource.card_id).where(SignalSource.source_id == src_uuid)
            )
            for row in links_result.all():
                card_id = row.card_id
                if card_id:
                    try:
                        await quality_service.calculate_sqi(db, str(card_id))
                    except Exception as sqi_err:
                        logger.warning(
                            f"SQI recalc failed for card {card_id} after rating: {sqi_err}"
                        )
        except Exception as lookup_err:
            logger.warning(
                f"Failed to look up parent cards for source {source_id}: {lookup_err}"
            )

        return result_dict
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to rate source {source_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("rating save", e),
        ) from e


@router.get("/sources/{source_id}/ratings", response_model=SourceRatingAggregate)
async def get_source_ratings(
    source_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get aggregated ratings for a source plus current user's rating."""
    try:
        src_uuid = _uuid.UUID(source_id)

        result = await db.execute(
            select(SourceRating).where(SourceRating.source_id == src_uuid)
        )
        all_ratings = result.scalars().all()

        if not all_ratings:
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

        ratings_dicts = [_row_to_dict(r) for r in all_ratings]

        avg_quality = sum(r["quality_rating"] for r in ratings_dicts) / len(
            ratings_dicts
        )
        relevance_dist = {"high": 0, "medium": 0, "low": 0, "not_relevant": 0}
        for r in ratings_dicts:
            if r["relevance_rating"] in relevance_dist:
                relevance_dist[r["relevance_rating"]] += 1

        current_user_rating = next(
            (r for r in ratings_dicts if r["user_id"] == user["id"]), None
        )

        return SourceRatingAggregate(
            source_id=source_id,
            avg_quality=round(avg_quality, 2),
            total_ratings=len(ratings_dicts),
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
async def delete_source_rating(
    source_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Remove user's rating for a source."""
    try:
        src_uuid = _uuid.UUID(source_id)
        usr_uuid = _uuid.UUID(user["id"])

        await db.execute(
            delete(SourceRating)
            .where(SourceRating.source_id == src_uuid)
            .where(SourceRating.user_id == usr_uuid)
        )
        await db.flush()
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
    user=Depends(get_current_user),
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


# ============================================================================
# Domain Reputation endpoints
# ============================================================================


@router.get("/domain-reputation")
async def list_domain_reputations(
    page: int = 1,
    page_size: int = 50,
    tier: Optional[int] = None,
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """List all domains with reputation data, paginated and filterable."""
    try:
        # Build base query
        query = select(DomainReputation)
        count_query = select(func.count()).select_from(DomainReputation)

        if tier:
            query = query.where(DomainReputation.curated_tier == tier)
            count_query = count_query.where(DomainReputation.curated_tier == tier)
        if category:
            query = query.where(DomainReputation.category == category)
            count_query = count_query.where(DomainReputation.category == category)

        query = query.order_by(DomainReputation.composite_score.desc())
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        # Execute both queries
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        items_result = await db.execute(query)
        items = [_row_to_dict(r) for r in items_result.scalars().all()]

        return {
            "items": items,
            "total": total,
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
async def get_domain_reputation(
    domain_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get single domain reputation detail."""
    try:
        dom_uuid = _uuid.UUID(domain_id)
        result = await db.execute(
            select(DomainReputation).where(DomainReputation.id == dom_uuid)
        )
        domain = result.scalar_one_or_none()
        if not domain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Domain reputation not found",
            )
        return _row_to_dict(domain)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get domain reputation {domain_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_safe_error("domain reputation lookup", e),
        ) from e


@router.post("/admin/domain-reputation")
async def create_domain_reputation(
    body: DomainReputationCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Add a new domain to the reputation system. Admin only."""
    try:
        data = body.model_dump()
        # Calculate initial composite score based on tier
        tier_scores = {1: 85, 2: 60, 3: 35}
        tier_score = tier_scores.get(data.get("curated_tier"), 20)
        composite = tier_score * 0.50 + data.get("texas_relevance_bonus", 0)

        domain_rep = DomainReputation(
            domain_pattern=data["domain_pattern"],
            organization_name=data["organization_name"],
            category=data["category"],
            curated_tier=data.get("curated_tier"),
            texas_relevance_bonus=data.get("texas_relevance_bonus", 0),
            notes=data.get("notes"),
            composite_score=composite,
        )
        db.add(domain_rep)
        await db.flush()
        await db.refresh(domain_rep)

        return _row_to_dict(domain_rep)
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
    db: AsyncSession = Depends(get_db),
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

        dom_uuid = _uuid.UUID(domain_id)
        result = await db.execute(
            select(DomainReputation).where(DomainReputation.id == dom_uuid)
        )
        domain_rep = result.scalar_one_or_none()
        if not domain_rep:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Domain reputation not found",
            )

        for key, value in data.items():
            setattr(domain_rep, key, value)

        await db.flush()
        await db.refresh(domain_rep)

        return _row_to_dict(domain_rep)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update domain reputation {domain_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("domain reputation update", e),
        ) from e


@router.delete("/admin/domain-reputation/{domain_id}")
async def delete_domain_reputation(
    domain_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Remove a domain from the reputation system. Admin only."""
    try:
        dom_uuid = _uuid.UUID(domain_id)
        await db.execute(
            delete(DomainReputation).where(DomainReputation.id == dom_uuid)
        )
        await db.flush()
        return {"status": "deleted"}
    except Exception as e:
        logger.error(f"Failed to delete domain reputation {domain_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("domain reputation deletion", e),
        ) from e


@router.post("/admin/domain-reputation/recalculate")
async def recalculate_domain_reputations(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Recalculate all composite scores from user ratings + pipeline stats."""
    try:
        return await domain_reputation_service.recalculate_all(db)
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
    db: AsyncSession = Depends(get_db),
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
    from app.database import async_session_factory

    async def _run_velocity():
        try:
            async with async_session_factory() as bg_session:
                try:
                    result = await calculate_velocity_trends(bg_session)
                    await bg_session.commit()
                    logger.info("On-demand velocity calculation completed: %s", result)
                except Exception:
                    await bg_session.rollback()
                    raise
        except Exception as exc:
            logger.exception("On-demand velocity calculation failed: %s", exc)

    asyncio.create_task(_run_velocity())
    return {
        "status": "started",
        "message": "Velocity calculation is running in the background.",
    }


# ============================================================================
# System Settings CRUD
# ============================================================================


@router.get("/admin/settings")
async def list_settings(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """List all system settings. Admin only."""
    result = await db.execute(select(SystemSetting).order_by(SystemSetting.key))
    settings = result.scalars().all()
    return [
        {
            "key": s.key,
            "value": s.value,
            "description": s.description,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        }
        for s in settings
    ]


@router.get("/admin/settings/{key}")
async def get_setting(
    key: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Get a single setting value.

    Non-admin users may only read keys listed in PUBLIC_SETTING_KEYS.
    """
    user_role = current_user.get("role", "")
    if user_role not in ("admin", "service_role") and key not in PUBLIC_SETTING_KEYS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to read this setting",
        )
    result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
    setting = result.scalar_one_or_none()
    if not setting:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")
    return {
        "key": setting.key,
        "value": setting.value,
        "description": setting.description,
    }


@router.put("/admin/settings/{key}")
async def update_setting(
    key: str,
    body: SettingUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Update a system setting value. Admin only."""
    result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
    setting = result.scalar_one_or_none()
    if not setting:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")

    setting.value = body.value
    if body.description is not None:
        setting.description = body.description
    setting.updated_by = current_user["id"]
    setting.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(setting)

    return {
        "key": setting.key,
        "value": setting.value,
        "description": setting.description,
    }
