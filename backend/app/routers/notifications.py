"""Notification preferences and digest preview router."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from app.deps import supabase, get_current_user, openai_client, _safe_error
from app.models.notification import (
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate,
    DigestPreviewResponse,
)
from app.digest_service import DigestService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["notifications"])


@router.get(
    "/me/notification-preferences",
    response_model=NotificationPreferencesResponse,
)
async def get_notification_preferences(
    current_user: dict = Depends(get_current_user),
):
    """Get current user's notification preferences.

    Creates default preferences if none exist yet.
    """
    user_id = current_user["id"]
    try:
        response = (
            supabase.table("notification_preferences")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )

        if response.data:
            return NotificationPreferencesResponse(**response.data[0])

        # Create default preferences for this user
        now = datetime.now(timezone.utc).isoformat()
        default_prefs = {
            "user_id": user_id,
            "notification_email": None,
            "digest_frequency": "weekly",
            "digest_day": "monday",
            "include_new_signals": True,
            "include_velocity_changes": True,
            "include_pattern_insights": True,
            "include_workstream_updates": True,
            "created_at": now,
            "updated_at": now,
        }
        insert_resp = (
            supabase.table("notification_preferences").insert(default_prefs).execute()
        )
        if insert_resp.data:
            return NotificationPreferencesResponse(**insert_resp.data[0])

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create default notification preferences",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get notification preferences for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("notification preferences retrieval", e),
        )


@router.put(
    "/me/notification-preferences",
    response_model=NotificationPreferencesResponse,
)
async def update_notification_preferences(
    updates: NotificationPreferencesUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Update notification preferences.

    Sets the user's preferred notification email, digest frequency,
    and content inclusion settings. The notification_email field is
    separate from the login email, allowing users with test/fake
    auth emails to receive digests at their real address.
    """
    user_id = current_user["id"]
    try:
        # Ensure preferences row exists (upsert pattern)
        existing = (
            supabase.table("notification_preferences")
            .select("id")
            .eq("user_id", user_id)
            .execute()
        )

        update_data = {
            k: v
            for k, v in updates.dict(exclude_unset=True).items()
            if v is not None or k == "notification_email"
        }
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()

        if existing.data:
            # Update existing row
            response = (
                supabase.table("notification_preferences")
                .update(update_data)
                .eq("user_id", user_id)
                .execute()
            )
        else:
            # Create new row with updates
            update_data["user_id"] = user_id
            update_data["created_at"] = datetime.now(timezone.utc).isoformat()
            response = (
                supabase.table("notification_preferences").insert(update_data).execute()
            )

        if response.data:
            return NotificationPreferencesResponse(**response.data[0])

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update notification preferences",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to update notification preferences for user {user_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("notification preferences update", e),
        )


@router.post("/me/digest/preview", response_model=DigestPreviewResponse)
async def preview_digest(
    current_user: dict = Depends(get_current_user),
):
    """Generate a preview of what the next digest email would look like.

    This endpoint generates the digest content without sending it,
    allowing users to see what they will receive and verify their
    notification email before enabling the digest.
    """
    user_id = current_user["id"]
    try:
        digest_service = DigestService(supabase, openai_client)
        result = await digest_service.generate_user_digest(user_id)

        if not result:
            # If no content, generate a sample/empty digest
            return DigestPreviewResponse(
                subject="Your Foresight Intelligence Digest — Preview",
                html_content=(
                    "<html><body><p>No new activity to report for this period. "
                    "Follow more signals or add cards to your workstreams to "
                    "receive digest updates.</p></body></html>"
                ),
                summary_json={"sections": {}, "note": "No activity in period"},
                sections_included=[],
            )

        return DigestPreviewResponse(**result)
    except Exception as e:
        logger.error(f"Failed to generate digest preview for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("digest preview generation", e),
        )
