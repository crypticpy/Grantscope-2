"""Card and workstream export router -- PDF, PPTX, CSV exports."""

import io
import logging
import uuid
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, get_current_user_hardcoded, _safe_error
from app.export_service import ExportService
from app.models.export import (
    ExportFormat,
    CardExportData,
    EXPORT_CONTENT_TYPES,
    get_export_filename,
)
from app.models.db.card import Card
from app.models.db.research import ResearchTask
from app.models.db.workstream import Workstream

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["card-export"])


# ============================================================================
# Single card export
# ============================================================================


@router.get("/cards/{card_id}/export/{format}")
async def export_card(
    card_id: str,
    format: str,
    include_charts: bool = True,
    current_user: dict = Depends(get_current_user_hardcoded),
    db: AsyncSession = Depends(get_db),
):
    """
    Export a single card in the specified format.

    Supported formats:
    - pdf: Portable Document Format with charts and full details
    - pptx: PowerPoint presentation with formatted slides
    - csv: Comma-Separated Values for data analysis

    Args:
        card_id: UUID of the card to export
        format: Export format (pdf, pptx, csv)
        include_charts: Whether to include visualizations (PDF/PPTX only)

    Returns:
        FileResponse for PDF/PPTX, StreamingResponse for CSV
    """
    # Validate format
    format_lower = format.lower()
    try:
        export_format = ExportFormat(format_lower)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid export format: {format}. Supported formats: pdf, pptx, csv",
        ) from e

    # Fetch card from database
    try:
        result = await db.execute(select(Card).where(Card.id == card_id))
        card_obj = result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Failed to fetch card {card_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("card retrieval for export", e),
        ) from e

    if not card_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Card not found: {card_id}"
        )

    # Note: pillar_name, goal_name, stage_name were previously fetched via
    # PostgREST joins on reference tables (pillars, goals, stages). These
    # reference tables may not have ORM models, so we pass None and let the
    # export service handle display.
    pillar_name = None
    goal_name = None
    stage_name = None

    # Fetch latest completed deep research report for this card
    research_report = None
    research_reports = []
    try:
        research_result = await db.execute(
            select(ResearchTask)
            .where(
                ResearchTask.card_id == card_id,
                ResearchTask.status == "completed",
                ResearchTask.task_type == "deep_research",
            )
            .order_by(ResearchTask.completed_at.desc())
            .limit(3)
        )
        research_tasks = research_result.scalars().all()

        for task in research_tasks:
            result_summary = task.result_summary or {}
            if result_summary.get("report_preview"):
                research_reports.append(
                    {
                        "completed_at": (
                            task.completed_at.isoformat() if task.completed_at else None
                        ),
                        "report": result_summary["report_preview"],
                    }
                )
        # Use the most recent report as the main one
        if research_reports:
            research_report = research_reports[0]["report"]
    except Exception as e:
        logger.warning(f"Failed to fetch research reports for export: {e}")

    # Create CardExportData from raw data with enriched names and research
    try:
        export_data = CardExportData(
            id=str(card_obj.id),
            name=card_obj.name,
            slug=card_obj.slug or "",
            summary=card_obj.summary,
            description=card_obj.description,
            pillar_id=card_obj.pillar_id,
            pillar_name=pillar_name,
            goal_id=card_obj.goal_id,
            goal_name=goal_name,
            anchor_id=card_obj.anchor_id,
            stage_id=card_obj.stage_id,
            stage_name=stage_name,
            horizon=card_obj.horizon,
            novelty_score=card_obj.novelty_score,
            maturity_score=card_obj.maturity_score,
            impact_score=card_obj.impact_score,
            relevance_score=card_obj.relevance_score,
            velocity_score=(
                float(card_obj.velocity_score)
                if card_obj.velocity_score is not None
                else None
            ),
            risk_score=card_obj.risk_score,
            opportunity_score=card_obj.opportunity_score,
            status=card_obj.status,
            created_at=(
                card_obj.created_at.isoformat() if card_obj.created_at else None
            ),
            updated_at=(
                card_obj.updated_at.isoformat() if card_obj.updated_at else None
            ),
            deep_research_report=research_report,
        )
    except Exception as e:
        logger.error(f"Failed to create CardExportData: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to prepare card data for export",
        ) from e

    # Initialize export service
    export_service = ExportService(db)

    # Generate export based on format
    try:
        if export_format == ExportFormat.PDF:
            file_path = await export_service.generate_pdf(
                export_data, include_charts=include_charts
            )
            filename = get_export_filename(export_data.name, export_format)
            content_type = EXPORT_CONTENT_TYPES[export_format]

            # Return file response (FastAPI handles cleanup with FileResponse)
            return FileResponse(
                path=file_path,
                filename=filename,
                media_type=content_type,
                background=None,  # File will be cleaned up after response is sent
            )

        elif export_format == ExportFormat.PPTX:
            file_path = await export_service.generate_pptx(
                export_data, include_charts=include_charts
            )
            filename = get_export_filename(export_data.name, export_format)
            content_type = EXPORT_CONTENT_TYPES[export_format]

            return FileResponse(
                path=file_path,
                filename=filename,
                media_type=content_type,
                background=None,
            )

        elif export_format == ExportFormat.CSV:
            csv_content = await export_service.generate_csv(export_data)
            filename = get_export_filename(export_data.name, export_format)
            content_type = EXPORT_CONTENT_TYPES[export_format]

            # Return streaming response for CSV
            return StreamingResponse(
                io.BytesIO(csv_content.encode("utf-8")),
                media_type=content_type,
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported export format: {format}",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Export generation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("export generation", e),
        ) from e


# ============================================================================
# Workstream Export Endpoints
# ============================================================================


@router.get("/workstreams/{workstream_id}/export/{format}")
async def export_workstream_report(
    workstream_id: str,
    format: str,
    current_user: dict = Depends(get_current_user_hardcoded),
    include_charts: bool = True,
    max_cards: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """
    Export a workstream report in the specified format.

    Generates a comprehensive report containing all cards associated with
    the workstream, including summary statistics and visualizations.

    Supported formats:
    - pdf: PDF document with charts and card details
    - pptx: PowerPoint presentation with slides for each card

    Note: CSV export is not supported for workstream reports.
    Use individual card exports for CSV data.

    Args:
        workstream_id: UUID of the workstream to export
        format: Export format ('pdf' or 'pptx')
        current_user: Authenticated user (injected)
        include_charts: Whether to include chart visualizations (default: True)
        max_cards: Maximum number of cards to include (default: 50, max: 100)

    Returns:
        FileResponse with the generated export file

    Raises:
        HTTPException 400: Invalid export format
        HTTPException 403: Not authorized to export this workstream
        HTTPException 404: Workstream not found
        HTTPException 500: Export generation failed
    """
    # Validate format (only pdf and pptx supported for workstream exports)
    format_lower = format.lower()
    if format_lower not in ["pdf", "pptx"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid export format '{format}'. Workstream reports support 'pdf' or 'pptx' formats only. Use individual card export for CSV.",
        )

    # Validate max_cards
    if max_cards < 1 or max_cards > 100:
        max_cards = min(max(max_cards, 1), 100)

    # Verify workstream exists and belongs to user
    try:
        ws_result = await db.execute(
            select(Workstream).where(Workstream.id == workstream_id)
        )
        workstream = ws_result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Failed to fetch workstream {workstream_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("workstream retrieval for export", e),
        ) from e

    if not workstream:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workstream not found"
        )

    # Verify ownership
    if str(workstream.user_id) != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to export this workstream",
        )

    # Initialize export service
    export_service = ExportService(db)

    # Get export format enum
    export_format = ExportFormat.PDF if format_lower == "pdf" else ExportFormat.PPTX

    # Generate export file path
    export_path = None

    try:
        if format_lower == "pdf":
            # Generate PDF report
            export_path = await export_service.generate_workstream_pdf(
                workstream_id=workstream_id,
                include_charts=include_charts,
                max_cards=max_cards,
            )
        else:
            # Generate PowerPoint report
            # First fetch workstream and cards for PPTX generation
            workstream_data, cards = await export_service.get_workstream_cards(
                workstream_id=workstream_id, max_cards=max_cards
            )

            if not workstream_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Workstream not found"
                )

            export_path = await export_service.generate_workstream_pptx(
                workstream=workstream_data,
                cards=cards,
                include_charts=include_charts,
                include_card_details=True,
            )

        # Verify file was created
        if not export_path or not Path(export_path).exists():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Export generation failed - file not created",
            )

        # Generate filename for download
        workstream_name = workstream.name or "workstream-report"
        filename = get_export_filename(workstream_name, export_format)

        # Get content type
        content_type = EXPORT_CONTENT_TYPES.get(
            export_format, "application/octet-stream"
        )

        logger.info(f"Workstream export generated: {workstream_id} as {format_lower}")

        # Return file response
        # Note: FileResponse will handle file cleanup after sending
        return FileResponse(
            path=export_path,
            filename=filename,
            media_type=content_type,
            background=None,  # Let FileResponse handle the response
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Failed to generate workstream export: {str(e)}")
        # Clean up temp file if it was created
        if export_path and Path(export_path).exists():
            try:
                Path(export_path).unlink()
            except Exception:
                pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("export generation", e),
        ) from e
