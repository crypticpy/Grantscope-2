"""Card review router -- pending count, single review, bulk review, dismiss."""

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, get_current_user_hardcoded, _safe_error, limiter
from app.helpers.score_history import SCORE_FIELDS
from app.models.db.card import Card
from app.models.db.card_extras import CardTimeline, CardScoreHistory
from app.models.db.discovery import DiscoveryBlock, UserCardDismissal
from app.models.review import CardReviewRequest, BulkReviewRequest, CardDismissRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["card-review"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_dict(obj, skip_cols=None) -> dict:
    """Serialize an ORM row to a plain dict, handling UUID/datetime/Decimal."""
    skip = skip_cols or set()
    result = {}
    for col in obj.__table__.columns:
        if col.name in skip:
            continue
        value = getattr(obj, col.name, None)
        if isinstance(value, uuid.UUID):
            result[col.name] = str(value)
        elif isinstance(value, (datetime, date)):
            result[col.name] = value.isoformat()
        elif isinstance(value, Decimal):
            result[col.name] = float(value)
        else:
            result[col.name] = value
    return result


def _card_dict_from_obj(card: Card) -> dict:
    """Convert a Card ORM object to a serializable dict for score comparison."""
    return _row_to_dict(card, skip_cols={"embedding", "search_vector"})


# ============================================================================
# Pending review count
# ============================================================================


@router.get("/discovery/pending/count")
async def get_pending_review_count(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Get count of cards pending review.

    Returns the total number of cards with review_status in
    ('discovered', 'pending_review').

    Returns:
        Object with count field
    """
    try:
        result = await db.execute(
            select(func.count(Card.id)).where(
                Card.review_status != "rejected",
                or_(
                    Card.review_status.in_(["discovered", "pending_review"]),
                    Card.status == "draft",
                ),
            )
        )
        count = result.scalar() or 0
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error("counting pending reviews", e),
        ) from e

    return {"count": count}


# ============================================================================
# Single card review
# ============================================================================


@router.post("/cards/{card_id}/review")
async def review_card(
    card_id: str,
    review_data: CardReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Review a discovered card.

    Actions:
    - approve: Set review_status to 'active', card becomes live
    - reject: Set review_status to 'rejected', record rejection metadata
    - edit_approve: Apply field updates, then set to 'active'

    Args:
        card_id: UUID of the card to review
        review_data: Review action and optional updates/reason

    Returns:
        Updated card data

    Raises:
        HTTPException 404: Card not found
        HTTPException 400: Invalid action or missing required fields
    """
    # Verify card exists
    try:
        result = await db.execute(select(Card).where(Card.id == uuid.UUID(card_id)))
        card = result.scalar_one_or_none()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error("fetching card for review", e),
        ) from e

    if card is None:
        raise HTTPException(status_code=404, detail="Card not found")

    # Snapshot old card data before mutation (for history tracking)
    old_card_data = _card_dict_from_obj(card)
    now = datetime.now(timezone.utc)

    if review_data.action == "approve":
        card.review_status = "active"
        card.status = "active"
        card.reviewed_at = now
        card.reviewed_by = uuid.UUID(current_user["id"])
        card.updated_at = now

    elif review_data.action == "reject":
        card.review_status = "rejected"
        card.rejected_at = now
        card.rejected_by = uuid.UUID(current_user["id"])
        card.rejection_reason = review_data.reason
        card.updated_at = now

    elif review_data.action == "edit_approve":
        if not review_data.updates:
            raise HTTPException(
                status_code=400, detail="Updates required for edit_approve action"
            )

        # Allowed fields for editing
        allowed_fields = {
            "name",
            "summary",
            "description",
            "pillar_id",
            "goal_id",
            "anchor_id",
            "stage_id",
            "horizon",
            "novelty_score",
            "maturity_score",
            "impact_score",
            "relevance_score",
        }

        # Apply allowed field updates
        filtered_updates = {
            k: v for k, v in review_data.updates.items() if k in allowed_fields
        }
        for field, value in filtered_updates.items():
            setattr(card, field, value)

        # Update slug if name changed
        if "name" in filtered_updates:
            card.slug = (
                filtered_updates["name"]
                .lower()
                .replace(" ", "-")
                .replace(":", "")
                .replace("/", "-")
            )

        card.review_status = "active"
        card.status = "active"
        card.reviewed_at = now
        card.reviewed_by = uuid.UUID(current_user["id"])
        card.review_notes = review_data.reason
        card.updated_at = now

    else:
        raise HTTPException(status_code=400, detail="Invalid review action")

    # Flush the card update
    try:
        await db.flush()
        await db.refresh(card)
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=_safe_error("updating card", e)
        ) from e

    updated_card_dict = _card_dict_from_obj(card)

    # Log the review action to card timeline
    updates_applied = None
    if review_data.action == "edit_approve" and review_data.updates:
        allowed_fields_set = {
            "name",
            "summary",
            "description",
            "pillar_id",
            "goal_id",
            "anchor_id",
            "stage_id",
            "horizon",
            "novelty_score",
            "maturity_score",
            "impact_score",
            "relevance_score",
        }
        updates_applied = [
            k for k in review_data.updates.keys() if k in allowed_fields_set
        ]
        # Also include the status/review fields that were set
        updates_applied.extend(
            [
                "review_status",
                "status",
                "reviewed_at",
                "reviewed_by",
                "review_notes",
                "updated_at",
            ]
        )

    timeline_entry = CardTimeline(
        card_id=uuid.UUID(card_id),
        event_type=f"review_{review_data.action}",
        title=f"Card {review_data.action}d",
        description=f"Card {review_data.action}d by reviewer",
        created_by=uuid.UUID(current_user["id"]),
        metadata_={
            "action": review_data.action,
            "reason": review_data.reason,
            "updates_applied": updates_applied,
        },
        created_at=now,
    )
    try:
        db.add(timeline_entry)
        await db.flush()
    except Exception as e:
        logger.warning("Failed to insert timeline entry for card %s: %s", card_id, e)

    # Track score and stage history for edit_approve actions
    if review_data.action == "edit_approve":
        # Record score history if any score fields changed
        _record_score_history_sa(
            db=db,
            old_card_data=old_card_data,
            new_card_data=updated_card_dict,
            card_id=card_id,
        )

        # Record stage history if stage or horizon changed
        await _record_stage_history_sa(
            db=db,
            old_card_data=old_card_data,
            new_card_data=updated_card_dict,
            card_id=card_id,
            user_id=current_user.get("id"),
            trigger="review",
            reason=review_data.reason,
        )

    # Update signal quality score after approval
    if review_data.action in ("approve", "edit_approve"):
        try:
            from app.signal_quality import update_signal_quality_score

            await update_signal_quality_score(db, card_id)
        except Exception as e:
            logger.warning(
                "Failed to update signal quality score for %s: %s", card_id, e
            )

    return updated_card_dict


# ============================================================================
# Bulk review
# ============================================================================


@router.post("/cards/bulk-review")
@limiter.limit("10/minute")
async def bulk_review_cards(
    request: Request,
    bulk_data: BulkReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Bulk approve or reject multiple cards using batch operations.

    Processes up to 100 cards in a single request using atomic batch updates.
    Cards are verified first, then updated in a single query for consistency.

    Args:
        bulk_data: List of card IDs and action to apply

    Returns:
        Summary with processed count and any failures
    """
    now = datetime.now(timezone.utc)
    card_ids = bulk_data.card_ids
    failed = []

    try:
        # Step 1: Verify all cards exist in a single query
        card_uuids = [uuid.UUID(cid) for cid in card_ids]
        result = await db.execute(select(Card.id).where(Card.id.in_(card_uuids)))
        existing_ids = {str(row[0]) for row in result.all()}

        # Identify cards that don't exist
        missing_ids = set(card_ids) - existing_ids
        failed.extend(
            {"id": missing_id, "error": "Card not found"} for missing_id in missing_ids
        )
        valid_ids = list(existing_ids)

        if not valid_ids:
            return {"processed": 0, "failed": failed}

        # Step 2: Fetch all valid cards and apply updates
        valid_uuids = [uuid.UUID(vid) for vid in valid_ids]
        cards_result = await db.execute(select(Card).where(Card.id.in_(valid_uuids)))
        cards = list(cards_result.scalars().all())

        user_uuid = uuid.UUID(current_user["id"])

        for card_obj in cards:
            if bulk_data.action == "approve":
                card_obj.review_status = "active"
                card_obj.status = "active"
                card_obj.reviewed_at = now
                card_obj.reviewed_by = user_uuid
                card_obj.updated_at = now
            else:  # reject
                card_obj.review_status = "rejected"
                card_obj.rejected_at = now
                card_obj.rejected_by = user_uuid
                card_obj.rejection_reason = bulk_data.reason
                card_obj.updated_at = now

        # Step 3: Flush all updates
        try:
            await db.flush()
        except Exception as e:
            # If batch update fails entirely, mark all as failed
            for cid in valid_ids:
                failed.append({"id": cid, "error": "Batch update failed"})
            return {"processed": 0, "failed": failed}

        updated_ids = [str(c.id) for c in cards]
        processed_count = len(updated_ids)

        # Check for any cards that weren't updated
        not_updated = set(valid_ids) - set(updated_ids)
        for cid in not_updated:
            failed.append({"id": cid, "error": "Update did not apply"})

        # Step 4: Batch insert timeline entries
        if updated_ids:
            for cid in updated_ids:
                timeline_entry = CardTimeline(
                    card_id=uuid.UUID(cid),
                    event_type=f"bulk_review_{bulk_data.action}",
                    title=f"Card bulk {bulk_data.action}d",
                    description=f"Card bulk {bulk_data.action}d",
                    created_by=user_uuid,
                    metadata_={"bulk_action": True, "reason": bulk_data.reason},
                    created_at=now,
                )
                db.add(timeline_entry)

            try:
                await db.flush()
            except Exception as e:
                logger.warning("Failed to insert bulk timeline entries: %s", e)

        # Step 5: Recompute signal quality scores for approved cards
        if bulk_data.action == "approve" and updated_ids:
            try:
                from app.signal_quality import update_signal_quality_score

                for cid in updated_ids:
                    try:
                        await update_signal_quality_score(db, cid)
                    except Exception as e:
                        logger.warning(
                            "Failed to update signal quality score for %s: %s",
                            cid,
                            e,
                        )
            except Exception as e:
                logger.warning(
                    "Failed to import signal quality module during bulk review: %s", e
                )

        return {"processed": processed_count, "failed": failed}

    except Exception as e:
        # If an unexpected error occurs, report it with context
        return {"processed": 0, "failed": [{"id": "batch_operation", "error": str(e)}]}


# ============================================================================
# Dismiss
# ============================================================================


@router.post("/cards/{card_id}/dismiss")
async def dismiss_card(
    card_id: str,
    dismiss_data: Optional[CardDismissRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Dismiss a card for the current user (soft-delete).

    Creates a user_card_dismissals record. If the card has been dismissed
    by 3 or more users, it gets added to discovery_blocks.

    Args:
        card_id: UUID of the card to dismiss
        dismiss_data: Optional reason for dismissal

    Returns:
        Dismissal status and block status if applicable
    """
    card_uuid = uuid.UUID(card_id)
    user_uuid = uuid.UUID(current_user["id"])

    # Verify card exists
    try:
        result = await db.execute(
            select(Card.id, Card.name).where(Card.id == card_uuid)
        )
        card_row = result.one_or_none()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error("fetching card for dismissal", e),
        ) from e

    if card_row is None:
        raise HTTPException(status_code=404, detail="Card not found")

    card_name = card_row[1]

    # Check if user already dismissed this card
    try:
        existing_result = await db.execute(
            select(UserCardDismissal.id).where(
                UserCardDismissal.user_id == user_uuid,
                UserCardDismissal.card_id == card_uuid,
            )
        )
        existing = existing_result.scalar_one_or_none()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error("checking existing dismissal", e),
        ) from e

    if existing is not None:
        raise HTTPException(status_code=400, detail="Card already dismissed by user")

    # Create dismissal record
    now = datetime.now(timezone.utc)
    dismissal = UserCardDismissal(
        user_id=user_uuid,
        card_id=card_uuid,
        reason=dismiss_data.reason if dismiss_data else None,
        dismissed_at=now,
    )
    try:
        db.add(dismissal)
        await db.flush()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error("creating dismissal record", e),
        ) from e

    # Check total dismissal count for this card
    try:
        count_result = await db.execute(
            select(func.count(UserCardDismissal.id)).where(
                UserCardDismissal.card_id == card_uuid,
            )
        )
        total_dismissals = count_result.scalar() or 0
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error("counting dismissals", e),
        ) from e

    blocked = False
    if total_dismissals >= 3:
        # Add to discovery_blocks if not already blocked
        try:
            block_result = await db.execute(
                select(DiscoveryBlock.id).where(
                    DiscoveryBlock.topic_name == card_name.lower(),
                )
            )
            existing_block = block_result.scalar_one_or_none()
        except Exception as e:
            logger.warning(
                "Failed to check existing discovery block for card %s: %s",
                card_id,
                e,
            )
            existing_block = None

        if existing_block is None:
            block = DiscoveryBlock(
                topic_name=card_name.lower(),
                reason="Dismissed by multiple users",
                blocked_by_count=total_dismissals,
                first_blocked_at=now,
                last_blocked_at=now,
            )
            try:
                db.add(block)
                await db.flush()
                blocked = True
                logger.info(
                    "Card %s blocked from discovery after %d dismissals",
                    card_id,
                    total_dismissals,
                )
            except Exception as e:
                logger.warning(
                    "Failed to create discovery block for card %s: %s", card_id, e
                )

    return {
        "status": "dismissed",
        "card_id": card_id,
        "blocked": blocked,
        "total_dismissals": total_dismissals,
    }


# ============================================================================
# Internal helpers (SQLAlchemy-based score/stage history)
# ============================================================================


def _record_score_history_sa(
    db: AsyncSession,
    old_card_data: dict,
    new_card_data: dict,
    card_id: str,
) -> None:
    """Record score history using SQLAlchemy (fire-and-forget add to session)."""
    scores_changed = any(
        old_card_data.get(field) != new_card_data.get(field) for field in SCORE_FIELDS
    )
    if not scores_changed:
        logger.debug(
            "No score changes detected for card %s, skipping history record",
            card_id,
        )
        return

    try:
        history = CardScoreHistory(
            card_id=uuid.UUID(card_id),
            recorded_at=datetime.now(timezone.utc),
            novelty_score=new_card_data.get("novelty_score"),
            maturity_score=new_card_data.get("maturity_score"),
            impact_score=new_card_data.get("impact_score"),
            relevance_score=new_card_data.get("relevance_score"),
            velocity_score=new_card_data.get("velocity_score"),
            risk_score=new_card_data.get("risk_score"),
            opportunity_score=new_card_data.get("opportunity_score"),
        )
        db.add(history)
        # flush will happen in the caller or at commit time
        logger.info("Recorded score history for card %s", card_id)
    except Exception as e:
        logger.error("Failed to record score history for card %s: %s", card_id, e)


async def _record_stage_history_sa(
    db: AsyncSession,
    old_card_data: dict,
    new_card_data: dict,
    card_id: str,
    user_id: Optional[str] = None,
    trigger: str = "manual",
    reason: Optional[str] = None,
) -> None:
    """Record stage transition to card_timeline using SQLAlchemy."""
    old_stage = old_card_data.get("stage_id")
    new_stage = new_card_data.get("stage_id")
    old_horizon = old_card_data.get("horizon")
    new_horizon = new_card_data.get("horizon")

    if old_stage == new_stage and old_horizon == new_horizon:
        logger.debug("No stage/horizon changes detected for card %s", card_id)
        return

    try:
        now = datetime.now(timezone.utc)
        timeline_entry = CardTimeline(
            card_id=uuid.UUID(card_id),
            event_type="stage_changed",
            title="Stage changed",
            description=f"Stage changed from {old_stage or 'none'} to {new_stage or 'none'}",
            created_by=uuid.UUID(user_id) if user_id else None,
            metadata_={
                "old_stage_id": old_stage,
                "new_stage_id": new_stage,
                "old_horizon": old_horizon,
                "new_horizon": new_horizon,
                "trigger": trigger,
                "reason": reason,
            },
            created_at=now,
        )
        db.add(timeline_entry)
        await db.flush()
        logger.info(
            "Recorded stage transition for card %s: %s -> %s",
            card_id,
            old_stage,
            new_stage,
        )
    except Exception as e:
        logger.error("Failed to record stage history for card %s: %s", card_id, e)
