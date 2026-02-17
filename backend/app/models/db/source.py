"""Source-related ORM models.

Tables
------
- sources             (articles / information that inform cards)
- discovered_sources  (every source found during discovery runs)
- signal_sources      (many-to-many junction: cards <-> sources)
- source_ratings      (per-user quality & relevance ratings)
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
    Float,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.types import NullType
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db.base import Base

__all__ = ["Source", "DiscoveredSource", "SignalSource", "SourceRating"]


# ═══════════════════════════════════════════════════════════════════════════
# sources
# ═══════════════════════════════════════════════════════════════════════════


class Source(Base):
    """An article, report, paper, or news item that informs a card."""

    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    card_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    # Core fields
    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Source metadata
    source_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    author: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    publisher: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    fetched_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )

    # AI analysis
    relevance_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2), nullable=True
    )

    # Enhanced research columns (1766434901)
    publication: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    full_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    key_excerpts: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(Text), server_default="{}", nullable=True
    )
    relevance_to_card: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2), nullable=True
    )
    api_source: Mapped[Optional[str]] = mapped_column(
        Text, server_default="manual", nullable=True
    )
    ingested_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )

    # Embedding (vector)
    embedding = Column("embedding", NullType(), nullable=True)

    # Quality fields (1766739004)
    is_peer_reviewed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    story_cluster_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    domain_reputation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    # Source quality & dedup (20260213000005)
    quality_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    domain: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duplicate_of: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    # Hybrid search (20260211)
    search_vector = Column("search_vector", NullType(), nullable=True)

    # Timestamp
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )


# ═══════════════════════════════════════════════════════════════════════════
# discovered_sources
# ═══════════════════════════════════════════════════════════════════════════


class DiscoveredSource(Base):
    """Persistent storage for every source found during discovery runs."""

    __tablename__ = "discovered_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    discovery_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )

    # Raw source data
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_snippet: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    full_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    source_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    domain: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Search context
    search_query: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    query_pillar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    query_priority: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Triage results
    triage_is_relevant: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    triage_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    triage_primary_pillar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    triage_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    triaged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Full analysis results
    analysis_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    analysis_key_excerpts: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(Text), nullable=True
    )
    analysis_pillars: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(Text), nullable=True
    )
    analysis_goals: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(Text), nullable=True
    )
    analysis_steep_categories: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(Text), nullable=True
    )
    analysis_anchors: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(Text), nullable=True
    )
    analysis_horizon: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    analysis_suggested_stage: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    analysis_triage_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    analysis_credibility: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    analysis_novelty: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    analysis_likelihood: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    analysis_impact: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    analysis_relevance: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    analysis_time_to_awareness_months: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    analysis_time_to_prepare_months: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    analysis_suggested_card_name: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    analysis_is_new_concept: Mapped[Optional[bool]] = mapped_column(
        Boolean, nullable=True
    )
    analysis_reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    analysis_entities: Mapped[Optional[dict]] = mapped_column(
        JSONB, server_default="'[]'", nullable=True
    )
    analyzed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Deduplication results
    dedup_status: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dedup_matched_card_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    dedup_similarity_score: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    deduplicated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Final outcome
    processing_status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="discovered"
    )
    resulting_card_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    resulting_source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_stage: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Embedding (vector)
    content_embedding = Column("content_embedding", NullType(), nullable=True)

    # Timestamps
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )


# ═══════════════════════════════════════════════════════════════════════════
# signal_sources  (many-to-many junction)
# ═══════════════════════════════════════════════════════════════════════════


class SignalSource(Base):
    """Junction table linking cards to sources with relationship metadata."""

    __tablename__ = "signal_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    card_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    relationship_type: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="primary"
    )
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    agent_reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    created_by: Mapped[Optional[str]] = mapped_column(
        Text, server_default="signal_agent", nullable=True
    )


# ═══════════════════════════════════════════════════════════════════════════
# source_ratings
# ═══════════════════════════════════════════════════════════════════════════


class SourceRating(Base):
    """Per-user quality and relevance ratings on individual sources."""

    __tablename__ = "source_ratings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    quality_rating: Mapped[int] = mapped_column(Integer, nullable=False)
    relevance_rating: Mapped[str] = mapped_column(Text, nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
