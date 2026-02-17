"""Supporting card-related ORM models.

Tables
------
- card_timeline          (events showing how cards evolve)
- card_follows           (users tracking specific cards)
- card_notes             (user comments on cards)
- card_score_history     (score snapshots for trend visualization)
- card_relationships     (relationships between cards)
- card_snapshots         (version history of card fields)
- entities               (extracted entities for knowledge graph)
- entity_relationships   (edges in the knowledge graph)
- implications_analyses  (implication analysis per card)
- implications           (hierarchical implications)
- user_signal_preferences (user pins / sort order for cards)
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
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.types import NullType
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db.base import Base

__all__ = [
    "CardTimeline",
    "CardFollow",
    "CardNote",
    "CardScoreHistory",
    "CardRelationship",
    "CardSnapshot",
    "Entity",
    "EntityRelationship",
    "ImplicationsAnalysis",
    "Implication",
    "UserSignalPreference",
]


# ═══════════════════════════════════════════════════════════════════════════
# card_timeline
# ═══════════════════════════════════════════════════════════════════════════


class CardTimeline(Base):
    """Events showing how cards evolve over time."""

    __tablename__ = "card_timeline"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    card_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSONB, server_default="{}", nullable=True
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    # Enhanced research additions (1766434901)
    triggered_by_source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    # 002_schema_fixes additions
    new_value: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    event_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    previous_value: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    triggered_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )


# ═══════════════════════════════════════════════════════════════════════════
# card_follows
# ═══════════════════════════════════════════════════════════════════════════


class CardFollow(Base):
    """Users tracking specific cards."""

    __tablename__ = "card_follows"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    card_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    priority: Mapped[Optional[str]] = mapped_column(
        Text, server_default="medium", nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 002_schema_fixes additions
    followed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    workstream_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )


# ═══════════════════════════════════════════════════════════════════════════
# card_notes
# ═══════════════════════════════════════════════════════════════════════════


class CardNote(Base):
    """User comments on cards."""

    __tablename__ = "card_notes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    card_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_private: Mapped[Optional[bool]] = mapped_column(
        Boolean, server_default="false", nullable=True
    )

    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )


# ═══════════════════════════════════════════════════════════════════════════
# card_score_history
# ═══════════════════════════════════════════════════════════════════════════


class CardScoreHistory(Base):
    """Historical score snapshots for cards (trend visualization)."""

    __tablename__ = "card_score_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    card_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Score snapshot
    maturity_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    velocity_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    novelty_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    impact_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    relevance_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    risk_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    opportunity_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )


# ═══════════════════════════════════════════════════════════════════════════
# card_relationships
# ═══════════════════════════════════════════════════════════════════════════


class CardRelationship(Base):
    """Relationships between cards for concept network visualization."""

    __tablename__ = "card_relationships"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    source_card_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    target_card_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    relationship_type: Mapped[str] = mapped_column(Text, nullable=False)
    strength: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 2), nullable=True)

    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )


# ═══════════════════════════════════════════════════════════════════════════
# card_snapshots
# ═══════════════════════════════════════════════════════════════════════════


class CardSnapshot(Base):
    """Version history of card description/summary fields."""

    __tablename__ = "card_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    card_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    field_name: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="description"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_length: Mapped[int] = mapped_column(Integer, nullable=False)
    # Column name is "trigger" in DB — a reserved word in Python but not SQL
    trigger: Mapped[str] = mapped_column("trigger", Text, nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    created_by: Mapped[Optional[str]] = mapped_column(
        Text, server_default="system", nullable=True
    )


# ═══════════════════════════════════════════════════════════════════════════
# entities
# ═══════════════════════════════════════════════════════════════════════════


class Entity(Base):
    """Extracted entities (technologies, orgs, concepts) for graph building."""

    __tablename__ = "entities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    card_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    canonical_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Embedding (vector)
    embedding = Column("embedding", NullType(), nullable=True)

    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )


# ═══════════════════════════════════════════════════════════════════════════
# entity_relationships
# ═══════════════════════════════════════════════════════════════════════════


class EntityRelationship(Base):
    """Relationships between entities for the knowledge graph."""

    __tablename__ = "entity_relationships"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    source_entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    target_entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    relationship_type: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2), server_default="0.7", nullable=True
    )
    context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )


# ═══════════════════════════════════════════════════════════════════════════
# implications_analyses
# ═══════════════════════════════════════════════════════════════════════════


class ImplicationsAnalysis(Base):
    """Implication analysis for a card from a specific perspective."""

    __tablename__ = "implications_analyses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    card_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    perspective: Mapped[str] = mapped_column(Text, nullable=False)
    perspective_detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )


# ═══════════════════════════════════════════════════════════════════════════
# implications
# ═══════════════════════════════════════════════════════════════════════════


class Implication(Base):
    """Hierarchical implications within an analysis."""

    __tablename__ = "implications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    analysis_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    order_level: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    likelihood_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    desirability_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    flag: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )


# ═══════════════════════════════════════════════════════════════════════════
# user_signal_preferences
# ═══════════════════════════════════════════════════════════════════════════


class UserSignalPreference(Base):
    """Per-user pin/sort order preferences for cards."""

    __tablename__ = "user_signal_preferences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    card_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    is_pinned: Mapped[Optional[bool]] = mapped_column(
        Boolean, server_default="false", nullable=True
    )
    custom_sort_order: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
