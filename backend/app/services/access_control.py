"""Shared access-control helpers for application-scoped resources."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.attachment import ApplicationAttachment
from app.models.db.collaboration import ApplicationCollaborator
from app.models.db.grant_application import GrantApplication
from app.models.db.proposal import Proposal

ROLE_VIEWER = "viewer"
ROLE_REVIEWER = "reviewer"
ROLE_EDITOR = "editor"
ROLE_OWNER = "owner"

_ROLE_RANK: dict[str, int] = {
    ROLE_VIEWER: 1,
    ROLE_REVIEWER: 2,
    ROLE_EDITOR: 3,
    ROLE_OWNER: 4,
}


def _to_uuid(value: str | uuid.UUID) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authenticated user ID",
        ) from exc


def _require_valid_role(role: str) -> None:
    if role not in _ROLE_RANK:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Invalid role requirement: {role}",
        )


async def require_application_access(
    db: AsyncSession,
    application_id: uuid.UUID,
    user_id: str | uuid.UUID,
    minimum_role: str = ROLE_VIEWER,
) -> str:
    """Require role-based access to an application and return resolved role."""
    _require_valid_role(minimum_role)
    user_uuid = _to_uuid(user_id)

    app_result = await db.execute(
        select(GrantApplication.user_id).where(GrantApplication.id == application_id)
    )
    owner_id = app_result.scalar_one_or_none()
    if owner_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    resolved_role: str | None
    if owner_id == user_uuid:
        resolved_role = ROLE_OWNER
    else:
        role_result = await db.execute(
            select(ApplicationCollaborator.role).where(
                ApplicationCollaborator.application_id == application_id,
                ApplicationCollaborator.user_id == user_uuid,
            )
        )
        resolved_role = role_result.scalar_one_or_none()

    if resolved_role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this application",
        )

    if _ROLE_RANK.get(resolved_role, 0) < _ROLE_RANK[minimum_role]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Insufficient permissions for this operation. "
                f"Requires {minimum_role} role or higher."
            ),
        )

    return resolved_role


async def require_attachment_access(
    db: AsyncSession,
    attachment_id: uuid.UUID,
    user_id: str | uuid.UUID,
    minimum_role: str = ROLE_VIEWER,
) -> ApplicationAttachment:
    """Load attachment and enforce access to its parent application."""
    attachment = await db.get(ApplicationAttachment, attachment_id)
    if attachment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )

    await require_application_access(
        db,
        application_id=attachment.application_id,
        user_id=user_id,
        minimum_role=minimum_role,
    )
    return attachment


async def require_proposal_access(
    db: AsyncSession,
    proposal_id: uuid.UUID,
    user_id: str | uuid.UUID,
    minimum_role: str = ROLE_VIEWER,
) -> Proposal:
    """Load proposal and enforce ownership or linked-application access."""
    _require_valid_role(minimum_role)
    user_uuid = _to_uuid(user_id)

    proposal = await db.get(Proposal, proposal_id)
    if proposal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proposal not found",
        )

    if proposal.user_id == user_uuid:
        return proposal

    if proposal.application_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this proposal",
        )

    await require_application_access(
        db,
        application_id=proposal.application_id,
        user_id=user_uuid,
        minimum_role=minimum_role,
    )
    return proposal
