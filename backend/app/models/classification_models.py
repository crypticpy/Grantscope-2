"""
Classification Validation Models

This module provides Pydantic models for the classification validation
API endpoints, enabling ground truth labeling and accuracy tracking
for AI-generated pillar classifications.

Supports:
- VALID_PILLAR_CODES: Set of allowed pillar classification codes
- ValidationSubmission: Request model for submitting ground truth labels
- ValidationSubmissionResponse: Response model for validation submission
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, validator


# Valid pillar codes for classification validation
# Must match PILLAR_DEFINITIONS in query_generator.py
VALID_PILLAR_CODES = {"CH", "EW", "HG", "HH", "MC", "PS"}


class ValidationSubmission(BaseModel):
    """Request model for submitting ground truth classification labels."""

    card_id: str = Field(..., description="UUID of the card being validated")
    ground_truth_pillar: str = Field(
        ...,
        pattern=r"^[A-Z]{2}$",
        description="Ground truth pillar code (CH, EW, HG, HH, MC, PS)",
    )
    reviewer_id: str = Field(
        ..., min_length=1, description="Identifier for the reviewer"
    )
    notes: Optional[str] = Field(
        None, max_length=1000, description="Optional reviewer notes"
    )

    @validator("card_id")
    def validate_card_id_format(cls, v):
        """Validate UUID format for card_id."""
        import re

        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            re.IGNORECASE,
        )
        if not uuid_pattern.match(v):
            raise ValueError("Invalid UUID format for card_id")
        return v

    @validator("ground_truth_pillar")
    def validate_pillar_code(cls, v):
        """Validate pillar code is in allowed list."""
        if v not in VALID_PILLAR_CODES:
            raise ValueError(
                f"Invalid pillar code. Must be one of: {', '.join(sorted(VALID_PILLAR_CODES))}"
            )
        return v


class ValidationSubmissionResponse(BaseModel):
    """Response model for validation submission."""

    id: str
    card_id: str
    ground_truth_pillar: str
    predicted_pillar: Optional[str] = None
    is_correct: Optional[bool] = None
    reviewer_id: str
    notes: Optional[str] = None
    created_at: datetime
