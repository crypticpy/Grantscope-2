"""
Domain Reputation Models for Source Authority Tracking

This module provides Pydantic models for the domain reputation API endpoints,
enabling CRUD operations on domain reputation records, leaderboard display,
and domain-based filtering for the information quality system.

Domain reputation combines curated editorial tiers with computed metrics
from user ratings and triage pass rates to produce a composite authority score.

Database Table: domain_reputation
Columns: id, domain_pattern, organization_name, category, curated_tier,
         user_quality_avg, user_relevance_avg, user_rating_count,
         triage_pass_rate, composite_score, texas_relevance_bonus,
         is_active, notes, created_at, updated_at
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# ============================================================================
# Domain Reputation Response Models
# ============================================================================


class DomainReputationResponse(BaseModel):
    """
    Full domain reputation record response.

    Includes both curated editorial data and computed metrics
    derived from user ratings and triage history.
    """

    id: str = Field(..., description="UUID of the domain reputation record")
    domain_pattern: str = Field(
        ..., description="Domain pattern (e.g., 'gartner.com', '*.gov')"
    )
    organization_name: str = Field(..., description="Human-readable organization name")
    category: str = Field(
        ..., description="Source category (e.g., 'government', 'academic', 'industry')"
    )
    curated_tier: Optional[int] = Field(
        None, description="Editorial curated tier (1=highest, 2=mid, 3=baseline)"
    )
    user_quality_avg: float = Field(
        default=0, description="Average user quality rating (1.0-5.0)"
    )
    user_relevance_avg: float = Field(
        default=0, description="Average user relevance rating"
    )
    user_rating_count: int = Field(
        default=0, description="Total number of user ratings for this domain"
    )
    triage_pass_rate: float = Field(
        default=0, description="Rate of cards from this domain passing triage (0.0-1.0)"
    )
    composite_score: float = Field(
        default=0, description="Computed composite reputation score"
    )
    texas_relevance_bonus: int = Field(
        default=0, description="Bonus points for Texas/Austin-specific sources (0-20)"
    )
    is_active: bool = Field(
        default=True, description="Whether this domain is actively tracked"
    )
    notes: Optional[str] = Field(None, description="Editorial notes about this domain")
    created_at: datetime = Field(..., description="When the domain record was created")
    updated_at: datetime = Field(
        ..., description="When the domain record was last updated"
    )


# ============================================================================
# Domain Reputation Request Models
# ============================================================================


class DomainReputationCreate(BaseModel):
    """
    Request body for adding a new domain reputation record.

    Used by administrators to seed the domain reputation table
    with curated editorial assessments.
    """

    domain_pattern: str = Field(
        ..., description="Domain pattern (e.g., 'gartner.com', '*.gov')"
    )
    organization_name: str = Field(..., description="Human-readable organization name")
    category: str = Field(
        ..., description="Source category (e.g., 'government', 'academic', 'industry')"
    )
    curated_tier: Optional[int] = Field(
        None,
        ge=1,
        le=3,
        description="Editorial curated tier (1=highest, 2=mid, 3=baseline)",
    )
    texas_relevance_bonus: int = Field(
        0,
        ge=0,
        le=20,
        description="Bonus points for Texas/Austin-specific sources (0-20)",
    )
    notes: Optional[str] = Field(None, description="Editorial notes about this domain")


class DomainReputationUpdate(BaseModel):
    """
    Request body for updating an existing domain reputation record.

    All fields are optional - only provided fields are updated.
    """

    organization_name: Optional[str] = Field(
        None, description="Updated organization name"
    )
    category: Optional[str] = Field(None, description="Updated source category")
    curated_tier: Optional[int] = Field(
        None,
        ge=1,
        le=3,
        description="Updated curated tier (1=highest, 2=mid, 3=baseline)",
    )
    texas_relevance_bonus: Optional[int] = Field(
        None, ge=0, le=20, description="Updated Texas relevance bonus (0-20)"
    )
    is_active: Optional[bool] = Field(
        None, description="Whether this domain should be actively tracked"
    )
    notes: Optional[str] = Field(None, description="Updated editorial notes")


# ============================================================================
# Domain Reputation Aggregation Models
# ============================================================================


class TopDomainsResponse(BaseModel):
    """
    Top domains leaderboard entry.

    Used to render the domain reputation leaderboard, showing
    the highest-scoring domains by composite reputation score.
    """

    id: str = Field(..., description="UUID of the domain reputation record")
    domain_pattern: str = Field(..., description="Domain pattern")
    organization_name: str = Field(..., description="Human-readable organization name")
    category: str = Field(..., description="Source category")
    curated_tier: Optional[int] = Field(None, description="Editorial curated tier")
    composite_score: float = Field(
        ..., description="Computed composite reputation score"
    )
    user_quality_avg: float = Field(..., description="Average user quality rating")
    user_rating_count: int = Field(..., description="Total number of user ratings")
    triage_pass_rate: float = Field(..., description="Rate of cards passing triage")


class DomainReputationList(BaseModel):
    """
    Paginated domain reputation list response.

    Used for admin views that list all tracked domains with
    pagination support.
    """

    items: List[DomainReputationResponse] = Field(
        default_factory=list, description="List of domain reputation records"
    )
    total: int = Field(default=0, description="Total number of matching records")
    page: int = Field(default=1, description="Current page number")
    page_size: int = Field(default=20, description="Number of items per page")
