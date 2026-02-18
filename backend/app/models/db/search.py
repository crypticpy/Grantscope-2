"""Search-related ORM models.

Tables
------
- saved_searches   (user-saved search configurations)
- search_history   (record of executed searches)
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db.base import Base

__all__ = ["SavedSearch", "SearchHistory"]


# ═══════════════════════════════════════════════════════════════════════════
# saved_searches
# ═══════════════════════════════════════════════════════════════════════════


class SavedSearch(Base):
    """A user-saved search configuration that can be reused."""

    __tablename__ = "saved_searches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    query_config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )

    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )


# ═══════════════════════════════════════════════════════════════════════════
# search_history
# ═══════════════════════════════════════════════════════════════════════════


class SearchHistory(Base):
    """Record of an executed search query."""

    __tablename__ = "search_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    query_config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    executed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    result_count: Mapped[Optional[int]] = mapped_column(
        Integer, server_default="0", nullable=True
    )
