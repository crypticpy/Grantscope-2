"""
Score and Stage History Models for Trend Visualization

This module provides Pydantic models for temporal tracking of card metrics,
enabling trend visualization and comparison features.

Supports:
- ScoreHistory: Historical score snapshots for timeline charts
- ScoreHistoryResponse: API response with score history data
- StageHistory: Maturity stage transition tracking with horizon changes
- CardRelationship: Concept network edges between related cards

Database Tables:
- card_score_history: Temporal score tracking (all 7 score types)
- card_timeline (enhanced): Stage transition tracking with old/new values
- card_relationships: Concept network edges between cards
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, validator
import re


# Valid horizon values for maturity stage horizons
VALID_HORIZONS = {"H1", "H2", "H3"}

# Valid relationship types for card relationships
VALID_RELATIONSHIP_TYPES = {"related", "similar", "derived", "dependent", "parent", "child"}


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


# ============================================================================
# Stage History Models
# ============================================================================

class StageHistory(BaseModel):
    """
    Response model for a stage transition record.

    Represents a single stage change event for a card, tracking
    the transition from one maturity stage to another with
    associated horizon changes.
    """
    id: str = Field(
        ...,
        description="UUID of the stage history record"
    )
    card_id: str = Field(
        ...,
        description="UUID of the card this history belongs to"
    )
    changed_at: datetime = Field(
        ...,
        description="Timestamp when the stage transition occurred"
    )
    old_stage_id: Optional[int] = Field(
        None,
        ge=1,
        le=8,
        description="Previous maturity stage ID (1-8), null for first record"
    )
    new_stage_id: int = Field(
        ...,
        ge=1,
        le=8,
        description="New maturity stage ID (1-8)"
    )
    old_horizon: Optional[str] = Field(
        None,
        pattern=r"^H[123]$",
        description="Previous horizon (H1, H2, or H3), null for first record"
    )
    new_horizon: str = Field(
        ...,
        pattern=r"^H[123]$",
        description="New horizon (H1, H2, or H3)"
    )
    trigger: Optional[str] = Field(
        None,
        max_length=100,
        description="What triggered the stage change (e.g., 'manual', 'auto-calculated', 'score_update')"
    )
    reason: Optional[str] = Field(
        None,
        max_length=1000,
        description="Optional explanation for the stage change"
    )

    @validator('card_id')
    def validate_card_uuid(cls, v):
        """Validate that card_id is a valid UUID format."""
        uuid_pattern = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            re.IGNORECASE
        )
        if not uuid_pattern.match(v):
            raise ValueError('Invalid UUID format for card_id')
        return v

    @validator('new_horizon')
    def validate_new_horizon(cls, v):
        """Validate that new_horizon is a known horizon value."""
        if v not in VALID_HORIZONS:
            raise ValueError(f'Invalid horizon. Must be one of: {", ".join(sorted(VALID_HORIZONS))}')
        return v

    @validator('old_horizon')
    def validate_old_horizon(cls, v):
        """Validate that old_horizon is a known horizon value if provided."""
        if v is not None and v not in VALID_HORIZONS:
            raise ValueError(f'Invalid horizon. Must be one of: {", ".join(sorted(VALID_HORIZONS))}')
        return v


class StageHistoryCreate(BaseModel):
    """
    Request model for creating a stage history record.

    Used internally when recording stage transitions during card updates.
    """
    card_id: str = Field(
        ...,
        description="UUID of the card"
    )
    old_stage_id: Optional[int] = Field(
        None,
        ge=1,
        le=8,
        description="Previous maturity stage ID (1-8)"
    )
    new_stage_id: int = Field(
        ...,
        ge=1,
        le=8,
        description="New maturity stage ID (1-8)"
    )
    old_horizon: Optional[str] = Field(
        None,
        pattern=r"^H[123]$",
        description="Previous horizon (H1, H2, or H3)"
    )
    new_horizon: str = Field(
        ...,
        pattern=r"^H[123]$",
        description="New horizon (H1, H2, or H3)"
    )
    trigger: Optional[str] = Field(
        "manual",
        max_length=100,
        description="What triggered the stage change"
    )
    reason: Optional[str] = Field(
        None,
        max_length=1000,
        description="Optional explanation for the stage change"
    )

    @validator('card_id')
    def validate_card_uuid(cls, v):
        """Validate that card_id is a valid UUID format."""
        uuid_pattern = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            re.IGNORECASE
        )
        if not uuid_pattern.match(v):
            raise ValueError('Invalid UUID format for card_id')
        return v


class StageHistoryList(BaseModel):
    """
    Response model for listing stage history records.

    Returns chronologically ordered stage transitions for a card.
    """
    history: List[StageHistory] = Field(
        default_factory=list,
        description="List of stage transition records, ordered by changed_at DESC"
    )
    total_count: int = Field(
        default=0,
        description="Total number of stage transitions for this card"
    )
    card_id: str = Field(
        ...,
        description="UUID of the card these records belong to"
    )


# ============================================================================
# Card Relationship Models
# ============================================================================

class CardRelationship(BaseModel):
    """
    Response model for a card relationship record.

    Represents a directed edge in the concept network graph,
    connecting a source card to a target card with relationship
    metadata for visualization.
    """
    id: str = Field(
        ...,
        description="UUID of the relationship record"
    )
    source_card_id: str = Field(
        ...,
        description="UUID of the source card (edge origin)"
    )
    target_card_id: str = Field(
        ...,
        description="UUID of the target card (edge destination)"
    )
    relationship_type: str = Field(
        ...,
        description="Type of relationship (related, similar, derived, dependent, parent, child)"
    )
    strength: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Relationship strength weight (0-1) for edge visualization"
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when the relationship was created"
    )

    @validator('source_card_id', 'target_card_id')
    def validate_uuid(cls, v):
        """Validate that card IDs are valid UUID format."""
        uuid_pattern = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            re.IGNORECASE
        )
        if not uuid_pattern.match(v):
            raise ValueError('Invalid UUID format for card_id')
        return v

    @validator('relationship_type')
    def validate_relationship_type(cls, v):
        """Validate that relationship_type is a known type."""
        if v not in VALID_RELATIONSHIP_TYPES:
            raise ValueError(
                f'Invalid relationship type. Must be one of: {", ".join(sorted(VALID_RELATIONSHIP_TYPES))}'
            )
        return v


class CardRelationshipCreate(BaseModel):
    """
    Request model for creating a card relationship.

    Used when establishing a new relationship between two cards
    in the concept network.
    """
    source_card_id: str = Field(
        ...,
        description="UUID of the source card"
    )
    target_card_id: str = Field(
        ...,
        description="UUID of the target card"
    )
    relationship_type: str = Field(
        ...,
        description="Type of relationship"
    )
    strength: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Relationship strength (0-1)"
    )

    @validator('source_card_id', 'target_card_id')
    def validate_uuid(cls, v):
        """Validate that card IDs are valid UUID format."""
        uuid_pattern = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            re.IGNORECASE
        )
        if not uuid_pattern.match(v):
            raise ValueError('Invalid UUID format for card_id')
        return v

    @validator('target_card_id')
    def validate_not_self_reference(cls, v, values):
        """Validate that source and target are different cards."""
        if 'source_card_id' in values and v == values['source_card_id']:
            raise ValueError('Cannot create self-referential relationship')
        return v

    @validator('relationship_type')
    def validate_relationship_type(cls, v):
        """Validate that relationship_type is a known type."""
        if v not in VALID_RELATIONSHIP_TYPES:
            raise ValueError(
                f'Invalid relationship type. Must be one of: {", ".join(sorted(VALID_RELATIONSHIP_TYPES))}'
            )
        return v


class RelatedCard(BaseModel):
    """
    Extended card model with relationship metadata.

    Used in concept network visualization to display related cards
    with their relationship context.
    """
    id: str = Field(
        ...,
        description="UUID of the related card"
    )
    name: str = Field(
        ...,
        description="Card display name"
    )
    slug: str = Field(
        ...,
        description="URL-friendly card identifier"
    )
    summary: Optional[str] = Field(
        None,
        description="Brief card summary"
    )
    pillar_id: Optional[str] = Field(
        None,
        description="Strategic pillar code"
    )
    stage_id: Optional[str] = Field(
        None,
        description="Maturity stage ID"
    )
    horizon: Optional[str] = Field(
        None,
        description="Planning horizon (H1, H2, H3)"
    )
    # Relationship context
    relationship_type: str = Field(
        ...,
        description="Type of relationship to the source card"
    )
    relationship_strength: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Strength of the relationship (0-1)"
    )
    relationship_id: str = Field(
        ...,
        description="UUID of the relationship record"
    )


class RelatedCardsList(BaseModel):
    """
    Response model for listing related cards.

    Returns cards connected to a source card in the concept network.
    """
    related_cards: List[RelatedCard] = Field(
        default_factory=list,
        description="List of cards related to the source card"
    )
    total_count: int = Field(
        default=0,
        description="Total number of related cards"
    )
    source_card_id: str = Field(
        ...,
        description="UUID of the card these relationships are for"
    )
