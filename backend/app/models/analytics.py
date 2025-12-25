"""
Analytics Models for Strategic Intelligence Dashboard

This module provides Pydantic models for the analytics API endpoints,
enabling trend velocity tracking, pillar coverage analysis, and
AI-generated strategic insights.

Supports:
- VelocityDataPoint: Individual time-series data point for trend velocity
- VelocityResponse: Response for /api/v1/analytics/velocity endpoint
- PillarCoverageItem: Coverage data for a single pillar
- PillarCoverageResponse: Response for /api/v1/analytics/pillar-coverage endpoint
- InsightItem: Individual AI-generated insight
- InsightsResponse: Response for /api/v1/analytics/insights endpoint
"""

from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class VelocityDataPoint(BaseModel):
    """
    Individual data point for trend velocity time series.

    Represents aggregated velocity metrics for a specific date,
    used for charting trend momentum over time.
    """
    date: str = Field(
        ...,
        description="Date in ISO format (YYYY-MM-DD)"
    )
    velocity: float = Field(
        ...,
        ge=0,
        description="Aggregated velocity score for the date"
    )
    count: int = Field(
        0,
        ge=0,
        description="Number of cards contributing to this data point"
    )
    avg_velocity_score: Optional[float] = Field(
        None,
        ge=0,
        le=100,
        description="Average velocity score of cards on this date"
    )


class VelocityResponse(BaseModel):
    """
    Response model for the trend velocity analytics endpoint.

    Contains time-series data showing trend momentum over the
    selected time period, with optional week-over-week comparison.
    """
    data: List[VelocityDataPoint] = Field(
        default_factory=list,
        description="Time-series velocity data points"
    )
    count: int = Field(
        0,
        ge=0,
        description="Total number of data points returned"
    )
    period_start: Optional[str] = Field(
        None,
        description="Start date of the analysis period (ISO format)"
    )
    period_end: Optional[str] = Field(
        None,
        description="End date of the analysis period (ISO format)"
    )
    week_over_week_change: Optional[float] = Field(
        None,
        description="Percentage change compared to previous week"
    )
    total_cards_analyzed: int = Field(
        0,
        ge=0,
        description="Total number of cards included in the analysis"
    )


class PillarCoverageItem(BaseModel):
    """
    Coverage data for a single strategic pillar.

    Shows activity distribution and card counts for one of the
    6 strategic pillars (CH, EW, HG, HH, MC, PS).
    """
    pillar_code: str = Field(
        ...,
        pattern=r"^[A-Z]{2}$",
        description="Two-letter pillar code (CH, EW, HG, HH, MC, PS)"
    )
    pillar_name: str = Field(
        ...,
        description="Full pillar name"
    )
    count: int = Field(
        0,
        ge=0,
        description="Number of cards in this pillar"
    )
    percentage: float = Field(
        0.0,
        ge=0.0,
        le=100.0,
        description="Percentage of total cards in this pillar"
    )
    avg_velocity: Optional[float] = Field(
        None,
        ge=0,
        le=100,
        description="Average velocity score for cards in this pillar"
    )
    trend_direction: Optional[str] = Field(
        None,
        pattern=r"^(up|down|stable)$",
        description="Trend direction compared to previous period"
    )


class PillarCoverageResponse(BaseModel):
    """
    Response model for the pillar coverage analytics endpoint.

    Contains distribution data showing activity across all
    6 strategic pillars for heatmap visualization.
    """
    data: List[PillarCoverageItem] = Field(
        default_factory=list,
        description="Coverage data for each pillar"
    )
    total_cards: int = Field(
        0,
        ge=0,
        description="Total number of cards across all pillars"
    )
    period_start: Optional[str] = Field(
        None,
        description="Start date of the analysis period (ISO format)"
    )
    period_end: Optional[str] = Field(
        None,
        description="End date of the analysis period (ISO format)"
    )


class InsightItem(BaseModel):
    """
    Individual AI-generated strategic insight.

    Represents a single emerging trend with its velocity score
    and AI-generated insight text for strategic decision-making.
    """
    trend_name: str = Field(
        ...,
        description="Name of the emerging trend"
    )
    score: float = Field(
        ...,
        ge=0,
        le=100,
        description="Composite score indicating trend significance"
    )
    insight: str = Field(
        ...,
        description="AI-generated strategic insight text"
    )
    pillar_id: Optional[str] = Field(
        None,
        pattern=r"^[A-Z]{2}$",
        description="Associated pillar code"
    )
    card_id: Optional[str] = Field(
        None,
        description="UUID of the associated card"
    )
    velocity_score: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Velocity score of the trend"
    )


class InsightsResponse(BaseModel):
    """
    Response model for the AI insights analytics endpoint.

    Contains top emerging trends with AI-generated strategic
    insights for executive decision-making.
    """
    insights: List[InsightItem] = Field(
        default_factory=list,
        description="List of AI-generated insights for top trends"
    )
    generated_at: Optional[datetime] = Field(
        None,
        description="Timestamp when insights were generated"
    )
    period_analyzed: Optional[str] = Field(
        None,
        description="Time period covered by the analysis"
    )
    ai_available: bool = Field(
        True,
        description="Whether AI service was available for insight generation"
    )
    fallback_message: Optional[str] = Field(
        None,
        description="Message displayed if AI service is unavailable"
    )
