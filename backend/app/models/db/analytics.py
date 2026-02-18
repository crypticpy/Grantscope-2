"""Analytics and caching ORM models.

Tables
------
- cached_insights    (TTL-based cache for AI-generated insights)
- domain_reputation  (credibility tiers and reputation for source domains)
- pattern_insights   (AI-detected cross-signal patterns)
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    Computed,
    Date,
    DateTime,
    Float,
    Integer,
    Numeric,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db.base import Base

__all__ = [
    "CachedInsight",
    "ClassificationValidation",
    "DomainReputation",
    "PatternInsight",
]


# ═══════════════════════════════════════════════════════════════════════════
# cached_insights
# ═══════════════════════════════════════════════════════════════════════════


class CachedInsight(Base):
    """TTL-based cache for AI-generated strategic insights."""

    __tablename__ = "cached_insights"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    # Cache key components
    pillar_filter: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    insight_limit: Mapped[Optional[int]] = mapped_column(
        Integer, server_default="5", nullable=True
    )
    cache_date: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=func.current_date()
    )

    # Cached content
    insights_json: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Cache validation metadata
    top_card_ids: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    card_data_hash: Mapped[str] = mapped_column(Text, nullable=False)

    # AI generation metadata
    ai_model_used: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    generation_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Timestamps
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


# ═══════════════════════════════════════════════════════════════════════════
# domain_reputation
# ═══════════════════════════════════════════════════════════════════════════


class DomainReputation(Base):
    """Credibility tiers and aggregated reputation for source domains."""

    __tablename__ = "domain_reputation"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    domain_pattern: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    organization_name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)

    curated_tier: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Aggregated user ratings
    user_quality_avg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2), server_default="0", nullable=True
    )
    user_relevance_avg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2), server_default="0", nullable=True
    )
    user_rating_count: Mapped[Optional[int]] = mapped_column(
        Integer, server_default="0", nullable=True
    )

    # Triage statistics
    triage_pass_rate: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 4), server_default="0", nullable=True
    )
    triage_total_count: Mapped[Optional[int]] = mapped_column(
        Integer, server_default="0", nullable=True
    )
    triage_pass_count: Mapped[Optional[int]] = mapped_column(
        Integer, server_default="0", nullable=True
    )

    # Composite score
    composite_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), server_default="0", nullable=True
    )
    texas_relevance_bonus: Mapped[Optional[int]] = mapped_column(
        Integer, server_default="0", nullable=True
    )

    # Status
    is_active: Mapped[Optional[bool]] = mapped_column(
        Boolean, server_default="true", nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )


# ═══════════════════════════════════════════════════════════════════════════
# pattern_insights
# ═══════════════════════════════════════════════════════════════════════════


class PatternInsight(Base):
    """AI-detected cross-signal patterns across strategic pillars."""

    __tablename__ = "pattern_insights"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    pattern_title: Mapped[str] = mapped_column(Text, nullable=False)
    pattern_summary: Mapped[str] = mapped_column(Text, nullable=False)
    opportunity: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2), server_default="0.5", nullable=True
    )
    affected_pillars: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(Text), server_default="{}", nullable=True
    )
    urgency: Mapped[Optional[str]] = mapped_column(
        Text, server_default="medium", nullable=True
    )
    related_card_ids: Mapped[Optional[list[uuid.UUID]]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), server_default="{}", nullable=True
    )
    status: Mapped[Optional[str]] = mapped_column(
        Text, server_default="active", nullable=True
    )

    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


# ═══════════════════════════════════════════════════════════════════════════
# classification_validations
# ═══════════════════════════════════════════════════════════════════════════


class ClassificationValidation(Base):
    """Human-verified classification validation for AI-predicted pillars."""

    __tablename__ = "classification_validations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    card_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    predicted_pillar: Mapped[str] = mapped_column(Text, nullable=False)
    ground_truth_pillar: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        Computed("predicted_pillar = ground_truth_pillar", persisted=True),
    )
    reviewer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence_at_prediction: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
