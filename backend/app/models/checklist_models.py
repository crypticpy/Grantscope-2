"""Pydantic request/response schemas for the Application Materials Checklist."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ChecklistItemResponse(BaseModel):
    """Full checklist item response (mirrors all DB columns)."""

    id: UUID
    application_id: UUID
    category: str = "other"
    description: str
    is_mandatory: bool = False
    is_completed: bool = False
    completed_at: Optional[datetime] = None
    completed_by: Optional[UUID] = None
    attachment_id: Optional[UUID] = None
    source: str = "extracted"
    sort_order: int = 0
    sub_deadline: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ChecklistItemCreate(BaseModel):
    """Request body for creating a custom checklist item."""

    description: str = Field(
        ..., min_length=1, max_length=2000, description="Item description"
    )
    category: str = Field(
        "other",
        description="Category: narrative, budget, timeline, evaluation, organizational, staffing, legal, registration, other",
    )
    is_mandatory: bool = Field(False, description="Whether this item is mandatory")
    sub_deadline: Optional[datetime] = Field(
        None, description="Sub-deadline for this item"
    )
    notes: Optional[str] = Field(None, max_length=5000, description="Additional notes")


class ChecklistItemUpdate(BaseModel):
    """Request body for updating a checklist item. All fields optional."""

    is_completed: Optional[bool] = None
    notes: Optional[str] = Field(None, max_length=5000)
    sub_deadline: Optional[datetime] = None
    description: Optional[str] = Field(None, min_length=1, max_length=2000)
    category: Optional[str] = None
    attachment_id: Optional[UUID] = None


class ChecklistListResponse(BaseModel):
    """Paginated list of checklist items with progress summary."""

    items: List[ChecklistItemResponse]
    total: int
    completed: int
    progress_pct: float


class AISuggestResponse(BaseModel):
    """Response from the AI-suggest endpoint."""

    suggestions: List[ChecklistItemResponse]
    message: str
