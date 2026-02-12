"""
AI Helper Models

This module provides Pydantic models for AI-assisted helper endpoints,
such as generating workstream descriptions from names and context.

Supports:
- SuggestDescriptionRequest: Request body for AI-generated workstream description
- SuggestDescriptionResponse: Response for AI-generated workstream description
"""

from typing import Optional, List
from pydantic import BaseModel, Field


class SuggestDescriptionRequest(BaseModel):
    """Request body for AI-generated workstream description."""

    name: str = Field(..., min_length=2, max_length=200, description="Workstream name")
    pillar_ids: Optional[List[str]] = Field(
        default=[], description="Strategic pillar IDs for context"
    )
    keywords: Optional[List[str]] = Field(
        default=[], description="Keywords for context"
    )


class SuggestDescriptionResponse(BaseModel):
    """Response for AI-generated workstream description."""

    description: str = Field(..., description="AI-generated workstream description")
