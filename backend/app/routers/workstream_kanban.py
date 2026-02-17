"""Workstream kanban card management router."""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.deps import supabase, get_current_user, _safe_error, openai_client, limiter
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
from app.models.research import ResearchTask
from app.research_service import ResearchService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["workstream-kanban"])


@router.get(
    "/me/workstreams/{workstream_id}/cards",
    response_model=WorkstreamCardsGroupedResponse,
)
@router.get(
    "/me/programs/{workstream_id}/cards",
    response_model=WorkstreamCardsGroupedResponse,
)
async def get_workstream_cards(
    workstream_id: str, current_user: dict = Depends(get_current_user)
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
    # Verify workstream belongs to user
    ws_response = (
        supabase.table("workstreams")
        .select("id, user_id")
        .eq("id", workstream_id)
        .execute()
    )
    if not ws_response.data:
        raise HTTPException(status_code=404, detail="Workstream not found")

    if ws_response.data[0]["user_id"] != current_user["id"]:
        raise HTTPException(
            status_code=403, detail="Not authorized to access this workstream"
        )

    # Fetch all cards with joined card details, ordered by position
    cards_response = (
        supabase.table("workstream_cards")
        .select("*, cards(*)")
        .eq("workstream_id", workstream_id)
        .order("position")
        .execute()
    )

    # Group cards by status — dynamically built from the full status set
    grouped = {status: [] for status in VALID_WORKSTREAM_CARD_STATUSES}

    for item in cards_response.data or []:
        card_status = item.get("status", "inbox")
        if card_status not in grouped:
            card_status = "inbox"

        card_with_details = WorkstreamCardWithDetails(
            id=item["id"],
            workstream_id=item["workstream_id"],
            card_id=item["card_id"],
            added_by=item["added_by"],
            added_at=item["added_at"],
            status=item.get("status", "inbox"),
            position=item.get("position", 0),
            notes=item.get("notes"),
            reminder_at=item.get("reminder_at"),
            added_from=item.get("added_from", "manual"),
            updated_at=item.get("updated_at"),
            card=item.get("cards"),
        )
        grouped[card_status].append(card_with_details)

    return WorkstreamCardsGroupedResponse(**grouped)


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
    current_user: dict = Depends(get_current_user),
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
    # Verify workstream belongs to user
    ws_response = (
        supabase.table("workstreams")
        .select("id, user_id")
        .eq("id", workstream_id)
        .execute()
    )
    if not ws_response.data:
        raise HTTPException(status_code=404, detail="Workstream not found")

    if ws_response.data[0]["user_id"] != current_user["id"]:
        raise HTTPException(
            status_code=403, detail="Not authorized to add cards to this workstream"
        )

    # Verify card exists
    card_response = (
        supabase.table("cards").select("*").eq("id", card_data.card_id).execute()
    )
    if not card_response.data:
        raise HTTPException(status_code=404, detail="Card not found")

    # Check if card is already in workstream
    existing = (
        supabase.table("workstream_cards")
        .select("id")
        .eq("workstream_id", workstream_id)
        .eq("card_id", card_data.card_id)
        .execute()
    )
    if existing.data:
        raise HTTPException(
            status_code=409, detail="Card is already in this workstream"
        )

    # Get max position for the target status column
    status = card_data.status or "inbox"
    position_response = (
        supabase.table("workstream_cards")
        .select("position")
        .eq("workstream_id", workstream_id)
        .eq("status", status)
        .order("position", desc=True)
        .limit(1)
        .execute()
    )

    next_position = 0
    if position_response.data:
        next_position = position_response.data[0]["position"] + 1

    # Create workstream card record
    now = datetime.now(timezone.utc).isoformat()
    new_card = {
        "workstream_id": workstream_id,
        "card_id": card_data.card_id,
        "added_by": current_user["id"],
        "added_at": now,
        "status": status,
        "position": next_position,
        "notes": card_data.notes,
        "added_from": "manual",
        "updated_at": now,
    }

    result = supabase.table("workstream_cards").insert(new_card).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to add card to workstream")

    inserted = result.data[0]
    return WorkstreamCardWithDetails(
        id=inserted["id"],
        workstream_id=inserted["workstream_id"],
        card_id=inserted["card_id"],
        added_by=inserted["added_by"],
        added_at=inserted["added_at"],
        status=inserted.get("status", "inbox"),
        position=inserted.get("position", 0),
        notes=inserted.get("notes"),
        reminder_at=inserted.get("reminder_at"),
        added_from=inserted.get("added_from", "manual"),
        updated_at=inserted.get("updated_at"),
        card=card_response.data[0],
    )


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
    current_user: dict = Depends(get_current_user),
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
    # Verify workstream belongs to user
    ws_response = (
        supabase.table("workstreams")
        .select("id, user_id")
        .eq("id", workstream_id)
        .execute()
    )
    if not ws_response.data:
        raise HTTPException(status_code=404, detail="Workstream not found")

    if ws_response.data[0]["user_id"] != current_user["id"]:
        raise HTTPException(
            status_code=403, detail="Not authorized to update cards in this workstream"
        )

    # Fetch the workstream card by its junction table ID (card_id param is actually workstream_card.id)
    # The frontend passes the workstream_card junction table ID, not the underlying card UUID
    wsc_response = (
        supabase.table("workstream_cards")
        .select("*, cards(*)")
        .eq("workstream_id", workstream_id)
        .eq("id", card_id)
        .execute()
    )

    if not wsc_response.data:
        raise HTTPException(status_code=404, detail="Card not found in this workstream")

    existing = wsc_response.data[0]
    workstream_card_id = existing["id"]

    # Build update dict
    update_dict = {"updated_at": datetime.now(timezone.utc).isoformat()}

    if update_data.status is not None:
        # If status changed, recalculate position
        if update_data.status != existing.get("status"):
            # Get max position in new column
            position_response = (
                supabase.table("workstream_cards")
                .select("position")
                .eq("workstream_id", workstream_id)
                .eq("status", update_data.status)
                .order("position", desc=True)
                .limit(1)
                .execute()
            )

            next_position = 0
            if position_response.data:
                next_position = position_response.data[0]["position"] + 1

            update_dict["status"] = update_data.status
            update_dict["position"] = (
                update_data.position
                if update_data.position is not None
                else next_position
            )
        else:
            update_dict["status"] = update_data.status
            if update_data.position is not None:
                update_dict["position"] = update_data.position
    elif update_data.position is not None:
        update_dict["position"] = update_data.position

    if update_data.notes is not None:
        update_dict["notes"] = update_data.notes

    if update_data.reminder_at is not None:
        update_dict["reminder_at"] = update_data.reminder_at

    # Perform update
    result = (
        supabase.table("workstream_cards")
        .update(update_dict)
        .eq("id", workstream_card_id)
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to update workstream card")

    updated = result.data[0]

    # Re-fetch with card details for response
    final_response = (
        supabase.table("workstream_cards")
        .select("*, cards(*)")
        .eq("id", workstream_card_id)
        .execute()
    )

    if not final_response.data:
        raise HTTPException(status_code=500, detail="Failed to retrieve updated card")

    item = final_response.data[0]
    return WorkstreamCardWithDetails(
        id=item["id"],
        workstream_id=item["workstream_id"],
        card_id=item["card_id"],
        added_by=item["added_by"],
        added_at=item["added_at"],
        status=item.get("status", "inbox"),
        position=item.get("position", 0),
        notes=item.get("notes"),
        reminder_at=item.get("reminder_at"),
        added_from=item.get("added_from", "manual"),
        updated_at=item.get("updated_at"),
        card=item.get("cards"),
    )


@router.delete("/me/workstreams/{workstream_id}/cards/{card_id}")
@router.delete("/me/programs/{workstream_id}/cards/{card_id}")
async def remove_card_from_workstream(
    workstream_id: str, card_id: str, current_user: dict = Depends(get_current_user)
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
    # Verify workstream belongs to user
    ws_response = (
        supabase.table("workstreams")
        .select("id, user_id")
        .eq("id", workstream_id)
        .execute()
    )
    if not ws_response.data:
        raise HTTPException(status_code=404, detail="Workstream not found")

    if ws_response.data[0]["user_id"] != current_user["id"]:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to remove cards from this workstream",
        )

    # Check card exists in workstream (card_id param is actually workstream_card.id - the junction table ID)
    existing = (
        supabase.table("workstream_cards")
        .select("id")
        .eq("workstream_id", workstream_id)
        .eq("id", card_id)
        .execute()
    )

    if not existing.data:
        raise HTTPException(status_code=404, detail="Card not found in this workstream")

    # Delete the association
    supabase.table("workstream_cards").delete().eq("workstream_id", workstream_id).eq(
        "id", card_id
    ).execute()

    return {"status": "removed", "message": "Card removed from workstream"}


@router.post(
    "/me/workstreams/{workstream_id}/cards/{card_id}/deep-dive",
    response_model=ResearchTask,
)
@router.post(
    "/me/programs/{workstream_id}/cards/{card_id}/deep-dive",
    response_model=ResearchTask,
)
async def trigger_card_deep_dive(
    workstream_id: str, card_id: str, current_user: dict = Depends(get_current_user)
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
    # Verify workstream belongs to user
    ws_response = (
        supabase.table("workstreams")
        .select("id, user_id")
        .eq("id", workstream_id)
        .execute()
    )
    if not ws_response.data:
        raise HTTPException(status_code=404, detail="Workstream not found")

    if ws_response.data[0]["user_id"] != current_user["id"]:
        raise HTTPException(
            status_code=403, detail="Not authorized to access this workstream"
        )

    # Verify card exists in workstream (card_id param is actually workstream_card.id - the junction table ID)
    wsc_response = (
        supabase.table("workstream_cards")
        .select("id, card_id")
        .eq("workstream_id", workstream_id)
        .eq("id", card_id)
        .execute()
    )

    if not wsc_response.data:
        raise HTTPException(status_code=404, detail="Card not found in this workstream")

    # Get the actual underlying card UUID for research
    actual_card_id = wsc_response.data[0]["card_id"]

    # Check rate limit for deep research
    service = ResearchService(supabase, openai_client)
    if not await service.check_rate_limit(actual_card_id):
        raise HTTPException(
            status_code=429, detail="Daily deep research limit reached (2 per card)"
        )

    # Create research task using the actual underlying card UUID
    task_record = {
        "user_id": current_user["id"],
        "card_id": actual_card_id,
        "task_type": "deep_research",
        "status": "queued",
    }

    task_result = supabase.table("research_tasks").insert(task_record).execute()

    if not task_result.data:
        raise HTTPException(status_code=500, detail="Failed to create research task")

    task = task_result.data[0]

    # Task execution is handled by the background worker (see `app.worker`).
    return ResearchTask(**task)


@router.post(
    "/me/workstreams/{workstream_id}/cards/{card_id}/quick-update",
    response_model=ResearchTask,
)
@router.post(
    "/me/programs/{workstream_id}/cards/{card_id}/quick-update",
    response_model=ResearchTask,
)
async def trigger_card_quick_update(
    workstream_id: str, card_id: str, current_user: dict = Depends(get_current_user)
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
    # Verify workstream belongs to user
    ws_response = (
        supabase.table("workstreams")
        .select("id, user_id")
        .eq("id", workstream_id)
        .execute()
    )
    if not ws_response.data:
        raise HTTPException(status_code=404, detail="Workstream not found")

    if ws_response.data[0]["user_id"] != current_user["id"]:
        raise HTTPException(
            status_code=403, detail="Not authorized to access this workstream"
        )

    # Verify card exists in workstream (card_id param is actually workstream_card.id - the junction table ID)
    wsc_response = (
        supabase.table("workstream_cards")
        .select("id, card_id")
        .eq("workstream_id", workstream_id)
        .eq("id", card_id)
        .execute()
    )

    if not wsc_response.data:
        raise HTTPException(status_code=404, detail="Card not found in this workstream")

    # Get the actual underlying card UUID for research
    actual_card_id = wsc_response.data[0]["card_id"]

    # Create research task using the actual underlying card UUID
    # task_type='quick_update' signals the worker to do a lighter 5-source update
    task_record = {
        "user_id": current_user["id"],
        "card_id": actual_card_id,
        "task_type": "quick_update",
        "status": "queued",
    }

    task_result = supabase.table("research_tasks").insert(task_record).execute()

    if not task_result.data:
        raise HTTPException(status_code=500, detail="Failed to create research task")

    task = task_result.data[0]

    # Task execution is handled by the background worker (see `app.worker`).
    return ResearchTask(**task)


@router.post(
    "/me/workstreams/{workstream_id}/cards/{card_id}/check-updates",
    response_model=ResearchTask,
)
@router.post(
    "/me/programs/{workstream_id}/cards/{card_id}/check-updates",
    response_model=ResearchTask,
)
async def trigger_card_check_updates(
    workstream_id: str, card_id: str, current_user: dict = Depends(get_current_user)
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
    return await trigger_card_quick_update(workstream_id, card_id, current_user)


@router.get(
    "/me/workstreams/{workstream_id}/research-status",
    response_model=WorkstreamResearchStatusResponse,
)
@router.get(
    "/me/programs/{workstream_id}/research-status",
    response_model=WorkstreamResearchStatusResponse,
)
async def get_workstream_research_status(
    workstream_id: str, current_user: dict = Depends(get_current_user)
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
    # Verify workstream belongs to user
    ws_response = (
        supabase.table("workstreams")
        .select("id, user_id")
        .eq("id", workstream_id)
        .execute()
    )
    if not ws_response.data:
        raise HTTPException(status_code=404, detail="Workstream not found")

    if ws_response.data[0]["user_id"] != current_user["id"]:
        raise HTTPException(
            status_code=403, detail="Not authorized to access this workstream"
        )

    # Get all card_ids in this workstream
    wsc_response = (
        supabase.table("workstream_cards")
        .select("card_id")
        .eq("workstream_id", workstream_id)
        .execute()
    )

    if not wsc_response.data:
        return WorkstreamResearchStatusResponse(tasks=[])

    card_ids = [item["card_id"] for item in wsc_response.data if item.get("card_id")]

    # If no valid card_ids, return empty response
    if not card_ids:
        return WorkstreamResearchStatusResponse(tasks=[])

    # Get research tasks for these cards that are:
    # - Currently active (queued or processing)
    # - Recently completed/failed (within last hour for feedback)
    try:
        one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

        # Query active tasks
        active_tasks = (
            supabase.table("research_tasks")
            .select("id, card_id, task_type, status, started_at, completed_at")
            .in_("card_id", card_ids)
            .in_("status", ["queued", "processing"])
            .execute()
        )

        # Query recently completed tasks
        recent_tasks = (
            supabase.table("research_tasks")
            .select("id, card_id, task_type, status, started_at, completed_at")
            .in_("card_id", card_ids)
            .in_("status", ["completed", "failed"])
            .gte("completed_at", one_hour_ago)
            .execute()
        )
    except Exception as e:
        logger.warning(f"Error querying research tasks: {e}")
        return WorkstreamResearchStatusResponse(tasks=[])

    # Combine and format results
    all_tasks = (active_tasks.data or []) + (recent_tasks.data or [])

    # Deduplicate by card_id, keeping the most recent task per card
    task_by_card: Dict[str, dict] = {}
    for task in all_tasks:
        card_id = task["card_id"]
        if card_id not in task_by_card:
            task_by_card[card_id] = task
        else:
            # Keep the more recent task (prefer active over completed)
            existing = task_by_card[card_id]
            if task["status"] in ["queued", "processing"]:
                task_by_card[card_id] = task
            elif existing["status"] not in ["queued", "processing"]:
                # Both are completed/failed - keep most recent by completed_at
                if task.get("completed_at", "") > existing.get("completed_at", ""):
                    task_by_card[card_id] = task

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
