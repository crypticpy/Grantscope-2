"""Core domain models for GrantScope API.

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
    department_id: Optional[str] = None
    title: Optional[str] = None
    bio: Optional[str] = None
    program_name: Optional[str] = None
    program_mission: Optional[str] = None
    team_size: Optional[str] = None
    budget_range: Optional[str] = None
    grant_experience: Optional[str] = None
    grant_categories: List[str] = []
    funding_range_min: Optional[int] = None
    funding_range_max: Optional[int] = None
    strategic_pillars: List[str] = []
    priorities: List[str] = []
    custom_priorities: Optional[str] = None
    help_wanted: List[str] = []
    update_frequency: Optional[str] = None
    profile_completed_at: Optional[str] = None
    profile_step: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ProfileSetupUpdate(BaseModel):
    """Payload for profile wizard step saves. All fields optional for partial updates."""

    display_name: Optional[str] = None
    department_id: Optional[str] = None
    title: Optional[str] = None
    bio: Optional[str] = None
    program_name: Optional[str] = None
    program_mission: Optional[str] = None
    team_size: Optional[str] = None
    budget_range: Optional[str] = None
    grant_experience: Optional[str] = None
    grant_categories: Optional[List[str]] = None
    funding_range_min: Optional[int] = None
    funding_range_max: Optional[int] = None
    strategic_pillars: Optional[List[str]] = None
    priorities: Optional[List[str]] = None
    custom_priorities: Optional[str] = None
    help_wanted: Optional[List[str]] = None
    update_frequency: Optional[str] = None
    profile_step: Optional[int] = None
    # profile_completed_at is computed server-side, not client-settable


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
    pipeline_status: Optional[str] = "discovered"
    pipeline_status_changed_at: Optional[datetime] = None
    novelty_score: Optional[int] = None
    maturity_score: Optional[int] = None
    impact_score: Optional[int] = None
    relevance_score: Optional[int] = None
    velocity_score: Optional[int] = None
    risk_score: Optional[int] = None
    opportunity_score: Optional[int] = None
    # Grant-specific fields
    grant_type: Optional[str] = None
    funding_amount_min: Optional[float] = None
    funding_amount_max: Optional[float] = None
    deadline: Optional[datetime] = None
    grantor: Optional[str] = None
    cfda_number: Optional[str] = None
    grants_gov_id: Optional[str] = None
    sam_opportunity_id: Optional[str] = None
    eligibility_text: Optional[str] = None
    match_requirement: Optional[str] = None
    category_id: Optional[str] = None
    source_url: Optional[str] = None
    alignment_score: Optional[int] = None
    readiness_score: Optional[int] = None
    competition_score: Optional[int] = None
    urgency_score: Optional[int] = None
    probability_score: Optional[int] = None
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
    pipeline_status: Optional[str] = Field(
        None,
        description="Pipeline status (discovered, evaluating, applying, submitted, awarded, active, closed, declined, expired)",
    )
    # Grant-specific fields
    grant_type: Optional[str] = Field(
        None, description="Grant type (federal, state, foundation, local, other)"
    )
    funding_amount_min: Optional[float] = Field(
        None, ge=0, description="Minimum funding amount"
    )
    funding_amount_max: Optional[float] = Field(
        None, ge=0, description="Maximum funding amount"
    )
    deadline: Optional[datetime] = Field(None, description="Application deadline")
    grantor: Optional[str] = Field(
        None, max_length=500, description="Granting organization"
    )
    category_id: Optional[str] = Field(None, description="Grant category code")
    source_url: Optional[str] = Field(
        None, max_length=2000, description="Source URL for the opportunity"
    )

    @validator("name")
    def name_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Name cannot be empty or whitespace")
        return v.strip()

    @validator("pipeline_status")
    def validate_pipeline_status(cls, v):
        if v is not None:
            from app.taxonomy import VALID_PIPELINE_STATUSES

            if v not in VALID_PIPELINE_STATUSES:
                raise ValueError(
                    f'Invalid pipeline_status "{v}". '
                    f"Valid values: {sorted(VALID_PIPELINE_STATUSES)}"
                )
        return v


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
