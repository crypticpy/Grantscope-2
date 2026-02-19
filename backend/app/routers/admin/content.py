"""Content management endpoints -- scan trigger, description quality,
enrichment, stats, purge, bulk-status, reanalyze, missing-embeddings."""

import logging
import uuid as _uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, _safe_error, limiter
from app.chat.admin_deps import require_admin
from app.models.db.card import Card
from app.models.db.research import ResearchTask
from app.routers.admin._helpers import _row_to_dict

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic request schemas
# ---------------------------------------------------------------------------


class PurgeRequest(BaseModel):
    max_age_days: int
    min_quality_score: Optional[float] = None
    dry_run: bool = True


class BulkStatusRequest(BaseModel):
    card_ids: list[str]
    new_status: str


class ReanalyzeRequest(BaseModel):
    card_ids: list[str]


# ---------------------------------------------------------------------------
# Existing endpoints
# ---------------------------------------------------------------------------


@router.post("/admin/scan")
@limiter.limit("3/minute")
async def trigger_manual_scan(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """
    Manually trigger content scan for up to 10 active cards.

    Queues update research tasks for active cards that haven't been
    updated in the last 24 hours, limited to 10 cards per invocation.
    Requires admin access.
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
            logger.info("Queued update task for card: %s", card.name)

        # Flush so the inserts are visible; commit happens on session close
        await db.flush()

        return {
            "status": "scan_triggered",
            "message": f"Queued {tasks_created} update tasks",
            "cards_queued": tasks_created,
        }

    except Exception as e:
        logger.error("Manual scan failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("manual scan", e),
        ) from e


@router.get("/admin/description-quality")
async def get_description_quality(
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Card description quality stats bucketed by length."""
    try:
        result = await db.execute(
            text(
                """
            SELECT
                COUNT(*) FILTER (WHERE description IS NULL OR description = '') AS missing,
                COUNT(*) FILTER (WHERE length(description) > 0 AND length(description) < 400) AS thin,
                COUNT(*) FILTER (WHERE length(description) >= 400 AND length(description) < 1600) AS short,
                COUNT(*) FILTER (WHERE length(description) >= 1600 AND length(description) < 3200) AS adequate,
                COUNT(*) FILTER (WHERE length(description) >= 3200) AS comprehensive,
                COUNT(*) AS total
            FROM cards
            WHERE status = 'active'
        """
            )
        )
        row = result.one()
        return {
            "missing": row.missing,
            "thin": row.thin,
            "short": row.short,
            "adequate": row.adequate,
            "comprehensive": row.comprehensive,
            "total": row.total,
        }
    except Exception as e:
        logger.error("Failed to get description quality stats: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("description quality stats", e),
        ) from e


@router.post("/admin/enrich-descriptions")
@limiter.limit("2/minute")
async def trigger_enrich_descriptions(
    request: Request,
    max_cards: int = Query(10, ge=1, le=500),
    threshold_chars: int = Query(1600, ge=100, le=5000),
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Trigger enrichment of cards with thin descriptions."""
    try:
        from app.enrichment_service import enrich_thin_descriptions

        stats = await enrich_thin_descriptions(
            db,
            threshold_chars=threshold_chars,
            max_cards=max_cards,
            triggered_by_user_id=current_user["id"],
        )
        return {
            "enriched": stats.get("queued", 0),
            "skipped": stats.get("already_queued", 0),
            "errors": stats.get("errors", 0),
        }
    except Exception as e:
        logger.error("Failed to trigger description enrichment: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("description enrichment", e),
        ) from e


# ---------------------------------------------------------------------------
# New endpoints
# ---------------------------------------------------------------------------


@router.get("/admin/content/stats")
async def get_content_stats(
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Extended content quality stats: descriptions, embeddings, status,
    pillar, origin, and average scores."""
    try:
        # Description quality distribution
        desc_result = await db.execute(
            text(
                """
                SELECT
                    COUNT(*) FILTER (WHERE description IS NULL OR description = '') AS missing,
                    COUNT(*) FILTER (WHERE length(description) > 0 AND length(description) < 400) AS thin,
                    COUNT(*) FILTER (WHERE length(description) >= 400 AND length(description) < 1600) AS short,
                    COUNT(*) FILTER (WHERE length(description) >= 1600 AND length(description) < 3200) AS adequate,
                    COUNT(*) FILTER (WHERE length(description) >= 3200) AS comprehensive,
                    COUNT(*) AS total
                FROM cards
                WHERE status = 'active'
                """
            )
        )
        desc_row = desc_result.one()

        # Embedding coverage
        emb_result = await db.execute(
            text(
                """
                SELECT
                    COUNT(*) FILTER (WHERE embedding IS NOT NULL) AS with_embedding,
                    COUNT(*) FILTER (WHERE embedding IS NULL) AS without_embedding,
                    COUNT(*) AS total
                FROM cards
                WHERE status = 'active'
                """
            )
        )
        emb_row = emb_result.one()

        # Cards by status
        status_result = await db.execute(
            text("SELECT status, count(*) AS cnt FROM cards GROUP BY status")
        )
        by_status = {row.status: row.cnt for row in status_result.all()}

        # Cards by pillar
        pillar_result = await db.execute(
            text(
                "SELECT pillar_id, count(*) AS cnt FROM cards "
                "WHERE pillar_id IS NOT NULL GROUP BY pillar_id"
            )
        )
        by_pillar = {row.pillar_id: row.cnt for row in pillar_result.all()}

        # Cards by origin
        origin_result = await db.execute(
            text(
                "SELECT origin, count(*) AS cnt FROM cards "
                "WHERE origin IS NOT NULL GROUP BY origin"
            )
        )
        by_origin = {row.origin: row.cnt for row in origin_result.all()}

        # Average scores for active cards
        scores_result = await db.execute(
            text(
                """
                SELECT
                    avg(impact_score) AS avg_impact,
                    avg(relevance_score) AS avg_relevance,
                    avg(alignment_score) AS avg_alignment
                FROM cards
                WHERE status = 'active'
                """
            )
        )
        scores_row = scores_result.one()

        return {
            "description_quality": {
                "missing": desc_row.missing,
                "thin": desc_row.thin,
                "short": desc_row.short,
                "adequate": desc_row.adequate,
                "comprehensive": desc_row.comprehensive,
                "total": desc_row.total,
            },
            "embedding_coverage": {
                "with_embedding": emb_row.with_embedding,
                "without_embedding": emb_row.without_embedding,
                "total": emb_row.total,
            },
            "by_status": by_status,
            "by_pillar": by_pillar,
            "by_origin": by_origin,
            "average_scores": {
                "impact": (
                    float(scores_row.avg_impact)
                    if scores_row.avg_impact is not None
                    else None
                ),
                "relevance": (
                    float(scores_row.avg_relevance)
                    if scores_row.avg_relevance is not None
                    else None
                ),
                "alignment": (
                    float(scores_row.avg_alignment)
                    if scores_row.avg_alignment is not None
                    else None
                ),
            },
        }
    except Exception as e:
        logger.error("Failed to get content stats: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("content stats", e),
        ) from e


@router.post("/admin/content/purge")
async def purge_old_cards(
    body: PurgeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Archive old and/or low-quality active cards."""
    try:
        if body.max_age_days < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="max_age_days must be >= 1",
            )

        cutoff = datetime.now(timezone.utc) - timedelta(days=body.max_age_days)

        # Build base filter
        conditions = [
            Card.status == "active",
            Card.created_at < cutoff,
        ]
        if body.min_quality_score is not None:
            conditions.append(Card.relevance_score < body.min_quality_score)

        # Count affected cards
        count_stmt = select(func.count()).select_from(Card).where(*conditions)
        count_result = await db.execute(count_stmt)
        affected_count = count_result.scalar_one()

        if not body.dry_run and affected_count > 0:
            update_stmt = update(Card).where(*conditions).values(status="archived")
            await db.execute(update_stmt)
            await db.flush()

        criteria = {"max_age_days": body.max_age_days}
        if body.min_quality_score is not None:
            criteria["min_quality_score"] = body.min_quality_score

        return {
            "affected_count": affected_count,
            "dry_run": body.dry_run,
            "criteria": criteria,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to purge cards: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("card purge", e),
        ) from e


@router.post("/admin/content/bulk-status")
async def bulk_update_status(
    body: BulkStatusRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Bulk update card statuses."""
    try:
        allowed_statuses = {"active", "archived", "rejected", "reviewing"}
        if body.new_status not in allowed_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"new_status must be one of {sorted(allowed_statuses)}",
            )
        if not body.card_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="card_ids must not be empty",
            )

        # Convert string IDs to UUIDs for the query
        card_uuids = []
        for cid in body.card_ids:
            try:
                card_uuids.append(_uuid.UUID(cid))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid card ID: {cid}",
                )

        stmt = (
            update(Card).where(Card.id.in_(card_uuids)).values(status=body.new_status)
        )
        result = await db.execute(stmt)
        await db.flush()

        return {"updated_count": result.rowcount}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to bulk update card status: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("bulk status update", e),
        ) from e


@router.post("/admin/content/reanalyze")
async def reanalyze_cards(
    body: ReanalyzeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Queue card_analysis tasks for specific cards."""
    try:
        if not body.card_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="card_ids must not be empty",
            )

        from app.card_analysis_service import queue_card_analysis

        queued_count = 0
        already_queued_count = 0

        for card_id in body.card_ids:
            task_id = await queue_card_analysis(db, card_id, current_user["id"])
            if task_id is not None:
                queued_count += 1
            else:
                already_queued_count += 1

        await db.flush()

        return {
            "queued_count": queued_count,
            "already_queued_count": already_queued_count,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to queue card reanalysis: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("card reanalysis", e),
        ) from e


@router.get("/admin/content/missing-embeddings")
async def get_missing_embeddings(
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List cards without embeddings (up to 100)."""
    try:
        result = await db.execute(
            text(
                """
                SELECT id, name, status, created_at
                FROM cards
                WHERE embedding IS NULL
                ORDER BY created_at DESC
                LIMIT 100
                """
            )
        )
        rows = result.all()
        return [
            {
                "id": str(row.id),
                "name": row.name,
                "status": row.status,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
    except Exception as e:
        logger.error("Failed to get missing embeddings: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("missing embeddings query", e),
        ) from e
