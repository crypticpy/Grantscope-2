"""Core domain models for Foresight API.

Foundational models representing the primary entities in the system:
cards, user profiles, and related lookup types.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator


class UserProfile(BaseModel):
    id: str
    email: str
    display_name: Optional[str] = None
    department: Optional[str] = None
    role: Optional[str] = None
    preferences: Dict[str, Any] = {}


class Card(BaseModel):
    id: str
    name: str
    slug: str
    summary: Optional[str] = None
    description: Optional[str] = None
    pillar_id: Optional[str] = None
    goal_id: Optional[str] = None
    anchor_id: Optional[str] = None
    stage_id: Optional[str] = None
    horizon: Optional[str] = None
    novelty_score: Optional[int] = None
    maturity_score: Optional[int] = None
    impact_score: Optional[int] = None
    relevance_score: Optional[int] = None
    velocity_score: Optional[int] = None
    risk_score: Optional[int] = None
    opportunity_score: Optional[int] = None
    signal_quality_score: Optional[int] = None
    status: str = "active"
    created_at: datetime
    updated_at: datetime


class CardCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200, description="Card name")
    summary: Optional[str] = Field(None, max_length=2000, description="Card summary")
    description: Optional[str] = Field(
        None, max_length=10000, description="Detailed description"
    )
    pillar_id: Optional[str] = Field(
        None, pattern=r"^[A-Z]{2}$", description="Pillar code (e.g., CH, MC)"
    )
    goal_id: Optional[str] = Field(
        None, pattern=r"^[A-Z]{2}\.\d+$", description="Goal code (e.g., CH.1)"
    )
    anchor_id: Optional[str] = None
    stage_id: Optional[str] = None
    horizon: Optional[str] = Field(
        None, pattern=r"^H[123]$", description="Horizon (H1, H2, H3)"
    )

    @validator("name")
    def name_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Name cannot be empty or whitespace")
        return v.strip()


class SimilarCard(BaseModel):
    """Response model for similar cards."""

    id: str
    name: str
    summary: Optional[str] = None
    similarity: float
    pillar_id: Optional[str] = None


class BlockedTopic(BaseModel):
    """Response model for blocked discovery topics."""

    id: str
    topic_pattern: str
    reason: str
    blocked_by_count: int
    created_at: datetime
