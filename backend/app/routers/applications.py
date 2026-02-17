"""Applications router for the Application Tracking feature.

Provides CRUD endpoints for managing grant applications, milestones,
status transitions, and a dashboard overview.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, get_current_user_hardcoded, _safe_error
from app.models.application_models import (
    ApplicationListResponse,
    ApplicationResponse,
    ApplicationUpdate,
    ApplicationWithDetails,
    DashboardResponse,
    DashboardStats,
    MilestoneCreate,
    MilestoneResponse,
    MilestoneUpdate,
    StatusHistoryResponse,
    StatusUpdateRequest,
)
from app.models.db.grant_application import GrantApplication
from app.models.db.milestone import ApplicationMilestone, ApplicationStatusHistory
from app.services.application_service import ApplicationService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["applications"])


# ---------------------------------------------------------------------------
# GET  /me/applications
# ---------------------------------------------------------------------------


@router.get("/me/applications", response_model=ApplicationListResponse)
async def list_my_applications(
    status_filter: str | None = Query(
        None, alias="status", description="Filter by status"
    ),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    sort_by: str = Query(
        "created_at",
        description="Sort by: created_at, deadline, status",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """List the authenticated user's grant applications with card details.

    Args:
        status_filter: Optional status value to filter by.
        limit: Maximum number of results (default 20, max 100).
        offset: Number of rows to skip.
        sort_by: Column to sort by.
        db: Async database session (injected).
        current_user: Authenticated user (injected).

    Returns:
        ApplicationListResponse with applications and total count.
    """
    try:
        user_id = uuid.UUID(current_user["id"])
        applications = await ApplicationService._list_applications_with_details(
            db,
            user_id=user_id,
            limit=limit,
            offset=offset,
            status_filter=status_filter,
            sort_by=sort_by,
        )

        # Total count (separate query for pagination)
        count_query = select(func.count(GrantApplication.id)).where(
            GrantApplication.user_id == user_id
        )
        if status_filter:
            count_query = count_query.where(GrantApplication.status == status_filter)
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

    except Exception as e:
        logger.error("Failed to list applications: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("listing applications", e),
        ) from e

    return ApplicationListResponse(
        applications=[ApplicationWithDetails(**app) for app in applications],
        total=total,
    )


# ---------------------------------------------------------------------------
# GET  /me/applications/dashboard
# ---------------------------------------------------------------------------


@router.get("/me/applications/dashboard", response_model=DashboardResponse)
async def get_application_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Get aggregated dashboard stats for the user's applications.

    Returns counts by status, pipeline value, upcoming deadlines, and
    the 10 most recent applications with card details.

    Args:
        db: Async database session (injected).
        current_user: Authenticated user (injected).

    Returns:
        DashboardResponse with stats and recent applications.
    """
    try:
        user_id = uuid.UUID(current_user["id"])
        dashboard = await ApplicationService.get_dashboard(db, user_id)
    except Exception as e:
        logger.error("Failed to build dashboard: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("building application dashboard", e),
        ) from e

    return DashboardResponse(
        stats=DashboardStats(**dashboard["stats"]),
        recent_applications=[
            ApplicationWithDetails(**app) for app in dashboard["recent_applications"]
        ],
    )


# ---------------------------------------------------------------------------
# GET  /applications/{application_id}
# ---------------------------------------------------------------------------


@router.get(
    "/applications/{application_id}",
    response_model=ApplicationWithDetails,
)
async def get_application(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Get full application detail with card info and milestone summary.

    Args:
        application_id: UUID of the application.
        db: Async database session (injected).
        current_user: Authenticated user (injected).

    Returns:
        ApplicationWithDetails with enriched card and milestone data.

    Raises:
        HTTPException 404: Application not found.
    """
    try:
        details = await ApplicationService.get_application_with_details(
            db, application_id
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )
    except Exception as e:
        logger.error("Failed to get application %s: %s", application_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("fetching application", e),
        ) from e

    return ApplicationWithDetails(**details)


# ---------------------------------------------------------------------------
# PATCH  /applications/{application_id}
# ---------------------------------------------------------------------------


@router.patch(
    "/applications/{application_id}",
    response_model=ApplicationResponse,
)
async def update_application(
    application_id: uuid.UUID,
    body: ApplicationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Update application fields (notes, awarded_amount, timestamps).

    Only fields present in the request body will be updated.

    Args:
        application_id: UUID of the application.
        body: ApplicationUpdate with optional fields.
        db: Async database session (injected).
        current_user: Authenticated user (injected).

    Returns:
        The updated ApplicationResponse.

    Raises:
        HTTPException 404: Application not found.
    """
    try:
        result = await db.execute(
            select(GrantApplication).where(GrantApplication.id == application_id)
        )
        application = result.scalar_one_or_none()
    except Exception as e:
        logger.error("Failed to fetch application %s: %s", application_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("fetching application", e),
        ) from e

    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    # Apply provided fields
    if body.status is not None:
        application.status = body.status
    if body.notes is not None:
        application.notes = body.notes
    if body.awarded_amount is not None:
        application.awarded_amount = body.awarded_amount
    if body.submitted_at is not None:
        application.submitted_at = body.submitted_at
    if body.decision_at is not None:
        application.decision_at = body.decision_at

    application.updated_at = func.now()

    try:
        await db.flush()
        await db.refresh(application)
    except Exception as e:
        logger.error("Failed to update application %s: %s", application_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("updating application", e),
        ) from e

    return ApplicationResponse.model_validate(application)


# ---------------------------------------------------------------------------
# POST  /applications/{application_id}/status
# ---------------------------------------------------------------------------


@router.post(
    "/applications/{application_id}/status",
    response_model=ApplicationResponse,
)
async def update_application_status(
    application_id: uuid.UUID,
    body: StatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Update application status with transition validation and history.

    Validates that the transition is allowed, records the change in
    status history, and sets lifecycle timestamps (submitted_at,
    decision_at) when appropriate.

    Args:
        application_id: UUID of the application.
        body: StatusUpdateRequest with new_status and optional reason.
        db: Async database session (injected).
        current_user: Authenticated user (injected).

    Returns:
        The updated ApplicationResponse.

    Raises:
        HTTPException 404: Application not found.
        HTTPException 400: Invalid status transition.
    """
    try:
        changed_by = uuid.UUID(current_user["id"])
        application = await ApplicationService.update_status(
            db,
            application_id=application_id,
            new_status=body.new_status,
            changed_by=changed_by,
            reason=body.reason,
        )
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )
    except Exception as e:
        logger.error("Failed to update status for %s: %s", application_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("updating application status", e),
        ) from e

    return ApplicationResponse.model_validate(application)


# ---------------------------------------------------------------------------
# POST  /applications/from-wizard/{wizard_session_id}
# ---------------------------------------------------------------------------


@router.post(
    "/applications/from-wizard/{wizard_session_id}",
    response_model=ApplicationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_application_from_wizard(
    wizard_session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Create a grant application from a completed wizard session.

    Fetches the wizard session, creates the application with card and
    workstream references, and auto-generates standard milestones from
    the grant context.

    Args:
        wizard_session_id: UUID of the wizard session.
        db: Async database session (injected).
        current_user: Authenticated user (injected).

    Returns:
        The created ApplicationResponse.

    Raises:
        HTTPException 404: Wizard session not found.
    """
    try:
        user_id = uuid.UUID(current_user["id"])
        application = await ApplicationService.create_from_wizard(
            db,
            wizard_session_id=wizard_session_id,
            user_id=user_id,
        )
        await db.commit()
        await db.refresh(application)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            "Failed to create application from wizard %s: %s",
            wizard_session_id,
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("creating application from wizard", e),
        ) from e

    return ApplicationResponse.model_validate(application)


# ---------------------------------------------------------------------------
# GET  /applications/{application_id}/milestones
# ---------------------------------------------------------------------------


@router.get(
    "/applications/{application_id}/milestones",
    response_model=list[MilestoneResponse],
)
async def list_milestones(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """List all milestones for a grant application.

    Returns milestones ordered by sort_order ascending.

    Args:
        application_id: UUID of the grant application.
        db: Async database session (injected).
        current_user: Authenticated user (injected).

    Returns:
        List of MilestoneResponse objects.
    """
    try:
        result = await db.execute(
            select(ApplicationMilestone)
            .where(ApplicationMilestone.application_id == application_id)
            .order_by(ApplicationMilestone.sort_order, ApplicationMilestone.created_at)
        )
        milestones = list(result.scalars().all())
    except Exception as e:
        logger.error(
            "Failed to list milestones for application %s: %s", application_id, e
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("listing milestones", e),
        ) from e

    return [MilestoneResponse.model_validate(ms) for ms in milestones]


# ---------------------------------------------------------------------------
# POST  /applications/{application_id}/milestones
# ---------------------------------------------------------------------------


@router.post(
    "/applications/{application_id}/milestones",
    response_model=MilestoneResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_milestone(
    application_id: uuid.UUID,
    body: MilestoneCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Add a milestone to a grant application.

    Automatically assigns the next sort_order value.

    Args:
        application_id: UUID of the grant application.
        body: MilestoneCreate with title and optional fields.
        db: Async database session (injected).
        current_user: Authenticated user (injected).

    Returns:
        The created MilestoneResponse.
    """
    # Determine next sort_order
    try:
        max_order_result = await db.execute(
            select(func.coalesce(func.max(ApplicationMilestone.sort_order), -1)).where(
                ApplicationMilestone.application_id == application_id
            )
        )
        next_order = (max_order_result.scalar() or 0) + 1
    except Exception:
        next_order = 0

    milestone = ApplicationMilestone(
        application_id=application_id,
        title=body.title,
        description=body.description,
        due_date=body.due_date,
        milestone_type=body.milestone_type,
        sort_order=next_order,
    )

    try:
        db.add(milestone)
        await db.flush()
        await db.refresh(milestone)
    except Exception as e:
        logger.error("Failed to create milestone: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("milestone creation", e),
        ) from e

    return MilestoneResponse.model_validate(milestone)


# ---------------------------------------------------------------------------
# PATCH  /applications/{application_id}/milestones/{milestone_id}
# ---------------------------------------------------------------------------


@router.patch(
    "/applications/{application_id}/milestones/{milestone_id}",
    response_model=MilestoneResponse,
)
async def update_milestone(
    application_id: uuid.UUID,
    milestone_id: uuid.UUID,
    body: MilestoneUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Update a milestone (toggle completion, edit title/description/due_date).

    When ``is_completed`` is set to True, ``completed_at`` is automatically
    set to the current timestamp. When set to False, ``completed_at`` is
    cleared.

    Args:
        application_id: UUID of the grant application.
        milestone_id: UUID of the milestone.
        body: MilestoneUpdate with optional fields.
        db: Async database session (injected).
        current_user: Authenticated user (injected).

    Returns:
        The updated MilestoneResponse.

    Raises:
        HTTPException 404: Milestone not found.
    """
    try:
        result = await db.execute(
            select(ApplicationMilestone).where(
                ApplicationMilestone.id == milestone_id,
                ApplicationMilestone.application_id == application_id,
            )
        )
        milestone = result.scalar_one_or_none()
    except Exception as e:
        logger.error("Failed to fetch milestone %s: %s", milestone_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("fetching milestone", e),
        ) from e

    if milestone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Milestone not found",
        )

    # Apply updates for provided fields
    if body.title is not None:
        milestone.title = body.title
    if body.description is not None:
        milestone.description = body.description
    if body.due_date is not None:
        milestone.due_date = body.due_date

    # Handle completion toggling
    if body.is_completed is not None:
        milestone.is_completed = body.is_completed
        if body.is_completed:
            milestone.completed_at = func.now()
        else:
            milestone.completed_at = None

    try:
        await db.flush()
        await db.refresh(milestone)
    except Exception as e:
        logger.error("Failed to update milestone %s: %s", milestone_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("milestone update", e),
        ) from e

    return MilestoneResponse.model_validate(milestone)


# ---------------------------------------------------------------------------
# GET  /applications/{application_id}/status-history
# ---------------------------------------------------------------------------


@router.get(
    "/applications/{application_id}/status-history",
    response_model=list[StatusHistoryResponse],
)
async def list_status_history(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """List status change history for a grant application.

    Returns history entries ordered by creation time (most recent first).

    Args:
        application_id: UUID of the grant application.
        db: Async database session (injected).
        current_user: Authenticated user (injected).

    Returns:
        List of StatusHistoryResponse objects.
    """
    try:
        result = await db.execute(
            select(ApplicationStatusHistory)
            .where(ApplicationStatusHistory.application_id == application_id)
            .order_by(ApplicationStatusHistory.created_at.desc())
        )
        history = list(result.scalars().all())
    except Exception as e:
        logger.error(
            "Failed to list status history for application %s: %s",
            application_id,
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("listing status history", e),
        ) from e

    return [StatusHistoryResponse.model_validate(entry) for entry in history]
