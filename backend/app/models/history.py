"""
Score and Stage History Models for Trend Visualization

This module provides Pydantic models for temporal tracking of card metrics,
enabling trend visualization and comparison features.

Supports:
- ScoreHistory: Historical score snapshots for timeline charts
- ScoreHistoryResponse: API response with score history data
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, validator


class ScoreHistory(BaseModel):
    """
    Historical score snapshot for a card at a specific point in time.

    Used for trend visualization showing how card scores have changed
    over time. Each record captures all 7 score dimensions.
    """
    id: str = Field(
        ...,
        description="UUID of the score history record"
    )
    card_id: str = Field(
        ...,
        description="UUID of the card this history belongs to"
    )
    recorded_at: datetime = Field(
        ...,
        description="Timestamp when this score snapshot was recorded"
    )
    # All 7 score dimensions (0-100 range)
    maturity_score: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Maturity score at this point in time (0-100)"
    )
    velocity_score: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Velocity score at this point in time (0-100)"
    )
    novelty_score: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Novelty score at this point in time (0-100)"
    )
    impact_score: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Impact score at this point in time (0-100)"
    )
    relevance_score: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Relevance score at this point in time (0-100)"
    )
    risk_score: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Risk score at this point in time (0-100)"
    )
    opportunity_score: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Opportunity score at this point in time (0-100)"
    )


class ScoreHistoryCreate(BaseModel):
    """
    Request model for creating a new score history record.

    Internal use - typically called when card scores are updated
    to track changes over time.
    """
    card_id: str = Field(
        ...,
        description="UUID of the card to record history for"
    )
    maturity_score: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Maturity score (0-100)"
    )
    velocity_score: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Velocity score (0-100)"
    )
    novelty_score: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Novelty score (0-100)"
    )
    impact_score: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Impact score (0-100)"
    )
    relevance_score: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Relevance score (0-100)"
    )
    risk_score: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Risk score (0-100)"
    )
    opportunity_score: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Opportunity score (0-100)"
    )


class ScoreHistoryResponse(BaseModel):
    """
    Response model for score history API endpoint.

    Returns a list of score snapshots for trend visualization.
    """
    history: List[ScoreHistory] = Field(
        default_factory=list,
        description="List of score history records ordered by recorded_at"
    )
    card_id: str = Field(
        ...,
        description="UUID of the card this history belongs to"
    )
    total_count: int = Field(
        default=0,
        ge=0,
        description="Total number of history records for this card"
    )
    start_date: Optional[datetime] = Field(
        None,
        description="Start date filter applied to the query"
    )
    end_date: Optional[datetime] = Field(
        None,
        description="End date filter applied to the query"
    )
