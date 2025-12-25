"""
Validation Models for Classification Accuracy Tracking

This module provides Pydantic models for the classification validation pipeline,
enabling manual review of AI-generated strategic pillar classifications to
achieve >85% accuracy target.

Database Table: classification_validations
Columns: id, card_id, predicted_pillar, ground_truth_pillar, reviewer_id, created_at, is_correct
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator
import re


# Valid strategic pillar codes (based on Austin strategic priorities)
# Must match PILLAR_DEFINITIONS in query_generator.py
VALID_PILLAR_CODES = {
    "CH",  # Community Health & Sustainability
    "EW",  # Economic & Workforce Development
    "HG",  # High-Performing Government
    "HH",  # Homelessness & Housing
    "MC",  # Mobility & Critical Infrastructure
    "PS",  # Public Safety
}


class ClassificationValidation(BaseModel):
    """
    Response model for classification validation records.

    Represents a ground truth label submitted by a human reviewer
    to validate AI classification accuracy.
    """
    id: str
    card_id: str
    predicted_pillar: str
    ground_truth_pillar: str
    reviewer_id: str
    is_correct: bool
    notes: Optional[str] = None
    confidence_at_prediction: Optional[float] = None
    created_at: datetime


class ClassificationValidationCreate(BaseModel):
    """
    Request model for submitting ground truth labels.

    Used by reviewers to provide correct pillar classifications
    for cards that have been AI-classified.
    """
    card_id: str = Field(
        ...,
        description="UUID of the card being validated"
    )
    ground_truth_pillar: str = Field(
        ...,
        pattern=r"^[A-Z]{2}$",
        description="Correct strategic pillar code (CH, EW, HG, HH, MC, PS)"
    )
    notes: Optional[str] = Field(
        None,
        max_length=1000,
        description="Optional notes explaining the classification decision"
    )

    @validator('card_id')
    def validate_uuid_format(cls, v):
        """Validate that card_id is a valid UUID format."""
        uuid_pattern = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            re.IGNORECASE
        )
        if not uuid_pattern.match(v):
            raise ValueError('Invalid UUID format for card_id')
        return v

    @validator('ground_truth_pillar')
    def validate_pillar_code(cls, v):
        """Validate that pillar code is a known strategic pillar."""
        if v not in VALID_PILLAR_CODES:
            raise ValueError(
                f'Invalid pillar code. Must be one of: {", ".join(sorted(VALID_PILLAR_CODES))}'
            )
        return v


class ClassificationAccuracyMetrics(BaseModel):
    """
    Response model for classification accuracy metrics.

    Provides aggregated accuracy statistics computed from
    the classification_validations table.
    """
    total_validations: int = Field(
        ...,
        description="Total number of validation records"
    )
    correct_classifications: int = Field(
        ...,
        description="Number of classifications that matched ground truth"
    )
    accuracy_percentage: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Overall accuracy as a percentage (0-100)"
    )
    accuracy_by_pillar: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Accuracy breakdown by strategic pillar"
    )
    meets_target: bool = Field(
        ...,
        description="Whether accuracy meets >85% target"
    )
    target_percentage: float = Field(
        default=85.0,
        description="Target accuracy percentage"
    )
    computed_at: datetime = Field(
        ...,
        description="Timestamp when metrics were computed"
    )


class ValidationSummary(BaseModel):
    """
    Summary of validation activity for monitoring and reporting.
    """
    validations_today: int = Field(
        default=0,
        description="Number of validations submitted today"
    )
    validations_this_week: int = Field(
        default=0,
        description="Number of validations submitted this week"
    )
    unique_reviewers: int = Field(
        default=0,
        description="Number of unique reviewers who have submitted validations"
    )
    cards_pending_validation: int = Field(
        default=0,
        description="Number of cards that need validation"
    )
    recent_validations: List[ClassificationValidation] = Field(
        default_factory=list,
        description="Most recent validation records"
    )


class ConfusionMatrixEntry(BaseModel):
    """
    Entry in a classification confusion matrix.

    Used for detailed accuracy analysis showing which pillars
    are commonly confused with each other.
    """
    predicted_pillar: str
    actual_pillar: str
    count: int
    percentage: float = Field(
        ge=0.0,
        le=100.0
    )


class ClassificationConfusionMatrix(BaseModel):
    """
    Confusion matrix for classification analysis.

    Helps identify systematic classification errors and
    pillars that are frequently confused.
    """
    matrix: List[ConfusionMatrixEntry] = Field(
        default_factory=list,
        description="List of confusion matrix entries"
    )
    total_predictions: int = Field(
        default=0,
        description="Total number of predictions in the matrix"
    )
    most_confused_pairs: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Top pairs of pillars that are most commonly confused"
    )
