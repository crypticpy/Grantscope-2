"""Grant-specific models for GrantScope API.

Models for departments, grant categories, and grant applications
supporting the grant discovery and management pipeline.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator


class Department(BaseModel):
    """City of Austin department."""

    id: str
    name: str
    abbreviation: str
    category_ids: List[str] = []
    is_active: bool = True
    created_at: Optional[datetime] = None


class GrantCategory(BaseModel):
    """Grant funding category."""

    id: str
    name: str
    description: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    created_at: Optional[datetime] = None


class GrantApplication(BaseModel):
    """A grant application tracking record."""

    id: str
    card_id: str
    workstream_id: str
    department_id: Optional[str] = None
    user_id: str
    status: str = "draft"
    proposal_content: Dict[str, Any] = {}
    awarded_amount: Optional[float] = None
    submitted_at: Optional[datetime] = None
    decision_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class GrantApplicationCreate(BaseModel):
    """Request model for creating a grant application."""

    card_id: str = Field(..., description="UUID of the grant opportunity card")
    workstream_id: str = Field(..., description="UUID of the program/workstream")
    department_id: Optional[str] = Field(None, description="Department abbreviation")
    notes: Optional[str] = Field(None, max_length=5000, description="Initial notes")

    @validator("card_id", "workstream_id")
    def validate_uuid_format(cls, v):
        import re

        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            re.IGNORECASE,
        )
        if not uuid_pattern.match(v):
            raise ValueError("Invalid UUID format")
        return v


class GrantApplicationUpdate(BaseModel):
    """Request model for updating a grant application."""

    status: Optional[str] = Field(None, description="Application status")
    proposal_content: Optional[Dict[str, Any]] = None
    awarded_amount: Optional[float] = None
    notes: Optional[str] = Field(None, max_length=5000)

    @validator("status")
    def validate_status(cls, v):
        valid = {
            "draft",
            "in_progress",
            "submitted",
            "awarded",
            "declined",
            "withdrawn",
        }
        if v and v not in valid:
            raise ValueError(
                f"Invalid status. Must be one of: {', '.join(sorted(valid))}"
            )
        return v
