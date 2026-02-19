"""Shared user profile utilities for the chat package.

Provides centralized profile loading and completion calculation
to ensure consistency across tool handlers and the grant assistant.
"""

from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.user import User


async def load_user_profile(db: AsyncSession, user_id_uuid) -> Dict[str, Any] | None:
    """Load user profile fields relevant to grant operations.

    Returns None if user not found, otherwise a dict with profile fields.
    """
    user_result = await db.execute(select(User).where(User.id == user_id_uuid))
    user_obj = user_result.scalar_one_or_none()
    if user_obj is None:
        return None

    profile: Dict[str, Any] = {}
    for field_name in [
        "department",
        "department_id",
        "display_name",
        "program_name",
        "program_mission",
        "grant_categories",
        "strategic_pillars",
        "priorities",
        "custom_priorities",
        "funding_range_min",
        "funding_range_max",
        "grant_experience",
        "team_size",
        "budget_range",
        "help_wanted",
    ]:
        val = getattr(user_obj, field_name, None)
        if val is not None:
            profile[field_name] = list(val) if isinstance(val, list) else val

    # Include profile_completed_at for completion check
    profile["_profile_completed_at"] = user_obj.profile_completed_at

    return profile


def compute_profile_completion(profile: Dict[str, Any]) -> tuple[int, List[str]]:
    """Compute profile completion percentage and missing fields.

    Uses the canonical 4-step model (25% each), matching the
    /me/profile-completion router endpoint.

    Returns (percentage, missing_fields).
    """
    completed_steps: List[int] = []
    missing: List[str] = []

    # Step 1 (25%): Identity -- department_id + display_name
    if profile.get("department_id") and profile.get("display_name"):
        completed_steps.append(1)
    else:
        if not profile.get("department_id"):
            missing.append("department_id")
        if not profile.get("display_name"):
            missing.append("display_name")

    # Step 2 (25%): Program -- program_name
    if profile.get("program_name"):
        completed_steps.append(2)
    else:
        missing.append("program_name")

    # Step 3 (25%): Grant interests -- grant_experience + grant_categories
    if profile.get("grant_experience") and profile.get("grant_categories"):
        completed_steps.append(3)
    else:
        if not profile.get("grant_experience"):
            missing.append("grant_experience")
        if not profile.get("grant_categories"):
            missing.append("grant_categories")

    # Step 4 (25%): Priorities -- priorities or custom_priorities
    priorities = profile.get("priorities")
    if (priorities and len(priorities) > 0) or profile.get("custom_priorities"):
        completed_steps.append(4)
    else:
        missing.append("priorities")

    return len(completed_steps) * 25, missing
