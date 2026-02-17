"""
Executive Brief Models for GrantScope2 Application.

This module provides Pydantic models for the executive brief generation system,
which creates leadership-ready briefings for cards in the workstream Kanban workflow.

Supports:
- ExecutiveBriefCreate: Request model for generating a new brief
- ExecutiveBriefResponse: Full brief data including content and metadata
- BriefStatusResponse: Lightweight status polling response
- BriefGenerateResponse: Response after triggering generation

Database Table: executive_briefs
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator
from uuid import UUID
from enum import Enum
import re


# Valid status values for brief generation
VALID_BRIEF_STATUSES = {"pending", "generating", "completed", "failed"}


class BriefStatusEnum(str, Enum):
    """Status values for brief generation."""

    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class BriefSection(BaseModel):
    """
    Individual section within an executive brief.

    Represents a single section like Executive Summary, Key Findings, etc.
    """

    title: str = Field(
        ..., description="Section title (e.g., 'Executive Summary', 'Key Findings')"
    )
    content: str = Field(..., description="Markdown-formatted section content")
    order: int = Field(0, ge=0, description="Order of section in the brief")


class ExecutiveBriefCreate(BaseModel):
    """
    Request model for generating a new executive brief.

    The brief is generated for a specific card within a workstream context,
    synthesizing card data, user notes, related cards, and source materials
    into a comprehensive leadership briefing.
    """

    workstream_card_id: str = Field(
        ...,
        description="UUID of the workstream_cards record (links card to workstream)",
    )
    card_id: str = Field(..., description="UUID of the card to generate a brief for")

    @validator("workstream_card_id", "card_id")
    def validate_uuid_format(cls, v):
        """Validate UUID format."""
        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            re.IGNORECASE,
        )
        if not uuid_pattern.match(v):
            raise ValueError("Invalid UUID format")
        return v


class ExecutiveBriefResponse(BaseModel):
    """
    Response model for executive brief data.

    Contains the full brief content (both structured JSON and markdown),
    generation metadata (tokens, timing, model), and status information.
    Briefs are visible to all authenticated users once generated.
    """

    id: str = Field(..., description="UUID of the executive brief record")
    workstream_card_id: str = Field(
        ..., description="UUID of the workstream_cards record this brief belongs to"
    )
    card_id: str = Field(..., description="UUID of the card this brief is about")
    created_by: str = Field(
        ..., description="UUID of the user who initiated brief generation"
    )
    status: str = Field(
        ...,
        description="Brief generation status: pending, generating, completed, failed",
    )
    version: int = Field(
        1, ge=1, description="Version number of this brief (1, 2, 3, etc.)"
    )
    sources_since_previous: Optional[Dict[str, Any]] = Field(
        None,
        description="Metadata about sources discovered since previous brief version",
    )

    # Brief content
    content: Optional[Dict[str, Any]] = Field(
        None, description="Structured brief content as JSON with sections"
    )
    content_markdown: Optional[str] = Field(
        None, description="Full brief as markdown for display and export"
    )
    summary: Optional[str] = Field(
        None, description="Executive summary extracted for quick display"
    )

    # Generation metadata
    generated_at: Optional[datetime] = Field(
        None, description="Timestamp when brief generation completed"
    )
    generation_time_ms: Optional[int] = Field(
        None, ge=0, description="Time taken to generate brief in milliseconds"
    )
    model_used: Optional[str] = Field(
        None, description="AI model used for generation (e.g., gpt-4o)"
    )
    prompt_tokens: Optional[int] = Field(
        None, ge=0, description="Number of tokens in the prompt"
    )
    completion_tokens: Optional[int] = Field(
        None, ge=0, description="Number of tokens in the completion"
    )

    # Error handling
    error_message: Optional[str] = Field(
        None, description="Error message if generation failed"
    )

    # Timestamps
    created_at: datetime = Field(
        ..., description="Timestamp when brief record was created"
    )
    updated_at: datetime = Field(
        ..., description="Timestamp when brief was last updated"
    )

    class Config:
        from_attributes = True

    @validator("status")
    def validate_status(cls, v):
        """Validate status is a known brief generation status."""
        if v not in VALID_BRIEF_STATUSES:
            raise ValueError(
                f'Invalid status. Must be one of: {", ".join(sorted(VALID_BRIEF_STATUSES))}'
            )
        return v


class BriefStatusResponse(BaseModel):
    """
    Lightweight response model for brief generation status polling.

    Used by the frontend to poll for generation completion without
    fetching the full brief content until ready.
    """

    id: str = Field(..., description="Brief identifier")
    status: str = Field(
        ...,
        description="Brief generation status: pending, generating, completed, failed",
    )
    version: int = Field(1, ge=1, description="Version number of this brief")
    summary: Optional[str] = Field(
        None, description="Executive summary (only populated when completed)"
    )
    error_message: Optional[str] = Field(
        None, description="Error message (only populated when failed)"
    )
    generated_at: Optional[datetime] = Field(
        None, description="Timestamp when generation completed"
    )
    progress_message: Optional[str] = Field(
        None, description="Progress message during processing"
    )

    @validator("status")
    def validate_status(cls, v):
        """Validate status is a known brief generation status."""
        if v not in VALID_BRIEF_STATUSES:
            raise ValueError(
                f'Invalid status. Must be one of: {", ".join(sorted(VALID_BRIEF_STATUSES))}'
            )
        return v


class BriefGenerateResponse(BaseModel):
    """
    Response after triggering brief generation.

    Returns the brief ID and initial pending status for polling.
    """

    id: str = Field(..., description="Unique identifier for tracking the brief")
    status: str = Field("pending", description="Initial status (always 'pending')")
    version: int = Field(
        1, ge=1, description="Version number of the brief being generated"
    )
    message: str = Field("Brief generation started", description="Status message")


class BriefListItem(BaseModel):
    """
    Compact brief representation for list views.

    Used when displaying multiple briefs (e.g., in workstream overview)
    without loading full content.
    """

    id: str = Field(..., description="UUID of the executive brief record")
    workstream_card_id: str = Field(
        ..., description="UUID of the workstream_cards record"
    )
    card_id: str = Field(..., description="UUID of the card")
    status: str = Field(..., description="Brief generation status")
    version: int = Field(1, ge=1, description="Version number of this brief")
    summary: Optional[str] = Field(None, description="Executive summary for preview")
    generated_at: Optional[datetime] = Field(
        None, description="When the brief was generated"
    )
    created_at: datetime = Field(..., description="When the brief record was created")

    class Config:
        from_attributes = True


class BriefVersionListItem(BaseModel):
    """
    Compact representation of a brief version for version history display.

    Used in the version history panel to show available versions
    without loading full content.
    """

    id: str = Field(..., description="UUID of the executive brief record")
    version: int = Field(..., ge=1, description="Version number (1, 2, 3, etc.)")
    status: str = Field(..., description="Brief generation status")
    summary: Optional[str] = Field(None, description="Executive summary for preview")
    sources_since_previous: Optional[Dict[str, Any]] = Field(
        None, description="Metadata about new sources since previous version"
    )
    generated_at: Optional[datetime] = Field(
        None, description="When the brief was generated"
    )
    created_at: datetime = Field(..., description="When the brief record was created")
    model_used: Optional[str] = Field(None, description="AI model used for generation")

    class Config:
        from_attributes = True


class BriefVersionsResponse(BaseModel):
    """
    Response containing all versions of a brief for a workstream card.

    Used by the version history panel to display available versions.
    """

    workstream_card_id: str = Field(
        ..., description="UUID of the workstream card these briefs belong to"
    )
    card_id: str = Field(..., description="UUID of the underlying card")
    total_versions: int = Field(..., ge=0, description="Total number of brief versions")
    versions: List[BriefVersionListItem] = Field(
        default_factory=list,
        description="List of brief versions, ordered by version DESC (newest first)",
    )
