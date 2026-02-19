"""User context tools for checking profile and programs.

Provides tools that let the grant assistant inspect the current
user's profile completion status and their list of programs
(workstreams) with card counts.
"""

from __future__ import annotations

import logging
import uuid as _uuid
from typing import Any, Dict, List

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.tools import ToolDefinition, registry
from app.models.db.user import User
from app.models.db.workstream import Workstream, WorkstreamCard

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool 11: check_user_programs
# ---------------------------------------------------------------------------


async def _handle_check_user_programs(
    db: AsyncSession, user_id: str, **kwargs: Any
) -> dict:
    """List the user's programs (workstreams) with card counts.

    Args:
        db: Async database session.
        user_id: Authenticated user UUID string.
        **kwargs: Unused (no parameters for this tool).

    Returns:
        Dict with ``programs`` list containing id, name, description,
        card_count, pillar_ids, keywords, and is_active for each.
    """
    try:
        try:
            user_uuid = _uuid.UUID(user_id)
        except ValueError:
            return {"error": "Invalid user ID format."}

        # Fetch all workstreams for this user
        ws_result = await db.execute(
            select(Workstream).where(Workstream.user_id == user_uuid)
        )
        workstreams = ws_result.scalars().all()

        # Batch count cards per workstream (avoids N+1 queries)
        ws_ids = [ws.id for ws in workstreams]
        count_map: Dict[str, int] = {}
        if ws_ids:
            counts_result = await db.execute(
                select(
                    WorkstreamCard.workstream_id,
                    func.count(WorkstreamCard.id),
                )
                .where(WorkstreamCard.workstream_id.in_(ws_ids))
                .group_by(WorkstreamCard.workstream_id)
            )
            count_map = {str(r[0]): r[1] for r in counts_result.all()}

        programs: List[Dict[str, Any]] = []

        for ws in workstreams:
            card_count = count_map.get(str(ws.id), 0)

            programs.append(
                {
                    "id": str(ws.id),
                    "name": ws.name,
                    "description": ws.description,
                    "card_count": card_count,
                    "pillar_ids": ws.pillar_ids or [],
                    "keywords": ws.keywords or [],
                    "is_active": ws.is_active if ws.is_active is not None else True,
                }
            )

        return {"programs": programs, "count": len(programs)}

    except Exception as exc:
        logger.exception("check_user_programs failed: %s", exc)
        return {"error": "Failed to retrieve your programs. Please try again."}


registry.register(
    ToolDefinition(
        name="check_user_programs",
        description=(
            "List all of the current user's grant tracking programs "
            "(workstreams), including the number of opportunities in each "
            "program, associated pillars, and keywords."
        ),
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
        handler=_handle_check_user_programs,
        requires_online=False,
    )
)


# ---------------------------------------------------------------------------
# Tool 12: check_user_profile
# ---------------------------------------------------------------------------


async def _handle_check_user_profile(
    db: AsyncSession, user_id: str, **kwargs: Any
) -> dict:
    """Check the user's profile data and completion percentage.

    Uses the same completion logic as the /me/profile-completion
    endpoint: four steps of 25% each covering identity, program,
    grant interests, and priorities.

    Args:
        db: Async database session.
        user_id: Authenticated user UUID string.
        **kwargs: Unused (no parameters for this tool).

    Returns:
        Dict with completion_percentage, missing_fields, and profile_data.
    """
    try:
        try:
            user_uuid = _uuid.UUID(user_id)
        except ValueError:
            return {"error": "Invalid user ID format."}

        user_result = await db.execute(select(User).where(User.id == user_uuid))
        user_obj = user_result.scalar_one_or_none()

        if user_obj is None:
            return {
                "error": "User profile not found. Please set up your profile first.",
            }

        # Compute profile completion (same logic as routers/users.py)
        completed_steps: List[int] = []
        missing: List[str] = []

        # Step 1 (25%): Identity -- department_id + display_name
        if user_obj.department_id and user_obj.display_name:
            completed_steps.append(1)
        else:
            if not user_obj.department_id:
                missing.append("department_id")
            if not user_obj.display_name:
                missing.append("display_name")

        # Step 2 (25%): Program -- program_name
        if user_obj.program_name:
            completed_steps.append(2)
        else:
            missing.append("program_name")

        # Step 3 (25%): Grant interests -- grant_experience + grant_categories
        if user_obj.grant_experience and user_obj.grant_categories:
            completed_steps.append(3)
        else:
            if not user_obj.grant_experience:
                missing.append("grant_experience")
            if not user_obj.grant_categories:
                missing.append("grant_categories")

        # Step 4 (25%): Priorities -- priorities or custom_priorities
        if (
            user_obj.priorities and len(user_obj.priorities) > 0
        ) or user_obj.custom_priorities:
            completed_steps.append(4)
        else:
            missing.append("priorities")

        percentage = len(completed_steps) * 25

        # Build profile data dict
        profile_data: Dict[str, Any] = {}
        for field_name in [
            "department",
            "department_id",
            "program_name",
            "program_mission",
            "grant_categories",
            "strategic_pillars",
            "priorities",
            "funding_range_min",
            "funding_range_max",
            "grant_experience",
            "team_size",
            "budget_range",
        ]:
            val = getattr(user_obj, field_name, None)
            if val is not None:
                if isinstance(val, list):
                    profile_data[field_name] = list(val)
                else:
                    profile_data[field_name] = val

        return {
            "completion_percentage": percentage,
            "missing_fields": missing,
            "is_complete": (
                user_obj.profile_completed_at is not None or percentage == 100
            ),
            "profile_data": profile_data,
        }

    except Exception as exc:
        logger.exception("check_user_profile failed: %s", exc)
        return {"error": "Failed to retrieve your profile. Please try again."}


registry.register(
    ToolDefinition(
        name="check_user_profile",
        description=(
            "Check the current user's profile completion status and data. "
            "Returns the completion percentage, list of missing fields, "
            "and current profile data including department, program, "
            "grant preferences, and strategic priorities."
        ),
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
        handler=_handle_check_user_profile,
        requires_online=False,
    )
)
