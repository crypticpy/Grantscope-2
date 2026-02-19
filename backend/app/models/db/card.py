"""Card ORM model -- the largest model in the system (~60+ columns).

The ``cards`` table is the atomic unit of strategic intelligence.  Columns
are accumulated from many migrations:

- 1766434534  : base creation (name, slug, scores, classification, status)
- 002_schema_fixes : triage_score, stage, follower_count, anchors[], pillars[],
                     goals[], steep_categories[], credibility/likelihood/novelty/
                     impact/relevance_score (NUMERIC overrides), source_count,
                     time_to_*_months, is_archived, top25_relevance TEXT[]
- 1766434750  : top25_relevance JSONB (overwrites TEXT[] from 002)
- 1766434900  : deep_research_at, deep_research_count_today, deep_research_reset_date
- 1766434901  : embedding VECTOR(1536)
- 1766435000  : review_status, discovered_at, discovery_run_id, ai_confidence,
                rejected_at, rejected_by, rejection_reason, discovery_metadata
- 1766435001  : reviewed_at, reviewed_by, review_notes, auto_approved_at
- 1766738200  : signal_quality_score
- 1766739003  : quality_score, quality_breakdown, origin, is_exploratory
- 1766739100  : source_preferences JSONB
- 1766739600  : velocity_trend, velocity_score (NUMERIC), velocity_updated_at
- 20260211    : search_vector (tsvector)
- 20260213000002 : profile_generated_at, profile_source_count, trend_direction
- 20260216000002 : grant_type, funding_amount_min/max, deadline, grantor,
                   cfda_number, grants_gov_id, sam_opportunity_id,
                   eligibility_text, match_requirement, category_id, source_url,
                   alignment_score, readiness_score, competition_score,
                   urgency_score, probability_score
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    Date,
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

__all__ = ["Card", "CardEmbedding"]


class Card(Base):
    __tablename__ = "cards"

    # ── Primary key ──────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    # ── Core identity ────────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Classification (FK to reference tables) ──────────────────────────
    pillar_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    goal_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    anchor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stage_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    horizon: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Pipeline lifecycle (20260220) ──────────────────────────────────
    pipeline_status: Mapped[Optional[str]] = mapped_column(
        Text, server_default="discovered", nullable=True
    )
    pipeline_status_changed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── AI-generated scores ──────────────────────────────────────────────
    # novelty/impact/relevance are NUMERIC(3,2) in prod DB (002_schema_fixes)
    novelty_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2), nullable=True
    )
    maturity_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    impact_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2), nullable=True
    )
    relevance_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2), nullable=True
    )
    velocity_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), server_default="0", nullable=True
    )
    risk_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    opportunity_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # ── Status / metadata ────────────────────────────────────────────────
    status: Mapped[Optional[str]] = mapped_column(
        Text, server_default="active", nullable=True
    )
    last_updated: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )

    # ── 002_schema_fixes extras ──────────────────────────────────────────
    triage_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    stage: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    follower_count: Mapped[Optional[int]] = mapped_column(
        Integer, server_default="0", nullable=True
    )
    anchors: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(Text), server_default="{}", nullable=True
    )
    time_to_prepare_months: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    credibility_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2), nullable=True
    )
    is_archived: Mapped[Optional[bool]] = mapped_column(
        Boolean, server_default="false", nullable=True
    )
    source_count: Mapped[Optional[int]] = mapped_column(
        Integer, server_default="0", nullable=True
    )
    time_to_awareness_months: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    pillars: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(Text), server_default="{}", nullable=True
    )
    steep_categories: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(Text), server_default="{}", nullable=True
    )
    goals: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(Text), server_default="{}", nullable=True
    )
    likelihood_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2), nullable=True
    )

    # top25_relevance — initially TEXT[] in 002, then overwritten as JSONB in 1766434750.
    # The JSONB migration wins (ADD COLUMN IF NOT EXISTS would skip if TEXT[] exists,
    # but the 002 migration also uses IF NOT EXISTS so order determines which lands).
    # We model it as JSONB per the later migration intent.
    top25_relevance: Mapped[Optional[dict]] = mapped_column(
        JSONB, server_default="'[]'::jsonb", nullable=True
    )

    # ── Research tracking (1766434900) ───────────────────────────────────
    deep_research_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deep_research_count_today: Mapped[Optional[int]] = mapped_column(
        Integer, server_default="0", nullable=True
    )
    deep_research_reset_date: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True
    )

    # ── Embedding (1766434901) ───────────────────────────────────────────
    # pgvector VECTOR(1536) — use old-style Column(NullType) because
    # SQLAlchemy 2.0 Mapped[] cannot resolve pgvector types.
    embedding = Column("embedding", NullType(), nullable=True)

    # ── Discovery workflow (1766435000) ──────────────────────────────────
    review_status: Mapped[Optional[str]] = mapped_column(
        Text, server_default="active", nullable=True
    )
    discovered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    discovery_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    ai_confidence: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2), nullable=True
    )
    rejected_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejected_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    discovery_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB, server_default="{}", nullable=True
    )

    # ── Discovery review additions (1766435001) ──────────────────────────
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    auto_approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Signal quality (1766738200) ──────────────────────────────────────
    signal_quality_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # ── Quality & origin (1766739003) ────────────────────────────────────
    quality_score: Mapped[Optional[int]] = mapped_column(
        Integer, server_default="0", nullable=True
    )
    quality_breakdown: Mapped[Optional[dict]] = mapped_column(
        JSONB, server_default="{}", nullable=True
    )
    origin: Mapped[Optional[str]] = mapped_column(
        Text, server_default="discovery", nullable=True
    )
    is_exploratory: Mapped[Optional[bool]] = mapped_column(
        Boolean, server_default="false", nullable=True
    )

    # ── Source preferences (1766739100) ──────────────────────────────────
    source_preferences: Mapped[Optional[dict]] = mapped_column(
        JSONB, server_default="{}", nullable=True
    )

    # ── Velocity trend (1766739600) ──────────────────────────────────────
    velocity_trend: Mapped[Optional[str]] = mapped_column(
        Text, server_default="stable", nullable=True
    )
    velocity_updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Hybrid search (20260211) ─────────────────────────────────────────
    # tsvector column — managed by DB trigger, use old-style Column
    search_vector = Column("search_vector", NullType(), nullable=True)

    # ── Profile tracking (20260213000002) ────────────────────────────────
    profile_generated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    profile_source_count: Mapped[Optional[int]] = mapped_column(
        Integer, server_default="0", nullable=True
    )
    trend_direction: Mapped[Optional[str]] = mapped_column(
        Text, server_default="unknown", nullable=True
    )

    # ── Grant columns (20260216000002) ───────────────────────────────────
    grant_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    funding_amount_min: Mapped[Optional[Decimal]] = mapped_column(
        Numeric, nullable=True
    )
    funding_amount_max: Mapped[Optional[Decimal]] = mapped_column(
        Numeric, nullable=True
    )
    deadline: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    grantor: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cfda_number: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    grants_gov_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sam_opportunity_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    eligibility_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    match_requirement: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Grant-specific AI scores (0-100)
    alignment_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    readiness_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    competition_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    urgency_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    probability_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


# ═══════════════════════════════════════════════════════════════════════════
# card_embeddings
# ═══════════════════════════════════════════════════════════════════════════


class CardEmbedding(Base):
    """Standalone embedding store for cards (separate from Card.embedding)."""

    __tablename__ = "card_embeddings"

    card_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    # pgvector VECTOR(1536) — use old-style Column(NullType) because
    # SQLAlchemy 2.0 Mapped[] cannot resolve pgvector types.
    embedding = Column("embedding", NullType(), nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
