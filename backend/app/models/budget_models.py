"""Pydantic request/response schemas for the Budget Builder feature."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BUDGET_CATEGORIES = (
    "personnel",
    "fringe_benefits",
    "travel",
    "equipment",
    "supplies",
    "contractual",
    "construction",
    "other_direct",
    "indirect_costs",
)

MATCH_TYPES = ("cash", "in_kind")

INDIRECT_BASES = ("mtdc", "tdc", "salary_wages")


# ---------------------------------------------------------------------------
# Line Item Schemas
# ---------------------------------------------------------------------------


class BudgetLineItemResponse(BaseModel):
    """Full representation of a budget line item returned from the API."""

    id: str
    application_id: str
    category: str
    description: str

    # Personnel-specific
    role: Optional[str] = None
    fte: Optional[float] = None
    annual_salary: Optional[float] = None
    months_on_project: Optional[float] = None

    # General
    quantity: Optional[float] = None
    unit_cost: Optional[float] = None
    total_cost: float
    justification: Optional[str] = None

    # Match / cost-share
    federal_share: Optional[float] = None
    match_share: Optional[float] = None
    match_type: Optional[str] = None

    # Metadata
    sort_order: int = 0
    is_indirect: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BudgetLineItemCreate(BaseModel):
    """Payload for creating a new budget line item."""

    category: str = Field(..., description="Budget category")
    description: str = Field(..., description="Line item description")

    # Personnel-specific (optional)
    role: Optional[str] = None
    fte: Optional[float] = None
    annual_salary: Optional[float] = None
    months_on_project: Optional[float] = None

    # General
    quantity: Optional[float] = None
    unit_cost: Optional[float] = None
    total_cost: float = Field(..., description="Total cost for this line item")

    justification: Optional[str] = None
    federal_share: Optional[float] = None
    match_share: Optional[float] = None
    match_type: Optional[str] = None

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        if v not in BUDGET_CATEGORIES:
            raise ValueError(
                f"Invalid category '{v}'. Must be one of: {', '.join(BUDGET_CATEGORIES)}"
            )
        return v

    @field_validator("match_type")
    @classmethod
    def validate_match_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in MATCH_TYPES:
            raise ValueError(
                f"Invalid match_type '{v}'. Must be one of: {', '.join(MATCH_TYPES)}"
            )
        return v


class BudgetLineItemUpdate(BaseModel):
    """Payload for updating an existing budget line item. All fields optional."""

    category: Optional[str] = None
    description: Optional[str] = None

    role: Optional[str] = None
    fte: Optional[float] = None
    annual_salary: Optional[float] = None
    months_on_project: Optional[float] = None

    quantity: Optional[float] = None
    unit_cost: Optional[float] = None
    total_cost: Optional[float] = None

    justification: Optional[str] = None
    federal_share: Optional[float] = None
    match_share: Optional[float] = None
    match_type: Optional[str] = None
    sort_order: Optional[int] = None
    is_indirect: Optional[bool] = None

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in BUDGET_CATEGORIES:
            raise ValueError(
                f"Invalid category '{v}'. Must be one of: {', '.join(BUDGET_CATEGORIES)}"
            )
        return v

    @field_validator("match_type")
    @classmethod
    def validate_match_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in MATCH_TYPES:
            raise ValueError(
                f"Invalid match_type '{v}'. Must be one of: {', '.join(MATCH_TYPES)}"
            )
        return v


# ---------------------------------------------------------------------------
# Settings Schemas
# ---------------------------------------------------------------------------


class BudgetSettingsResponse(BaseModel):
    """Full representation of budget settings returned from the API."""

    id: str
    application_id: str
    fringe_rate: Optional[float] = None
    indirect_rate: Optional[float] = None
    indirect_base: Optional[str] = None
    match_required: Optional[bool] = None
    match_percentage: Optional[float] = None
    match_total_required: Optional[float] = None
    fiscal_year_start: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BudgetSettingsUpdate(BaseModel):
    """Payload for updating budget settings. All fields optional."""

    fringe_rate: Optional[float] = None
    indirect_rate: Optional[float] = None
    indirect_base: Optional[str] = None
    match_required: Optional[bool] = None
    match_percentage: Optional[float] = None
    match_total_required: Optional[float] = None
    fiscal_year_start: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("indirect_base")
    @classmethod
    def validate_indirect_base(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in INDIRECT_BASES:
            raise ValueError(
                f"Invalid indirect_base '{v}'. Must be one of: {', '.join(INDIRECT_BASES)}"
            )
        return v


# ---------------------------------------------------------------------------
# Calculation & Summary Schemas
# ---------------------------------------------------------------------------


class BudgetCategoryTotals(BaseModel):
    """Subtotals for a single budget category."""

    category: str
    subtotal: float
    federal: float
    match: float
    item_count: int


class BudgetCalculation(BaseModel):
    """Full budget calculation result with category breakdowns and totals."""

    categories: List[BudgetCategoryTotals]
    total_direct: float
    total_indirect: float
    grand_total: float
    total_federal: float
    total_match: float
    match_gap: float = 0.0


class BudgetFullResponse(BaseModel):
    """Combined response: line items, settings, and calculated totals."""

    items: List[BudgetLineItemResponse]
    settings: BudgetSettingsResponse
    calculations: BudgetCalculation


# ---------------------------------------------------------------------------
# Validation Schemas
# ---------------------------------------------------------------------------


class BudgetValidationIssue(BaseModel):
    """A single validation issue (error or warning)."""

    level: str = Field(..., description="Severity: 'error' or 'warning'")
    message: str
    category: Optional[str] = None


class BudgetValidationResponse(BaseModel):
    """Result of budget validation."""

    valid: bool
    issues: List[BudgetValidationIssue]


# ---------------------------------------------------------------------------
# Prefill Request
# ---------------------------------------------------------------------------


class BudgetPrefillRequest(BaseModel):
    """Request body for pre-filling budget from wizard plan data."""

    plan_data: dict = Field(..., description="Plan data from the wizard session")
