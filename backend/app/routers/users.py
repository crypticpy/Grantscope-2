"""User profile router."""

import logging
import uuid as _uuid
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, get_current_user, _safe_error
from app.models.core import UserProfile
from app.models.db.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["users"])


# ---------------------------------------------------------------------------
# Helper: ORM row -> dict (safe JSON-serialisable conversion)
# ---------------------------------------------------------------------------


def _row_to_dict(obj, skip_cols=None) -> dict:
    skip = skip_cols or set()
    result = {}
    for col in obj.__table__.columns:
        if col.name in skip:
            continue
        value = getattr(obj, col.name, None)
        if isinstance(value, _uuid.UUID):
            result[col.name] = str(value)
        elif isinstance(value, (datetime, date)):
            result[col.name] = value.isoformat()
        elif isinstance(value, Decimal):
            result[col.name] = float(value)
        else:
            result[col.name] = value
    return result


@router.get("/me", response_model=UserProfile)
async def get_current_user_profile(current_user: dict = Depends(get_current_user)):
    """Get current user profile"""
    return UserProfile(**current_user)


@router.patch("/me", response_model=UserProfile)
async def update_user_profile(
    updates: dict,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update user profile"""
    try:
        user_uuid = _uuid.UUID(current_user["id"])

        result = await db.execute(select(User).where(User.id == user_uuid))
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Apply updates to the ORM object
        allowed_fields = {
            "display_name",
            "department",
            "role",
            "preferences",
            "department_id",
            "title",
        }
        for key, value in updates.items():
            if key in allowed_fields and hasattr(user, key):
                setattr(user, key, value)

        await db.flush()
        await db.refresh(user)

        user_dict = _row_to_dict(user)
        return UserProfile(**user_dict)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update user profile: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=_safe_error("user profile update", e),
        ) from e
