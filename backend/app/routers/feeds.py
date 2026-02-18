"""RSS Feeds management router."""

import logging
import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import (
    get_db,
    get_current_user_hardcoded,
    _safe_error,
    openai_client,
    limiter,
)
from app.rss_service import RSSService
from app.ai_service import AIService
from app.models.db.rss import RssFeed, RssFeedItem

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["feeds"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class FeedCreate(BaseModel):
    """Request body for creating a new RSS feed."""

    url: str = Field(..., description="RSS feed URL")
    name: str = Field(..., description="Human-readable feed name")
    category: Optional[str] = Field("general", description="Feed category")
    pillar_id: Optional[str] = Field(
        None, description="Strategic pillar to lock this feed to"
    )
    check_interval_hours: Optional[int] = Field(
        6, ge=1, le=168, description="Check interval in hours"
    )


class FeedUpdate(BaseModel):
    """Request body for updating an RSS feed."""

    name: Optional[str] = None
    category: Optional[str] = None
    pillar_id: Optional[str] = None
    check_interval_hours: Optional[int] = Field(None, ge=1, le=168)
    status: Optional[str] = None


class FeedResponse(BaseModel):
    """Response model for a single feed."""

    id: str
    name: str
    url: str
    category: Optional[str] = None
    pillar_id: Optional[str] = None
    status: Optional[str] = None
    check_interval_hours: Optional[int] = None
    last_checked_at: Optional[str] = None
    next_check_at: Optional[str] = None
    error_count: int = 0
    last_error: Optional[str] = None
    feed_title: Optional[str] = None
    feed_link: Optional[str] = None
    articles_found_total: int = 0
    articles_matched_total: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        extra = "allow"


class FeedStatsResponse(FeedResponse):
    """Feed response with additional stats."""

    recent_items_7d: int = 0


class FeedItemResponse(BaseModel):
    """Response model for a feed item."""

    id: str
    feed_id: str
    url: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[str] = None
    processed: bool = False
    triage_result: Optional[str] = None
    card_id: Optional[str] = None
    source_id: Optional[str] = None
    created_at: Optional[str] = None

    class Config:
        extra = "allow"


class FeedCheckResponse(BaseModel):
    """Response model for feed check results."""

    feeds_checked: int = 0
    items_found: int = 0
    items_new: int = 0
    errors: int = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_dict(obj, skip_cols=None) -> dict:
    skip = skip_cols or set()
    result = {}
    for col in obj.__table__.columns:
        if col.name in skip:
            continue
        value = getattr(obj, col.key, None)
        if isinstance(value, uuid.UUID):
            result[col.name] = str(value)
        elif isinstance(value, (datetime, date)):
            result[col.name] = value.isoformat()
        elif isinstance(value, Decimal):
            result[col.name] = float(value)
        else:
            result[col.name] = value
    return result


def _get_rss_service(db: AsyncSession) -> RSSService:
    """Create an RSSService instance with the database session and AI clients."""
    ai_service = AIService(openai_client)
    return RSSService(db, ai_service)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/feeds", response_model=List[FeedStatsResponse])
async def list_feeds(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    List all RSS feeds with stats.

    Returns feeds with name, url, category, status, last_checked, error_count,
    articles_found_total, articles_matched_total, and recent_items_7d.
    """
    try:
        service = _get_rss_service(db)
        feeds = await service.get_feed_stats()
        return [FeedStatsResponse(**f) for f in feeds]
    except Exception as e:
        logger.error(f"Failed to list feeds: {e}")
        raise HTTPException(status_code=500, detail=_safe_error("list feeds", e)) from e


@router.post("/feeds", response_model=FeedResponse)
@limiter.limit("10/minute")
async def create_feed(
    request: Request,
    body: FeedCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Add a new RSS feed subscription.

    Performs an initial check of the feed immediately after creation.
    Rate limited to 10 requests per minute.
    """
    try:
        service = _get_rss_service(db)
        feed = await service.add_feed(
            url=body.url,
            name=body.name,
            category=body.category or "general",
            pillar_id=body.pillar_id,
            check_interval_hours=body.check_interval_hours or 6,
        )
        return FeedResponse(**feed)
    except Exception as e:
        logger.error(f"Failed to create feed: {e}")
        raise HTTPException(
            status_code=500, detail=_safe_error("create feed", e)
        ) from e


@router.get("/feeds/{feed_id}", response_model=dict)
async def get_feed(
    feed_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Get feed details with recent items.

    Returns the feed record plus the last 50 items.
    """
    try:
        # Fetch the feed record
        feed_stmt = select(RssFeed).where(RssFeed.id == feed_id)
        feed_result = await db.execute(feed_stmt)
        feed_row = feed_result.scalar_one_or_none()
        if not feed_row:
            raise HTTPException(status_code=404, detail="Feed not found")

        # Fetch recent items
        items_stmt = (
            select(RssFeedItem)
            .where(RssFeedItem.feed_id == feed_id)
            .order_by(RssFeedItem.published_at.desc())
            .limit(50)
        )
        items_result = await db.execute(items_stmt)
        item_rows = items_result.scalars().all()

        return {
            "feed": _row_to_dict(feed_row),
            "items": [_row_to_dict(item) for item in item_rows],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get feed {feed_id}: {e}")
        raise HTTPException(status_code=500, detail=_safe_error("get feed", e)) from e


@router.put("/feeds/{feed_id}", response_model=FeedResponse)
async def update_feed(
    feed_id: str,
    body: FeedUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Update feed settings.

    Accepts partial updates of name, category, pillar_id,
    check_interval_hours, and status.
    """
    try:
        service = _get_rss_service(db)
        update_kwargs = body.dict(exclude_none=True)
        if not update_kwargs:
            raise HTTPException(status_code=400, detail="No fields to update")
        feed = await service.update_feed(feed_id, **update_kwargs)
        return FeedResponse(**feed)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to update feed {feed_id}: {e}")
        raise HTTPException(
            status_code=500, detail=_safe_error("update feed", e)
        ) from e


@router.delete("/feeds/{feed_id}")
async def delete_feed(
    feed_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Delete an RSS feed and its items.
    """
    try:
        service = _get_rss_service(db)
        deleted = await service.delete_feed(feed_id)
        if not deleted:
            raise HTTPException(
                status_code=404, detail="Feed not found or delete failed"
            )
        return {"message": f"Feed {feed_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete feed {feed_id}: {e}")
        raise HTTPException(
            status_code=500, detail=_safe_error("delete feed", e)
        ) from e


@router.post("/feeds/check", response_model=FeedCheckResponse)
@limiter.limit("2/minute")
async def check_feeds(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Trigger a manual feed check for all due feeds.

    Rate limited to 2 requests per minute.
    Checks all active feeds whose next_check_at has passed.
    """
    try:
        service = _get_rss_service(db)
        stats = await service.check_feeds()
        return FeedCheckResponse(**stats)
    except Exception as e:
        logger.error(f"Failed to check feeds: {e}")
        raise HTTPException(
            status_code=500, detail=_safe_error("check feeds", e)
        ) from e


@router.get("/feeds/{feed_id}/items", response_model=List[FeedItemResponse])
async def list_feed_items(
    feed_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
    limit: int = 50,
    offset: int = 0,
    triage_result: Optional[str] = None,
):
    """
    List feed items with pagination.

    Supports filtering by triage_result (matched, pending, irrelevant).
    """
    try:
        # Verify feed exists
        feed_stmt = select(RssFeed.id).where(RssFeed.id == feed_id)
        feed_result = await db.execute(feed_stmt)
        if not feed_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Feed not found")

        # Build items query
        items_stmt = select(RssFeedItem).where(RssFeedItem.feed_id == feed_id)

        if triage_result:
            items_stmt = items_stmt.where(RssFeedItem.triage_result == triage_result)

        items_stmt = (
            items_stmt.order_by(RssFeedItem.published_at.desc())
            .offset(offset)
            .limit(limit)
        )

        items_result = await db.execute(items_stmt)
        item_rows = items_result.scalars().all()

        return [FeedItemResponse(**_row_to_dict(item)) for item in item_rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list items for feed {feed_id}: {e}")
        raise HTTPException(
            status_code=500, detail=_safe_error("list feed items", e)
        ) from e
