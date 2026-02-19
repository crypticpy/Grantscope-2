"""Export router for DOCX generation of proposals, budgets, and packages.

Provides endpoints that fetch application data from the database and
generate downloadable Word documents via DocxExportService.
"""

import io
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, get_current_user_hardcoded, _safe_error
from app.models.db.budget import BudgetLineItem, BudgetSettings
from app.models.db.checklist import ChecklistItem
from app.models.db.grant_application import GrantApplication
from app.models.db.proposal import Proposal
from app.services.access_control import (
    ROLE_VIEWER,
    require_application_access,
    require_proposal_access,
)
from app.services.docx_export_service import DocxExportService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["exports"])

# DOCX content type
_DOCX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_safe_filename(raw: str, suffix: str) -> str:
    """Sanitise a title into a safe filename."""
    safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in raw)[:40]
    return f"{safe.strip()}_{suffix}.docx"


def _row_to_dict(row) -> dict:
    """Convert a SQLAlchemy ORM row into a plain dict for serialisation."""
    obj = row[0] if hasattr(row, "__getitem__") else row
    data: dict = {}
    for col in obj.__table__.columns:
        value = getattr(obj, col.key, None)
        # Convert Decimal / UUID / datetime so downstream code works with
        # basic Python types and str-based dict access.
        if hasattr(value, "isoformat"):
            value = value.isoformat()
        elif isinstance(value, uuid.UUID):
            value = str(value)
        data[col.key] = value
    return data


async def _fetch_budget_items(
    db: AsyncSession,
    application_id: uuid.UUID,
) -> list[dict]:
    """Fetch all budget line items for an application, ordered by sort_order."""
    result = await db.execute(
        select(BudgetLineItem)
        .where(BudgetLineItem.application_id == application_id)
        .order_by(BudgetLineItem.sort_order)
    )
    return [_row_to_dict(row) for row in result.scalars().all()]


async def _fetch_budget_settings(
    db: AsyncSession,
    application_id: uuid.UUID,
) -> dict:
    """Fetch budget settings for an application, returning defaults if absent."""
    result = await db.execute(
        select(BudgetSettings).where(BudgetSettings.application_id == application_id)
    )
    row = result.scalars().first()
    if row:
        return _row_to_dict(row)
    return {
        "fringe_rate": 0.35,
        "indirect_rate": 0.10,
        "indirect_base": "mtdc",
        "match_required": False,
        "match_percentage": None,
    }


async def _fetch_checklist_items(
    db: AsyncSession,
    application_id: uuid.UUID,
) -> list[dict]:
    """Fetch all checklist items for an application, ordered by sort_order."""
    result = await db.execute(
        select(ChecklistItem)
        .where(ChecklistItem.application_id == application_id)
        .order_by(ChecklistItem.sort_order)
    )
    return [_row_to_dict(row) for row in result.scalars().all()]


def _compute_budget_calculations(
    budget_items: list[dict],
    settings: dict,
) -> dict:
    """Derive summary totals from budget line items and settings.

    Returns a dict with direct_total, indirect_total, grand_total,
    federal_share, and match_share.
    """
    direct_total = 0.0
    indirect_total = 0.0

    for item in budget_items:
        cost = float(item.get("total_cost", 0) or 0)
        if item.get("is_indirect") or item.get("category") == "indirect_costs":
            indirect_total += cost
        else:
            direct_total += cost

    grand_total = direct_total + indirect_total

    # Compute match split if applicable
    match_required = settings.get("match_required", False)
    match_pct = float(settings.get("match_percentage", 0) or 0)
    if match_required and match_pct > 0:
        match_share = grand_total * match_pct
        federal_share = grand_total - match_share
    else:
        federal_share = grand_total
        match_share = 0.0

    return {
        "direct_total": direct_total,
        "indirect_total": indirect_total,
        "grand_total": grand_total,
        "federal_share": federal_share,
        "match_share": match_share,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/applications/{application_id}/export/docx")
async def export_application_docx(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Export a full application package (proposal + budget + checklist) as DOCX.

    Fetches the grant application, its associated proposal, budget items,
    budget settings, and checklist items, then generates a combined Word
    document with page breaks between sections.

    Args:
        application_id: UUID of the grant application.
        db: Async database session (injected).
        current_user: Authenticated user (injected).

    Returns:
        StreamingResponse with the DOCX file.

    Raises:
        HTTPException 404: Application or proposal not found.
        HTTPException 500: Document generation failed.
    """
    await require_application_access(
        db,
        application_id=application_id,
        user_id=current_user["id"],
        minimum_role=ROLE_VIEWER,
    )

    # Fetch the application
    result = await db.execute(
        select(GrantApplication).where(GrantApplication.id == application_id)
    )
    application = result.scalars().first()
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grant application not found",
        )

    app_dict = _row_to_dict(application)

    # Fetch the proposal linked to this application
    proposal_result = await db.execute(
        select(Proposal).where(Proposal.application_id == application_id)
    )
    proposal = proposal_result.scalars().first()
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No proposal found for this application",
        )

    proposal_dict = _row_to_dict(proposal)

    # Fetch supporting data
    budget_items = await _fetch_budget_items(db, application_id)
    budget_settings = await _fetch_budget_settings(db, application_id)
    checklist_items = await _fetch_checklist_items(db, application_id)
    budget_calculations = _compute_budget_calculations(budget_items, budget_settings)
    budget_calculations["title"] = proposal_dict.get("title", "Grant Application")

    # Build grant context from application metadata
    grant_context = app_dict.get("proposal_content") or {}

    try:
        docx_bytes = DocxExportService.generate_package_docx(
            proposal=proposal_dict,
            budget_items=budget_items,
            budget_settings=budget_settings,
            budget_calculations=budget_calculations,
            checklist_items=checklist_items,
            grant_context=grant_context,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("application DOCX export", e),
        ) from e

    filename = _make_safe_filename(proposal_dict.get("title", "application"), "package")

    return StreamingResponse(
        io.BytesIO(docx_bytes),
        media_type=_DOCX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/applications/{application_id}/export/budget-docx")
async def export_budget_docx(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Export the budget detail for an application as a standalone DOCX.

    Args:
        application_id: UUID of the grant application.
        db: Async database session (injected).
        current_user: Authenticated user (injected).

    Returns:
        StreamingResponse with the DOCX file.

    Raises:
        HTTPException 404: Application not found.
        HTTPException 500: Document generation failed.
    """
    await require_application_access(
        db,
        application_id=application_id,
        user_id=current_user["id"],
        minimum_role=ROLE_VIEWER,
    )

    # Verify application exists
    result = await db.execute(
        select(GrantApplication).where(GrantApplication.id == application_id)
    )
    application = result.scalars().first()
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grant application not found",
        )

    # Fetch budget data
    budget_items = await _fetch_budget_items(db, application_id)
    budget_settings = await _fetch_budget_settings(db, application_id)
    budget_calculations = _compute_budget_calculations(budget_items, budget_settings)

    # Try to derive a title from the linked proposal
    proposal_result = await db.execute(
        select(Proposal.title).where(Proposal.application_id == application_id)
    )
    proposal_title_row = proposal_result.first()
    budget_calculations["title"] = (
        proposal_title_row[0] if proposal_title_row else "Grant Application"
    )

    try:
        docx_bytes = DocxExportService.generate_budget_docx(
            budget_items=budget_items,
            settings=budget_settings,
            calculations=budget_calculations,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("budget DOCX export", e),
        ) from e

    filename = _make_safe_filename(budget_calculations.get("title", "budget"), "budget")

    return StreamingResponse(
        io.BytesIO(docx_bytes),
        media_type=_DOCX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/proposals/{proposal_id}/export/docx")
async def export_proposal_docx(
    proposal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Export a proposal narrative as a DOCX document.

    Optionally includes budget data if the proposal is linked to an
    application that has budget line items.

    Args:
        proposal_id: UUID of the proposal.
        db: Async database session (injected).
        current_user: Authenticated user (injected).

    Returns:
        StreamingResponse with the DOCX file.

    Raises:
        HTTPException 404: Proposal not found.
        HTTPException 500: Document generation failed.
    """
    proposal = await require_proposal_access(
        db,
        proposal_id=proposal_id,
        user_id=current_user["id"],
        minimum_role=ROLE_VIEWER,
    )

    proposal_dict = _row_to_dict(proposal)

    # Optionally fetch budget items if proposal is linked to an application
    budget_items: list[dict] | None = None
    grant_context: dict | None = None

    if proposal.application_id:
        budget_items = await _fetch_budget_items(db, proposal.application_id)
        if not budget_items:
            budget_items = None

        # Fetch grant context from the application
        app_result = await db.execute(
            select(GrantApplication).where(
                GrantApplication.id == proposal.application_id
            )
        )
        app_row = app_result.scalars().first()
        if app_row:
            grant_context = _row_to_dict(app_row).get("proposal_content")

    try:
        docx_bytes = DocxExportService.generate_proposal_docx(
            proposal=proposal_dict,
            grant_context=grant_context,
            budget_items=budget_items,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("proposal DOCX export", e),
        ) from e

    filename = _make_safe_filename(proposal_dict.get("title", "proposal"), "proposal")

    return StreamingResponse(
        io.BytesIO(docx_bytes),
        media_type=_DOCX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
