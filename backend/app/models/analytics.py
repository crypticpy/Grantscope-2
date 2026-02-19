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

    date: str = Field(..., description="Date in ISO format (YYYY-MM-DD)")
    velocity: float = Field(
        ..., ge=0, description="Aggregated velocity score for the date"
    )
    count: int = Field(
        0, ge=0, description="Number of cards contributing to this data point"
    )
    avg_velocity_score: Optional[float] = Field(
        None, ge=0, le=100, description="Average velocity score of cards on this date"
    )


class VelocityResponse(BaseModel):
    """
    Response model for the trend velocity analytics endpoint.

    Contains time-series data showing trend momentum over the
    selected time period, with optional week-over-week comparison.
    """

    data: List[VelocityDataPoint] = Field(
        default_factory=list, description="Time-series velocity data points"
    )
    count: int = Field(0, ge=0, description="Total number of data points returned")
    period_start: Optional[str] = Field(
        None, description="Start date of the analysis period (ISO format)"
    )
    period_end: Optional[str] = Field(
        None, description="End date of the analysis period (ISO format)"
    )
    week_over_week_change: Optional[float] = Field(
        None, description="Percentage change compared to previous week"
    )
    total_cards_analyzed: int = Field(
        0, ge=0, description="Total number of cards included in the analysis"
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
        description="Two-letter pillar code (CH, EW, HG, HH, MC, PS)",
    )
    pillar_name: str = Field(..., description="Full pillar name")
    count: int = Field(0, ge=0, description="Number of cards in this pillar")
    percentage: float = Field(
        0.0, ge=0.0, le=100.0, description="Percentage of total cards in this pillar"
    )
    avg_velocity: Optional[float] = Field(
        None,
        ge=0,
        le=100,
        description="Average velocity score for cards in this pillar",
    )
    trend_direction: Optional[str] = Field(
        None,
        pattern=r"^(up|down|stable)$",
        description="Trend direction compared to previous period",
    )


class PillarCoverageResponse(BaseModel):
    """
    Response model for the pillar coverage analytics endpoint.

    Contains distribution data showing activity across all
    6 strategic pillars for heatmap visualization.
    """

    data: List[PillarCoverageItem] = Field(
        default_factory=list, description="Coverage data for each pillar"
    )
    total_cards: int = Field(
        0, ge=0, description="Total number of cards across all pillars"
    )
    period_start: Optional[str] = Field(
        None, description="Start date of the analysis period (ISO format)"
    )
    period_end: Optional[str] = Field(
        None, description="End date of the analysis period (ISO format)"
    )


class InsightItem(BaseModel):
    """
    Individual AI-generated strategic insight.

    Represents a single emerging trend with its velocity score
    and AI-generated insight text for strategic decision-making.
    """

    trend_name: str = Field(..., description="Name of the emerging trend")
    score: float = Field(
        ..., ge=0, le=100, description="Composite score indicating trend significance"
    )
    insight: str = Field(..., description="AI-generated strategic insight text")
    pillar_id: Optional[str] = Field(
        None, pattern=r"^[A-Z]{2}$", description="Associated pillar code"
    )
    card_id: Optional[str] = Field(None, description="UUID of the associated card")
    card_slug: Optional[str] = Field(
        None, description="URL slug of the associated card for navigation"
    )
    velocity_score: Optional[int] = Field(
        None, ge=0, le=100, description="Velocity score of the trend"
    )


class InsightsResponse(BaseModel):
    """
    Response model for the AI insights analytics endpoint.

    Contains top emerging trends with AI-generated strategic
    insights for executive decision-making.
    """

    insights: List[InsightItem] = Field(
        default_factory=list, description="List of AI-generated insights for top trends"
    )
    generated_at: Optional[datetime] = Field(
        None, description="Timestamp when insights were generated"
    )
    period_analyzed: Optional[str] = Field(
        None, description="Time period covered by the analysis"
    )
    ai_available: bool = Field(
        True, description="Whether AI service was available for insight generation"
    )
    fallback_message: Optional[str] = Field(
        None, description="Message displayed if AI service is unavailable"
    )


# ============================================================================
# Comprehensive Analytics Models
# ============================================================================


class StageDistribution(BaseModel):
    """Distribution of cards across maturity stages."""

    stage_id: str = Field(..., description="Stage identifier (1-8)")
    stage_name: str = Field(..., description="Stage display name")
    count: int = Field(0, ge=0, description="Number of cards in this stage")
    percentage: float = Field(0.0, ge=0.0, le=100.0, description="Percentage of total")


class HorizonDistribution(BaseModel):
    """Distribution of cards across time horizons."""

    horizon: str = Field(..., description="Horizon code (H1, H2, H3)")
    label: str = Field(..., description="Human-readable horizon label")
    count: int = Field(0, ge=0, description="Number of cards in this horizon")
    percentage: float = Field(0.0, ge=0.0, le=100.0, description="Percentage of total")


class TrendingTopic(BaseModel):
    """A trending topic/category based on card activity."""

    name: str = Field(..., description="Topic or category name")
    count: int = Field(..., ge=0, description="Number of related items")
    trend: str = Field("stable", description="Trend direction: up, down, stable")
    velocity_avg: Optional[float] = Field(None, description="Average velocity score")


class SourceStats(BaseModel):
    """Statistics about discovery sources."""

    total_sources: int = Field(0, ge=0, description="Total unique sources in system")
    sources_this_week: int = Field(0, ge=0, description="Sources added this week")
    sources_by_type: dict = Field(
        default_factory=dict, description="Count by source type"
    )


class DiscoveryStats(BaseModel):
    """Statistics about the discovery process."""

    total_discovery_runs: int = Field(
        0, ge=0, description="Total discovery runs executed"
    )
    runs_this_week: int = Field(0, ge=0, description="Discovery runs this week")
    total_searches: int = Field(0, ge=0, description="Total search queries performed")
    searches_this_week: int = Field(0, ge=0, description="Searches this week")
    cards_discovered: int = Field(
        0, ge=0, description="Total cards created via discovery"
    )
    avg_cards_per_run: float = Field(
        0.0, ge=0, description="Average cards created per run"
    )


class WorkstreamEngagement(BaseModel):
    """Statistics about workstream usage."""

    total_workstreams: int = Field(0, ge=0, description="Total workstreams in system")
    active_workstreams: int = Field(
        0, ge=0, description="Workstreams with recent activity"
    )
    unique_cards_in_workstreams: int = Field(
        0, ge=0, description="Unique cards saved to workstreams"
    )
    avg_cards_per_workstream: float = Field(
        0.0, ge=0, description="Average cards per workstream"
    )


class FollowStats(BaseModel):
    """Statistics about card following."""

    total_follows: int = Field(0, ge=0, description="Total follow relationships")
    unique_cards_followed: int = Field(
        0, ge=0, description="Unique cards being followed"
    )
    unique_users_following: int = Field(
        0, ge=0, description="Users actively following cards"
    )
    most_followed_cards: List[dict] = Field(
        default_factory=list, description="Top followed cards"
    )


class SystemWideStats(BaseModel):
    """
    Comprehensive system-wide analytics response.

    Contains all system-level statistics for the analytics dashboard.
    """

    # Core card stats
    total_cards: int = Field(0, ge=0, description="Total cards in system")
    active_cards: int = Field(0, ge=0, description="Active cards")
    cards_this_week: int = Field(0, ge=0, description="Cards created this week")
    cards_this_month: int = Field(0, ge=0, description="Cards created this month")

    # Distribution stats
    cards_by_pillar: List[PillarCoverageItem] = Field(default_factory=list)
    cards_by_stage: List[StageDistribution] = Field(default_factory=list)
    cards_by_horizon: List[HorizonDistribution] = Field(default_factory=list)
    cards_by_pipeline_status: List[dict] = Field(
        default_factory=list, description="Pipeline status distribution"
    )

    # Trending
    trending_pillars: List[TrendingTopic] = Field(default_factory=list)
    hot_topics: List[TrendingTopic] = Field(default_factory=list)

    # Source & discovery
    source_stats: SourceStats = Field(default_factory=SourceStats)
    discovery_stats: DiscoveryStats = Field(default_factory=DiscoveryStats)

    # Engagement
    workstream_engagement: WorkstreamEngagement = Field(
        default_factory=WorkstreamEngagement
    )
    follow_stats: FollowStats = Field(default_factory=FollowStats)

    # Metadata
    generated_at: datetime = Field(default_factory=datetime.now)


class UserFollowItem(BaseModel):
    """A card that the user is following."""

    card_id: str = Field(..., description="Card UUID")
    card_slug: Optional[str] = Field(None, description="URL slug for navigation")
    card_name: str = Field(..., description="Card name")
    pillar_id: Optional[str] = Field(None, description="Pillar code")
    horizon: Optional[str] = Field(None, description="Time horizon")
    velocity_score: Optional[int] = Field(None, description="Card velocity score")
    followed_at: datetime = Field(..., description="When the user followed this card")
    priority: str = Field("medium", description="User's priority for this card")
    follower_count: int = Field(1, ge=1, description="Total followers for this card")


class PopularCard(BaseModel):
    """A popular card that others are following."""

    card_id: str = Field(..., description="Card UUID")
    card_slug: Optional[str] = Field(None, description="URL slug for navigation")
    card_name: str = Field(..., description="Card name")
    summary: str = Field(..., description="Card summary")
    pillar_id: Optional[str] = Field(None, description="Pillar code")
    horizon: Optional[str] = Field(None, description="Time horizon")
    velocity_score: Optional[int] = Field(None, description="Card velocity score")
    follower_count: int = Field(0, ge=0, description="Number of followers")
    is_followed_by_user: bool = Field(
        False, description="Whether current user follows this"
    )


class UserEngagementComparison(BaseModel):
    """Comparison of user engagement vs community average."""

    user_follow_count: int = Field(0, ge=0, description="Cards user is following")
    avg_community_follows: float = Field(
        0.0, ge=0, description="Average follows per user"
    )
    user_workstream_count: int = Field(0, ge=0, description="User's workstream count")
    avg_community_workstreams: float = Field(
        0.0, ge=0, description="Average workstreams per user"
    )
    user_percentile_follows: float = Field(
        0.0, description="User's percentile for follows"
    )
    user_percentile_workstreams: float = Field(
        0.0, description="User's percentile for workstreams"
    )


class PillarAffinity(BaseModel):
    """User's affinity for a pillar based on their follows."""

    pillar_code: str = Field(..., description="Pillar code")
    pillar_name: str = Field(..., description="Pillar name")
    user_count: int = Field(0, ge=0, description="User's follows in this pillar")
    user_percentage: float = Field(0.0, description="Percentage of user's follows")
    community_percentage: float = Field(0.0, description="Community average percentage")
    affinity_score: float = Field(0.0, description="How much more/less than avg")


class PersonalStats(BaseModel):
    """
    Personal analytics for the current user.

    Contains user-specific statistics and comparisons to community.
    """

    # User's follows
    following: List[UserFollowItem] = Field(default_factory=list)
    total_following: int = Field(0, ge=0)

    # Engagement comparison
    engagement: UserEngagementComparison = Field(
        default_factory=UserEngagementComparison
    )

    # Pillar preferences
    pillar_affinity: List[PillarAffinity] = Field(default_factory=list)

    # Social discovery - what others are following that user isn't
    popular_not_followed: List[PopularCard] = Field(default_factory=list)
    recently_popular: List[PopularCard] = Field(default_factory=list)

    # User activity
    workstream_count: int = Field(0, ge=0)
    cards_in_workstreams: int = Field(0, ge=0)

    # Metadata
    generated_at: datetime = Field(default_factory=datetime.now)
