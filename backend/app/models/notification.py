"""Notification models for GrantScope API.

Models for notification preferences, digest configuration,
and digest preview responses.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator


VALID_DIGEST_FREQUENCIES = {"daily", "weekly", "none"}
VALID_DIGEST_DAYS = {"monday", "tuesday", "wednesday", "thursday", "friday"}


class NotificationPreferencesResponse(BaseModel):
    """Response model for notification preferences."""

    id: str
    user_id: str
    notification_email: Optional[str] = None
    digest_frequency: str = "weekly"
    digest_day: str = "monday"
    include_new_signals: bool = True
    include_velocity_changes: bool = True
    include_pattern_insights: bool = True
    include_workstream_updates: bool = True
    last_digest_sent_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class NotificationPreferencesUpdate(BaseModel):
    """Request model for updating notification preferences."""

    notification_email: Optional[str] = Field(
        None,
        max_length=254,
        description="Email for digest delivery (NULL = use auth email)",
    )
    digest_frequency: Optional[str] = Field(
        None, description="Frequency: daily, weekly, or none"
    )
    digest_day: Optional[str] = Field(None, description="Day of week for weekly digest")
    include_new_signals: Optional[bool] = None
    include_velocity_changes: Optional[bool] = None
    include_pattern_insights: Optional[bool] = None
    include_workstream_updates: Optional[bool] = None

    @validator("digest_frequency")
    def validate_frequency(cls, v):
        if v is not None and v not in VALID_DIGEST_FREQUENCIES:
            raise ValueError(
                f"Invalid digest_frequency. Must be one of: "
                f"{', '.join(VALID_DIGEST_FREQUENCIES)}"
            )
        return v

    @validator("digest_day")
    def validate_day(cls, v):
        if v is not None and v not in VALID_DIGEST_DAYS:
            raise ValueError(
                f"Invalid digest_day. Must be one of: "
                f"{', '.join(VALID_DIGEST_DAYS)}"
            )
        return v

    @validator("notification_email")
    def validate_email_format(cls, v):
        if v is not None:
            import re

            email_pattern = re.compile(
                r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
            )
            if not email_pattern.match(v):
                raise ValueError("Invalid email format")
        return v


class DigestPreviewResponse(BaseModel):
    """Response model for digest preview."""

    subject: str
    html_content: str
    summary_json: Dict[str, Any]
    sections_included: List[str]
