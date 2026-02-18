"""User ORM model.

Maps to the ``users`` table created in ``1766434534_create_users_and_cards.sql``
with additional columns from ``20260216000002_grant_schema.sql``
(department_id, title).
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import ARRAY, DateTime, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db.base import Base

__all__ = ["User"]


class User(Base):
    __tablename__ = "users"

    # Primary key  (Supabase FK to auth.users is not modelled in SQLAlchemy)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)

    # Core fields
    email: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    department: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    role: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    preferences: Mapped[Optional[dict]] = mapped_column(
        JSONB, server_default="{}", nullable=True
    )

    # Grant schema additions (20260216000002)
    department_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Profile wizard fields
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    program_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    program_mission: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    team_size: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    budget_range: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    grant_experience: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    grant_categories: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(Text), server_default="{}", nullable=True
    )
    funding_range_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    funding_range_max: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    strategic_pillars: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(Text), server_default="{}", nullable=True
    )
    priorities: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(Text), server_default="{}", nullable=True
    )
    custom_priorities: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    help_wanted: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(Text), server_default="{}", nullable=True
    )
    update_frequency: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    profile_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    profile_step: Mapped[Optional[int]] = mapped_column(
        Integer, server_default="0", nullable=True
    )

    # Timestamps
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
