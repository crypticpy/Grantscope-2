"""Research models for GrantScope API.

Models for research task creation, status tracking,
and related constants.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, validator


VALID_TASK_TYPES = {"update", "deep_research", "workstream_analysis"}


class ResearchTaskCreate(BaseModel):
    """Request model for creating a research task."""

    card_id: Optional[str] = Field(None, description="Card ID for card-based research")
    workstream_id: Optional[str] = Field(
        None, description="Workstream ID for workstream analysis"
    )
    task_type: str = Field(
        ..., description="One of: update, deep_research, workstream_analysis"
    )

    @validator("task_type")
    def task_type_must_be_valid(cls, v):
        if v not in VALID_TASK_TYPES:
            raise ValueError(
                f"Invalid task_type. Must be one of: {', '.join(VALID_TASK_TYPES)}"
            )
        return v

    @validator("card_id", "workstream_id")
    def validate_uuid_format(cls, v):
        if v is not None:
            import re

            uuid_pattern = re.compile(
                r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
                re.IGNORECASE,
            )
            if not uuid_pattern.match(v):
                raise ValueError("Invalid UUID format")
        return v


class ResearchTask(BaseModel):
    """Response model for research task status."""

    id: str
    user_id: str
    card_id: Optional[str] = None
    workstream_id: Optional[str] = None
    task_type: str
    status: str
    query: Optional[str] = None
    result_summary: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
