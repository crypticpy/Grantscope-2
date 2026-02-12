"""Card and workstream export router -- PDF, PPTX, CSV exports."""

import io
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse, FileResponse

from app.deps import supabase, get_current_user, _safe_error
from app.export_service import ExportService
from app.models.export import (
    ExportFormat,
    CardExportData,
    EXPORT_CONTENT_TYPES,
    get_export_filename,
)

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
    current_user: dict = Depends(get_current_user),
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
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid export format: {format}. Supported formats: pdf, pptx, csv",
        )

    # Fetch card from database with joined reference data
    response = (
        supabase.table("cards")
        .select("*, pillars(name), goals(name), stages(name)")
        .eq("id", card_id)
        .single()
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Card not found: {card_id}"
        )

    card_data = response.data

    # Extract joined names
    pillar_name = (
        card_data.get("pillars", {}).get("name") if card_data.get("pillars") else None
    )
    goal_name = (
        card_data.get("goals", {}).get("name") if card_data.get("goals") else None
    )
    stage_name = (
        card_data.get("stages", {}).get("name") if card_data.get("stages") else None
    )

    # Fetch latest completed deep research report for this card
    research_report = None
    research_reports = []
    try:
        research_response = (
            supabase.table("research_tasks")
            .select("id, task_type, result_summary, completed_at")
            .eq("card_id", card_id)
            .eq("status", "completed")
            .eq("task_type", "deep_research")
            .order("completed_at", desc=True)
            .limit(3)
            .execute()
        )

        if research_response.data:
            for task in research_response.data:
                if task.get("result_summary", {}).get("report_preview"):
                    research_reports.append(
                        {
                            "completed_at": task.get("completed_at"),
                            "report": task["result_summary"]["report_preview"],
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
            id=card_data["id"],
            name=card_data["name"],
            slug=card_data.get("slug", ""),
            summary=card_data.get("summary"),
            description=card_data.get("description"),
            pillar_id=card_data.get("pillar_id"),
            pillar_name=pillar_name,
            goal_id=card_data.get("goal_id"),
            goal_name=goal_name,
            anchor_id=card_data.get("anchor_id"),
            stage_id=card_data.get("stage_id"),
            stage_name=stage_name,
            horizon=card_data.get("horizon"),
            novelty_score=card_data.get("novelty_score"),
            maturity_score=card_data.get("maturity_score"),
            impact_score=card_data.get("impact_score"),
            relevance_score=card_data.get("relevance_score"),
            velocity_score=card_data.get("velocity_score"),
            risk_score=card_data.get("risk_score"),
            opportunity_score=card_data.get("opportunity_score"),
            status=card_data.get("status"),
            created_at=card_data.get("created_at"),
            updated_at=card_data.get("updated_at"),
            deep_research_report=research_report,
        )
    except Exception as e:
        logger.error(f"Failed to create CardExportData: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to prepare card data for export",
        )

    # Initialize export service
    export_service = ExportService(supabase)

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
        )


# ============================================================================
# Workstream Export Endpoints
# ============================================================================


@router.get("/workstreams/{workstream_id}/export/{format}")
async def export_workstream_report(
    workstream_id: str,
    format: str,
    current_user: dict = Depends(get_current_user),
    include_charts: bool = True,
    max_cards: int = 50,
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
    ws_response = (
        supabase.table("workstreams").select("*").eq("id", workstream_id).execute()
    )
    if not ws_response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workstream not found"
        )

    workstream = ws_response.data[0]

    # Verify ownership
    if workstream.get("user_id") != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to export this workstream",
        )

    # Initialize export service
    export_service = ExportService(supabase)

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
        workstream_name = workstream.get("name", "workstream-report")
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
        )
