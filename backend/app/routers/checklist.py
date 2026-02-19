"""Checklist router for the Application Materials Checklist feature.

Provides CRUD endpoints for managing checklist items attached to grant
applications, plus AI-powered suggestions for missing materials.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, get_current_user_hardcoded, _safe_error
from app.models.checklist_models import (
    AISuggestResponse,
    ChecklistItemCreate,
    ChecklistItemResponse,
    ChecklistItemUpdate,
    ChecklistListResponse,
)
from app.models.db.attachment import ApplicationAttachment
from app.models.db.checklist import ChecklistItem
from app.services.access_control import (
    ROLE_EDITOR,
    ROLE_VIEWER,
    require_application_access,
)
from app.services.checklist_service import ChecklistService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["checklist"])


# ---------------------------------------------------------------------------
# GET  /applications/{application_id}/checklist
# ---------------------------------------------------------------------------


@router.get(
    "/applications/{application_id}/checklist",
    response_model=ChecklistListResponse,
)
async def list_checklist_items(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """List all checklist items for a grant application.

    Returns items ordered by sort_order with progress statistics.

    Args:
        application_id: UUID of the grant application.
        db: Async database session (injected).
        current_user: Authenticated user (injected).

    Returns:
        ChecklistListResponse with items, total, completed count, and progress %.
    """
    await require_application_access(
        db,
        application_id=application_id,
        user_id=current_user["id"],
        minimum_role=ROLE_VIEWER,
    )

    try:
        result = await db.execute(
            select(ChecklistItem)
            .where(ChecklistItem.application_id == application_id)
            .order_by(ChecklistItem.sort_order, ChecklistItem.created_at)
        )
        items = list(result.scalars().all())
    except Exception as e:
        logger.error("Failed to list checklist items for %s: %s", application_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("listing checklist items", e),
        ) from e

    total = len(items)
    completed = sum(1 for item in items if item.is_completed)
    progress_pct = round((completed / total * 100), 1) if total > 0 else 0.0

    return ChecklistListResponse(
        items=[ChecklistItemResponse.model_validate(item) for item in items],
        total=total,
        completed=completed,
        progress_pct=progress_pct,
    )


# ---------------------------------------------------------------------------
# POST /applications/{application_id}/checklist
# ---------------------------------------------------------------------------


@router.post(
    "/applications/{application_id}/checklist",
    response_model=ChecklistItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_checklist_item(
    application_id: uuid.UUID,
    body: ChecklistItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Add a custom checklist item to a grant application.

    Items created via this endpoint are tagged with ``source='user_added'``.

    Args:
        application_id: UUID of the grant application.
        body: ChecklistItemCreate with description and optional fields.
        db: Async database session (injected).
        current_user: Authenticated user (injected).

    Returns:
        The created ChecklistItemResponse.
    """
    await require_application_access(
        db,
        application_id=application_id,
        user_id=current_user["id"],
        minimum_role=ROLE_EDITOR,
    )

    # Determine next sort_order
    try:
        max_order_result = await db.execute(
            select(func.coalesce(func.max(ChecklistItem.sort_order), -1)).where(
                ChecklistItem.application_id == application_id
            )
        )
        next_order = (max_order_result.scalar() or 0) + 1
    except Exception:
        next_order = 0

    item = ChecklistItem(
        application_id=application_id,
        description=body.description,
        category=body.category,
        is_mandatory=body.is_mandatory,
        sub_deadline=body.sub_deadline,
        notes=body.notes,
        source="user_added",
        sort_order=next_order,
    )

    try:
        db.add(item)
        await db.flush()
        await db.refresh(item)
    except Exception as e:
        logger.error("Failed to create checklist item: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("checklist item creation", e),
        ) from e

    return ChecklistItemResponse.model_validate(item)


# ---------------------------------------------------------------------------
# PATCH /applications/{application_id}/checklist/{item_id}
# ---------------------------------------------------------------------------


@router.patch(
    "/applications/{application_id}/checklist/{item_id}",
    response_model=ChecklistItemResponse,
)
async def update_checklist_item(
    application_id: uuid.UUID,
    item_id: uuid.UUID,
    body: ChecklistItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Update a checklist item (toggle completion, edit notes, etc.).

    When ``is_completed`` is set to True, ``completed_at`` and ``completed_by``
    are automatically populated. When set to False, those fields are cleared.

    Args:
        application_id: UUID of the grant application.
        item_id: UUID of the checklist item.
        body: ChecklistItemUpdate with optional fields.
        db: Async database session (injected).
        current_user: Authenticated user (injected).

    Returns:
        The updated ChecklistItemResponse.

    Raises:
        HTTPException 404: Checklist item not found.
    """
    await require_application_access(
        db,
        application_id=application_id,
        user_id=current_user["id"],
        minimum_role=ROLE_EDITOR,
    )

    try:
        result = await db.execute(
            select(ChecklistItem).where(
                ChecklistItem.id == item_id,
                ChecklistItem.application_id == application_id,
            )
        )
        item = result.scalar_one_or_none()
    except Exception as e:
        logger.error("Failed to fetch checklist item %s: %s", item_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("fetching checklist item", e),
        ) from e

    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Checklist item not found",
        )

    # Apply updates for provided fields
    if body.description is not None:
        item.description = body.description
    if body.category is not None:
        item.category = body.category
    if body.notes is not None:
        item.notes = body.notes
    if body.sub_deadline is not None:
        item.sub_deadline = body.sub_deadline
    if body.attachment_id is not None:
        attachment = await db.get(ApplicationAttachment, body.attachment_id)
        if attachment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Attachment not found",
            )
        if attachment.application_id != application_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="attachment_id must belong to the same application",
            )
        item.attachment_id = body.attachment_id

    # Handle completion toggling
    if body.is_completed is not None:
        item.is_completed = body.is_completed
        if body.is_completed:
            item.completed_at = func.now()
            item.completed_by = uuid.UUID(current_user["id"])
        else:
            item.completed_at = None
            item.completed_by = None

    try:
        await db.flush()
        await db.refresh(item)
    except Exception as e:
        logger.error("Failed to update checklist item %s: %s", item_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("checklist item update", e),
        ) from e

    return ChecklistItemResponse.model_validate(item)


# ---------------------------------------------------------------------------
# DELETE /applications/{application_id}/checklist/{item_id}
# ---------------------------------------------------------------------------


@router.delete(
    "/applications/{application_id}/checklist/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_checklist_item(
    application_id: uuid.UUID,
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Delete a user-added checklist item.

    Only items with ``source='user_added'`` can be deleted. Attempting to
    delete extracted or AI-suggested items returns a 400 error.

    Args:
        application_id: UUID of the grant application.
        item_id: UUID of the checklist item.
        db: Async database session (injected).
        current_user: Authenticated user (injected).

    Raises:
        HTTPException 404: Checklist item not found.
        HTTPException 400: Item is not user-added and cannot be deleted.
    """
    await require_application_access(
        db,
        application_id=application_id,
        user_id=current_user["id"],
        minimum_role=ROLE_EDITOR,
    )

    try:
        result = await db.execute(
            select(ChecklistItem).where(
                ChecklistItem.id == item_id,
                ChecklistItem.application_id == application_id,
            )
        )
        item = result.scalar_one_or_none()
    except Exception as e:
        logger.error("Failed to fetch checklist item %s for deletion: %s", item_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("fetching checklist item", e),
        ) from e

    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Checklist item not found",
        )

    if item.source != "user_added":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete {item.source} items. Only user-added items can be deleted.",
        )

    try:
        await db.delete(item)
        await db.flush()
    except Exception as e:
        logger.error("Failed to delete checklist item %s: %s", item_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("checklist item deletion", e),
        ) from e


# ---------------------------------------------------------------------------
# POST /applications/{application_id}/checklist/ai-suggest
# ---------------------------------------------------------------------------


@router.post(
    "/applications/{application_id}/checklist/ai-suggest",
    response_model=AISuggestResponse,
)
async def ai_suggest_checklist_items(
    application_id: uuid.UUID,
    grant_type: str | None = Query(
        None, description="Grant type hint: federal, state, local"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """AI-suggest missing checklist items based on grant type.

    Analyzes the grant type and existing items, then creates suggestions
    for commonly required materials that are not yet on the checklist.

    Args:
        application_id: UUID of the grant application.
        grant_type: Optional grant type (federal, state, local).
        db: Async database session (injected).
        current_user: Authenticated user (injected).

    Returns:
        AISuggestResponse with newly created suggestions and a summary message.
    """
    await require_application_access(
        db,
        application_id=application_id,
        user_id=current_user["id"],
        minimum_role=ROLE_EDITOR,
    )

    try:
        new_items = await ChecklistService.ai_suggest_items(
            db=db,
            application_id=application_id,
            grant_type=grant_type,
        )
    except Exception as e:
        logger.error("AI suggestion failed for application %s: %s", application_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("AI checklist suggestion", e),
        ) from e

    suggestions = [ChecklistItemResponse.model_validate(item) for item in new_items]
    count = len(suggestions)

    if count == 0:
        message = (
            "No new suggestions — your checklist already covers the standard items."
        )
    else:
        message = f"Added {count} suggested item{'s' if count != 1 else ''} to your checklist."

    return AISuggestResponse(
        suggestions=suggestions,
        message=message,
    )
