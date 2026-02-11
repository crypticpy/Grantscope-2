"""
Source Rating Models for User-Generated Source Quality Assessment

This module provides Pydantic models for the source rating API endpoints,
enabling users to rate information sources on quality and municipal relevance.
Ratings feed into the Source Quality Index (SQI) and domain reputation system.

Database Table: source_ratings
Columns: id, source_id, user_id, quality_rating, relevance_rating, comment, created_at, updated_at
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum


class RelevanceRating(str, Enum):
    """Municipal relevance assessment levels for source rating."""

    high = "high"
    medium = "medium"
    low = "low"
    not_relevant = "not_relevant"


# ============================================================================
# Source Rating Request Models
# ============================================================================


class SourceRatingCreate(BaseModel):
    """
    Request body for creating or updating a source rating.

    Users submit a quality star rating (1-5), a municipal relevance
    assessment, and an optional brief comment.
    """

    quality_rating: int = Field(..., ge=1, le=5, description="Quality star rating 1-5")
    relevance_rating: RelevanceRating = Field(
        ..., description="Municipal relevance assessment"
    )
    comment: Optional[str] = Field(
        None, max_length=280, description="Optional brief note about the source"
    )


# ============================================================================
# Source Rating Response Models
# ============================================================================


class SourceRatingResponse(BaseModel):
    """
    Response model for a single source rating.

    Represents an individual user's rating of a source, including
    quality score, relevance assessment, and optional comment.
    """

    id: str = Field(..., description="UUID of the source rating")
    source_id: str = Field(..., description="UUID of the rated source")
    user_id: str = Field(..., description="UUID of the user who submitted the rating")
    quality_rating: int = Field(..., ge=1, le=5, description="Quality star rating 1-5")
    relevance_rating: str = Field(
        ..., description="Municipal relevance assessment level"
    )
    comment: Optional[str] = Field(
        None, description="Optional brief note about the source"
    )
    created_at: datetime = Field(..., description="When the rating was created")
    updated_at: datetime = Field(..., description="When the rating was last updated")


class SourceRatingAggregate(BaseModel):
    """
    Aggregated rating statistics for a source.

    Provides computed averages, total counts, and relevance distribution
    across all user ratings for a given source. Optionally includes
    the current user's rating if authenticated.
    """

    source_id: str = Field(..., description="UUID of the source")
    avg_quality: float = Field(..., description="Average quality rating (1.0-5.0)")
    total_ratings: int = Field(
        ..., description="Total number of ratings for this source"
    )
    relevance_distribution: dict = Field(
        ...,
        description="Count per relevance level: {high: N, medium: N, low: N, not_relevant: N}",
    )
    current_user_rating: Optional[SourceRatingResponse] = Field(
        None, description="Current authenticated user's rating, if one exists"
    )
