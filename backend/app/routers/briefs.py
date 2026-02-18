"""Executive briefs router."""

import logging
import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, get_current_user_hardcoded, _safe_error, openai_client
from app.brief_service import ExecutiveBriefService
from app.export_service import ExportService
from app.models.brief import (
    ExecutiveBriefResponse,
    BriefGenerateResponse,
    BriefStatusResponse,
    BriefVersionsResponse,
    BriefVersionListItem,
)
from app.models.briefs_extra import (
    BulkExportRequest,
    BulkBriefCardStatus,
    BulkBriefStatusResponse,
)
from app.models.export import ExportFormat, EXPORT_CONTENT_TYPES, get_export_filename
from app.models.db.brief import ExecutiveBrief
from app.models.db.workstream import Workstream, WorkstreamCard
from app.models.db.card import Card

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["briefs"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_dict(obj, skip_cols=None) -> dict:
    skip = skip_cols or set()
    result = {}
    for col in obj.__table__.columns:
        if col.name in skip:
            continue
        value = getattr(obj, col.key, None)
        if isinstance(value, uuid.UUID):
            result[col.name] = str(value)
        elif isinstance(value, (datetime, date)):
            result[col.name] = value.isoformat()
        elif isinstance(value, Decimal):
            result[col.name] = float(value)
        else:
            result[col.name] = value
    return result


async def _verify_workstream_ownership(
    db: AsyncSession, workstream_id: str, user_id: str
) -> Workstream:
    """Verify the workstream exists and belongs to the user. Returns the row."""
    stmt = select(Workstream).where(Workstream.id == workstream_id)
    result = await db.execute(stmt)
    ws = result.scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail="Workstream not found")
    if str(ws.user_id) != user_id:
        raise HTTPException(
            status_code=403, detail="Not authorized to access this workstream"
        )
    return ws


async def _get_workstream_card(
    db: AsyncSession, workstream_id: str, card_id: str
) -> WorkstreamCard:
    """Get a workstream_card record. Raises 404 if not found."""
    stmt = (
        select(WorkstreamCard)
        .where(WorkstreamCard.workstream_id == workstream_id)
        .where(WorkstreamCard.card_id == card_id)
    )
    result = await db.execute(stmt)
    wsc = result.scalar_one_or_none()
    if not wsc:
        raise HTTPException(status_code=404, detail="Card not found in this workstream")
    return wsc


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post(
    "/me/workstreams/{workstream_id}/cards/{card_id}/brief",
    response_model=BriefGenerateResponse,
)
async def generate_executive_brief(
    workstream_id: str,
    card_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Generate a new version of an executive brief for a card in a workstream.

    Creates a new brief version that runs asynchronously.
    Each call creates a new version (v1, v2, v3, etc.).
    Poll GET .../brief/status for completion status.

    Args:
        workstream_id: UUID of the workstream
        card_id: UUID of the card
        current_user: Authenticated user (injected)

    Returns:
        BriefGenerateResponse with brief ID, version, and pending status

    Raises:
        HTTPException 404: Workstream or card not found
        HTTPException 403: Not authorized to access workstream
    """
    await _verify_workstream_ownership(db, workstream_id, current_user["id"])
    wsc = await _get_workstream_card(db, workstream_id, card_id)
    workstream_card_id = str(wsc.id)

    brief_service = ExecutiveBriefService(db, openai_client)

    try:
        # Check if there's a brief currently generating
        existing_brief = await brief_service.get_brief_by_workstream_card(
            workstream_card_id
        )

        if existing_brief and existing_brief.get("status") in ("pending", "generating"):
            # Don't allow generating while another is in progress
            return BriefGenerateResponse(
                id=existing_brief["id"],
                status=existing_brief["status"],
                version=existing_brief.get("version", 1),
                message="Brief generation already in progress",
            )

        # Get the last completed brief to determine new sources
        last_completed = await brief_service.get_latest_completed_brief(
            workstream_card_id
        )
        since_timestamp = None
        sources_since_previous = None

        if last_completed and last_completed.get("generated_at"):
            since_timestamp = last_completed["generated_at"]
            # Count new sources since last brief
            new_source_count = await brief_service.count_new_sources(
                card_id, since_timestamp
            )
            sources_since_previous = {
                "count": new_source_count,
                "since_version": last_completed.get("version", 1),
                "since_date": since_timestamp,
            }

        # Create the brief record with pending status (auto-increments version)
        brief_record = await brief_service.create_brief_record(
            workstream_card_id=workstream_card_id,
            card_id=card_id,
            user_id=current_user["id"],
            sources_since_previous=sources_since_previous,
        )

        brief_id = brief_record["id"]
        brief_version = brief_record.get("version", 1)

        return BriefGenerateResponse(
            id=brief_id,
            status="pending",
            version=brief_version,
            message=f"Brief v{brief_version} queued for generation",
        )

    except Exception as e:
        logger.error(f"Failed to initiate brief generation: {str(e)}")
        raise HTTPException(
            status_code=500, detail=_safe_error("brief generation", e)
        ) from e


@router.get(
    "/me/workstreams/{workstream_id}/cards/{card_id}/brief",
    response_model=ExecutiveBriefResponse,
)
async def get_executive_brief(
    workstream_id: str,
    card_id: str,
    version: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Get an executive brief for a card in a workstream.

    Returns the latest version by default, or a specific version if provided.
    Returns 404 if no brief exists.

    Args:
        workstream_id: UUID of the workstream
        card_id: UUID of the card
        version: Optional version number (defaults to latest)
        current_user: Authenticated user (injected)

    Returns:
        ExecutiveBriefResponse with full brief content

    Raises:
        HTTPException 404: Workstream, card, or brief not found
        HTTPException 403: Not authorized to access workstream
    """
    await _verify_workstream_ownership(db, workstream_id, current_user["id"])
    wsc = await _get_workstream_card(db, workstream_id, card_id)
    workstream_card_id = str(wsc.id)

    # Fetch the brief (latest or specific version)
    brief_service = ExecutiveBriefService(db, openai_client)
    brief = await brief_service.get_brief_by_workstream_card(
        workstream_card_id, version=version
    )

    if not brief:
        if version:
            raise HTTPException(
                status_code=404, detail=f"Brief version {version} not found"
            )
        raise HTTPException(status_code=404, detail="No brief found for this card")

    return ExecutiveBriefResponse(**brief)


@router.get(
    "/me/workstreams/{workstream_id}/cards/{card_id}/brief/versions",
    response_model=BriefVersionsResponse,
)
async def get_brief_versions(
    workstream_id: str,
    card_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Get all versions of executive briefs for a card in a workstream.

    Returns a list of all brief versions, ordered by version number descending.

    Args:
        workstream_id: UUID of the workstream
        card_id: UUID of the card
        current_user: Authenticated user (injected)

    Returns:
        BriefVersionsResponse with list of all versions

    Raises:
        HTTPException 404: Workstream or card not found
        HTTPException 403: Not authorized to access workstream
    """
    await _verify_workstream_ownership(db, workstream_id, current_user["id"])
    wsc = await _get_workstream_card(db, workstream_id, card_id)
    workstream_card_id = str(wsc.id)

    # Fetch all versions
    brief_service = ExecutiveBriefService(db, openai_client)
    versions = await brief_service.get_brief_versions(workstream_card_id)

    # Convert to response model
    version_items = [
        BriefVersionListItem(
            id=v["id"],
            version=v.get("version", 1),
            status=v["status"],
            summary=v.get("summary"),
            sources_since_previous=v.get("sources_since_previous"),
            generated_at=v.get("generated_at"),
            created_at=v["created_at"],
            model_used=v.get("model_used"),
        )
        for v in versions
    ]

    return BriefVersionsResponse(
        workstream_card_id=workstream_card_id,
        card_id=card_id,
        total_versions=len(version_items),
        versions=version_items,
    )


@router.get(
    "/me/workstreams/{workstream_id}/cards/{card_id}/brief/status",
    response_model=BriefStatusResponse,
)
async def get_brief_status(
    workstream_id: str,
    card_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Get the status of brief generation for a card.

    Used for polling during async brief generation.
    Returns status, summary (if complete), or error (if failed).

    Args:
        workstream_id: UUID of the workstream
        card_id: UUID of the card
        current_user: Authenticated user (injected)

    Returns:
        BriefStatusResponse with generation status

    Raises:
        HTTPException 404: Workstream, card, or brief not found
        HTTPException 403: Not authorized to access workstream
    """
    await _verify_workstream_ownership(db, workstream_id, current_user["id"])
    wsc = await _get_workstream_card(db, workstream_id, card_id)
    workstream_card_id = str(wsc.id)

    # Fetch the most recent brief
    brief_service = ExecutiveBriefService(db, openai_client)
    brief = await brief_service.get_brief_by_workstream_card(workstream_card_id)

    if not brief:
        raise HTTPException(status_code=404, detail="No brief found for this card")

    # Build progress message based on status
    progress_message = None
    if brief["status"] == "pending":
        progress_message = "Brief generation queued..."
    elif brief["status"] == "generating":
        progress_message = "Generating executive brief..."

    return BriefStatusResponse(
        id=brief["id"],
        status=brief["status"],
        version=brief.get("version", 1),
        summary=brief.get("summary"),
        error_message=brief.get("error_message"),
        generated_at=brief.get("generated_at"),
        progress_message=progress_message,
    )


@router.get("/me/workstreams/{workstream_id}/cards/{card_id}/brief/export/{format}")
async def export_brief(
    workstream_id: str,
    card_id: str,
    format: str,
    version: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Export an executive brief in the specified format.

    Exports the brief content (not the original card) as a PDF or PowerPoint
    presentation formatted for executive communication.

    Args:
        workstream_id: UUID of the workstream
        card_id: UUID of the card
        format: Export format (pdf or pptx)
        version: Optional version number to export (defaults to latest)
        current_user: Authenticated user (injected)

    Returns:
        FileResponse with the exported brief document

    Raises:
        HTTPException 400: Invalid export format
        HTTPException 404: Workstream, card, or brief not found
        HTTPException 403: Not authorized to access workstream
    """
    # Validate format
    format_lower = format.lower()
    if format_lower not in ("pdf", "pptx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid export format: {format}. Supported formats: pdf, pptx",
        )

    await _verify_workstream_ownership(db, workstream_id, current_user["id"])
    wsc = await _get_workstream_card(db, workstream_id, card_id)
    workstream_card_id = str(wsc.id)

    # Fetch the brief
    brief_service = ExecutiveBriefService(db, openai_client)
    brief = await brief_service.get_brief_by_workstream_card(
        workstream_card_id, version=version
    )

    if not brief:
        raise HTTPException(status_code=404, detail="No brief found for this card")

    if brief["status"] != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Brief is not yet complete. Please wait for generation to finish.",
        )

    # Fetch card info for the export (including classification)
    try:
        card_stmt = select(Card).where(Card.id == card_id)
        card_result = await db.execute(card_stmt)
        card_row = card_result.scalar_one_or_none()
    except Exception:
        card_row = None

    card_name = "Unknown Card"
    classification = {}
    if card_row:
        card_name = card_row.name or "Unknown Card"
        classification = {
            "pillar": card_row.pillar_id,
            "horizon": card_row.horizon,
            "stage": card_row.stage_id,
        }

    # Generate export using ExportService
    export_service = ExportService(db)

    try:
        # Parse generated_at if present
        generated_at = None
        if brief.get("generated_at"):
            if isinstance(brief["generated_at"], str):
                generated_at = datetime.fromisoformat(
                    brief["generated_at"].replace("Z", "+00:00")
                )
            else:
                generated_at = brief["generated_at"]

        if format_lower == "pdf":
            # Use professional PDF with logo, branding, and AI disclosure
            file_path = await export_service.generate_professional_brief_pdf(
                brief_title=card_name,
                card_name=card_name,
                executive_summary=brief.get("summary", ""),
                content_markdown=brief.get("content_markdown", ""),
                generated_at=generated_at,
                version=brief.get("version", 1),
                classification=classification,
            )
            content_type = "application/pdf"
            extension = "pdf"
        else:
            file_path = await export_service.generate_brief_pptx(
                brief_title=card_name,
                card_name=card_name,
                executive_summary=brief.get("summary", ""),
                content_markdown=brief.get("content_markdown", ""),
                generated_at=generated_at,
                version=brief.get("version", 1),
                classification=classification,
                use_gamma=True,  # Try Gamma.app first, fallback to local
            )
            content_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            extension = "pptx"

        # Generate safe filename
        safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in card_name)
        safe_name = safe_name[:50]  # Limit length
        version_str = (
            f"_v{brief.get('version', 1)}" if brief.get("version", 1) > 1 else ""
        )
        filename = f"Brief_{safe_name}{version_str}.{extension}"

        return FileResponse(
            path=file_path, filename=filename, media_type=content_type, background=None
        )

    except Exception as e:
        logger.error(f"Brief export generation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("export generation", e),
        ) from e


# =============================================================================
# Bulk Brief Export (Portfolio)
# =============================================================================


@router.get("/me/workstreams/{workstream_id}/bulk-brief-status")
async def get_bulk_brief_status(
    workstream_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
) -> BulkBriefStatusResponse:
    """
    Get brief status for all cards in the Brief column.

    Used by the frontend to show which cards have completed briefs
    before initiating a bulk export.

    Args:
        workstream_id: UUID of the workstream
        current_user: Authenticated user (injected)

    Returns:
        BulkBriefStatusResponse with summary counts and per-card status
    """
    ws = await _verify_workstream_ownership(db, workstream_id, current_user["id"])

    # Get all workstream_cards in brief column, joined with cards
    wsc_stmt = (
        select(WorkstreamCard, Card)
        .join(Card, WorkstreamCard.card_id == Card.id)
        .where(WorkstreamCard.workstream_id == workstream_id)
        .where(WorkstreamCard.status == "brief")
        .order_by(WorkstreamCard.position)
    )
    wsc_result = await db.execute(wsc_stmt)
    wsc_rows = wsc_result.all()

    card_statuses = []
    cards_with_briefs = 0
    cards_ready = 0

    for wsc_row, card_row in wsc_rows:
        card_id = str(wsc_row.card_id)
        position = wsc_row.position or 0

        # Check for completed brief
        brief_stmt = (
            select(ExecutiveBrief)
            .where(ExecutiveBrief.workstream_card_id == wsc_row.id)
            .where(ExecutiveBrief.status == "completed")
            .limit(1)
        )
        brief_result = await db.execute(brief_stmt)
        brief_row = brief_result.scalar_one_or_none()

        has_brief = brief_row is not None
        brief_status = brief_row.status if has_brief else None

        if has_brief:
            cards_with_briefs += 1
            if brief_status == "completed":
                cards_ready += 1

        card_statuses.append(
            BulkBriefCardStatus(
                card_id=card_id,
                card_name=card_row.name if card_row else "Unknown",
                has_brief=has_brief,
                brief_status=brief_status,
                position=position,
            )
        )

    return BulkBriefStatusResponse(
        total_cards=len(card_statuses),
        cards_with_briefs=cards_with_briefs,
        cards_ready=cards_ready,
        card_statuses=card_statuses,
    )


@router.post("/me/workstreams/{workstream_id}/bulk-brief-export")
async def bulk_brief_export(
    workstream_id: str,
    request: BulkExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Export multiple briefs as a single portfolio presentation.

    Generates an AI-synthesized portfolio deck combining briefs from
    multiple cards in the Brief column. Uses Gamma.app for PPTX with
    fallback to local generation.

    Args:
        workstream_id: UUID of the workstream
        request: BulkExportRequest with format and card order
        current_user: Authenticated user (injected)

    Returns:
        FileResponse with the exported portfolio document

    Raises:
        HTTPException 400: Invalid format, no cards, or >15 cards
        HTTPException 403: Not authorized
        HTTPException 404: Workstream not found
    """
    from app.brief_service import ExecutiveBriefService, PortfolioBrief
    from app.gamma_service import (
        GammaPortfolioService,
        PortfolioCard,
        PortfolioSynthesisData,
        calculate_slides_per_card,
    )

    # Validate format
    format_lower = request.format.lower()
    if format_lower not in ("pdf", "pptx"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid format: {request.format}. Supported: pdf, pptx",
        )

    # Validate card count
    if not request.card_order:
        raise HTTPException(status_code=400, detail="No cards provided for export")

    if len(request.card_order) > 15:
        raise HTTPException(
            status_code=400,
            detail="Maximum 15 cards per portfolio. Archive some cards or create separate workstreams.",
        )

    ws = await _verify_workstream_ownership(db, workstream_id, current_user["id"])
    workstream_name = ws.name or "Strategic Portfolio"

    # Fetch briefs in the specified order
    brief_service = ExecutiveBriefService(db, openai_client)
    portfolio_briefs = []
    skipped_cards = []

    for cid in request.card_order:
        # Get workstream_card record
        wsc_stmt = (
            select(WorkstreamCard)
            .where(WorkstreamCard.workstream_id == workstream_id)
            .where(WorkstreamCard.card_id == cid)
        )
        wsc_result = await db.execute(wsc_stmt)
        wsc_row = wsc_result.scalar_one_or_none()

        if not wsc_row:
            skipped_cards.append(cid)
            continue

        workstream_card_id = str(wsc_row.id)

        # Get latest completed brief
        brief = await brief_service.get_latest_completed_brief(workstream_card_id)
        if not brief:
            skipped_cards.append(cid)
            continue

        # Get card data via SQLAlchemy
        card_stmt = select(Card).where(Card.id == cid)
        card_result = await db.execute(card_stmt)
        card_row = card_result.scalar_one_or_none()

        if not card_row:
            skipped_cards.append(cid)
            continue

        card_data = _row_to_dict(card_row)

        portfolio_briefs.append(
            PortfolioBrief(
                card_id=cid,
                card_name=card_data.get("name", "Unknown"),
                pillar_id=card_data.get("pillar_id", ""),
                horizon=card_data.get("horizon", ""),
                stage_id=card_data.get("stage_id", ""),
                brief_summary=brief.get("summary", ""),
                brief_content_markdown=brief.get("content_markdown", ""),
                impact_score=card_data.get("impact_score", 50),
                relevance_score=card_data.get("relevance_score", 50),
                velocity_score=card_data.get("velocity_score", 50),
            )
        )

    if not portfolio_briefs:
        raise HTTPException(
            status_code=400,
            detail="No completed briefs found for the specified cards. Generate briefs first.",
        )

    logger.info(
        f"Generating portfolio export: {len(portfolio_briefs)} briefs, format={format_lower}"
    )
    if skipped_cards:
        logger.warning(f"Skipped {len(skipped_cards)} cards without completed briefs")

    try:
        # Step 1: Generate AI synthesis
        logger.info("Generating portfolio synthesis...")
        synthesis = await brief_service.synthesize_portfolio(
            briefs=portfolio_briefs, workstream_name=workstream_name
        )

        # Convert to Gamma format
        gamma_cards = [
            PortfolioCard(
                card_id=b.card_id,
                card_name=b.card_name,
                pillar_id=b.pillar_id,
                horizon=b.horizon,
                stage_id=b.stage_id,
                brief_summary=b.brief_summary,
                brief_content=b.brief_content_markdown[:1500],  # Truncate for slides
                impact_score=b.impact_score,
                relevance_score=b.relevance_score,
            )
            for b in portfolio_briefs
        ]

        synthesis_data = PortfolioSynthesisData(
            executive_overview=synthesis.executive_overview,
            key_themes=synthesis.key_themes,
            priority_matrix=synthesis.priority_matrix,
            cross_cutting_insights=synthesis.cross_cutting_insights,
            recommended_actions=synthesis.recommended_actions,
            urgency_statement=synthesis.urgency_statement,
            implementation_guidance=synthesis.implementation_guidance,
            ninety_day_actions=synthesis.ninety_day_actions,
            risk_summary=synthesis.risk_summary,
            opportunity_summary=synthesis.opportunity_summary,
        )

        # Step 2: Generate presentation
        if format_lower == "pptx":
            # Try Gamma first
            gamma_service = GammaPortfolioService()

            if gamma_service.is_available():
                logger.info(
                    f"Generating portfolio via Gamma for {len(gamma_cards)} cards..."
                )
                result = await gamma_service.generate_portfolio_presentation(
                    workstream_name=workstream_name,
                    cards=gamma_cards,
                    synthesis=synthesis_data,
                    include_images=True,
                    export_format="pptx",
                )

                if result.success and result.pptx_url:
                    # Download from Gamma
                    from app.gamma_service import GammaService

                    gamma_dl = GammaService()
                    pptx_bytes = await gamma_dl.download_export(result.pptx_url)

                    if pptx_bytes:
                        import tempfile

                        temp_file = tempfile.NamedTemporaryFile(
                            suffix=".pptx", delete=False, prefix="grantscope_portfolio_"
                        )
                        temp_file.write(pptx_bytes)
                        temp_file.close()

                        safe_name = "".join(
                            c if c.isalnum() or c in " -_" else "_"
                            for c in workstream_name
                        )[:40]
                        filename = f"Portfolio_{safe_name}.pptx"

                        logger.info(
                            f"Portfolio generated via Gamma: {len(portfolio_briefs)} cards"
                        )

                        return FileResponse(
                            path=temp_file.name,
                            filename=filename,
                            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        )

                logger.warning(
                    f"Gamma portfolio failed: {result.error_message}, falling back to local"
                )
            else:
                logger.info(
                    "Gamma API not available (no API key or disabled), using local generation"
                )

            # Fallback to local PPTX generation
            logger.info("Generating portfolio locally...")
            export_service = ExportService(db)
            file_path = await export_service.generate_portfolio_pptx_local(
                workstream_name=workstream_name,
                briefs=portfolio_briefs,
                synthesis=synthesis_data,
            )

            safe_name = "".join(
                c if c.isalnum() or c in " -_" else "_" for c in workstream_name
            )[:40]
            filename = f"Portfolio_{safe_name}.pptx"

            return FileResponse(
                path=file_path,
                filename=filename,
                media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )

        else:
            # PDF generation - expanded detail format
            export_service = ExportService(db)
            file_path = await export_service.generate_portfolio_pdf(
                workstream_name=workstream_name,
                briefs=portfolio_briefs,
                synthesis=synthesis_data,
            )

            safe_name = "".join(
                c if c.isalnum() or c in " -_" else "_" for c in workstream_name
            )[:40]
            filename = f"Portfolio_{safe_name}.pdf"

            return FileResponse(
                path=file_path, filename=filename, media_type="application/pdf"
            )

    except Exception as e:
        logger.error(f"Portfolio export failed: {str(e)}")
        raise HTTPException(
            status_code=500, detail=_safe_error("portfolio generation", e)
        ) from e
