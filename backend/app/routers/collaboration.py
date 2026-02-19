"""Collaboration router for the Review Workflow feature.

Provides endpoints for managing application collaborators, inline comments,
section approvals, and the review submission workflow.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, get_current_user_hardcoded, _safe_error
from app.models.collaboration_models import (
    CollaboratorAdd,
    CollaboratorListResponse,
    CollaboratorResponse,
    CommentCreate,
    CommentListResponse,
    CommentResponse,
    CommentUpdate,
    ReviewSubmitResponse,
    SectionApprovalResponse,
)
from app.models.db.collaboration import ApplicationComment
from app.models.db.proposal import Proposal
from app.services.access_control import (
    ROLE_EDITOR,
    ROLE_OWNER,
    ROLE_REVIEWER,
    ROLE_VIEWER,
    require_application_access,
    require_proposal_access,
)
from app.services.collaboration_service import CollaborationService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["collaboration"])

_EDITOR_ROLES = {ROLE_EDITOR, ROLE_OWNER}
_REVIEWER_ROLES = {ROLE_REVIEWER, ROLE_EDITOR, ROLE_OWNER}


# ---------------------------------------------------------------------------
# Helper: convert ORM collaborator to response dict
# ---------------------------------------------------------------------------


def _collab_to_response(collab) -> CollaboratorResponse:
    """Map an ApplicationCollaborator ORM instance to CollaboratorResponse."""
    return CollaboratorResponse(
        id=str(collab.id),
        application_id=str(collab.application_id),
        user_id=str(collab.user_id),
        role=collab.role,
        invited_by=str(collab.invited_by) if collab.invited_by else None,
        invited_at=collab.invited_at,
        accepted_at=collab.accepted_at,
    )


def _comment_to_response(comment) -> CommentResponse:
    """Map an ApplicationComment ORM instance to CommentResponse."""
    return CommentResponse(
        id=str(comment.id),
        application_id=str(comment.application_id),
        proposal_id=str(comment.proposal_id) if comment.proposal_id else None,
        section_name=comment.section_name,
        parent_id=str(comment.parent_id) if comment.parent_id else None,
        author_id=str(comment.author_id),
        content=comment.content,
        is_resolved=comment.is_resolved,
        resolved_by=str(comment.resolved_by) if comment.resolved_by else None,
        resolved_at=comment.resolved_at,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


# ---------------------------------------------------------------------------
# GET  /applications/{application_id}/collaborators
# ---------------------------------------------------------------------------


@router.get(
    "/applications/{application_id}/collaborators",
    response_model=CollaboratorListResponse,
)
async def list_collaborators(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """List all collaborators for a grant application.

    Args:
        application_id: UUID of the grant application.
        db: Async database session (injected).
        current_user: Authenticated user (injected).

    Returns:
        CollaboratorListResponse with collaborators and total count.
    """
    await require_application_access(
        db,
        application_id=application_id,
        user_id=current_user["id"],
        minimum_role=ROLE_VIEWER,
    )

    try:
        collaborators = await CollaborationService.list_collaborators(
            db=db, application_id=application_id
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("listing collaborators", e),
        ) from e

    items = [_collab_to_response(c) for c in collaborators]
    return CollaboratorListResponse(collaborators=items, total=len(items))


# ---------------------------------------------------------------------------
# POST /applications/{application_id}/collaborators
# ---------------------------------------------------------------------------


@router.post(
    "/applications/{application_id}/collaborators",
    response_model=CollaboratorResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_collaborator(
    application_id: uuid.UUID,
    body: CollaboratorAdd,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Add a collaborator to a grant application.

    Args:
        application_id: UUID of the grant application.
        body: CollaboratorAdd with user_id and role.
        db: Async database session (injected).
        current_user: Authenticated user (injected).

    Returns:
        The created CollaboratorResponse.

    Raises:
        HTTPException 409: User is already a collaborator.
        HTTPException 400: Target user not found or invalid role.
    """
    await require_application_access(
        db,
        application_id=application_id,
        user_id=current_user["id"],
        minimum_role=ROLE_OWNER,
    )

    try:
        collaborator = await CollaborationService.add_collaborator(
            db=db,
            application_id=application_id,
            user_id=uuid.UUID(body.user_id),
            role=body.role,
            invited_by=uuid.UUID(current_user["id"]),
        )
    except ValueError as e:
        error_msg = str(e)
        if "application not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg,
            ) from e
        if "already a collaborator" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error_msg,
            ) from e
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        ) from e
    except IntegrityError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a collaborator on this application",
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("adding collaborator", e),
        ) from e

    return _collab_to_response(collaborator)


# ---------------------------------------------------------------------------
# DELETE /applications/{application_id}/collaborators/{user_id}
# ---------------------------------------------------------------------------


@router.delete(
    "/applications/{application_id}/collaborators/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_collaborator(
    application_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Remove a collaborator from a grant application.

    The application owner cannot be removed.

    Args:
        application_id: UUID of the grant application.
        user_id: UUID of the collaborator to remove.
        db: Async database session (injected).
        current_user: Authenticated user (injected).

    Raises:
        HTTPException 400: Cannot remove owner, or collaborator not found.
    """
    await require_application_access(
        db,
        application_id=application_id,
        user_id=current_user["id"],
        minimum_role=ROLE_OWNER,
    )

    try:
        await CollaborationService.remove_collaborator(
            db=db, application_id=application_id, user_id=user_id
        )
    except ValueError as e:
        if "application not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            ) from e
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("removing collaborator", e),
        ) from e


# ---------------------------------------------------------------------------
# POST /applications/{application_id}/submit-for-review
# ---------------------------------------------------------------------------


@router.post(
    "/applications/{application_id}/submit-for-review",
    response_model=ReviewSubmitResponse,
)
async def submit_for_review(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Submit an application for review.

    Transitions the application status to 'under_review'.

    Args:
        application_id: UUID of the grant application.
        db: Async database session (injected).
        current_user: Authenticated user (injected).

    Returns:
        ReviewSubmitResponse with success message and new status.
    """
    await require_application_access(
        db,
        application_id=application_id,
        user_id=current_user["id"],
        minimum_role=ROLE_EDITOR,
    )

    try:
        new_status = await CollaborationService.submit_for_review(
            db=db,
            application_id=application_id,
            user_id=uuid.UUID(current_user["id"]),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("submitting for review", e),
        ) from e

    return ReviewSubmitResponse(
        message="Application submitted for review",
        new_status=new_status,
    )


# ---------------------------------------------------------------------------
# POST /proposals/{proposal_id}/sections/{section_name}/approve
# ---------------------------------------------------------------------------


@router.post(
    "/proposals/{proposal_id}/sections/{section_name}/approve",
    response_model=SectionApprovalResponse,
)
async def approve_section(
    proposal_id: uuid.UUID,
    section_name: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Approve a proposal section.

    Sets the section's approval status to 'approved' in the section_approvals JSONB.

    Args:
        proposal_id: UUID of the proposal.
        section_name: Name of the section to approve.
        db: Async database session (injected).
        current_user: Authenticated user (injected).

    Returns:
        SectionApprovalResponse with approval details.
    """
    await require_proposal_access(
        db,
        proposal_id=proposal_id,
        user_id=current_user["id"],
        minimum_role=ROLE_REVIEWER,
    )

    try:
        result = await CollaborationService.approve_section(
            db=db,
            proposal_id=proposal_id,
            section_name=section_name,
            reviewer_id=uuid.UUID(current_user["id"]),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("section approval", e),
        ) from e

    return SectionApprovalResponse(
        section_name=result["section_name"],
        status=result["status"],
        reviewer_id=result["reviewer_id"],
        reviewed_at=result["reviewed_at"],
    )


# ---------------------------------------------------------------------------
# POST /proposals/{proposal_id}/sections/{section_name}/revise
# ---------------------------------------------------------------------------


@router.post(
    "/proposals/{proposal_id}/sections/{section_name}/revise",
    response_model=SectionApprovalResponse,
)
async def request_revision(
    proposal_id: uuid.UUID,
    section_name: str,
    notes: str | None = Query(None, description="Optional reviewer notes"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Request revision on a proposal section.

    Sets the section's approval status to 'needs_revision' in the section_approvals JSONB.

    Args:
        proposal_id: UUID of the proposal.
        section_name: Name of the section requiring revision.
        notes: Optional reviewer notes.
        db: Async database session (injected).
        current_user: Authenticated user (injected).

    Returns:
        SectionApprovalResponse with revision details.
    """
    await require_proposal_access(
        db,
        proposal_id=proposal_id,
        user_id=current_user["id"],
        minimum_role=ROLE_REVIEWER,
    )

    try:
        result = await CollaborationService.request_revision(
            db=db,
            proposal_id=proposal_id,
            section_name=section_name,
            reviewer_id=uuid.UUID(current_user["id"]),
            notes=notes,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("section revision request", e),
        ) from e

    return SectionApprovalResponse(
        section_name=result["section_name"],
        status=result["status"],
        reviewer_id=result["reviewer_id"],
        reviewed_at=result["reviewed_at"],
    )


# ---------------------------------------------------------------------------
# GET  /applications/{application_id}/comments
# ---------------------------------------------------------------------------


@router.get(
    "/applications/{application_id}/comments",
    response_model=CommentListResponse,
)
async def list_comments(
    application_id: uuid.UUID,
    proposal_id: str | None = Query(None, description="Filter by proposal UUID"),
    section_name: str | None = Query(None, description="Filter by section name"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """List comments for a grant application with optional filters.

    Args:
        application_id: UUID of the grant application.
        proposal_id: Optional filter by proposal UUID.
        section_name: Optional filter by section name.
        db: Async database session (injected).
        current_user: Authenticated user (injected).

    Returns:
        CommentListResponse with comments, total, and unresolved_count.
    """
    await require_application_access(
        db,
        application_id=application_id,
        user_id=current_user["id"],
        minimum_role=ROLE_VIEWER,
    )

    try:
        pid = uuid.UUID(proposal_id) if proposal_id else None
        if pid is not None:
            proposal = await db.get(Proposal, pid)
            if proposal is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Proposal not found",
                )
            if proposal.application_id != application_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="proposal_id does not belong to this application",
                )
        comments = await CollaborationService.list_comments(
            db=db,
            application_id=application_id,
            proposal_id=pid,
            section_name=section_name,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("listing comments", e),
        ) from e

    items = [_comment_to_response(c) for c in comments]
    unresolved = sum(1 for c in comments if not c.is_resolved)

    return CommentListResponse(
        comments=items,
        total=len(items),
        unresolved_count=unresolved,
    )


# ---------------------------------------------------------------------------
# POST /applications/{application_id}/comments
# ---------------------------------------------------------------------------


@router.post(
    "/applications/{application_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_comment(
    application_id: uuid.UUID,
    body: CommentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Add a comment to a grant application.

    Supports optional proposal/section targeting and reply threading via parent_id.

    Args:
        application_id: UUID of the grant application.
        body: CommentCreate with content and optional targeting fields.
        db: Async database session (injected).
        current_user: Authenticated user (injected).

    Returns:
        The created CommentResponse.
    """
    role = await require_application_access(
        db,
        application_id=application_id,
        user_id=current_user["id"],
        minimum_role=ROLE_VIEWER,
    )
    if role not in _REVIEWER_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Reviewer, editor, or owner role is required to create comments",
        )

    proposal_uuid: uuid.UUID | None = None
    if body.proposal_id:
        try:
            proposal_uuid = uuid.UUID(body.proposal_id)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid proposal_id format. Must be a valid UUID.",
            ) from e

        proposal = await db.get(Proposal, proposal_uuid)
        if proposal is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proposal not found",
            )
        if proposal.application_id != application_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="proposal_id does not belong to this application",
            )

    parent_uuid: uuid.UUID | None = None
    if body.parent_id:
        try:
            parent_uuid = uuid.UUID(body.parent_id)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid parent_id format. Must be a valid UUID.",
            ) from e

        parent_comment = await db.get(ApplicationComment, parent_uuid)
        if parent_comment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent comment not found",
            )
        if parent_comment.application_id != application_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="parent_id does not belong to this application",
            )

    comment = ApplicationComment(
        application_id=application_id,
        author_id=uuid.UUID(current_user["id"]),
        content=body.content,
        proposal_id=proposal_uuid,
        section_name=body.section_name,
        parent_id=parent_uuid,
    )

    try:
        db.add(comment)
        await db.flush()
        await db.refresh(comment)
    except Exception as e:
        logger.error(
            "Failed to create comment for application %s: %s", application_id, e
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("comment creation", e),
        ) from e

    return _comment_to_response(comment)


# ---------------------------------------------------------------------------
# PATCH /applications/{application_id}/comments/{comment_id}
# ---------------------------------------------------------------------------


@router.patch(
    "/applications/{application_id}/comments/{comment_id}",
    response_model=CommentResponse,
)
async def update_comment(
    application_id: uuid.UUID,
    comment_id: uuid.UUID,
    body: CommentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Update a comment (resolve/unresolve or edit content).

    When is_resolved is set to True, resolved_by and resolved_at are populated.
    When is_resolved is set to False, those fields are cleared.

    Args:
        application_id: UUID of the grant application.
        comment_id: UUID of the comment.
        body: CommentUpdate with optional is_resolved and/or content.
        db: Async database session (injected).
        current_user: Authenticated user (injected).

    Returns:
        The updated CommentResponse.

    Raises:
        HTTPException 404: Comment not found.
    """
    role = await require_application_access(
        db,
        application_id=application_id,
        user_id=current_user["id"],
        minimum_role=ROLE_VIEWER,
    )

    try:
        result = await db.execute(
            select(ApplicationComment).where(
                ApplicationComment.id == comment_id,
                ApplicationComment.application_id == application_id,
            )
        )
        comment = result.scalar_one_or_none()
    except Exception as e:
        logger.error("Failed to fetch comment %s: %s", comment_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("fetching comment", e),
        ) from e

    if comment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found",
        )

    current_user_id = uuid.UUID(current_user["id"])

    # Apply content update
    if body.content is not None:
        if comment.author_id != current_user_id and role not in _EDITOR_ROLES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the comment author or an editor/owner can edit content",
            )
        comment.content = body.content

    # Handle resolution toggling
    if body.is_resolved is not None:
        if role not in _REVIEWER_ROLES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Reviewer, editor, or owner role is required to resolve comments",
            )
        comment.is_resolved = body.is_resolved
        if body.is_resolved:
            comment.resolved_by = current_user_id
            comment.resolved_at = func.now()
        else:
            comment.resolved_by = None
            comment.resolved_at = None

    try:
        await db.flush()
        await db.refresh(comment)
    except Exception as e:
        logger.error("Failed to update comment %s: %s", comment_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("comment update", e),
        ) from e

    return _comment_to_response(comment)
