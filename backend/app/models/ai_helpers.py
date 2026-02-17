"""
AI Helper Models

This module provides Pydantic models for AI-assisted helper endpoints,
such as generating workstream descriptions from names and context.

Supports:
- SuggestDescriptionRequest: Request body for AI-generated workstream description
- SuggestDescriptionResponse: Response for AI-generated workstream description
- ReadinessAssessmentRequest: Request body for grant readiness assessment
- ReadinessScoreBreakdown: Individual readiness factor score
- ReadinessAssessmentResponse: Response from readiness assessment
"""

from typing import Optional, List
from pydantic import BaseModel, Field


class SuggestDescriptionRequest(BaseModel):
    """Request body for AI-generated workstream description."""

    name: str = Field(..., min_length=2, max_length=200, description="Workstream name")
    pillar_ids: Optional[List[str]] = Field(
        default=[], description="Strategic pillar IDs for context"
    )
    keywords: Optional[List[str]] = Field(
        default=[], description="Keywords for context"
    )


class SuggestDescriptionResponse(BaseModel):
    """Response for AI-generated workstream description."""

    description: str = Field(..., description="AI-generated workstream description")


# ============================================================================
# Grant Readiness Assessment Models
# ============================================================================


class ReadinessAssessmentRequest(BaseModel):
    """Request for AI-powered grant readiness assessment."""

    department_id: Optional[str] = Field(None, description="Department abbreviation")
    program_description: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Description of the program seeking grants",
    )

    # Readiness questionnaire responses
    staff_capacity: Optional[str] = Field(
        None,
        description="Description of available staff for grant management",
    )
    past_grants: Optional[str] = Field(
        None,
        description="History of past grant applications and awards",
    )
    matching_funds: Optional[str] = Field(
        None,
        description="Availability of matching funds or in-kind contributions",
    )
    financial_systems: Optional[str] = Field(
        None,
        description="Financial tracking and reporting infrastructure",
    )
    reporting_capability: Optional[str] = Field(
        None,
        description="Ability to meet federal/state reporting requirements",
    )
    partnerships: Optional[str] = Field(
        None,
        description="Existing partnerships relevant to grant activities",
    )

    grant_categories: List[str] = Field(
        default=[], description="Grant categories of interest"
    )
    budget_range_min: Optional[float] = Field(
        None, ge=0, description="Minimum grant amount of interest"
    )
    budget_range_max: Optional[float] = Field(
        None, ge=0, description="Maximum grant amount of interest"
    )


class ReadinessScoreBreakdown(BaseModel):
    """Individual readiness factor score."""

    factor: str
    score: int = Field(..., ge=0, le=100)
    assessment: str
    recommendations: List[str] = []


class ReadinessAssessmentResponse(BaseModel):
    """Response from readiness assessment."""

    overall_score: int = Field(
        ..., ge=0, le=100, description="Overall readiness score 0-100"
    )
    readiness_level: str = Field(..., description="low|moderate|high|very_high")
    summary: str = Field(..., description="2-3 sentence summary of readiness")

    scores: List[ReadinessScoreBreakdown] = Field(
        default=[], description="Per-factor scores"
    )

    strengths: List[str] = Field(default=[], description="Key strengths identified")
    gaps: List[str] = Field(default=[], description="Key gaps to address")
    recommendations: List[str] = Field(
        default=[], description="Specific improvement actions"
    )

    suggested_grant_types: List[str] = Field(
        default=[],
        description="Recommended grant types based on readiness",
    )
    estimated_preparation_weeks: Optional[int] = Field(
        None, description="Estimated weeks to application-ready"
    )
