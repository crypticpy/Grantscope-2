"""Proposal models for GrantScope API."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ProposalSection(BaseModel):
    """A single section of a proposal."""

    content: str = ""
    ai_draft: Optional[str] = None
    last_edited: Optional[str] = None


class Proposal(BaseModel):
    """A grant proposal draft."""

    id: str
    card_id: str
    workstream_id: str
    user_id: str
    application_id: Optional[str] = None
    title: str
    version: int = 1
    status: str = "draft"
    sections: Dict[str, Any] = {}
    ai_model: Optional[str] = None
    ai_generation_metadata: Dict[str, Any] = {}
    reviewer_id: Optional[str] = None
    review_notes: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ProposalCreate(BaseModel):
    """Request to create a new proposal."""

    card_id: str = Field(..., description="UUID of the grant opportunity card")
    workstream_id: str = Field(..., description="UUID of the program/workstream")
    title: Optional[str] = Field(
        None,
        max_length=500,
        description="Proposal title (auto-generated if not provided)",
    )


class ProposalUpdate(BaseModel):
    """Request to update a proposal."""

    title: Optional[str] = Field(None, max_length=500)
    status: Optional[str] = None
    sections: Optional[Dict[str, Any]] = None
    review_notes: Optional[str] = None


class GenerateSectionRequest(BaseModel):
    """Request to AI-generate a specific proposal section."""

    section_name: str = Field(
        ...,
        description="Section to generate (executive_summary, needs_statement, project_description, budget_narrative, timeline, evaluation_plan)",
    )
    additional_context: Optional[str] = Field(
        None, max_length=5000, description="Extra context for AI generation"
    )


class GenerateSectionResponse(BaseModel):
    """Response from AI section generation."""

    section_name: str
    ai_draft: str
    model_used: str


class ProposalListResponse(BaseModel):
    """List of proposals."""

    proposals: List[Proposal]
    total: int
