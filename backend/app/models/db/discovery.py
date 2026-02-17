"""Discovery-related ORM models.

Tables
------
- discovery_runs        (automated discovery scan sessions)
- discovery_blocks      (topics/domains to exclude from discovery)
- user_card_dismissals  (per-user card dismissals from discovery queue)
- discovery_schedule    (scheduled discovery run configuration)
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    Numeric,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.types import NullType
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db.base import Base

__all__ = [
    "DiscoveryRun",
    "DiscoveryBlock",
    "UserCardDismissal",
    "DiscoverySchedule",
]


# ═══════════════════════════════════════════════════════════════════════════
# discovery_runs
# ═══════════════════════════════════════════════════════════════════════════


class DiscoveryRun(Base):
    """Tracks automated discovery scan sessions."""

    __tablename__ = "discovery_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    # Timing
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Status
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="running")

    # Scope
    pillars_scanned: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(Text), server_default="{}", nullable=True
    )
    priorities_scanned: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(Text), server_default="{}", nullable=True
    )

    # Metrics
    queries_generated: Mapped[Optional[int]] = mapped_column(
        Integer, server_default="0", nullable=True
    )
    sources_found: Mapped[Optional[int]] = mapped_column(
        Integer, server_default="0", nullable=True
    )
    sources_relevant: Mapped[Optional[int]] = mapped_column(
        Integer, server_default="0", nullable=True
    )
    cards_created: Mapped[Optional[int]] = mapped_column(
        Integer, server_default="0", nullable=True
    )
    cards_enriched: Mapped[Optional[int]] = mapped_column(
        Integer, server_default="0", nullable=True
    )
    cards_deduplicated: Mapped[Optional[int]] = mapped_column(
        Integer, server_default="0", nullable=True
    )

    # Cost tracking
    estimated_cost: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 4), server_default="0", nullable=True
    )

    # Error handling
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Summary
    summary_report: Mapped[Optional[dict]] = mapped_column(
        JSONB, server_default="{}", nullable=True
    )

    # Trigger context
    triggered_by: Mapped[Optional[str]] = mapped_column(
        Text, server_default="scheduled", nullable=True
    )
    triggered_by_user: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    # Quality stats (1766739005)
    quality_stats: Mapped[Optional[dict]] = mapped_column(
        JSONB, server_default="{}", nullable=True
    )

    # Signal agent stats (20260213000004)
    signal_agent_stats: Mapped[Optional[dict]] = mapped_column(
        JSONB, server_default="{}", nullable=True
    )

    # Metadata
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )


# ═══════════════════════════════════════════════════════════════════════════
# discovery_blocks
# ═══════════════════════════════════════════════════════════════════════════


class DiscoveryBlock(Base):
    """Topics, domains, or keywords to exclude from discovery scans."""

    __tablename__ = "discovery_blocks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    # Topic identification
    topic_name: Mapped[str] = mapped_column(Text, nullable=False)
    # topic_embedding: VECTOR(1536) -- managed by pgvector, use old-style Column
    topic_embedding = Column("topic_embedding", NullType(), nullable=True)
    keywords: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(Text), server_default="{}", nullable=True
    )

    # Usage tracking
    blocked_by_count: Mapped[Optional[int]] = mapped_column(
        Integer, server_default="1", nullable=True
    )
    first_blocked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    last_blocked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )

    # Context
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    example_sources: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(Text), nullable=True
    )

    # Status
    is_active: Mapped[Optional[bool]] = mapped_column(
        Boolean, server_default="true", nullable=True
    )

    # Categorization
    block_type: Mapped[Optional[str]] = mapped_column(
        Text, server_default="topic", nullable=True
    )

    # Timestamps
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )


# ═══════════════════════════════════════════════════════════════════════════
# user_card_dismissals
# ═══════════════════════════════════════════════════════════════════════════


class UserCardDismissal(Base):
    """Tracks when users dismiss cards from their discovery queue."""

    __tablename__ = "user_card_dismissals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    # References
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    card_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # Dismissal context
    dismissed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dismiss_type: Mapped[Optional[str]] = mapped_column(
        Text, server_default="not_relevant", nullable=True
    )

    # Feedback
    feedback_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suggest_block_topic: Mapped[Optional[bool]] = mapped_column(
        Boolean, server_default="false", nullable=True
    )

    # Metadata
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )


# ═══════════════════════════════════════════════════════════════════════════
# discovery_schedule
# ═══════════════════════════════════════════════════════════════════════════


class DiscoverySchedule(Base):
    """Configuration for scheduled discovery runs."""

    __tablename__ = "discovery_schedule"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(Text, nullable=False, server_default="default")
    enabled: Mapped[Optional[bool]] = mapped_column(
        Boolean, server_default="true", nullable=True
    )
    cron_expression: Mapped[Optional[str]] = mapped_column(
        Text, server_default="0 6 * * *", nullable=True
    )
    timezone: Mapped[Optional[str]] = mapped_column(
        Text, server_default="America/Chicago", nullable=True
    )
    interval_hours: Mapped[Optional[int]] = mapped_column(
        Integer, server_default="24", nullable=True
    )
    max_search_queries_per_run: Mapped[Optional[int]] = mapped_column(
        Integer, server_default="20", nullable=True
    )
    pillars_to_scan: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(Text), nullable=True
    )
    process_rss_first: Mapped[Optional[bool]] = mapped_column(
        Boolean, server_default="true", nullable=True
    )
    last_run_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_run_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_run_status: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_run_summary: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
