"""Source rating endpoints -- user-accessible source quality/relevance ratings."""

import logging
import uuid as _uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, get_current_user, _safe_error
from app.models.source_rating import (
    SourceRatingCreate,
    SourceRatingResponse,
    SourceRatingAggregate,
)
from app.models.db.source import SourceRating, SignalSource
from app.routers.admin._helpers import _row_to_dict
from app import quality_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["sources"])


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
            (r for r in ratings_dicts if r["user_id"] == str(user["id"])), None
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
