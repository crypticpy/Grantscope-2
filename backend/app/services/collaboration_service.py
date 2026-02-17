"""Business logic for the Collaboration/Review Workflow feature."""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.collaboration import ApplicationCollaborator, ApplicationComment
from app.models.db.grant_application import GrantApplication
from app.models.db.proposal import Proposal as ProposalDB

logger = logging.getLogger(__name__)


class CollaborationService:
    """Service layer for collaboration and review operations."""

    # ------------------------------------------------------------------
    # Collaborator management
    # ------------------------------------------------------------------

    @staticmethod
    async def add_collaborator(
        db: AsyncSession,
        application_id: uuid.UUID,
        user_id: uuid.UUID,
        role: str,
        invited_by: uuid.UUID,
    ) -> ApplicationCollaborator:
        """Add a collaborator to an application.

        Args:
            db: Async database session.
            application_id: UUID of the grant application.
            user_id: UUID of the user to invite.
            role: Collaboration role (owner, editor, reviewer, viewer).
            invited_by: UUID of the user performing the invitation.

        Returns:
            The newly created ApplicationCollaborator record.

        Raises:
            ValueError: If the target user does not exist or is already a collaborator.
        """
        # Verify target user exists
        user_check = await db.execute(
            text("SELECT id FROM users WHERE id = :uid"),
            {"uid": user_id},
        )
        if user_check.first() is None:
            raise ValueError("User not found")

        # Check if already a collaborator
        existing = await db.execute(
            select(ApplicationCollaborator).where(
                ApplicationCollaborator.application_id == application_id,
                ApplicationCollaborator.user_id == user_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ValueError("User is already a collaborator on this application")

        collaborator = ApplicationCollaborator(
            application_id=application_id,
            user_id=user_id,
            role=role,
            invited_by=invited_by,
        )
        db.add(collaborator)
        await db.flush()
        await db.refresh(collaborator)
        return collaborator

    @staticmethod
    async def remove_collaborator(
        db: AsyncSession,
        application_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Remove a collaborator from an application.

        Owners cannot be removed.

        Args:
            db: Async database session.
            application_id: UUID of the grant application.
            user_id: UUID of the collaborator to remove.

        Raises:
            ValueError: If the user is the owner or is not a collaborator.
        """
        result = await db.execute(
            select(ApplicationCollaborator).where(
                ApplicationCollaborator.application_id == application_id,
                ApplicationCollaborator.user_id == user_id,
            )
        )
        collaborator = result.scalar_one_or_none()

        if collaborator is None:
            raise ValueError("Collaborator not found")

        if collaborator.role == "owner":
            raise ValueError("Cannot remove the application owner")

        await db.delete(collaborator)
        await db.flush()

    @staticmethod
    async def check_access(
        db: AsyncSession,
        application_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> str | None:
        """Check a user's access level for an application.

        Returns the role string if the user has access, or None otherwise.
        Also checks if the user is the application owner (grant_applications.user_id).

        Args:
            db: Async database session.
            application_id: UUID of the grant application.
            user_id: UUID of the user to check.

        Returns:
            Role string ('owner', 'editor', 'reviewer', 'viewer') or None.
        """
        # Check if user is the application owner
        app_result = await db.execute(
            select(GrantApplication).where(GrantApplication.id == application_id)
        )
        application = app_result.scalar_one_or_none()
        if application and application.user_id == user_id:
            return "owner"

        # Check collaborator table
        collab_result = await db.execute(
            select(ApplicationCollaborator.role).where(
                ApplicationCollaborator.application_id == application_id,
                ApplicationCollaborator.user_id == user_id,
            )
        )
        row = collab_result.first()
        return row[0] if row else None

    # ------------------------------------------------------------------
    # Review workflow
    # ------------------------------------------------------------------

    @staticmethod
    async def submit_for_review(
        db: AsyncSession,
        application_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> str:
        """Submit an application for review.

        Updates the application status to 'under_review'.

        Args:
            db: Async database session.
            application_id: UUID of the grant application.
            user_id: UUID of the submitting user.

        Returns:
            The new status string.

        Raises:
            ValueError: If the application is not found.
        """
        result = await db.execute(
            select(GrantApplication).where(GrantApplication.id == application_id)
        )
        application = result.scalar_one_or_none()
        if application is None:
            raise ValueError("Application not found")

        application.status = "under_review"
        await db.flush()
        return "under_review"

    @staticmethod
    async def approve_section(
        db: AsyncSession,
        proposal_id: uuid.UUID,
        section_name: str,
        reviewer_id: uuid.UUID,
    ) -> dict:
        """Approve a proposal section.

        Updates the section_approvals JSONB column for the given section.

        Args:
            db: Async database session.
            proposal_id: UUID of the proposal.
            section_name: Name of the section to approve.
            reviewer_id: UUID of the reviewing user.

        Returns:
            Dict with section_name, status, reviewer_id, and reviewed_at.

        Raises:
            ValueError: If the proposal is not found.
        """
        result = await db.execute(
            select(ProposalDB).where(ProposalDB.id == proposal_id)
        )
        proposal = result.scalar_one_or_none()
        if proposal is None:
            raise ValueError("Proposal not found")

        now_iso = datetime.now(timezone.utc).isoformat()
        approval_entry = {
            "status": "approved",
            "reviewer_id": str(reviewer_id),
            "reviewed_at": now_iso,
        }

        # Update the section_approvals JSONB
        # Use raw SQL for JSONB key update since the column may not be on the ORM yet
        await db.execute(
            text(
                "UPDATE proposals "
                "SET section_approvals = COALESCE(section_approvals, '{}'::jsonb) || :patch, "
                "    updated_at = NOW() "
                "WHERE id = :pid"
            ),
            {
                "patch": {section_name: approval_entry},
                "pid": proposal_id,
            },
        )
        await db.flush()

        return {
            "section_name": section_name,
            "status": "approved",
            "reviewer_id": str(reviewer_id),
            "reviewed_at": now_iso,
        }

    @staticmethod
    async def request_revision(
        db: AsyncSession,
        proposal_id: uuid.UUID,
        section_name: str,
        reviewer_id: uuid.UUID,
        notes: str | None = None,
    ) -> dict:
        """Request revision on a proposal section.

        Updates the section_approvals JSONB column with 'needs_revision' status.

        Args:
            db: Async database session.
            proposal_id: UUID of the proposal.
            section_name: Name of the section requiring revision.
            reviewer_id: UUID of the reviewing user.
            notes: Optional reviewer notes explaining the revision request.

        Returns:
            Dict with section_name, status, reviewer_id, reviewed_at, and notes.

        Raises:
            ValueError: If the proposal is not found.
        """
        result = await db.execute(
            select(ProposalDB).where(ProposalDB.id == proposal_id)
        )
        proposal = result.scalar_one_or_none()
        if proposal is None:
            raise ValueError("Proposal not found")

        now_iso = datetime.now(timezone.utc).isoformat()
        revision_entry: dict = {
            "status": "needs_revision",
            "reviewer_id": str(reviewer_id),
            "reviewed_at": now_iso,
        }
        if notes:
            revision_entry["notes"] = notes

        await db.execute(
            text(
                "UPDATE proposals "
                "SET section_approvals = COALESCE(section_approvals, '{}'::jsonb) || :patch, "
                "    updated_at = NOW() "
                "WHERE id = :pid"
            ),
            {
                "patch": {section_name: revision_entry},
                "pid": proposal_id,
            },
        )
        await db.flush()

        return {
            "section_name": section_name,
            "status": "needs_revision",
            "reviewer_id": str(reviewer_id),
            "reviewed_at": now_iso,
            "notes": notes,
        }

    # ------------------------------------------------------------------
    # Listing helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def list_collaborators(
        db: AsyncSession,
        application_id: uuid.UUID,
    ) -> list[ApplicationCollaborator]:
        """List all collaborators for an application.

        Args:
            db: Async database session.
            application_id: UUID of the grant application.

        Returns:
            List of ApplicationCollaborator records ordered by invited_at.
        """
        result = await db.execute(
            select(ApplicationCollaborator)
            .where(ApplicationCollaborator.application_id == application_id)
            .order_by(ApplicationCollaborator.invited_at)
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_comments(
        db: AsyncSession,
        application_id: uuid.UUID,
        proposal_id: uuid.UUID | None = None,
        section_name: str | None = None,
    ) -> list[ApplicationComment]:
        """List comments for an application with optional filters.

        Args:
            db: Async database session.
            application_id: UUID of the grant application.
            proposal_id: Optional filter by proposal UUID.
            section_name: Optional filter by section name.

        Returns:
            List of ApplicationComment records ordered by created_at ascending.
        """
        query = select(ApplicationComment).where(
            ApplicationComment.application_id == application_id
        )

        if proposal_id is not None:
            query = query.where(ApplicationComment.proposal_id == proposal_id)
        if section_name is not None:
            query = query.where(ApplicationComment.section_name == section_name)

        query = query.order_by(ApplicationComment.created_at.asc())

        result = await db.execute(query)
        return list(result.scalars().all())
