"""
Card Creation Models for User-Generated Intelligence Cards

This module provides Pydantic models for the card creation API endpoints,
enabling users to create intelligence cards from topic phrases or with
full manual detail. Supports both quick-create (AI-assisted) and
detailed manual workflows.

Endpoints:
- POST /api/v1/cards/from-topic - Quick card creation from topic phrase
- POST /api/v1/cards/manual - Full manual card creation
- POST /api/v1/cards/keyword-suggestions - AI keyword suggestions for topics
"""

from typing import Optional, List
from pydantic import BaseModel, Field, validator


# ============================================================================
# Quick Card Creation Models
# ============================================================================


class CreateCardFromTopicRequest(BaseModel):
    """
    Request body for quick card creation from a topic phrase.

    The system uses AI to expand the topic into a full card with
    name, description, pillar classification, and initial scoring.
    Optionally triggers a background source scan.
    """

    topic: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Topic phrase to create a card from",
    )
    workstream_id: Optional[str] = Field(
        None, description="Optional workstream to associate the card with"
    )
    pillar_hints: Optional[List[str]] = Field(
        None, description="Optional pillar code hints (e.g., ['CH', 'MC'])"
    )

    @validator("topic")
    def clean_topic(cls, v):
        """Clean and validate topic text."""
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Topic must be at least 3 characters after trimming")
        return v

    @validator("pillar_hints")
    def validate_pillar_hints(cls, v):
        """Validate pillar hint codes if provided."""
        if v is not None:
            valid_codes = {"CH", "EW", "HG", "HH", "MC", "PS"}
            for code in v:
                if code not in valid_codes:
                    raise ValueError(
                        f'Invalid pillar code "{code}". '
                        f'Must be one of: {", ".join(sorted(valid_codes))}'
                    )
        return v


class CreateCardFromTopicResponse(BaseModel):
    """
    Response for quick card creation.

    Returns the created card's ID and name, along with the status
    indicating whether a background scan was initiated.
    """

    card_id: str = Field(..., description="UUID of the created card")
    card_name: str = Field(..., description="AI-generated card name based on the topic")
    status: str = Field(
        ..., description="'created' or 'scanning' indicating card state"
    )
    scan_job_id: Optional[str] = Field(
        None, description="Background scan job ID if scanning was initiated"
    )
    message: str = Field(..., description="Human-readable status message")


# ============================================================================
# Manual Card Creation Models
# ============================================================================


class ManualCardCreateRequest(BaseModel):
    """
    Request body for full manual card creation.

    Allows users to specify all card fields directly, including
    optional seed URLs for initial source analysis.
    """

    name: str = Field(..., min_length=3, max_length=200, description="Card title")
    description: str = Field(
        ..., min_length=10, max_length=5000, description="Detailed card description"
    )
    pillar_ids: Optional[List[str]] = Field(
        None, description="Strategic pillar codes to assign (e.g., ['CH', 'MC'])"
    )
    horizon: Optional[str] = Field(
        None, description="Time horizon classification (H1, H2, H3)"
    )
    stage: Optional[str] = Field(None, description="Maturity stage ID")
    seed_urls: Optional[List[str]] = Field(
        None, max_length=10, description="Up to 10 URLs for initial source analysis"
    )
    is_exploratory: bool = Field(
        False, description="Whether this card is exploratory (less structured)"
    )

    @validator("name")
    def clean_name(cls, v):
        """Clean and validate card name."""
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Card name must be at least 3 characters after trimming")
        return v

    @validator("description")
    def clean_description(cls, v):
        """Clean and validate card description."""
        v = v.strip()
        if len(v) < 10:
            raise ValueError(
                "Description must be at least 10 characters after trimming"
            )
        return v

    @validator("horizon")
    def validate_horizon(cls, v):
        """Validate horizon value if provided."""
        if v is not None and v not in {"H1", "H2", "H3"}:
            raise ValueError("Horizon must be one of: H1, H2, H3")
        return v

    @validator("pillar_ids")
    def validate_pillar_ids(cls, v):
        """Validate pillar codes if provided."""
        if v is not None:
            valid_codes = {"CH", "EW", "HG", "HH", "MC", "PS"}
            for code in v:
                if code not in valid_codes:
                    raise ValueError(
                        f'Invalid pillar code "{code}". '
                        f'Must be one of: {", ".join(sorted(valid_codes))}'
                    )
        return v

    @validator("seed_urls")
    def validate_seed_urls(cls, v):
        """Validate seed URLs if provided."""
        if v is not None:
            if len(v) > 10:
                raise ValueError("Maximum 10 seed URLs allowed")
            for url in v:
                if not url.startswith(("http://", "https://")):
                    raise ValueError(
                        f"Invalid URL: {url}. Must start with http:// or https://"
                    )
        return v


# ============================================================================
# Keyword Suggestion Models
# ============================================================================


class KeywordSuggestionResponse(BaseModel):
    """
    Response for AI-powered keyword suggestions.

    Returns a list of municipal-relevant keyword suggestions
    based on the provided topic phrase.
    """

    topic: str = Field(..., description="The original topic phrase")
    suggestions: List[str] = Field(
        ..., description="5-10 municipal-relevant keyword suggestions"
    )
