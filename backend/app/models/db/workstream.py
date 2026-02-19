"""Workstream-related ORM models.

Tables
------
- workstreams       (user-defined research streams)
- workstream_cards  (cards assigned to workstreams, with kanban status)
- workstream_scans  (targeted discovery scans scoped to a workstream)
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    Numeric,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db.base import Base

__all__ = ["Workstream", "WorkstreamCard", "WorkstreamScan"]


# ═══════════════════════════════════════════════════════════════════════════
# workstreams
# ═══════════════════════════════════════════════════════════════════════════


class Workstream(Base):
    """A user-defined research stream with filters and kanban tracking."""

    __tablename__ = "workstreams"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Original filter columns (from 1766434548)
    pillar_ids: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text), nullable=True)
    goal_ids: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text), nullable=True)
    stage_ids: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text), nullable=True)
    horizon: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    keywords: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(Text), server_default="{}", nullable=True
    )

    # Settings
    is_active: Mapped[Optional[bool]] = mapped_column(
        Boolean, server_default="true", nullable=True
    )
    auto_add: Mapped[Optional[bool]] = mapped_column(
        Boolean, server_default="false", nullable=True
    )

    # Schema fixes additions (002)
    horizons: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(Text), server_default="{}", nullable=True
    )
    min_stage: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_stage: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pipeline_statuses: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(Text), server_default="{}", nullable=True
    )
    notification_enabled: Mapped[Optional[bool]] = mapped_column(
        Boolean, server_default="true", nullable=True
    )
    anchors: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(Text), server_default="{}", nullable=True
    )
    is_default: Mapped[Optional[bool]] = mapped_column(
        Boolean, server_default="false", nullable=True
    )
    pillars: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(Text), server_default="{}", nullable=True
    )
    goals: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(Text), server_default="{}", nullable=True
    )

    # Auto scan (1766739300)
    auto_scan: Mapped[Optional[bool]] = mapped_column(
        Boolean, server_default="false", nullable=True
    )

    # Grant program columns (20260216000002)
    program_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    department_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    budget: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)
    fiscal_year: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    total_awarded: Mapped[Optional[Decimal]] = mapped_column(
        Numeric, server_default="0", nullable=True
    )
    total_pending: Mapped[Optional[Decimal]] = mapped_column(
        Numeric, server_default="0", nullable=True
    )
    category_ids: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(Text), server_default="{}", nullable=True
    )

    # Timestamps
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )


# ═══════════════════════════════════════════════════════════════════════════
# workstream_cards
# ═══════════════════════════════════════════════════════════════════════════


class WorkstreamCard(Base):
    """A card assigned to a workstream, with kanban position and metadata."""

    __tablename__ = "workstream_cards"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    workstream_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    card_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    added_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    added_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )

    # Kanban columns (1766437000)
    status: Mapped[Optional[str]] = mapped_column(
        Text, server_default="inbox", nullable=True
    )
    position: Mapped[Optional[int]] = mapped_column(
        Integer, server_default="0", nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reminder_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    added_from: Mapped[Optional[str]] = mapped_column(
        Text, server_default="manual", nullable=True
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )


# ═══════════════════════════════════════════════════════════════════════════
# workstream_scans
# ═══════════════════════════════════════════════════════════════════════════


class WorkstreamScan(Base):
    """Tracks workstream-specific targeted discovery scans."""

    __tablename__ = "workstream_scans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    workstream_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # Job status
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="queued")

    # Configuration snapshot
    config: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )

    # Results summary
    results: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Timestamps
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Error handling
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
