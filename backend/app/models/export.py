"""
Export Models for Intelligence Cards

This module provides Pydantic models for the export and reporting
functionality, enabling generation of PDF, PowerPoint, and CSV
exports for intelligence cards and workstream reports.

Supports:
- ExportFormat: Enum for supported export formats (PDF, PPTX, CSV)
- ExportRequest: Configuration options for export generation
- ExportResponse: Metadata about generated export files
- WorkstreamExportRequest: Options for workstream report generation
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, validator


class ExportFormat(str, Enum):
    """
    Supported export formats for intelligence cards.

    - PDF: Portable Document Format for printable reports
    - PPTX: PowerPoint format for presentation slides
    - CSV: Comma-Separated Values for data analysis in Excel
    """
    PDF = "pdf"
    PPTX = "pptx"
    CSV = "csv"


class ChartOptions(BaseModel):
    """
    Configuration options for chart generation in exports.

    Controls which visualizations to include in PDF and PowerPoint exports.
    """
    include_score_radar: bool = Field(
        True,
        description="Include radar chart showing all score dimensions"
    )
    include_score_bars: bool = Field(
        True,
        description="Include bar chart showing individual scores"
    )
    include_pillar_distribution: bool = Field(
        False,
        description="Include pillar distribution chart (workstream reports only)"
    )
    chart_dpi: int = Field(
        300,
        ge=72,
        le=600,
        description="DPI resolution for chart images (72-600)"
    )


class ExportRequest(BaseModel):
    """
    Request model for individual card export.

    Configures export format and optional features like
    chart inclusion and branding options.
    """
    format: ExportFormat = Field(
        ...,
        description="Export format: pdf, pptx, or csv"
    )
    include_charts: bool = Field(
        True,
        description="Include visualizations in PDF/PPTX exports"
    )
    include_description: bool = Field(
        True,
        description="Include full description text in export"
    )
    include_metadata: bool = Field(
        True,
        description="Include metadata like created_at, updated_at"
    )
    chart_options: Optional[ChartOptions] = Field(
        None,
        description="Advanced chart configuration options"
    )

    @validator('include_charts')
    def charts_only_for_visual_formats(cls, v, values):
        """Charts are only relevant for PDF and PPTX formats."""
        # Note: This is just a warning - we'll ignore charts for CSV
        return v


class ExportResponse(BaseModel):
    """
    Response model for export generation result.

    Contains metadata about the generated export file.
    Note: The actual file is returned via FileResponse/StreamingResponse,
    this model is used for async export status or export metadata endpoints.
    """
    success: bool = Field(
        ...,
        description="Whether the export was successfully generated"
    )
    format: ExportFormat = Field(
        ...,
        description="Format of the generated export"
    )
    filename: str = Field(
        ...,
        description="Suggested filename for the export"
    )
    content_type: str = Field(
        ...,
        description="MIME type of the export file"
    )
    file_size_bytes: Optional[int] = Field(
        None,
        ge=0,
        description="Size of the generated file in bytes"
    )
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the export was generated"
    )
    card_id: Optional[str] = Field(
        None,
        description="ID of the exported card (if single card export)"
    )
    card_name: Optional[str] = Field(
        None,
        description="Name of the exported card"
    )
    charts_included: bool = Field(
        False,
        description="Whether charts were included in the export"
    )
    error_message: Optional[str] = Field(
        None,
        description="Error message if export failed"
    )


class WorkstreamExportRequest(BaseModel):
    """
    Request model for workstream report export.

    Configures export options for aggregated workstream reports
    containing multiple intelligence cards.
    """
    format: ExportFormat = Field(
        ...,
        description="Export format: pdf or pptx (CSV not supported for workstreams)"
    )
    include_summary: bool = Field(
        True,
        description="Include summary page with aggregate statistics"
    )
    include_charts: bool = Field(
        True,
        description="Include visualizations (pillar distribution, score aggregates)"
    )
    include_card_details: bool = Field(
        True,
        description="Include detailed sections for each card"
    )
    max_cards: int = Field(
        50,
        ge=1,
        le=100,
        description="Maximum number of cards to include in report"
    )
    chart_options: Optional[ChartOptions] = Field(
        None,
        description="Advanced chart configuration options"
    )

    @validator('format')
    def validate_workstream_format(cls, v):
        """Workstream reports only support PDF and PPTX formats."""
        if v == ExportFormat.CSV:
            raise ValueError(
                'CSV format is not supported for workstream reports. '
                'Use PDF or PPTX for workstream exports.'
            )
        return v


class WorkstreamExportResponse(BaseModel):
    """
    Response model for workstream report generation result.

    Contains metadata about the generated workstream report.
    """
    success: bool = Field(
        ...,
        description="Whether the export was successfully generated"
    )
    format: ExportFormat = Field(
        ...,
        description="Format of the generated export"
    )
    filename: str = Field(
        ...,
        description="Suggested filename for the export"
    )
    content_type: str = Field(
        ...,
        description="MIME type of the export file"
    )
    file_size_bytes: Optional[int] = Field(
        None,
        ge=0,
        description="Size of the generated file in bytes"
    )
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the export was generated"
    )
    workstream_id: str = Field(
        ...,
        description="ID of the exported workstream"
    )
    workstream_name: Optional[str] = Field(
        None,
        description="Name of the exported workstream"
    )
    cards_included: int = Field(
        0,
        ge=0,
        description="Number of cards included in the report"
    )
    charts_included: bool = Field(
        False,
        description="Whether charts were included in the export"
    )
    error_message: Optional[str] = Field(
        None,
        description="Error message if export failed"
    )


class CardExportData(BaseModel):
    """
    Card data structure used for export generation.

    Contains all card fields needed for rendering exports,
    with null-safe handling for optional fields.
    """
    id: str = Field(..., description="Unique card identifier")
    name: str = Field(..., description="Card name/title")
    slug: str = Field(..., description="URL-friendly slug")
    summary: Optional[str] = Field(None, description="Brief card summary")
    description: Optional[str] = Field(None, description="Full card description")

    # Classification
    pillar_id: Optional[str] = Field(None, description="Strategic pillar code")
    pillar_name: Optional[str] = Field(None, description="Strategic pillar name")
    goal_id: Optional[str] = Field(None, description="Goal ID")
    goal_name: Optional[str] = Field(None, description="Goal name")
    anchor_id: Optional[str] = Field(None, description="Anchor ID")
    anchor_name: Optional[str] = Field(None, description="Anchor name")
    stage_id: Optional[str] = Field(None, description="Maturity stage ID")
    stage_name: Optional[str] = Field(None, description="Maturity stage name")
    horizon: Optional[str] = Field(None, description="Time horizon (H1, H2, H3)")

    # Scores (all optional, display as N/A if null)
    novelty_score: Optional[int] = Field(None, ge=0, le=100, description="Novelty score (0-100)")
    maturity_score: Optional[int] = Field(None, ge=0, le=100, description="Maturity score (0-100)")
    impact_score: Optional[int] = Field(None, ge=0, le=100, description="Impact score (0-100)")
    relevance_score: Optional[int] = Field(None, ge=0, le=100, description="Relevance score (0-100)")
    velocity_score: Optional[int] = Field(None, ge=0, le=100, description="Velocity score (0-100)")
    risk_score: Optional[int] = Field(None, ge=0, le=100, description="Risk score (0-100)")
    opportunity_score: Optional[int] = Field(None, ge=0, le=100, description="Opportunity score (0-100)")

    # Metadata
    status: Optional[str] = Field(None, description="Card status")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

    # Deep Research
    deep_research_report: Optional[str] = Field(None, description="Latest deep research report markdown")

    def get_score_display(self, score_name: str) -> str:
        """
        Get display value for a score field, returning 'N/A' if null.

        Args:
            score_name: Name of the score field (e.g., 'novelty_score')

        Returns:
            String representation of score or 'N/A'
        """
        value = getattr(self, score_name, None)
        return str(value) if value is not None else "N/A"

    def get_all_scores(self) -> dict:
        """
        Get all scores as a dictionary for chart generation.

        Returns:
            Dict mapping score names to values (None for missing scores)
        """
        return {
            "Novelty": self.novelty_score,
            "Maturity": self.maturity_score,
            "Impact": self.impact_score,
            "Relevance": self.relevance_score,
            "Velocity": self.velocity_score,
            "Risk": self.risk_score,
            "Opportunity": self.opportunity_score,
        }


# MIME type constants for exports
EXPORT_CONTENT_TYPES = {
    ExportFormat.PDF: "application/pdf",
    ExportFormat.PPTX: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ExportFormat.CSV: "text/csv",
}


def get_export_filename(name: str, format: ExportFormat) -> str:
    """
    Generate a filename for an export based on card/workstream name and format.

    Args:
        name: Card or workstream name
        format: Export format

    Returns:
        Sanitized filename with appropriate extension
    """
    # Sanitize name for filename use
    safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '' for c in name)
    safe_name = safe_name.strip().replace(' ', '_')[:50]  # Limit length

    if not safe_name:
        safe_name = "export"

    return f"{safe_name}.{format.value}"
