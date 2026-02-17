"""Business logic for the Budget Builder feature.

Handles budget line item calculations, pre-fill from wizard plan data,
validation, and CSV export.
"""

import csv
import io
import logging
import uuid
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.budget import BudgetLineItem, BudgetSettings

logger = logging.getLogger(__name__)

# Two-decimal quantizer for money rounding
_TWO_PLACES = Decimal("0.01")

# Budget categories in standard display order
CATEGORY_ORDER = [
    "personnel",
    "fringe_benefits",
    "travel",
    "equipment",
    "supplies",
    "contractual",
    "construction",
    "other_direct",
    "indirect_costs",
]


def _to_float(value: Optional[Decimal]) -> float:
    """Convert a Decimal to float, returning 0.0 for None."""
    if value is None:
        return 0.0
    return float(value)


def _to_decimal(value: Optional[float]) -> Optional[Decimal]:
    """Convert a float to Decimal, returning None for None."""
    if value is None:
        return None
    return Decimal(str(value)).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


class BudgetService:
    """Static-method service for budget operations."""

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    @staticmethod
    async def get_or_create_settings(
        db: AsyncSession, application_id: uuid.UUID
    ) -> BudgetSettings:
        """Fetch existing budget settings or create with defaults.

        Args:
            db: Async database session.
            application_id: UUID of the grant application.

        Returns:
            The BudgetSettings row (existing or newly created).
        """
        stmt = select(BudgetSettings).where(
            BudgetSettings.application_id == application_id
        )
        result = await db.execute(stmt)
        settings = result.scalar_one_or_none()

        if settings is not None:
            return settings

        settings = BudgetSettings(application_id=application_id)
        db.add(settings)
        await db.flush()
        await db.refresh(settings)
        return settings

    # ------------------------------------------------------------------
    # Calculations
    # ------------------------------------------------------------------

    @staticmethod
    async def calculate_totals(
        db: AsyncSession, application_id: uuid.UUID
    ) -> Dict[str, Any]:
        """Calculate full budget totals grouped by category.

        Returns a dict matching the BudgetCalculation schema:
        - categories: per-category subtotals
        - total_direct, total_indirect, grand_total
        - total_federal, total_match, match_gap
        """
        # Fetch all line items for this application
        stmt = (
            select(BudgetLineItem)
            .where(BudgetLineItem.application_id == application_id)
            .order_by(BudgetLineItem.sort_order, BudgetLineItem.created_at)
        )
        result = await db.execute(stmt)
        items = result.scalars().all()

        # Fetch settings
        settings = await BudgetService.get_or_create_settings(db, application_id)

        # Group items by category
        cat_items: Dict[str, List[BudgetLineItem]] = defaultdict(list)
        for item in items:
            cat_items[item.category].append(item)

        # Build per-category totals
        categories: List[Dict[str, Any]] = []
        total_direct = Decimal("0")
        total_indirect = Decimal("0")
        total_federal = Decimal("0")
        total_match = Decimal("0")
        personnel_subtotal = Decimal("0")

        for cat_name in CATEGORY_ORDER:
            cat_list = cat_items.get(cat_name, [])
            subtotal = sum((item.total_cost or Decimal("0")) for item in cat_list)
            federal = sum((item.federal_share or Decimal("0")) for item in cat_list)
            match = sum((item.match_share or Decimal("0")) for item in cat_list)

            categories.append(
                {
                    "category": cat_name,
                    "subtotal": _to_float(subtotal),
                    "federal": _to_float(federal),
                    "match": _to_float(match),
                    "item_count": len(cat_list),
                }
            )

            if cat_name == "indirect_costs":
                total_indirect += subtotal
            else:
                total_direct += subtotal

            if cat_name == "personnel":
                personnel_subtotal = subtotal

            total_federal += federal
            total_match += match

        # Auto-calculate fringe if no fringe line items exist
        fringe_rate = settings.fringe_rate or Decimal("0.35")
        fringe_items = cat_items.get("fringe_benefits", [])
        if not fringe_items and personnel_subtotal > 0:
            auto_fringe = (personnel_subtotal * fringe_rate).quantize(
                _TWO_PLACES, rounding=ROUND_HALF_UP
            )
            # Update the fringe category entry
            for cat in categories:
                if cat["category"] == "fringe_benefits":
                    cat["subtotal"] = _to_float(auto_fringe)
                    cat["federal"] = _to_float(auto_fringe)
                    break
            total_direct += auto_fringe
            total_federal += auto_fringe

        # Auto-calculate indirect costs if no indirect line items exist
        indirect_rate = settings.indirect_rate or Decimal("0.10")
        indirect_base_type = settings.indirect_base or "mtdc"
        indirect_items = cat_items.get("indirect_costs", [])

        if not indirect_items and total_direct > 0:
            if indirect_base_type == "mtdc":
                # MTDC approximation: total_direct * 0.85
                mtdc_base = (total_direct * Decimal("0.85")).quantize(
                    _TWO_PLACES, rounding=ROUND_HALF_UP
                )
                auto_indirect = (mtdc_base * indirect_rate).quantize(
                    _TWO_PLACES, rounding=ROUND_HALF_UP
                )
            elif indirect_base_type == "tdc":
                auto_indirect = (total_direct * indirect_rate).quantize(
                    _TWO_PLACES, rounding=ROUND_HALF_UP
                )
            elif indirect_base_type == "salary_wages":
                auto_indirect = (personnel_subtotal * indirect_rate).quantize(
                    _TWO_PLACES, rounding=ROUND_HALF_UP
                )
            else:
                auto_indirect = Decimal("0")

            # Update the indirect category entry
            for cat in categories:
                if cat["category"] == "indirect_costs":
                    cat["subtotal"] = _to_float(auto_indirect)
                    cat["federal"] = _to_float(auto_indirect)
                    break
            total_indirect = auto_indirect
            total_federal += auto_indirect

        grand_total = total_direct + total_indirect

        # Match gap
        match_gap = Decimal("0")
        if settings.match_required and settings.match_total_required:
            match_gap = (settings.match_total_required - total_match).quantize(
                _TWO_PLACES, rounding=ROUND_HALF_UP
            )
            if match_gap < 0:
                match_gap = Decimal("0")

        return {
            "categories": categories,
            "total_direct": _to_float(total_direct),
            "total_indirect": _to_float(total_indirect),
            "grand_total": _to_float(grand_total),
            "total_federal": _to_float(total_federal),
            "total_match": _to_float(total_match),
            "match_gap": _to_float(match_gap),
        }

    # ------------------------------------------------------------------
    # Pre-fill from wizard plan data
    # ------------------------------------------------------------------

    @staticmethod
    async def create_from_plan_data(
        db: AsyncSession,
        application_id: uuid.UUID,
        plan_data: Dict[str, Any],
    ) -> List[BudgetLineItem]:
        """Parse wizard plan_data and create budget line items + settings.

        Expects plan_data keys:
        - "staffing_plan": list of {role, fte, salary?, months?}
        - "budget": list of {category, description, amount, justification?}
        - "funding_range": {min?, max?}

        Returns the list of created BudgetLineItem objects.
        """
        created_items: List[BudgetLineItem] = []
        sort_idx = 0

        # -- Personnel from staffing_plan --
        staffing = plan_data.get("staffing_plan", [])
        if isinstance(staffing, list):
            for entry in staffing:
                if not isinstance(entry, dict):
                    continue
                role = entry.get("role", "Staff")
                fte = entry.get("fte", 1.0)
                salary = entry.get("salary", 75000)  # Default estimate
                months = entry.get("months", 12)
                total = (
                    Decimal(str(salary))
                    * Decimal(str(fte))
                    * (Decimal(str(months)) / Decimal("12"))
                )
                total = total.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)

                item = BudgetLineItem(
                    application_id=application_id,
                    category="personnel",
                    description=f"{role} ({fte} FTE, {months} months)",
                    role=str(role),
                    fte=_to_decimal(fte),
                    annual_salary=_to_decimal(salary),
                    months_on_project=_to_decimal(months),
                    total_cost=total,
                    federal_share=total,
                    sort_order=sort_idx,
                )
                db.add(item)
                created_items.append(item)
                sort_idx += 1

        # -- Categorized budget entries --
        budget_entries = plan_data.get("budget", [])
        if isinstance(budget_entries, list):
            for entry in budget_entries:
                if not isinstance(entry, dict):
                    continue
                category = entry.get("category", "other_direct")
                if category not in CATEGORY_ORDER:
                    category = "other_direct"

                amount = entry.get("amount", 0)
                total = _to_decimal(amount) or Decimal("0")

                item = BudgetLineItem(
                    application_id=application_id,
                    category=category,
                    description=entry.get(
                        "description", category.replace("_", " ").title()
                    ),
                    quantity=_to_decimal(entry.get("quantity", 1)),
                    unit_cost=_to_decimal(entry.get("unit_cost")),
                    total_cost=total,
                    federal_share=total,
                    justification=entry.get("justification"),
                    is_indirect=(category == "indirect_costs"),
                    sort_order=sort_idx,
                )
                db.add(item)
                created_items.append(item)
                sort_idx += 1

        # -- Budget settings from funding range --
        funding_range = plan_data.get("funding_range", {})
        if isinstance(funding_range, dict) and funding_range:
            settings = await BudgetService.get_or_create_settings(db, application_id)
            notes_parts: List[str] = []
            if "min" in funding_range:
                notes_parts.append(f"Funding min: ${funding_range['min']:,.0f}")
            if "max" in funding_range:
                notes_parts.append(f"Funding max: ${funding_range['max']:,.0f}")
            if notes_parts:
                settings.notes = "; ".join(notes_parts)

        await db.flush()
        for item in created_items:
            await db.refresh(item)

        return created_items

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    async def validate_budget(
        db: AsyncSession,
        application_id: uuid.UUID,
        grant_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run validation checks against the budget.

        Returns {valid: bool, issues: [{level, message, category?}]}.
        """
        issues: List[Dict[str, Any]] = []

        # Fetch items
        stmt = select(BudgetLineItem).where(
            BudgetLineItem.application_id == application_id
        )
        result = await db.execute(stmt)
        items = result.scalars().all()

        if not items:
            issues.append(
                {
                    "level": "error",
                    "message": "Budget has no line items",
                    "category": None,
                }
            )
            return {"valid": False, "issues": issues}

        # Check: total_cost > 0 for all items
        for item in items:
            if item.total_cost is None or item.total_cost <= 0:
                issues.append(
                    {
                        "level": "error",
                        "message": f"Line item '{item.description}' has invalid total cost",
                        "category": item.category,
                    }
                )

        # Calculate totals for further checks
        totals = await BudgetService.calculate_totals(db, application_id)
        grand_total = totals["grand_total"]

        # Check: budget total within grant funding range
        if grant_context:
            funding_range = grant_context.get("funding_range", {})
            if isinstance(funding_range, dict):
                min_amount = funding_range.get("min")
                max_amount = funding_range.get("max")
                if min_amount is not None and grand_total < float(min_amount):
                    issues.append(
                        {
                            "level": "warning",
                            "message": f"Budget total (${grand_total:,.2f}) is below the "
                            f"minimum funding amount (${float(min_amount):,.2f})",
                            "category": None,
                        }
                    )
                if max_amount is not None and grand_total > float(max_amount):
                    issues.append(
                        {
                            "level": "error",
                            "message": f"Budget total (${grand_total:,.2f}) exceeds the "
                            f"maximum funding amount (${float(max_amount):,.2f})",
                            "category": None,
                        }
                    )

        # Check: match requirement met
        settings = await BudgetService.get_or_create_settings(db, application_id)
        if settings.match_required and settings.match_total_required:
            match_gap = totals["match_gap"]
            if match_gap > 0:
                issues.append(
                    {
                        "level": "error",
                        "message": f"Match requirement not met. Gap: ${match_gap:,.2f}",
                        "category": None,
                    }
                )

        # Check: mandatory categories for federal grants
        present_categories = {item.category for item in items}
        federal_required = {"personnel", "fringe_benefits", "indirect_costs"}
        missing = federal_required - present_categories

        # Only check auto-calculated categories if there are no items AND no
        # personnel to derive them from
        has_personnel = "personnel" in present_categories
        if not has_personnel and "personnel" in missing:
            issues.append(
                {
                    "level": "warning",
                    "message": "No personnel costs included. Most federal grants "
                    "require a staffing plan.",
                    "category": "personnel",
                }
            )
        # Fringe and indirect are auto-calculated from personnel, so only warn
        # if personnel exists but these are explicitly missing with zero auto-calc
        if has_personnel:
            if "fringe_benefits" in missing and totals["categories"]:
                fringe_total = next(
                    (
                        c["subtotal"]
                        for c in totals["categories"]
                        if c["category"] == "fringe_benefits"
                    ),
                    0,
                )
                if fringe_total == 0:
                    issues.append(
                        {
                            "level": "warning",
                            "message": "No fringe benefits calculated. Verify fringe rate in settings.",
                            "category": "fringe_benefits",
                        }
                    )

        valid = not any(issue["level"] == "error" for issue in issues)
        return {"valid": valid, "issues": issues}

    # ------------------------------------------------------------------
    # CSV Export
    # ------------------------------------------------------------------

    @staticmethod
    async def export_csv(db: AsyncSession, application_id: uuid.UUID) -> str:
        """Generate a CSV string of the budget.

        Columns: Category, Description, Quantity, Unit Cost, Total, Federal Share,
        Match Share, Justification.  Includes subtotal rows per category and a
        grand total row at the bottom.
        """
        stmt = (
            select(BudgetLineItem)
            .where(BudgetLineItem.application_id == application_id)
            .order_by(BudgetLineItem.sort_order, BudgetLineItem.created_at)
        )
        result = await db.execute(stmt)
        items = result.scalars().all()

        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow(
            [
                "Category",
                "Description",
                "Quantity",
                "Unit Cost",
                "Total",
                "Federal Share",
                "Match Share",
                "Justification",
            ]
        )

        # Group items by category in standard order
        cat_items: Dict[str, List[BudgetLineItem]] = defaultdict(list)
        for item in items:
            cat_items[item.category].append(item)

        grand_total = Decimal("0")
        grand_federal = Decimal("0")
        grand_match = Decimal("0")

        for cat_name in CATEGORY_ORDER:
            cat_list = cat_items.get(cat_name, [])
            if not cat_list:
                continue

            cat_total = Decimal("0")
            cat_federal = Decimal("0")
            cat_match = Decimal("0")

            for item in cat_list:
                total = item.total_cost or Decimal("0")
                federal = item.federal_share or Decimal("0")
                match = item.match_share or Decimal("0")

                writer.writerow(
                    [
                        cat_name.replace("_", " ").title(),
                        item.description,
                        _to_float(item.quantity),
                        _to_float(item.unit_cost),
                        _to_float(total),
                        _to_float(federal),
                        _to_float(match),
                        item.justification or "",
                    ]
                )

                cat_total += total
                cat_federal += federal
                cat_match += match

            # Subtotal row
            writer.writerow(
                [
                    f"  Subtotal: {cat_name.replace('_', ' ').title()}",
                    "",
                    "",
                    "",
                    _to_float(cat_total),
                    _to_float(cat_federal),
                    _to_float(cat_match),
                    "",
                ]
            )

            grand_total += cat_total
            grand_federal += cat_federal
            grand_match += cat_match

        # Grand total row
        writer.writerow(
            [
                "GRAND TOTAL",
                "",
                "",
                "",
                _to_float(grand_total),
                _to_float(grand_federal),
                _to_float(grand_match),
                "",
            ]
        )

        return output.getvalue()
