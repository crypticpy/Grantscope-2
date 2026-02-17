"""WizardSession ORM model.

Maps to the ``wizard_sessions`` table from migration
``20260216100001_wizard_sessions.sql``.  Guided grant application wizard
sessions tracking progress through AI-powered interviews.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db.base import Base

__all__ = ["WizardSession"]


class WizardSession(Base):
    __tablename__ = "wizard_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    # References
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    proposal_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    card_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    # Wizard state
    entry_path: Mapped[str] = mapped_column(Text, nullable=False)
    current_step: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="in_progress"
    )

    # Structured data collected during wizard
    grant_context: Mapped[Optional[dict]] = mapped_column(
        JSONB, server_default="{}", nullable=True
    )
    interview_data: Mapped[Optional[dict]] = mapped_column(
        JSONB, server_default="{}", nullable=True
    )
    plan_data: Mapped[Optional[dict]] = mapped_column(
        JSONB, server_default="{}", nullable=True
    )

    # Timestamps
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
