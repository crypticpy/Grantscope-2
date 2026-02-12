"""Card review router -- pending count, single review, bulk review, dismiss."""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from app.deps import supabase, get_current_user, limiter
from app.helpers.score_history import (
    _record_score_history,
    _record_stage_history,
    SCORE_FIELDS,
)
from app.models.review import CardReviewRequest, BulkReviewRequest, CardDismissRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["card-review"])


# ============================================================================
# Pending review count
# ============================================================================


@router.get("/discovery/pending/count")
async def get_pending_review_count(current_user: dict = Depends(get_current_user)):
    """
    Get count of cards pending review.

    Returns the total number of cards with review_status in
    ('discovered', 'pending_review').

    Returns:
        Object with count field
    """
    response = (
        supabase.table("cards")
        .select("id", count="exact")
        .neq("review_status", "rejected")
        .or_("review_status.in.(discovered,pending_review),status.eq.draft")
        .execute()
    )

    return {"count": response.count or 0}


# ============================================================================
# Single card review
# ============================================================================


@router.post("/cards/{card_id}/review")
async def review_card(
    card_id: str,
    review_data: CardReviewRequest,
    current_user: dict = Depends(get_current_user),
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
    card_check = supabase.table("cards").select("*").eq("id", card_id).execute()
    if not card_check.data:
        raise HTTPException(status_code=404, detail="Card not found")

    card = card_check.data[0]
    now = datetime.now().isoformat()

    if review_data.action == "approve":
        # Approve the card - set it to active
        update_data = {
            "review_status": "active",
            "status": "active",
            "reviewed_at": now,
            "reviewed_by": current_user["id"],
            "updated_at": now,
        }

    elif review_data.action == "reject":
        # Reject the card
        update_data = {
            "review_status": "rejected",
            "rejected_at": now,
            "rejected_by": current_user["id"],
            "rejection_reason": review_data.reason,
            "updated_at": now,
        }

    elif review_data.action == "edit_approve":
        # Apply updates then approve
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

        update_data = {
            k: v for k, v in review_data.updates.items() if k in allowed_fields
        } | {
            "review_status": "active",
            "status": "active",
            "reviewed_at": now,
            "reviewed_by": current_user["id"],
            "review_notes": review_data.reason,
            "updated_at": now,
        }
        # Update slug if name changed
        if "name" in update_data:
            update_data["slug"] = (
                update_data["name"]
                .lower()
                .replace(" ", "-")
                .replace(":", "")
                .replace("/", "-")
            )

    else:
        raise HTTPException(status_code=400, detail="Invalid review action")

    # Perform the update
    response = supabase.table("cards").update(update_data).eq("id", card_id).execute()

    if not response.data:
        raise HTTPException(status_code=400, detail="Failed to update card")
    updated_card = response.data[0]

    # Log the review action to card timeline
    timeline_entry = {
        "card_id": card_id,
        "event_type": f"review_{review_data.action}",
        "description": f"Card {review_data.action}d by reviewer",
        "user_id": current_user["id"],
        "metadata": {
            "action": review_data.action,
            "reason": review_data.reason,
            "updates_applied": (
                list(update_data.keys())
                if review_data.action == "edit_approve"
                else None
            ),
        },
        "created_at": now,
    }
    supabase.table("card_timeline").insert(timeline_entry).execute()

    # Track score and stage history for edit_approve actions
    if review_data.action == "edit_approve":
        # Record score history if any score fields changed
        _record_score_history(
            supabase_client=supabase,
            old_card_data=card,
            new_card_data=updated_card,
            card_id=card_id,
        )

        # Record stage history if stage or horizon changed
        _record_stage_history(
            supabase_client=supabase,
            old_card_data=card,
            new_card_data=updated_card,
            card_id=card_id,
            user_id=current_user.get("id"),
            trigger="review",
            reason=review_data.reason,
        )

    # Update signal quality score after approval
    if review_data.action in ("approve", "edit_approve"):
        try:
            from app.signal_quality import update_signal_quality_score

            update_signal_quality_score(supabase, card_id)
        except Exception as e:
            logger.warning(f"Failed to update signal quality score for {card_id}: {e}")

    return updated_card


# ============================================================================
# Bulk review
# ============================================================================


@router.post("/cards/bulk-review")
@limiter.limit("10/minute")
async def bulk_review_cards(
    request: Request,
    bulk_data: BulkReviewRequest,
    current_user: dict = Depends(get_current_user),
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
    now = datetime.now().isoformat()
    card_ids = bulk_data.card_ids
    failed = []

    try:
        # Step 1: Verify all cards exist in a single query
        existing_cards = (
            supabase.table("cards").select("id").in_("id", card_ids).execute()
        )
        existing_ids = (
            {card["id"] for card in existing_cards.data}
            if existing_cards.data
            else set()
        )

        # Identify cards that don't exist
        missing_ids = set(card_ids) - existing_ids
        failed.extend(
            {"id": missing_id, "error": "Card not found"}
            for missing_id in missing_ids
        )
        # Get the list of valid card IDs to process
        valid_ids = list(existing_ids)

        if not valid_ids:
            return {"processed": 0, "failed": failed}

        # Step 2: Prepare update data based on action
        if bulk_data.action == "approve":
            update_data = {
                "review_status": "active",
                "status": "active",
                "reviewed_at": now,
                "reviewed_by": current_user["id"],
                "updated_at": now,
            }
        else:  # reject
            update_data = {
                "review_status": "rejected",
                "rejected_at": now,
                "rejected_by": current_user["id"],
                "rejection_reason": bulk_data.reason,
                "updated_at": now,
            }

        # Step 3: Batch update all valid cards in a single query
        update_response = (
            supabase.table("cards").update(update_data).in_("id", valid_ids).execute()
        )

        if not update_response.data:
            # If batch update fails entirely, mark all as failed
            for card_id in valid_ids:
                failed.append({"id": card_id, "error": "Batch update failed"})
            return {"processed": 0, "failed": failed}

        # Get the IDs that were actually updated
        updated_ids = [card["id"] for card in update_response.data]
        processed_count = len(updated_ids)

        # Check for any cards that weren't updated (shouldn't happen but handle gracefully)
        not_updated = set(valid_ids) - set(updated_ids)
        for card_id in not_updated:
            failed.append({"id": card_id, "error": "Update did not apply"})

        # Step 4: Batch insert timeline entries for all successfully updated cards
        if updated_ids:
            timeline_entries = [
                {
                    "card_id": card_id,
                    "event_type": f"bulk_review_{bulk_data.action}",
                    "description": f"Card bulk {bulk_data.action}d",
                    "user_id": current_user["id"],
                    "metadata": {"bulk_action": True, "reason": bulk_data.reason},
                    "created_at": now,
                }
                for card_id in updated_ids
            ]
            # Insert all timeline entries in a single batch
            supabase.table("card_timeline").insert(timeline_entries).execute()

        # Step 5: Recompute signal quality scores for approved cards
        if bulk_data.action == "approve" and updated_ids:
            try:
                from app.signal_quality import update_signal_quality_score

                for card_id in updated_ids:
                    try:
                        update_signal_quality_score(supabase, card_id)
                    except Exception as e:
                        logger.warning(
                            f"Failed to update signal quality score for {card_id}: {e}"
                        )
            except Exception as e:
                logger.warning(
                    f"Failed to import signal quality module during bulk review: {e}"
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
    current_user: dict = Depends(get_current_user),
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
    # Verify card exists
    card_check = supabase.table("cards").select("id, name").eq("id", card_id).execute()
    if not card_check.data:
        raise HTTPException(status_code=404, detail="Card not found")

    card = card_check.data[0]
    now = datetime.now().isoformat()

    # Check if user already dismissed this card
    existing = (
        supabase.table("user_card_dismissals")
        .select("id")
        .eq("user_id", current_user["id"])
        .eq("card_id", card_id)
        .execute()
    )

    if existing.data:
        raise HTTPException(status_code=400, detail="Card already dismissed by user")

    # Create dismissal record
    dismissal_record = {
        "user_id": current_user["id"],
        "card_id": card_id,
        "reason": dismiss_data.reason if dismiss_data else None,
        "dismissed_at": now,
    }
    supabase.table("user_card_dismissals").insert(dismissal_record).execute()

    # Check total dismissal count for this card
    dismissal_count = (
        supabase.table("user_card_dismissals")
        .select("id", count="exact")
        .eq("card_id", card_id)
        .execute()
    )

    blocked = False
    if dismissal_count.count >= 3:
        # Add to discovery_blocks if not already blocked
        block_check = (
            supabase.table("discovery_blocks")
            .select("id")
            .eq("card_id", card_id)
            .execute()
        )

        if not block_check.data:
            block_record = {
                "card_id": card_id,
                "topic_pattern": card["name"].lower(),
                "reason": "Dismissed by multiple users",
                "blocked_by_count": dismissal_count.count,
                "created_at": now,
            }
            supabase.table("discovery_blocks").insert(block_record).execute()
            blocked = True
            logger.info(
                f"Card {card_id} blocked from discovery after {dismissal_count.count} dismissals"
            )

    return {
        "status": "dismissed",
        "card_id": card_id,
        "blocked": blocked,
        "total_dismissals": dismissal_count.count,
    }
