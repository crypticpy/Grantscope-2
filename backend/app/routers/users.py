"""User profile router."""

import logging
import uuid as _uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, get_current_user, _safe_error
from app.models.core import UserProfile, ProfileSetupUpdate
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


async def _get_or_create_user(db: AsyncSession, current_user: dict) -> User:
    """Fetch the User row from the DB, creating it if absent."""
    user_uuid = _uuid.UUID(current_user["id"])
    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()
    if user:
        return user
    # First-time DB access for this hardcoded user — seed a row
    user = User(
        id=user_uuid,
        email=current_user.get("email", ""),
        display_name=current_user.get("display_name"),
        department=current_user.get("department"),
        role=current_user.get("role"),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@router.get("/me", response_model=UserProfile)
async def get_current_user_profile(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get current user profile from DB (falls back to hardcoded data)."""
    try:
        user = await _get_or_create_user(db, current_user)
        return UserProfile(**_row_to_dict(user))
    except Exception:
        # Fallback to hardcoded user data if DB is unreachable
        return UserProfile(**current_user)


PROFILE_FIELDS = {
    "display_name",
    "department",
    "role",
    "preferences",
    "department_id",
    "title",
    # Profile wizard fields
    "bio",
    "program_name",
    "program_mission",
    "team_size",
    "budget_range",
    "grant_experience",
    "grant_categories",
    "funding_range_min",
    "funding_range_max",
    "strategic_pillars",
    "priorities",
    "custom_priorities",
    "help_wanted",
    "update_frequency",
    "profile_completed_at",
    "profile_step",
}


@router.patch("/me", response_model=UserProfile)
async def update_user_profile(
    updates: ProfileSetupUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update user profile (upserts if no DB row exists)."""
    try:
        user = await _get_or_create_user(db, current_user)

        update_data = updates.model_dump(exclude_none=True)
        for key, value in update_data.items():
            if key in PROFILE_FIELDS and hasattr(user, key):
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


@router.get("/me/profile-completion")
async def get_profile_completion(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Return profile completion percentage and details."""
    try:
        user = await _get_or_create_user(db, current_user)

        completed_steps = []
        missing = []

        # Step 1 (25%): Identity — department_id + display_name
        if user.department_id and user.display_name:
            completed_steps.append(1)
        else:
            if not user.department_id:
                missing.append("department_id")
            if not user.display_name:
                missing.append("display_name")

        # Step 2 (25%): Program — program_name
        if user.program_name:
            completed_steps.append(2)
        else:
            missing.append("program_name")

        # Step 3 (25%): Grant interests — grant_experience + grant_categories
        if user.grant_experience and user.grant_categories:
            completed_steps.append(3)
        else:
            if not user.grant_experience:
                missing.append("grant_experience")
            if not user.grant_categories:
                missing.append("grant_categories")

        # Step 4 (25%): Priorities — priorities or custom_priorities
        if (user.priorities and len(user.priorities) > 0) or user.custom_priorities:
            completed_steps.append(4)
        else:
            missing.append("priorities")

        percentage = len(completed_steps) * 25

        return {
            "percentage": percentage,
            "completed_steps": completed_steps,
            "missing": missing,
            "is_complete": user.profile_completed_at is not None,
        }
    except Exception as e:
        logger.error(f"Failed to get profile completion: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=_safe_error("profile completion", e),
        ) from e
