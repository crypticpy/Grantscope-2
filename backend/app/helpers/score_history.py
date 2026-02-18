"""Score and stage history tracking helpers extracted from main.py.

Functions for recording score changes and stage transitions to the
card_score_history and card_timeline tables respectively.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.card_extras import CardScoreHistory, CardTimeline

logger = logging.getLogger(__name__)

# Define all score fields for tracking
SCORE_FIELDS = [
    "novelty_score",
    "maturity_score",
    "impact_score",
    "relevance_score",
    "velocity_score",
    "risk_score",
    "opportunity_score",
]


async def _record_score_history(
    db: AsyncSession,
    old_card_data: Dict[str, Any],
    new_card_data: Dict[str, Any],
    card_id: str,
) -> bool:
    """
    Record score history to card_score_history table if any scores have changed.

    Compares old and new card data and inserts a new history record if at least
    one score value has changed. This enables temporal trend tracking.

    Args:
        db: AsyncSession instance
        old_card_data: Card data before the update
        new_card_data: Card data after the update
        card_id: UUID of the card being tracked

    Returns:
        True if a history record was inserted, False otherwise
    """
    # Check if any score has changed
    scores_changed = False
    for field in SCORE_FIELDS:
        old_value = old_card_data.get(field)
        new_value = new_card_data.get(field)
        if old_value != new_value:
            scores_changed = True
            break

    if not scores_changed:
        logger.debug(
            f"No score changes detected for card {card_id}, skipping history record"
        )
        return False

    try:
        # Prepare the history record with new scores
        history_obj = CardScoreHistory(
            id=uuid.uuid4(),
            card_id=uuid.UUID(card_id) if isinstance(card_id, str) else card_id,
            recorded_at=datetime.now(timezone.utc),
            novelty_score=new_card_data.get("novelty_score"),
            maturity_score=new_card_data.get("maturity_score"),
            impact_score=new_card_data.get("impact_score"),
            relevance_score=new_card_data.get("relevance_score"),
            velocity_score=new_card_data.get("velocity_score"),
            risk_score=new_card_data.get("risk_score"),
            opportunity_score=new_card_data.get("opportunity_score"),
        )

        # Insert the history record
        db.add(history_obj)
        await db.flush()
        logger.info(f"Recorded score history for card {card_id}")
        return True

    except Exception as e:
        # Log error but don't fail the main operation
        logger.error(f"Failed to record score history for card {card_id}: {e}")
        return False


async def _record_stage_history(
    db: AsyncSession,
    old_card_data: Dict[str, Any],
    new_card_data: Dict[str, Any],
    card_id: str,
    user_id: Optional[str] = None,
    trigger: str = "manual",
    reason: Optional[str] = None,
) -> bool:
    """
    Record stage transition to card_timeline table if stage or horizon has changed.

    Creates a timeline entry with event_type='stage_changed' and includes both
    old and new stage/horizon values for tracking maturity progression.

    Args:
        db: AsyncSession instance
        old_card_data: Card data before the update
        new_card_data: Card data after the update
        card_id: UUID of the card being tracked
        user_id: Optional user ID who triggered the change
        trigger: What triggered the change (manual, api, auto-calculated)
        reason: Optional explanation for the stage change

    Returns:
        True if a history record was inserted, False otherwise
    """
    old_stage = old_card_data.get("stage_id")
    new_stage = new_card_data.get("stage_id")
    old_horizon = old_card_data.get("horizon")
    new_horizon = new_card_data.get("horizon")

    # Check if stage or horizon changed
    if old_stage == new_stage and old_horizon == new_horizon:
        logger.debug(f"No stage/horizon changes detected for card {card_id}")
        return False

    try:
        timeline_obj = CardTimeline(
            card_id=uuid.UUID(card_id) if isinstance(card_id, str) else card_id,
            event_type="stage_changed",
            title="Stage Changed",
            description=f"Stage changed from {old_stage or 'none'} to {new_stage or 'none'}",
            created_by=uuid.UUID(user_id) if user_id else None,
            old_stage_id=int(old_stage) if old_stage else None,
            new_stage_id=int(new_stage) if new_stage else None,
            old_horizon=old_horizon,
            new_horizon=new_horizon,
            trigger=trigger,
            reason=reason,
            metadata_={
                "old_stage_id": old_stage,
                "new_stage_id": new_stage,
                "old_horizon": old_horizon,
                "new_horizon": new_horizon,
            },
            created_at=datetime.now(timezone.utc),
        )

        db.add(timeline_obj)
        await db.flush()
        logger.info(
            f"Recorded stage transition for card {card_id}: {old_stage} -> {new_stage}"
        )
        return True

    except Exception as e:
        # Log error but don't fail the main operation
        logger.error(f"Failed to record stage history for card {card_id}: {e}")
        return False
