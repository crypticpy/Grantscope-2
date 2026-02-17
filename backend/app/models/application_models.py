"""Pydantic request/response schemas for the Application Tracking feature."""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ApplicationResponse(BaseModel):
    """Full grant application response (mirrors all DB columns)."""

    id: str
    card_id: str
    workstream_id: str
    department_id: Optional[str] = None
    user_id: str
    status: Optional[str] = "draft"
    proposal_content: Optional[dict] = None
    awarded_amount: Optional[float] = None
    submitted_at: Optional[datetime] = None
    decision_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ApplicationWithDetails(ApplicationResponse):
    """Application response enriched with card details and milestone progress."""

    card_title: Optional[str] = None
    grantor_name: Optional[str] = None
    funding_amount_max: Optional[float] = None
    deadline: Optional[str] = None
    milestone_count: int = 0
    completed_milestones: int = 0
    progress_pct: float = 0.0


class ApplicationListResponse(BaseModel):
    """Paginated list of applications with total count."""

    applications: List[ApplicationWithDetails]
    total: int


class ApplicationUpdate(BaseModel):
    """Request body for updating application fields. All fields optional."""

    status: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=10000)
    awarded_amount: Optional[float] = None
    submitted_at: Optional[datetime] = None
    decision_at: Optional[datetime] = None


class StatusUpdateRequest(BaseModel):
    """Request body for updating application status with a reason."""

    new_status: str = Field(..., description="Target status value")
    reason: Optional[str] = Field(
        None, max_length=2000, description="Reason for status change"
    )


class DashboardStats(BaseModel):
    """Aggregated statistics for the application dashboard."""

    total_applications: int = 0
    by_status: Dict[str, int] = Field(default_factory=dict)
    total_pipeline_value: float = 0.0
    submitted_count: int = 0
    awarded_count: int = 0
    upcoming_deadlines: int = 0


class DashboardResponse(BaseModel):
    """Dashboard response with stats and recent applications."""

    stats: DashboardStats
    recent_applications: List[ApplicationWithDetails]


class MilestoneResponse(BaseModel):
    """Full milestone response (mirrors all DB columns)."""

    id: str
    application_id: str
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    is_completed: bool = False
    completed_at: Optional[datetime] = None
    milestone_type: str = "custom"
    reminder_sent: Optional[bool] = False
    sort_order: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MilestoneCreate(BaseModel):
    """Request body for creating a milestone."""

    title: str = Field(..., min_length=1, max_length=500, description="Milestone title")
    description: Optional[str] = Field(
        None, max_length=5000, description="Milestone description"
    )
    due_date: Optional[datetime] = Field(None, description="Due date for the milestone")
    milestone_type: str = Field(
        "custom",
        description="Type: deadline, loi, draft_review, internal_review, submission, reporting, custom",
    )


class MilestoneUpdate(BaseModel):
    """Request body for updating a milestone. All fields optional."""

    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = Field(None, max_length=5000)
    due_date: Optional[datetime] = None
    is_completed: Optional[bool] = None


class StatusHistoryResponse(BaseModel):
    """Status change history entry."""

    id: str
    application_id: str
    old_status: Optional[str] = None
    new_status: str
    changed_by: str
    reason: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
