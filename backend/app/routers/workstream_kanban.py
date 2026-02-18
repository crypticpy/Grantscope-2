"""Workstream kanban card management router.

Migrated from Supabase PostgREST to SQLAlchemy 2.0 async.
"""

import logging
import uuid
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, get_current_user_hardcoded, _safe_error
from app.models.workstream import (
    WorkstreamCardBase,
    WorkstreamCardWithDetails,
    WorkstreamCardCreate,
    WorkstreamCardUpdate,
    WorkstreamCardsGroupedResponse,
    VALID_WORKSTREAM_CARD_STATUSES,
    WorkstreamResearchStatus,
    WorkstreamResearchStatusResponse,
)
from app.models.research import ResearchTask as ResearchTaskSchema
from app.models.db.workstream import Workstream, WorkstreamCard
from app.models.db.card import Card
from app.models.db.research import ResearchTask

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["workstream-kanban"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_dict(obj, skip_cols=None) -> dict:
    """Convert an ORM model instance to a plain dict, serialising
    UUID / datetime / Decimal values so they are JSON-friendly."""
    skip = skip_cols or set()
    result = {}
    for col in obj.__table__.columns:
        if col.name in skip:
            continue
        value = getattr(obj, col.key, None)
        if isinstance(value, uuid.UUID):
            result[col.name] = str(value)
        elif isinstance(value, (datetime, date)):
            result[col.name] = value.isoformat()
        elif isinstance(value, Decimal):
            result[col.name] = float(value)
        else:
            result[col.name] = value
    return result


def _wsc_to_response(
    wsc: WorkstreamCard, card_dict: Optional[dict] = None
) -> WorkstreamCardWithDetails:
    """Build a WorkstreamCardWithDetails from a WorkstreamCard ORM row."""
    return WorkstreamCardWithDetails(
        id=str(wsc.id),
        workstream_id=str(wsc.workstream_id) if wsc.workstream_id else "",
        card_id=str(wsc.card_id) if wsc.card_id else "",
        added_by=str(wsc.added_by) if wsc.added_by else "",
        added_at=wsc.added_at,
        status=wsc.status or "inbox",
        position=wsc.position or 0,
        notes=wsc.notes,
        reminder_at=wsc.reminder_at,
        added_from=wsc.added_from or "manual",
        updated_at=wsc.updated_at,
        card=card_dict,
    )


async def _verify_workstream_ownership(
    db: AsyncSession, workstream_id: str, user_id: str, action: str = "access"
) -> Workstream:
    """Verify the workstream exists and belongs to the current user.

    Returns the Workstream ORM object on success.
    Raises HTTPException 404/403 on failure.
    """
    result = await db.execute(
        select(Workstream).where(Workstream.id == uuid.UUID(workstream_id))
    )
    ws = result.scalar_one_or_none()
    if ws is None:
        raise HTTPException(status_code=404, detail="Workstream not found")
    if str(ws.user_id) != user_id:
        raise HTTPException(
            status_code=403, detail=f"Not authorized to {action} this workstream"
        )
    return ws


# ============================================================================
# GET  /me/workstreams/{workstream_id}/cards  (Kanban view)
# ============================================================================


@router.get(
    "/me/workstreams/{workstream_id}/cards",
    response_model=WorkstreamCardsGroupedResponse,
)
@router.get(
    "/me/programs/{workstream_id}/cards",
    response_model=WorkstreamCardsGroupedResponse,
)
async def get_workstream_cards(
    workstream_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Get all cards in a workstream grouped by status (Kanban view).

    Returns cards organized into columns:
    - inbox: Newly added cards awaiting review
    - screening: Cards being screened for relevance
    - research: Cards actively being researched
    - brief: Cards with completed briefs
    - watching: Cards being monitored for updates
    - archived: Archived cards
    - discovered: New grant opportunity identified by system
    - evaluating: Under review for fit and feasibility
    - applying: Actively preparing application
    - submitted: Application submitted, awaiting decision
    - awarded: Grant awarded
    - declined: Application not selected or opportunity passed
    - expired: Deadline passed without application

    Each card includes full card details joined from the cards table.

    Args:
        workstream_id: UUID of the workstream
        current_user: Authenticated user (injected)

    Returns:
        WorkstreamCardsGroupedResponse with cards grouped by status

    Raises:
        HTTPException 404: Workstream not found or not owned by user
    """
    try:
        await _verify_workstream_ownership(db, workstream_id, current_user["id"])

        # Fetch all workstream_cards + joined card details, ordered by position
        ws_uuid = uuid.UUID(workstream_id)
        result = await db.execute(
            select(WorkstreamCard, Card)
            .outerjoin(Card, WorkstreamCard.card_id == Card.id)
            .where(WorkstreamCard.workstream_id == ws_uuid)
            .order_by(WorkstreamCard.position)
        )
        rows = result.all()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error("fetching workstream cards", e),
        ) from e

    # Group cards by status -- dynamically built from the full status set
    grouped: Dict[str, list] = {status: [] for status in VALID_WORKSTREAM_CARD_STATUSES}

    for wsc, card_obj in rows:
        card_status = wsc.status or "inbox"
        if card_status not in grouped:
            card_status = "inbox"

        card_dict = (
            _row_to_dict(card_obj, skip_cols={"embedding", "search_vector"})
            if card_obj
            else None
        )
        grouped[card_status].append(_wsc_to_response(wsc, card_dict))

    return WorkstreamCardsGroupedResponse(**grouped)


# ============================================================================
# POST /me/workstreams/{workstream_id}/cards  (add card)
# ============================================================================


@router.post(
    "/me/workstreams/{workstream_id}/cards",
    response_model=WorkstreamCardWithDetails,
)
@router.post(
    "/me/programs/{workstream_id}/cards",
    response_model=WorkstreamCardWithDetails,
)
async def add_card_to_workstream(
    workstream_id: str,
    card_data: WorkstreamCardCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Add a card to a workstream.

    The card will be added with the specified status (defaults to 'inbox')
    and positioned at the end of that column.

    Args:
        workstream_id: UUID of the workstream
        card_data: Card addition request (card_id, optional status/notes)
        current_user: Authenticated user (injected)

    Returns:
        WorkstreamCardWithDetails with the created card association

    Raises:
        HTTPException 404: Workstream or card not found
        HTTPException 403: Not authorized
        HTTPException 409: Card already in workstream
    """
    try:
        await _verify_workstream_ownership(
            db, workstream_id, current_user["id"], action="add cards to"
        )

        ws_uuid = uuid.UUID(workstream_id)
        card_uuid = uuid.UUID(card_data.card_id)

        # Verify card exists
        card_result = await db.execute(select(Card).where(Card.id == card_uuid))
        card_obj = card_result.scalar_one_or_none()
        if card_obj is None:
            raise HTTPException(status_code=404, detail="Card not found")

        # Check if card is already in workstream
        existing_result = await db.execute(
            select(WorkstreamCard.id).where(
                WorkstreamCard.workstream_id == ws_uuid,
                WorkstreamCard.card_id == card_uuid,
            )
        )
        if existing_result.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=409, detail="Card is already in this workstream"
            )

        # Get max position for the target status column
        status = card_data.status or "inbox"
        pos_result = await db.execute(
            select(func.coalesce(func.max(WorkstreamCard.position), -1)).where(
                WorkstreamCard.workstream_id == ws_uuid,
                WorkstreamCard.status == status,
            )
        )
        next_position = (pos_result.scalar() or -1) + 1

        # Create workstream card record
        now = datetime.now(timezone.utc)
        new_wsc = WorkstreamCard(
            workstream_id=ws_uuid,
            card_id=card_uuid,
            added_by=uuid.UUID(current_user["id"]),
            added_at=now,
            status=status,
            position=next_position,
            notes=card_data.notes,
            added_from="manual",
            updated_at=now,
        )
        db.add(new_wsc)
        await db.flush()
        await db.refresh(new_wsc)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=_safe_error("adding card to workstream", e),
        ) from e

    card_dict = _row_to_dict(card_obj, skip_cols={"embedding", "search_vector"})
    return _wsc_to_response(new_wsc, card_dict)


# ============================================================================
# PATCH /me/workstreams/{workstream_id}/cards/{card_id}  (update card)
# ============================================================================


@router.patch(
    "/me/workstreams/{workstream_id}/cards/{card_id}",
    response_model=WorkstreamCardWithDetails,
)
@router.patch(
    "/me/programs/{workstream_id}/cards/{card_id}",
    response_model=WorkstreamCardWithDetails,
)
async def update_workstream_card(
    workstream_id: str,
    card_id: str,
    update_data: WorkstreamCardUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Update a workstream card's status, position, notes, or reminder.

    When changing status (moving to a different column), the card is placed
    at the end of the new column unless a specific position is provided.

    Args:
        workstream_id: UUID of the workstream
        card_id: UUID of the card
        update_data: Update request (status, position, notes, reminder_at)
        current_user: Authenticated user (injected)

    Returns:
        WorkstreamCardWithDetails with updated data

    Raises:
        HTTPException 404: Workstream or card not found
        HTTPException 403: Not authorized
    """
    try:
        await _verify_workstream_ownership(
            db, workstream_id, current_user["id"], action="update cards in"
        )

        ws_uuid = uuid.UUID(workstream_id)
        wsc_uuid = uuid.UUID(card_id)

        # Fetch the workstream card by its junction table ID
        # (card_id param is actually workstream_card.id)
        result = await db.execute(
            select(WorkstreamCard, Card)
            .outerjoin(Card, WorkstreamCard.card_id == Card.id)
            .where(
                WorkstreamCard.workstream_id == ws_uuid,
                WorkstreamCard.id == wsc_uuid,
            )
        )
        row = result.one_or_none()
        if row is None:
            raise HTTPException(
                status_code=404, detail="Card not found in this workstream"
            )

        wsc, card_obj = row

        # Apply updates
        wsc.updated_at = datetime.now(timezone.utc)

        if update_data.status is not None:
            if update_data.status != wsc.status:
                # Status changed -- recalculate position in new column
                pos_result = await db.execute(
                    select(func.coalesce(func.max(WorkstreamCard.position), -1)).where(
                        WorkstreamCard.workstream_id == ws_uuid,
                        WorkstreamCard.status == update_data.status,
                    )
                )
                next_position = (pos_result.scalar() or -1) + 1

                wsc.status = update_data.status
                wsc.position = (
                    update_data.position
                    if update_data.position is not None
                    else next_position
                )
            else:
                wsc.status = update_data.status
                if update_data.position is not None:
                    wsc.position = update_data.position
        elif update_data.position is not None:
            wsc.position = update_data.position

        if update_data.notes is not None:
            wsc.notes = update_data.notes

        if update_data.reminder_at is not None:
            wsc.reminder_at = update_data.reminder_at

        await db.flush()
        await db.refresh(wsc)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=_safe_error("updating workstream card", e),
        ) from e

    card_dict = (
        _row_to_dict(card_obj, skip_cols={"embedding", "search_vector"})
        if card_obj
        else None
    )
    return _wsc_to_response(wsc, card_dict)


# ============================================================================
# DELETE /me/workstreams/{workstream_id}/cards/{card_id}  (remove card)
# ============================================================================


@router.delete("/me/workstreams/{workstream_id}/cards/{card_id}")
@router.delete("/me/programs/{workstream_id}/cards/{card_id}")
async def remove_card_from_workstream(
    workstream_id: str,
    card_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Remove a card from a workstream.

    This only removes the association; the card itself is not deleted.

    Args:
        workstream_id: UUID of the workstream
        card_id: UUID of the card
        current_user: Authenticated user (injected)

    Returns:
        Success message

    Raises:
        HTTPException 404: Workstream or card not found
        HTTPException 403: Not authorized
    """
    try:
        await _verify_workstream_ownership(
            db, workstream_id, current_user["id"], action="remove cards from"
        )

        ws_uuid = uuid.UUID(workstream_id)
        wsc_uuid = uuid.UUID(card_id)

        # Check card exists in workstream (card_id param is workstream_card.id)
        result = await db.execute(
            select(WorkstreamCard).where(
                WorkstreamCard.workstream_id == ws_uuid,
                WorkstreamCard.id == wsc_uuid,
            )
        )
        wsc = result.scalar_one_or_none()
        if wsc is None:
            raise HTTPException(
                status_code=404, detail="Card not found in this workstream"
            )

        await db.delete(wsc)
        await db.flush()

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=_safe_error("removing card from workstream", e),
        ) from e

    return {"status": "removed", "message": "Card removed from workstream"}


# ============================================================================
# POST /me/workstreams/{workstream_id}/cards/{card_id}/deep-dive
# ============================================================================


@router.post(
    "/me/workstreams/{workstream_id}/cards/{card_id}/deep-dive",
    response_model=ResearchTaskSchema,
)
@router.post(
    "/me/programs/{workstream_id}/cards/{card_id}/deep-dive",
    response_model=ResearchTaskSchema,
)
async def trigger_card_deep_dive(
    workstream_id: str,
    card_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Trigger deep research for a card in the workstream.

    Creates a research task with task_type='deep_research' for the specified card.
    The research runs asynchronously; poll GET /research/{task_id} for status.

    Rate limited to 2 deep research requests per card per day.

    Args:
        workstream_id: UUID of the workstream
        card_id: UUID of the card
        current_user: Authenticated user (injected)

    Returns:
        ResearchTask with the created task details

    Raises:
        HTTPException 404: Workstream or card not found
        HTTPException 403: Not authorized
        HTTPException 429: Daily rate limit exceeded
    """
    try:
        await _verify_workstream_ownership(db, workstream_id, current_user["id"])

        ws_uuid = uuid.UUID(workstream_id)
        wsc_uuid = uuid.UUID(card_id)

        # Verify card exists in workstream (card_id param is workstream_card.id)
        result = await db.execute(
            select(WorkstreamCard.id, WorkstreamCard.card_id).where(
                WorkstreamCard.workstream_id == ws_uuid,
                WorkstreamCard.id == wsc_uuid,
            )
        )
        wsc_row = result.one_or_none()
        if wsc_row is None:
            raise HTTPException(
                status_code=404, detail="Card not found in this workstream"
            )

        actual_card_id = wsc_row.card_id

        # Check rate limit for deep research (inline -- replaces ResearchService.check_rate_limit)
        card_result = await db.execute(
            select(
                Card.deep_research_count_today,
                Card.deep_research_reset_date,
            ).where(Card.id == actual_card_id)
        )
        card_row = card_result.one_or_none()
        if card_row is not None:
            today = date.today()
            count_today = card_row.deep_research_count_today or 0
            reset_date = card_row.deep_research_reset_date

            if reset_date != today:
                # Reset counter for new day
                card_update_result = await db.execute(
                    select(Card).where(Card.id == actual_card_id)
                )
                card_obj = card_update_result.scalar_one()
                card_obj.deep_research_count_today = 0
                card_obj.deep_research_reset_date = today
                await db.flush()
                # Allowed -- counter was reset
            elif count_today >= 2:
                raise HTTPException(
                    status_code=429,
                    detail="Daily deep research limit reached (2 per card)",
                )

        # Create research task
        new_task = ResearchTask(
            user_id=uuid.UUID(current_user["id"]),
            card_id=actual_card_id,
            task_type="deep_research",
            status="queued",
        )
        db.add(new_task)
        await db.flush()
        await db.refresh(new_task)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=_safe_error("creating deep research task", e),
        ) from e

    # Task execution is handled by the background worker (see `app.worker`).
    return ResearchTaskSchema(**_row_to_dict(new_task))


# ============================================================================
# POST /me/workstreams/{workstream_id}/cards/{card_id}/quick-update
# ============================================================================


@router.post(
    "/me/workstreams/{workstream_id}/cards/{card_id}/quick-update",
    response_model=ResearchTaskSchema,
)
@router.post(
    "/me/programs/{workstream_id}/cards/{card_id}/quick-update",
    response_model=ResearchTaskSchema,
)
async def trigger_card_quick_update(
    workstream_id: str,
    card_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Trigger a quick 5-source update for a card in the workstream.

    Creates a research task with task_type='quick_update' for the specified card.
    This is a lighter-weight research update compared to deep_research.
    The research runs asynchronously; poll GET /research/{task_id} for status.

    Args:
        workstream_id: UUID of the workstream
        card_id: UUID of the workstream card (junction table ID)
        current_user: Authenticated user (injected)

    Returns:
        ResearchTask with the created task details

    Raises:
        HTTPException 404: Workstream or card not found
        HTTPException 403: Not authorized
    """
    try:
        await _verify_workstream_ownership(db, workstream_id, current_user["id"])

        ws_uuid = uuid.UUID(workstream_id)
        wsc_uuid = uuid.UUID(card_id)

        # Verify card exists in workstream (card_id param is workstream_card.id)
        result = await db.execute(
            select(WorkstreamCard.id, WorkstreamCard.card_id).where(
                WorkstreamCard.workstream_id == ws_uuid,
                WorkstreamCard.id == wsc_uuid,
            )
        )
        wsc_row = result.one_or_none()
        if wsc_row is None:
            raise HTTPException(
                status_code=404, detail="Card not found in this workstream"
            )

        actual_card_id = wsc_row.card_id

        # Create research task (quick_update signals the worker for lighter update)
        new_task = ResearchTask(
            user_id=uuid.UUID(current_user["id"]),
            card_id=actual_card_id,
            task_type="quick_update",
            status="queued",
        )
        db.add(new_task)
        await db.flush()
        await db.refresh(new_task)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=_safe_error("creating quick update task", e),
        ) from e

    # Task execution is handled by the background worker (see `app.worker`).
    return ResearchTaskSchema(**_row_to_dict(new_task))


# ============================================================================
# POST /me/workstreams/{workstream_id}/cards/{card_id}/check-updates
# ============================================================================


@router.post(
    "/me/workstreams/{workstream_id}/cards/{card_id}/check-updates",
    response_model=ResearchTaskSchema,
)
@router.post(
    "/me/programs/{workstream_id}/cards/{card_id}/check-updates",
    response_model=ResearchTaskSchema,
)
async def trigger_card_check_updates(
    workstream_id: str,
    card_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Check for updates on a watched card.

    This is an alias for quick-update, used by the kanban board's "Check for Updates"
    action on cards in the Watching column. Creates a research task with task_type='quick_update'.

    Args:
        workstream_id: UUID of the workstream
        card_id: UUID of the workstream card (junction table ID)
        current_user: Authenticated user (injected)

    Returns:
        ResearchTask with the created task details

    Raises:
        HTTPException 404: Workstream or card not found
        HTTPException 403: Not authorized
    """
    # Delegate to the quick-update implementation
    return await trigger_card_quick_update(workstream_id, card_id, db, current_user)


# ============================================================================
# GET  /me/workstreams/{workstream_id}/research-status
# ============================================================================


@router.get(
    "/me/workstreams/{workstream_id}/research-status",
    response_model=WorkstreamResearchStatusResponse,
)
@router.get(
    "/me/programs/{workstream_id}/research-status",
    response_model=WorkstreamResearchStatusResponse,
)
async def get_workstream_research_status(
    workstream_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Get active research tasks for cards in a workstream.

    Returns all research tasks (queued, processing) and recently completed tasks (last hour)
    for cards that are in the specified workstream. Used to show research progress indicators.

    Args:
        workstream_id: UUID of the workstream
        current_user: Authenticated user (injected)

    Returns:
        WorkstreamResearchStatusResponse with list of active tasks

    Raises:
        HTTPException 404: Workstream not found
        HTTPException 403: Not authorized
    """
    try:
        await _verify_workstream_ownership(db, workstream_id, current_user["id"])

        ws_uuid = uuid.UUID(workstream_id)

        # Get all card_ids in this workstream
        wsc_result = await db.execute(
            select(WorkstreamCard.card_id).where(
                WorkstreamCard.workstream_id == ws_uuid
            )
        )
        card_ids = [row[0] for row in wsc_result.all() if row[0] is not None]

        if not card_ids:
            return WorkstreamResearchStatusResponse(tasks=[])

        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)

        # Query active tasks (queued/processing) and recently completed/failed
        tasks_result = await db.execute(
            select(
                ResearchTask.id,
                ResearchTask.card_id,
                ResearchTask.task_type,
                ResearchTask.status,
                ResearchTask.started_at,
                ResearchTask.completed_at,
            ).where(
                ResearchTask.card_id.in_(card_ids),
                or_(
                    ResearchTask.status.in_(["queued", "processing"]),
                    and_(
                        ResearchTask.status.in_(["completed", "failed"]),
                        ResearchTask.completed_at >= one_hour_ago,
                    ),
                ),
            )
        )
        all_tasks = tasks_result.all()

    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Error querying research tasks: %s", e)
        return WorkstreamResearchStatusResponse(tasks=[])

    # Deduplicate by card_id, keeping the most recent task per card
    task_by_card: Dict[str, dict] = {}
    for row in all_tasks:
        t = {
            "id": str(row.id),
            "card_id": str(row.card_id),
            "task_type": row.task_type,
            "status": row.status,
            "started_at": row.started_at,
            "completed_at": row.completed_at,
        }
        cid = t["card_id"]
        if cid not in task_by_card:
            task_by_card[cid] = t
        else:
            existing = task_by_card[cid]
            if t["status"] in ["queued", "processing"]:
                task_by_card[cid] = t
            elif existing["status"] not in ["queued", "processing"]:
                # Both are completed/failed -- keep most recent by completed_at
                t_completed = t.get("completed_at") or datetime.min.replace(
                    tzinfo=timezone.utc
                )
                e_completed = existing.get("completed_at") or datetime.min.replace(
                    tzinfo=timezone.utc
                )
                if isinstance(t_completed, str):
                    t_completed = datetime.fromisoformat(t_completed)
                if isinstance(e_completed, str):
                    e_completed = datetime.fromisoformat(e_completed)
                if t_completed > e_completed:
                    task_by_card[cid] = t

    result_tasks = [
        WorkstreamResearchStatus(
            card_id=t["card_id"],
            task_id=t["id"],
            task_type=t["task_type"],
            status=t["status"],
            started_at=t.get("started_at"),
            completed_at=t.get("completed_at"),
        )
        for t in task_by_card.values()
    ]

    return WorkstreamResearchStatusResponse(tasks=result_tasks)
