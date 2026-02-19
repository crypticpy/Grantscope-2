"""RSS feed management admin endpoints.

CRUD operations on RSS feed subscriptions, trigger immediate checks, and
view recent feed items.
"""

import logging
from datetime import datetime, timedelta, timezone
import ipaddress
from typing import Literal, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, HttpUrl, field_validator

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update as sa_update, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.admin_deps import require_admin
from app.deps import get_db, _safe_error
from app.models.db.rss import RssFeed, RssFeedItem
from app.routers.admin._helpers import _row_to_dict

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


class RssFeedCreate(BaseModel):
    """Request body for adding a new RSS feed."""

    url: HttpUrl
    name: str
    category: Optional[str] = "general"
    pillar_id: Optional[str] = None
    check_interval_hours: Optional[int] = 6

    @field_validator("url")
    @classmethod
    def validate_url_scheme_and_host(cls, v: HttpUrl) -> HttpUrl:
        url_str = str(v)
        parsed = urlparse(url_str)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("Only http and https URLs are allowed")
        hostname = parsed.hostname or ""
        try:
            addr = ipaddress.ip_address(hostname)
            for network in _BLOCKED_NETWORKS:
                if addr in network:
                    raise ValueError(
                        "URLs pointing to private/loopback IP ranges are not allowed"
                    )
        except ValueError as exc:
            # If it's our own raised ValueError, re-raise
            if "not allowed" in str(exc):
                raise
            # Otherwise hostname is a domain name, not an IP -- that's fine
        return v


class RssFeedUpdate(BaseModel):
    """Request body for updating an RSS feed."""

    name: Optional[str] = None
    category: Optional[str] = None
    pillar_id: Optional[str] = None
    check_interval_hours: Optional[int] = None
    status: Optional[Literal["active", "paused", "error"]] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _feed_to_dict(feed: RssFeed) -> dict:
    """Convert an RssFeed ORM object to a JSON-safe dict."""
    return {
        "id": str(feed.id),
        "url": feed.url,
        "name": feed.name,
        "category": feed.category,
        "pillar_id": feed.pillar_id,
        "check_interval_hours": feed.check_interval_hours,
        "status": feed.status,
        "last_checked_at": (
            feed.last_checked_at.isoformat() if feed.last_checked_at else None
        ),
        "next_check_at": (
            feed.next_check_at.isoformat() if feed.next_check_at else None
        ),
        "error_count": feed.error_count or 0,
        "last_error": feed.last_error,
        "feed_title": feed.feed_title,
        "feed_link": feed.feed_link,
        "articles_found_total": feed.articles_found_total or 0,
        "articles_matched_total": feed.articles_matched_total or 0,
        "created_at": feed.created_at.isoformat() if feed.created_at else None,
        "updated_at": feed.updated_at.isoformat() if feed.updated_at else None,
    }


def _item_to_dict(item: RssFeedItem) -> dict:
    """Convert an RssFeedItem ORM object to a JSON-safe dict."""
    return {
        "id": str(item.id),
        "feed_id": str(item.feed_id),
        "url": item.url,
        "title": item.title,
        "content": (item.content[:500] if item.content else None),
        "author": item.author,
        "published_at": (item.published_at.isoformat() if item.published_at else None),
        "processed": item.processed,
        "triage_result": item.triage_result,
        "card_id": str(item.card_id) if item.card_id else None,
        "source_id": str(item.source_id) if item.source_id else None,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


# ---------------------------------------------------------------------------
# GET /admin/rss/feeds
# ---------------------------------------------------------------------------


@router.get("/admin/rss/feeds")
async def list_feeds(
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(require_admin),
    status_filter: Optional[str] = Query(None, alias="status"),
):
    """List all RSS feeds with status info and recent item counts."""
    try:
        query = select(RssFeed).order_by(RssFeed.name)
        if status_filter:
            query = query.where(RssFeed.status == status_filter)

        result = await db.execute(query)
        feeds = result.scalars().all()

        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
        enriched = []

        for feed in feeds:
            feed_dict = _feed_to_dict(feed)

            # Count recent items for this feed
            try:
                count_result = await db.execute(
                    select(func.count(RssFeedItem.id))
                    .where(RssFeedItem.feed_id == feed.id)
                    .where(RssFeedItem.created_at >= seven_days_ago)
                )
                feed_dict["recent_items_7d"] = count_result.scalar() or 0
            except Exception:
                feed_dict["recent_items_7d"] = 0

            enriched.append(feed_dict)

        return {"feeds": enriched, "total": len(enriched)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to list RSS feeds: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("RSS feed listing", e),
        ) from e


# ---------------------------------------------------------------------------
# POST /admin/rss/feeds
# ---------------------------------------------------------------------------


@router.post("/admin/rss/feeds", status_code=status.HTTP_201_CREATED)
async def create_feed(
    body: RssFeedCreate,
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(require_admin),
):
    """Add a new RSS feed subscription.

    The feed will be scheduled for its first check immediately.
    """
    try:
        # Check for duplicate URL
        url_str = str(body.url)
        existing = await db.execute(select(RssFeed).where(RssFeed.url == url_str))
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A feed with URL '{url_str}' already exists",
            )

        interval = max(1, min(168, body.check_interval_hours or 6))
        feed_obj = RssFeed(
            url=url_str,
            name=body.name,
            category=body.category or "general",
            pillar_id=body.pillar_id,
            check_interval_hours=interval,
            next_check_at=datetime.now(timezone.utc),
        )
        db.add(feed_obj)
        await db.flush()
        await db.refresh(feed_obj)
        await db.commit()

        return _feed_to_dict(feed_obj)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create RSS feed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("RSS feed creation", e),
        ) from e


# ---------------------------------------------------------------------------
# PATCH /admin/rss/feeds/{feed_id}
# ---------------------------------------------------------------------------


@router.patch("/admin/rss/feeds/{feed_id}")
async def update_feed(
    feed_id: str,
    body: RssFeedUpdate,
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(require_admin),
):
    """Update RSS feed properties (name, category, status, check interval)."""
    try:
        result = await db.execute(select(RssFeed).where(RssFeed.id == feed_id))
        feed = result.scalar_one_or_none()
        if not feed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feed {feed_id} not found",
            )

        update_data = body.model_dump(exclude_none=True)
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No fields to update",
            )

        # Clamp interval
        if "check_interval_hours" in update_data:
            update_data["check_interval_hours"] = max(
                1, min(168, update_data["check_interval_hours"])
            )

        update_data["updated_at"] = datetime.now(timezone.utc)

        await db.execute(
            sa_update(RssFeed).where(RssFeed.id == feed_id).values(**update_data)
        )
        await db.commit()

        # Refresh and return
        result = await db.execute(select(RssFeed).where(RssFeed.id == feed_id))
        feed = result.scalar_one_or_none()
        return _feed_to_dict(feed)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update RSS feed %s: %s", feed_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("RSS feed update", e),
        ) from e


# ---------------------------------------------------------------------------
# DELETE /admin/rss/feeds/{feed_id}
# ---------------------------------------------------------------------------


@router.delete("/admin/rss/feeds/{feed_id}")
async def delete_feed(
    feed_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(require_admin),
):
    """Remove an RSS feed and its items."""
    try:
        result = await db.execute(select(RssFeed).where(RssFeed.id == feed_id))
        feed = result.scalar_one_or_none()
        if not feed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feed {feed_id} not found",
            )

        # Delete items first (if no cascade configured)
        await db.execute(sa_delete(RssFeedItem).where(RssFeedItem.feed_id == feed_id))
        await db.execute(sa_delete(RssFeed).where(RssFeed.id == feed_id))
        await db.commit()

        return {"deleted": True, "feed_id": feed_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete RSS feed %s: %s", feed_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("RSS feed deletion", e),
        ) from e


# ---------------------------------------------------------------------------
# POST /admin/rss/feeds/{feed_id}/check-now
# ---------------------------------------------------------------------------


@router.post("/admin/rss/feeds/{feed_id}/check-now")
async def check_feed_now(
    feed_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(require_admin),
):
    """Trigger an immediate check on a specific RSS feed.

    Sets ``next_check_at`` to now so the worker picks it up on the next cycle,
    and resets the feed status to ``active`` if it was in error state.
    """
    try:
        result = await db.execute(select(RssFeed).where(RssFeed.id == feed_id))
        feed = result.scalar_one_or_none()
        if not feed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feed {feed_id} not found",
            )

        now = datetime.now(timezone.utc)
        update_values = {
            "next_check_at": now,
            "updated_at": now,
        }
        # Reset error status so feed will be picked up
        if feed.status == "error":
            update_values["status"] = "active"
            update_values["error_count"] = 0

        await db.execute(
            sa_update(RssFeed).where(RssFeed.id == feed_id).values(**update_values)
        )
        await db.commit()

        # Refresh and return
        result = await db.execute(select(RssFeed).where(RssFeed.id == feed_id))
        feed = result.scalar_one_or_none()

        return {
            "message": "Feed scheduled for immediate check",
            "feed": _feed_to_dict(feed),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to trigger check on RSS feed %s: %s", feed_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("RSS feed check trigger", e),
        ) from e


# ---------------------------------------------------------------------------
# GET /admin/rss/feeds/{feed_id}/items
# ---------------------------------------------------------------------------


@router.get("/admin/rss/feeds/{feed_id}/items")
async def list_feed_items(
    feed_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(require_admin),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    triage_result: Optional[str] = Query(None),
):
    """View recent items from a specific RSS feed with pagination."""
    try:
        # Verify feed exists
        feed_result = await db.execute(select(RssFeed).where(RssFeed.id == feed_id))
        feed = feed_result.scalar_one_or_none()
        if not feed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feed {feed_id} not found",
            )

        # Build query
        query = select(RssFeedItem).where(RssFeedItem.feed_id == feed_id)
        count_query = select(func.count(RssFeedItem.id)).where(
            RssFeedItem.feed_id == feed_id
        )

        if triage_result:
            query = query.where(RssFeedItem.triage_result == triage_result)
            count_query = count_query.where(RssFeedItem.triage_result == triage_result)

        # Total count
        total = (await db.execute(count_query)).scalar() or 0

        # Paginated items
        offset = (page - 1) * page_size
        query = (
            query.order_by(RssFeedItem.created_at.desc())
            .limit(page_size)
            .offset(offset)
        )
        result = await db.execute(query)
        items = result.scalars().all()

        return {
            "feed_id": feed_id,
            "feed_name": feed.name,
            "items": [_item_to_dict(item) for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to list items for RSS feed %s: %s", feed_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("RSS feed items listing", e),
        ) from e
