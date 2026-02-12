"""
Briefs Extra Models for Bulk Export Operations

This module provides Pydantic models for the bulk brief export API endpoints,
supporting bulk export requests, per-card brief status tracking, and
aggregated bulk brief status responses.

Supports:
- BulkExportRequest: Request body for bulk brief export
- BulkBriefCardStatus: Status of a single card for bulk export
- BulkBriefStatusResponse: Response for bulk brief status check
"""

from typing import Optional, List
from pydantic import BaseModel


class BulkExportRequest(BaseModel):
    """Request body for bulk brief export."""

    format: str = "pptx"  # "pptx" or "pdf"
    card_order: List[str]  # Ordered list of card IDs (from Kanban position)

    class Config:
        json_schema_extra = {
            "example": {"format": "pptx", "card_order": ["uuid-1", "uuid-2", "uuid-3"]}
        }


class BulkBriefCardStatus(BaseModel):
    """Status of a single card for bulk export."""

    card_id: str
    card_name: str
    has_brief: bool
    brief_status: Optional[str] = None
    position: int = 0


class BulkBriefStatusResponse(BaseModel):
    """Response for bulk brief status check."""

    total_cards: int
    cards_with_briefs: int
    cards_ready: int
    card_statuses: List[BulkBriefCardStatus]
