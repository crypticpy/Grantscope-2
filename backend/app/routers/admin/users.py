"""User management admin endpoints.

Provides CRUD operations for managing platform users, including creation,
listing, updating, and password resets.  All endpoints require admin-level
authentication via ``require_admin``.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import HARDCODED_USERS, _hash_password
from app.chat.admin_deps import require_admin
from app.deps import get_db
from app.models.db.card import Card
from app.models.db.research import ResearchTask
from app.models.db.user import User
from app.models.db.workstream import Workstream
from app.routers.admin._helpers import _row_to_dict

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Pydantic request / response models
# ---------------------------------------------------------------------------


class UserListResponse(BaseModel):
    users: list[dict]
    total: int
    page: int
    page_size: int


class CreateUserRequest(BaseModel):
    email: str
    display_name: str = ""
    role: str = "user"
    password: str = Field(..., min_length=8)


class UpdateUserRequest(BaseModel):
    display_name: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    department_id: Optional[str] = None
    title: Optional[str] = None
    is_active: Optional[bool] = None


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=8)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SKIP_COLS = {"preferences"}  # large JSONB blobs omitted from list views


def _user_dict(user: User, *, verbose: bool = False) -> dict:
    """Convert a User ORM instance to a JSON-safe dict.

    Always excludes ``hashed_password`` (which doesn't exist on the ORM model
    but guards against future additions).  When *verbose* is False the large
    ``preferences`` JSONB column is also excluded.
    """
    skip = set() if verbose else _SKIP_COLS
    return _row_to_dict(user, skip_cols=skip)


# ---------------------------------------------------------------------------
# GET /admin/users -- paginated list with optional search
# ---------------------------------------------------------------------------


@router.get("/admin/users", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Filter by email or display_name"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Return a paginated list of all users.

    An optional *search* query parameter performs a case-insensitive ILIKE
    match against ``email`` and ``display_name``.
    """
    try:
        # Base query
        base_q = select(User)
        count_q = select(func.count()).select_from(User)

        if search:
            pattern = f"%{search}%"
            filter_clause = or_(
                User.email.ilike(pattern),
                User.display_name.ilike(pattern),
            )
            base_q = base_q.where(filter_clause)
            count_q = count_q.where(filter_clause)

        # Total count
        total_result = await db.execute(count_q)
        total = total_result.scalar() or 0

        # Paginated rows
        offset = (page - 1) * page_size
        rows_q = (
            base_q.order_by(User.created_at.desc().nullslast())
            .offset(offset)
            .limit(page_size)
        )
        result = await db.execute(rows_q)
        users = result.scalars().all()

        return UserListResponse(
            users=[_user_dict(u) for u in users],
            total=total,
            page=page,
            page_size=page_size,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to list users")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list users. Please try again or contact support.",
        ) from e


# ---------------------------------------------------------------------------
# GET /admin/users/{user_id} -- single user with activity stats
# ---------------------------------------------------------------------------


@router.get("/admin/users/{user_id}")
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Return detailed information for a single user including activity stats.

    Computed stats:
    - ``cards_count``: number of cards created by the user
    - ``workstreams_count``: number of workstreams owned by the user
    - ``research_tasks_count``: number of research tasks initiated
    - ``last_activity``: most recent timestamp across cards, workstreams,
      and research tasks
    """
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid user ID format: {user_id}",
        )

    try:
        # Fetch user row
        result = await db.execute(select(User).where(User.id == uid))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found",
            )

        user_data = _user_dict(user, verbose=True)

        # Activity stats -- simple count queries
        cards_count_q = (
            select(func.count()).select_from(Card).where(Card.created_by == uid)
        )
        workstreams_count_q = (
            select(func.count())
            .select_from(Workstream)
            .where(Workstream.user_id == uid)
        )
        research_count_q = (
            select(func.count())
            .select_from(ResearchTask)
            .where(ResearchTask.user_id == uid)
        )

        # Last activity: max of the most recent timestamps across tables
        last_card_q = select(func.max(Card.created_at)).where(Card.created_by == uid)
        last_workstream_q = select(func.max(Workstream.created_at)).where(
            Workstream.user_id == uid
        )
        last_research_q = select(func.max(ResearchTask.created_at)).where(
            ResearchTask.user_id == uid
        )

        # Execute all stat queries
        cards_result = await db.execute(cards_count_q)
        workstreams_result = await db.execute(workstreams_count_q)
        research_result = await db.execute(research_count_q)
        last_card_result = await db.execute(last_card_q)
        last_workstream_result = await db.execute(last_workstream_q)
        last_research_result = await db.execute(last_research_q)

        cards_count = cards_result.scalar() or 0
        workstreams_count = workstreams_result.scalar() or 0
        research_tasks_count = research_result.scalar() or 0

        # Determine the latest activity timestamp
        timestamps = [
            ts
            for ts in [
                last_card_result.scalar(),
                last_workstream_result.scalar(),
                last_research_result.scalar(),
            ]
            if ts is not None
        ]
        last_activity = max(timestamps).isoformat() if timestamps else None

        user_data["stats"] = {
            "cards_count": cards_count,
            "workstreams_count": workstreams_count,
            "research_tasks_count": research_tasks_count,
            "last_activity": last_activity,
        }

        return user_data

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to fetch user %s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch user details. Please try again or contact support.",
        ) from e


# ---------------------------------------------------------------------------
# POST /admin/users -- create a new user
# ---------------------------------------------------------------------------


@router.post("/admin/users", status_code=status.HTTP_201_CREATED)
async def create_user(
    body: CreateUserRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Create a new user account.

    The user is inserted into the ``users`` database table **and** added to
    the runtime ``HARDCODED_USERS`` dictionary so that they can authenticate
    immediately without a server restart.
    """
    email = body.email.lower().strip()
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is required",
        )

    try:
        # Check email uniqueness in HARDCODED_USERS
        if email in HARDCODED_USERS:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A user with email '{email}' already exists (runtime)",
            )

        # Check email uniqueness in DB
        existing = await db.execute(
            select(func.count()).select_from(User).where(User.email == email)
        )
        if (existing.scalar() or 0) > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A user with email '{email}' already exists",
            )

        # Generate a new user ID
        new_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        # Insert into DB
        new_user = User(
            id=new_id,
            email=email,
            display_name=body.display_name or email.split("@")[0],
            role=body.role,
            department=None,
            created_at=now,
            updated_at=now,
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)

        # Add to HARDCODED_USERS so they can log in immediately
        hashed = _hash_password(body.password)
        HARDCODED_USERS[email] = {
            "id": str(new_id),
            "email": email,
            "display_name": new_user.display_name,
            "department": new_user.department or "",
            "role": body.role,
            "hashed_password": hashed,
            "created_at": now.isoformat(),
        }

        logger.info(
            "Admin %s created new user %s (%s)",
            current_user.get("email"),
            email,
            new_id,
        )

        return _user_dict(new_user)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to create user %s", email)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user. Please try again or contact support.",
        ) from e


# ---------------------------------------------------------------------------
# PATCH /admin/users/{user_id} -- update user fields
# ---------------------------------------------------------------------------


@router.patch("/admin/users/{user_id}")
async def update_user(
    user_id: str,
    body: UpdateUserRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Update mutable fields on an existing user.

    Only fields explicitly provided in the request body are modified;
    ``None`` values are skipped.  Changes are propagated to the runtime
    ``HARDCODED_USERS`` dictionary when applicable.
    """
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid user ID format: {user_id}",
        )

    try:
        result = await db.execute(select(User).where(User.id == uid))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found",
            )

        # Apply updates only for provided (non-None) fields
        update_fields = body.model_dump(exclude_unset=True)
        if not update_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update",
            )

        # Map of request field -> ORM attribute (is_active is not on the model,
        # but we handle it gracefully below)
        orm_fields = {"display_name", "role", "department", "department_id", "title"}

        for field_name, value in update_fields.items():
            if field_name in orm_fields and hasattr(user, field_name):
                setattr(user, field_name, value)

        user.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(user)

        # Propagate changes to HARDCODED_USERS if this user exists there
        user_email = user.email
        if user_email in HARDCODED_USERS:
            hc = HARDCODED_USERS[user_email]
            if "display_name" in update_fields:
                hc["display_name"] = update_fields["display_name"]
            if "role" in update_fields:
                hc["role"] = update_fields["role"]
            if "department" in update_fields:
                hc["department"] = update_fields["department"]

        logger.info(
            "Admin %s updated user %s (fields: %s)",
            current_user.get("email"),
            user_email,
            list(update_fields.keys()),
        )

        return _user_dict(user)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to update user %s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user. Please try again or contact support.",
        ) from e


# ---------------------------------------------------------------------------
# POST /admin/users/{user_id}/reset-password
# ---------------------------------------------------------------------------


@router.post("/admin/users/{user_id}/reset-password")
async def reset_password(
    user_id: str,
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Reset a user's password.

    Because the ``users`` database table does **not** store password hashes,
    this endpoint only updates the runtime ``HARDCODED_USERS`` dictionary.
    The change will **not** persist across server restarts unless the user
    is also defined in the hardcoded seed data in ``auth.py``.

    A warning is logged to make operators aware of this limitation.
    """
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid user ID format: {user_id}",
        )

    try:
        # Verify the user exists in the DB
        result = await db.execute(select(User).where(User.id == uid))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found",
            )

        user_email = user.email
        hashed = _hash_password(body.new_password)

        # Update runtime dict if user is there
        if user_email in HARDCODED_USERS:
            HARDCODED_USERS[user_email]["hashed_password"] = hashed
            logger.info(
                "Admin %s reset password for user %s (runtime dict updated)",
                current_user.get("email"),
                user_email,
            )
        else:
            logger.warning(
                "Admin %s reset password for user %s, but user is NOT in "
                "HARDCODED_USERS -- they may not be able to log in until "
                "added to the runtime dict (e.g. via POST /admin/users or "
                "server restart with updated seed data).",
                current_user.get("email"),
                user_email,
            )

        logger.warning(
            "Password reset for %s does NOT persist across server restarts. "
            "Update the hardcoded seed data in auth.py or migrate to a "
            "persistent credential store.",
            user_email,
        )

        return {
            "status": "ok",
            "message": f"Password reset for {user_email}",
            "persisted": False,
            "warning": (
                "Password change is runtime-only and will not persist across "
                "server restarts. Update auth.py seed data or use a persistent "
                "credential store for permanent changes."
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to reset password for user %s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset password. Please try again or contact support.",
        ) from e
