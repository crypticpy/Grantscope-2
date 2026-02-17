"""Review models for GrantScope API.

Models for card review workflows including individual review,
bulk review operations, and card dismissal.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CardReviewRequest(BaseModel):
    """Request model for reviewing a discovered card."""

    action: str = Field(
        ...,
        pattern=r"^(approve|reject|edit_approve)$",
        description="Review action: approve, reject, or edit_approve",
    )
    updates: Optional[Dict[str, Any]] = Field(
        None, description="Card field updates (for edit_approve action)"
    )
    reason: Optional[str] = Field(
        None, max_length=1000, description="Reason for rejection or edit notes"
    )


class BulkReviewRequest(BaseModel):
    """Request model for bulk card review operations."""

    card_ids: List[str] = Field(
        ..., min_items=1, max_items=100, description="List of card IDs to review"
    )
    action: str = Field(
        ..., pattern=r"^(approve|reject)$", description="Bulk action: approve or reject"
    )
    reason: Optional[str] = Field(
        None, max_length=500, description="Optional reason for bulk action"
    )


class CardDismissRequest(BaseModel):
    """Request model for user card dismissal."""

    reason: Optional[str] = Field(
        None, max_length=500, description="Optional reason for dismissal"
    )
