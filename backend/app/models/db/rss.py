"""RSS feed monitoring ORM models.

Tables
------
- rss_feeds       (feed subscriptions)
- rss_feed_items  (individual articles from feeds)
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db.base import Base

__all__ = ["RssFeed", "RssFeedItem"]


class RssFeed(Base):
    """An RSS feed subscription for monitoring."""

    __tablename__ = "rss_feeds"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(
        Text, server_default="general", nullable=True
    )
    pillar_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    check_interval_hours: Mapped[Optional[int]] = mapped_column(
        Integer, server_default="6", nullable=True
    )
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_check_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    status: Mapped[Optional[str]] = mapped_column(
        Text, server_default="active", nullable=True
    )
    error_count: Mapped[Optional[int]] = mapped_column(
        Integer, server_default="0", nullable=True
    )
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    feed_title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    feed_link: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    articles_found_total: Mapped[Optional[int]] = mapped_column(
        Integer, server_default="0", nullable=True
    )
    articles_matched_total: Mapped[Optional[int]] = mapped_column(
        Integer, server_default="0", nullable=True
    )
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSONB, server_default="{}", nullable=True
    )

    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )


class RssFeedItem(Base):
    """An individual article from an RSS feed."""

    __tablename__ = "rss_feed_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    feed_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    author: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    content_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processed: Mapped[Optional[bool]] = mapped_column(
        Boolean, server_default="false", nullable=True
    )
    triage_result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    card_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSONB, server_default="{}", nullable=True
    )

    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
