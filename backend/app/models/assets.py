"""
Card Asset Models

This module provides Pydantic models for the card assets API endpoints,
representing generated assets such as briefs, research reports, and exports
associated with cards.

Supports:
- CardAsset: Represents a generated asset for a card
- CardAssetsResponse: Response containing all assets for a card
"""

from typing import Optional, List
from pydantic import BaseModel


class CardAsset(BaseModel):
    """Represents a generated asset (brief, research report, export) for a card."""

    id: str
    type: str  # 'brief', 'research', 'pdf_export', 'pptx_export'
    title: str
    created_at: str
    version: Optional[int] = None
    file_size: Optional[int] = None
    download_count: Optional[int] = None
    ai_generated: bool = True
    ai_model: Optional[str] = None
    status: str = "ready"  # 'ready', 'generating', 'failed'
    metadata: Optional[dict] = None


class CardAssetsResponse(BaseModel):
    """Response containing all assets for a card."""

    card_id: str
    assets: List[CardAsset]
    total_count: int
