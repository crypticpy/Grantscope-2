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

from app.chat.profile_utils import compute_profile_completion, load_user_profile
from app.chat.tools import ToolDefinition, registry
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

        profile = await load_user_profile(db, user_uuid)

        if profile is None:
            return {
                "error": "User profile not found. Please set up your profile first.",
            }

        percentage, missing = compute_profile_completion(profile)

        # Strip internal keys before returning profile data
        profile_data = {k: v for k, v in profile.items() if not k.startswith("_")}

        return {
            "completion_percentage": percentage,
            "missing_fields": missing,
            "is_complete": (
                profile.get("_profile_completed_at") is not None or percentage == 100
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
