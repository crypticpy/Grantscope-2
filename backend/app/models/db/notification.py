"""Notification ORM models.

Tables
------
- notification_preferences  (per-user email digest configuration)
- digest_logs               (generated digest content for audit/retry)
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db.base import Base

__all__ = ["NotificationPreference", "DigestLog"]


class NotificationPreference(Base):
    """Per-user email digest configuration."""

    __tablename__ = "notification_preferences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    notification_email: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    digest_frequency: Mapped[Optional[str]] = mapped_column(
        Text, server_default="weekly", nullable=True
    )
    digest_day: Mapped[Optional[str]] = mapped_column(
        Text, server_default="monday", nullable=True
    )
    include_new_signals: Mapped[Optional[bool]] = mapped_column(
        Boolean, server_default="true", nullable=True
    )
    include_velocity_changes: Mapped[Optional[bool]] = mapped_column(
        Boolean, server_default="true", nullable=True
    )
    include_pattern_insights: Mapped[Optional[bool]] = mapped_column(
        Boolean, server_default="true", nullable=True
    )
    include_workstream_updates: Mapped[Optional[bool]] = mapped_column(
        Boolean, server_default="true", nullable=True
    )
    last_digest_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )


class DigestLog(Base):
    """Audit log of generated digest emails."""

    __tablename__ = "digest_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    digest_type: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="weekly"
    )
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    html_content: Mapped[str] = mapped_column(Text, nullable=False)
    summary_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="generated"
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
