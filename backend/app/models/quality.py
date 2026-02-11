"""
Source Quality Index (SQI) Models for Card Quality Assessment

This module provides Pydantic models for the SQI and quality tier API
endpoints, enabling quality-based filtering and detailed quality breakdown
display for intelligence cards.

Quality Tiers:
- high: SQI 75-100
- moderate: SQI 50-74
- needs_verification: SQI 0-49

SQI Components:
- source_authority: Domain reputation score
- source_diversity: Source type variety
- corroboration: Independent story cluster count
- recency: Source freshness
- municipal_specificity: Municipal relevance
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum


class QualityTier(str, Enum):
    """Quality tier classification based on SQI score ranges."""

    high = "high"  # 75-100
    moderate = "moderate"  # 50-74
    needs_verification = "needs_verification"  # 0-49


# ============================================================================
# Quality Breakdown Response Models
# ============================================================================


class QualityBreakdown(BaseModel):
    """
    Full SQI breakdown response for an intelligence card.

    Provides the composite quality score along with individual component
    scores that contribute to the overall SQI. Used to render the quality
    breakdown panel in the card detail view.
    """

    quality_score: int = Field(
        ..., ge=0, le=100, description="Composite SQI score 0-100"
    )
    quality_tier: QualityTier = Field(
        ...,
        description="Quality tier classification (high, moderate, needs_verification)",
    )
    source_authority: int = Field(
        ..., ge=0, le=100, description="Domain reputation score 0-100"
    )
    source_diversity: int = Field(
        ..., ge=0, le=100, description="Source type variety score 0-100"
    )
    corroboration: int = Field(
        ..., ge=0, le=100, description="Independent story cluster count score 0-100"
    )
    recency: int = Field(..., ge=0, le=100, description="Source freshness score 0-100")
    municipal_specificity: int = Field(
        ..., ge=0, le=100, description="Municipal relevance score 0-100"
    )
    source_count: int = Field(
        ..., ge=0, description="Total number of sources contributing to this card"
    )
    cluster_count: int = Field(
        ..., ge=0, description="Number of independent source clusters"
    )
    calculated_at: Optional[datetime] = Field(
        None, description="When the SQI was last calculated"
    )


# ============================================================================
# Quality Filter Models
# ============================================================================


class QualityTierFilter(BaseModel):
    """
    Filter parameters for quality tier-based card filtering.

    Used as query parameters on card listing endpoints to filter
    by quality tier or score range.
    """

    tier: Optional[QualityTier] = Field(
        None, description="Filter by quality tier classification"
    )
    min_score: Optional[int] = Field(
        None, ge=0, le=100, description="Minimum SQI score (0-100)"
    )
    max_score: Optional[int] = Field(
        None, ge=0, le=100, description="Maximum SQI score (0-100)"
    )
