"""Budget Builder router -- CRUD for line items, settings, calculations, export.

Uses SQLAlchemy async sessions (not supabase-py) with the hardcoded auth
dependency for the current single-tester phase.
"""

import io
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, get_current_user_hardcoded, _safe_error
from app.models.budget_models import (
    BudgetFullResponse,
    BudgetLineItemCreate,
    BudgetLineItemResponse,
    BudgetLineItemUpdate,
    BudgetPrefillRequest,
    BudgetSettingsResponse,
    BudgetSettingsUpdate,
    BudgetValidationResponse,
)
from app.models.db.budget import BudgetLineItem, BudgetSettings
from app.services.budget_service import BudgetService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["budget"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _decimal_to_float(val):
    """Convert Decimal or None to float for Pydantic serialization."""
    if val is None:
        return None
    return float(val)


def _item_to_response(item: BudgetLineItem) -> BudgetLineItemResponse:
    """Convert a SQLAlchemy BudgetLineItem to a Pydantic response."""
    return BudgetLineItemResponse(
        id=str(item.id),
        application_id=str(item.application_id),
        category=item.category,
        description=item.description,
        role=item.role,
        fte=_decimal_to_float(item.fte),
        annual_salary=_decimal_to_float(item.annual_salary),
        months_on_project=_decimal_to_float(item.months_on_project),
        quantity=_decimal_to_float(item.quantity),
        unit_cost=_decimal_to_float(item.unit_cost),
        total_cost=_decimal_to_float(item.total_cost),
        justification=item.justification,
        federal_share=_decimal_to_float(item.federal_share),
        match_share=_decimal_to_float(item.match_share),
        match_type=item.match_type,
        sort_order=item.sort_order,
        is_indirect=item.is_indirect,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _settings_to_response(settings: BudgetSettings) -> BudgetSettingsResponse:
    """Convert a SQLAlchemy BudgetSettings to a Pydantic response."""
    return BudgetSettingsResponse(
        id=str(settings.id),
        application_id=str(settings.application_id),
        fringe_rate=_decimal_to_float(settings.fringe_rate),
        indirect_rate=_decimal_to_float(settings.indirect_rate),
        indirect_base=settings.indirect_base,
        match_required=settings.match_required,
        match_percentage=_decimal_to_float(settings.match_percentage),
        match_total_required=_decimal_to_float(settings.match_total_required),
        fiscal_year_start=settings.fiscal_year_start,
        notes=settings.notes,
        created_at=settings.created_at,
        updated_at=settings.updated_at,
    )


async def _get_item_or_404(
    db: AsyncSession, item_id: uuid.UUID, application_id: uuid.UUID
) -> BudgetLineItem:
    """Fetch a line item by ID, scoped to an application. Raises 404 if not found."""
    stmt = select(BudgetLineItem).where(
        BudgetLineItem.id == item_id,
        BudgetLineItem.application_id == application_id,
    )
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget line item not found",
        )
    return item


# ---------------------------------------------------------------------------
# GET full budget
# ---------------------------------------------------------------------------


@router.get(
    "/applications/{application_id}/budget",
    response_model=BudgetFullResponse,
)
async def get_full_budget(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Retrieve the full budget for an application: items, settings, and calculations.

    Args:
        application_id: UUID of the grant application.
        db: Async database session (injected).
        current_user: Authenticated user (injected).

    Returns:
        BudgetFullResponse with items, settings, and calculations.
    """
    try:
        # Fetch items
        stmt = (
            select(BudgetLineItem)
            .where(BudgetLineItem.application_id == application_id)
            .order_by(BudgetLineItem.sort_order, BudgetLineItem.created_at)
        )
        result = await db.execute(stmt)
        items = result.scalars().all()

        # Fetch or create settings
        settings = await BudgetService.get_or_create_settings(db, application_id)

        # Calculate totals
        calculations = await BudgetService.calculate_totals(db, application_id)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("fetching budget", e),
        ) from e

    return BudgetFullResponse(
        items=[_item_to_response(item) for item in items],
        settings=_settings_to_response(settings),
        calculations=calculations,
    )


# ---------------------------------------------------------------------------
# POST create line item
# ---------------------------------------------------------------------------


@router.post(
    "/applications/{application_id}/budget/items",
    response_model=BudgetLineItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_line_item(
    application_id: uuid.UUID,
    body: BudgetLineItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Add a new line item to the application's budget.

    Args:
        application_id: UUID of the grant application.
        body: BudgetLineItemCreate with category, description, total_cost, etc.
        db: Async database session (injected).
        current_user: Authenticated user (injected).

    Returns:
        The created BudgetLineItemResponse.
    """
    try:
        from decimal import Decimal

        item = BudgetLineItem(
            application_id=application_id,
            category=body.category,
            description=body.description,
            role=body.role,
            fte=Decimal(str(body.fte)) if body.fte is not None else None,
            annual_salary=(
                Decimal(str(body.annual_salary))
                if body.annual_salary is not None
                else None
            ),
            months_on_project=(
                Decimal(str(body.months_on_project))
                if body.months_on_project is not None
                else None
            ),
            quantity=Decimal(str(body.quantity)) if body.quantity is not None else None,
            unit_cost=(
                Decimal(str(body.unit_cost)) if body.unit_cost is not None else None
            ),
            total_cost=Decimal(str(body.total_cost)),
            justification=body.justification,
            federal_share=(
                Decimal(str(body.federal_share))
                if body.federal_share is not None
                else None
            ),
            match_share=(
                Decimal(str(body.match_share)) if body.match_share is not None else None
            ),
            match_type=body.match_type,
            is_indirect=(body.category == "indirect_costs"),
        )
        db.add(item)
        await db.flush()
        await db.refresh(item)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("creating budget line item", e),
        ) from e

    return _item_to_response(item)


# ---------------------------------------------------------------------------
# PATCH update line item
# ---------------------------------------------------------------------------


@router.patch(
    "/applications/{application_id}/budget/items/{item_id}",
    response_model=BudgetLineItemResponse,
)
async def update_line_item(
    application_id: uuid.UUID,
    item_id: uuid.UUID,
    body: BudgetLineItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Update an existing budget line item.

    Only fields present in the request body will be modified.

    Args:
        application_id: UUID of the grant application.
        item_id: UUID of the line item to update.
        body: BudgetLineItemUpdate with optional fields.
        db: Async database session (injected).
        current_user: Authenticated user (injected).

    Returns:
        The updated BudgetLineItemResponse.
    """
    try:
        item = await _get_item_or_404(db, item_id, application_id)

        from decimal import Decimal

        update_data = body.model_dump(exclude_unset=True)

        for field_name, value in update_data.items():
            if value is None and field_name in (
                "role",
                "justification",
                "match_type",
            ):
                # Allow explicitly setting nullable text fields to None
                setattr(item, field_name, value)
            elif value is not None:
                # Convert float fields to Decimal for DB storage
                decimal_fields = {
                    "fte",
                    "annual_salary",
                    "months_on_project",
                    "quantity",
                    "unit_cost",
                    "total_cost",
                    "federal_share",
                    "match_share",
                }
                if field_name in decimal_fields:
                    setattr(item, field_name, Decimal(str(value)))
                else:
                    setattr(item, field_name, value)

        # Auto-set is_indirect flag based on category
        if "category" in update_data and update_data["category"] is not None:
            item.is_indirect = update_data["category"] == "indirect_costs"

        await db.flush()
        await db.refresh(item)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("updating budget line item", e),
        ) from e

    return _item_to_response(item)


# ---------------------------------------------------------------------------
# DELETE line item
# ---------------------------------------------------------------------------


@router.delete(
    "/applications/{application_id}/budget/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_line_item(
    application_id: uuid.UUID,
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Delete a budget line item.

    Args:
        application_id: UUID of the grant application.
        item_id: UUID of the line item to delete.
        db: Async database session (injected).
        current_user: Authenticated user (injected).
    """
    try:
        item = await _get_item_or_404(db, item_id, application_id)
        await db.delete(item)
        await db.flush()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("deleting budget line item", e),
        ) from e


# ---------------------------------------------------------------------------
# PATCH budget settings
# ---------------------------------------------------------------------------


@router.patch(
    "/applications/{application_id}/budget/settings",
    response_model=BudgetSettingsResponse,
)
async def update_budget_settings(
    application_id: uuid.UUID,
    body: BudgetSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Update budget settings (fringe rate, indirect rate, match requirements, etc.).

    Args:
        application_id: UUID of the grant application.
        body: BudgetSettingsUpdate with optional fields.
        db: Async database session (injected).
        current_user: Authenticated user (injected).

    Returns:
        The updated BudgetSettingsResponse.
    """
    try:
        settings = await BudgetService.get_or_create_settings(db, application_id)

        from decimal import Decimal

        update_data = body.model_dump(exclude_unset=True)

        for field_name, value in update_data.items():
            if value is not None:
                decimal_fields = {
                    "fringe_rate",
                    "indirect_rate",
                    "match_percentage",
                    "match_total_required",
                }
                if field_name in decimal_fields:
                    setattr(settings, field_name, Decimal(str(value)))
                else:
                    setattr(settings, field_name, value)
            else:
                # Allow nulling out optional fields
                setattr(settings, field_name, value)

        await db.flush()
        await db.refresh(settings)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("updating budget settings", e),
        ) from e

    return _settings_to_response(settings)


# ---------------------------------------------------------------------------
# POST prefill from wizard plan data
# ---------------------------------------------------------------------------


@router.post(
    "/applications/{application_id}/budget/prefill",
    response_model=list[BudgetLineItemResponse],
    status_code=status.HTTP_201_CREATED,
)
async def prefill_budget(
    application_id: uuid.UUID,
    body: BudgetPrefillRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Pre-fill budget line items from wizard plan data.

    Parses staffing_plan and budget entries from the plan_data and creates
    corresponding BudgetLineItem rows.

    Args:
        application_id: UUID of the grant application.
        body: BudgetPrefillRequest containing plan_data dict.
        db: Async database session (injected).
        current_user: Authenticated user (injected).

    Returns:
        List of created BudgetLineItemResponse objects.
    """
    try:
        items = await BudgetService.create_from_plan_data(
            db, application_id, body.plan_data
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("pre-filling budget", e),
        ) from e

    return [_item_to_response(item) for item in items]


# ---------------------------------------------------------------------------
# GET CSV export
# ---------------------------------------------------------------------------


@router.get("/applications/{application_id}/budget/export/csv")
async def export_budget_csv(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Export the budget as a CSV file.

    Args:
        application_id: UUID of the grant application.
        db: Async database session (injected).
        current_user: Authenticated user (injected).

    Returns:
        StreamingResponse with CSV content.
    """
    try:
        csv_content = await BudgetService.export_csv(db, application_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("exporting budget CSV", e),
        ) from e

    filename = f"budget_{application_id}.csv"
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# POST validate budget
# ---------------------------------------------------------------------------


@router.post(
    "/applications/{application_id}/budget/validate",
    response_model=BudgetValidationResponse,
)
async def validate_budget(
    application_id: uuid.UUID,
    grant_context: Optional[dict] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Run validation checks on the budget.

    Optionally accepts a grant_context dict in the request body to check
    the budget against the grant's funding range.

    Args:
        application_id: UUID of the grant application.
        grant_context: Optional dict with funding_range, etc.
        db: Async database session (injected).
        current_user: Authenticated user (injected).

    Returns:
        BudgetValidationResponse with valid flag and list of issues.
    """
    try:
        result = await BudgetService.validate_budget(db, application_id, grant_context)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("validating budget", e),
        ) from e

    return BudgetValidationResponse(**result)
