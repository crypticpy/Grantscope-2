"""Notification preferences and digest preview router.

Migrated from Supabase PostgREST to SQLAlchemy 2.0 async.
"""

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import (
    get_db,
    get_current_user_hardcoded,
    _safe_error,
    openai_client,
)
from app.models.db.notification import NotificationPreference
from app.models.notification import (
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate,
    DigestPreviewResponse,
)
from app.digest_service import DigestService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["notifications"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_dict(obj, skip_cols=None) -> dict:
    """Convert an ORM model instance to a plain dict with JSON-safe values."""
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


# ============================================================================
# Notification Preferences
# ============================================================================


@router.get(
    "/me/notification-preferences",
    response_model=NotificationPreferencesResponse,
)
async def get_notification_preferences(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Get current user's notification preferences.

    Creates default preferences if none exist yet.
    """
    user_id = current_user["id"]
    try:
        result = await db.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_id == uuid.UUID(user_id)
            )
        )
        item = result.scalar_one_or_none()

        if item is not None:
            return NotificationPreferencesResponse(**_row_to_dict(item))

        # Create default preferences for this user
        now = datetime.now(timezone.utc)
        item = NotificationPreference(
            user_id=uuid.UUID(user_id),
            notification_email=None,
            digest_frequency="weekly",
            digest_day="monday",
            include_new_signals=True,
            include_velocity_changes=True,
            include_pattern_insights=True,
            include_workstream_updates=True,
            created_at=now,
            updated_at=now,
        )
        db.add(item)
        await db.flush()
        await db.refresh(item)

        return NotificationPreferencesResponse(**_row_to_dict(item))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get notification preferences for user %s: %s", user_id, e
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("notification preferences retrieval", e),
        ) from e


@router.put(
    "/me/notification-preferences",
    response_model=NotificationPreferencesResponse,
)
async def update_notification_preferences(
    updates: NotificationPreferencesUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Update notification preferences.

    Sets the user's preferred notification email, digest frequency,
    and content inclusion settings. The notification_email field is
    separate from the login email, allowing users with test/fake
    auth emails to receive digests at their real address.
    """
    user_id = current_user["id"]
    try:
        # Check for existing preferences
        result = await db.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_id == uuid.UUID(user_id)
            )
        )
        item = result.scalar_one_or_none()

        # Build update dict -- include notification_email even if None (to allow clearing)
        update_data = {
            k: v
            for k, v in updates.dict(exclude_unset=True).items()
            if v is not None or k == "notification_email"
        }

        now = datetime.now(timezone.utc)

        if item is not None:
            # Update existing row
            for key, value in update_data.items():
                setattr(item, key, value)
            item.updated_at = now
        else:
            # Create new row with updates
            item = NotificationPreference(
                user_id=uuid.UUID(user_id),
                created_at=now,
                updated_at=now,
                **update_data,
            )
            db.add(item)

        await db.flush()
        await db.refresh(item)

        return NotificationPreferencesResponse(**_row_to_dict(item))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to update notification preferences for user %s: %s", user_id, e
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("notification preferences update", e),
        ) from e


@router.post("/me/digest/preview", response_model=DigestPreviewResponse)
async def preview_digest(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Generate a preview of what the next digest email would look like.

    This endpoint generates the digest content without sending it,
    allowing users to see what they will receive and verify their
    notification email before enabling the digest.
    """
    user_id = current_user["id"]
    try:
        digest_service = DigestService(db, openai_client)
        result = await digest_service.generate_user_digest(user_id)

        if not result:
            # If no content, generate a sample/empty digest
            return DigestPreviewResponse(
                subject="Your GrantScope2 Intelligence Digest -- Preview",
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
        logger.error("Failed to generate digest preview for user %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("digest preview generation", e),
        ) from e
