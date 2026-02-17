"""Pydantic request/response schemas for the Collaboration/Review Workflow."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Collaborator schemas
# ---------------------------------------------------------------------------

VALID_ROLES = {"owner", "editor", "reviewer", "viewer"}


class CollaboratorResponse(BaseModel):
    """Full collaborator record returned by the API."""

    id: str
    application_id: str
    user_id: str
    role: str
    invited_by: Optional[str] = None
    invited_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CollaboratorAdd(BaseModel):
    """Request body for adding a collaborator to an application."""

    user_id: str = Field(..., description="UUID of the user to invite")
    role: str = Field(
        "viewer",
        description="Role: owner, editor, reviewer, or viewer",
    )

    def model_post_init(self, __context) -> None:  # noqa: D401
        """Validate that the role is one of the allowed values."""
        if self.role not in VALID_ROLES:
            raise ValueError(
                f"Invalid role '{self.role}'. Must be one of: {', '.join(sorted(VALID_ROLES))}"
            )


class CollaboratorListResponse(BaseModel):
    """List of collaborators with total count."""

    collaborators: List[CollaboratorResponse]
    total: int


# ---------------------------------------------------------------------------
# Comment schemas
# ---------------------------------------------------------------------------


class CommentResponse(BaseModel):
    """Full comment record returned by the API."""

    id: str
    application_id: str
    proposal_id: Optional[str] = None
    section_name: Optional[str] = None
    parent_id: Optional[str] = None
    author_id: str
    content: str
    is_resolved: bool = False
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CommentCreate(BaseModel):
    """Request body for creating a comment."""

    content: str = Field(
        ..., min_length=1, max_length=10000, description="Comment text"
    )
    proposal_id: Optional[str] = Field(
        None, description="UUID of the proposal (optional)"
    )
    section_name: Optional[str] = Field(
        None,
        description="Proposal section name (e.g. executive_summary, needs_statement)",
    )
    parent_id: Optional[str] = Field(
        None, description="UUID of parent comment for threading"
    )


class CommentUpdate(BaseModel):
    """Request body for updating a comment (resolve or edit)."""

    is_resolved: Optional[bool] = None
    content: Optional[str] = Field(None, min_length=1, max_length=10000)


class CommentListResponse(BaseModel):
    """List of comments with total and unresolved counts."""

    comments: List[CommentResponse]
    total: int
    unresolved_count: int


# ---------------------------------------------------------------------------
# Section approval schemas
# ---------------------------------------------------------------------------


class SectionApprovalRequest(BaseModel):
    """Request body for approving or requesting revision on a proposal section."""

    section_name: str = Field(
        ...,
        description="Section to approve/revise (e.g. executive_summary, budget_narrative)",
    )
    notes: Optional[str] = Field(
        None, max_length=5000, description="Optional reviewer notes"
    )


class SectionApprovalResponse(BaseModel):
    """Response after approving or requesting revision on a section."""

    section_name: str
    status: str
    reviewer_id: str
    reviewed_at: str


class ReviewSubmitResponse(BaseModel):
    """Response after submitting an application for review."""

    message: str
    new_status: str
