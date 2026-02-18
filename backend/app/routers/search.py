"""Saved searches and search history router.

Migrated from Supabase PostgREST to SQLAlchemy 2.0 async.
"""

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, get_current_user_hardcoded, _safe_error
from app.models.db.search import SavedSearch as SavedSearchORM, SearchHistory
from app.models.search import (
    SavedSearchCreate,
    SavedSearchUpdate,
    SavedSearch,
    SavedSearchList,
    SearchHistoryCreate,
    SearchHistoryEntry,
    SearchHistoryList,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["search"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_dict(obj, skip_cols=None) -> dict:
    """Convert an ORM model instance to a plain dict with JSON-safe values."""
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


# ============================================================================
# Saved Searches
# ============================================================================


@router.get("/saved-searches", response_model=SavedSearchList)
async def list_saved_searches(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    List all saved searches for the current user.

    Returns saved searches ordered by last_used_at descending (most recently used first).
    """
    try:
        result = await db.execute(
            select(SavedSearchORM)
            .where(SavedSearchORM.user_id == uuid.UUID(current_user["id"]))
            .order_by(SavedSearchORM.last_used_at.desc())
        )
        rows = list(result.scalars().all())
    except Exception as e:
        logger.error("Failed to list saved searches: %s", e)
        raise HTTPException(
            status_code=500, detail=_safe_error("listing saved searches", e)
        ) from e

    saved_searches = [SavedSearch(**_row_to_dict(row)) for row in rows]
    return SavedSearchList(
        saved_searches=saved_searches, total_count=len(saved_searches)
    )


@router.post(
    "/saved-searches",
    response_model=SavedSearch,
    status_code=status.HTTP_201_CREATED,
)
async def create_saved_search(
    saved_search_data: SavedSearchCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Create a new saved search.

    Saves the search configuration with a user-defined name for quick re-execution
    from the sidebar.

    Args:
        saved_search_data: Name and query configuration for the saved search
        current_user: Authenticated user (injected)

    Returns:
        Created SavedSearch object

    Raises:
        HTTPException 400: Failed to create saved search
    """
    now = datetime.now(timezone.utc)
    item = SavedSearchORM(
        user_id=uuid.UUID(current_user["id"]),
        name=saved_search_data.name,
        query_config=saved_search_data.query_config,
        created_at=now,
        last_used_at=now,
        updated_at=now,
    )

    try:
        db.add(item)
        await db.flush()
        await db.refresh(item)
    except Exception as e:
        logger.error("Failed to create saved search: %s", e)
        raise HTTPException(
            status_code=500, detail=_safe_error("saved search creation", e)
        ) from e

    return SavedSearch(**_row_to_dict(item))


@router.get("/saved-searches/{saved_search_id}", response_model=SavedSearch)
async def get_saved_search(
    saved_search_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Get a specific saved search by ID.

    Also updates the last_used_at timestamp to track usage.

    Args:
        saved_search_id: UUID of the saved search
        current_user: Authenticated user (injected)

    Returns:
        SavedSearch object

    Raises:
        HTTPException 404: Saved search not found
        HTTPException 403: Saved search belongs to another user
    """
    try:
        result = await db.execute(
            select(SavedSearchORM).where(
                SavedSearchORM.id == uuid.UUID(saved_search_id)
            )
        )
        item = result.scalar_one_or_none()
    except Exception as e:
        logger.error("Failed to fetch saved search %s: %s", saved_search_id, e)
        raise HTTPException(
            status_code=500, detail=_safe_error("fetching saved search", e)
        ) from e

    if item is None:
        raise HTTPException(status_code=404, detail="Saved search not found")

    # Verify ownership
    if str(item.user_id) != current_user["id"]:
        raise HTTPException(
            status_code=403, detail="Not authorized to access this saved search"
        )

    # Update last_used_at timestamp
    try:
        item.last_used_at = datetime.now(timezone.utc)
        await db.flush()
        await db.refresh(item)
    except Exception as e:
        logger.error(
            "Failed to update saved search last_used_at %s: %s", saved_search_id, e
        )
        raise HTTPException(
            status_code=500, detail=_safe_error("updating saved search", e)
        ) from e

    return SavedSearch(**_row_to_dict(item))


@router.patch("/saved-searches/{saved_search_id}", response_model=SavedSearch)
async def update_saved_search(
    saved_search_id: str,
    saved_search_data: SavedSearchUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Update an existing saved search.

    - Verifies the saved search belongs to the current user
    - Accepts partial updates (name and/or query_config can be updated)
    - Returns the updated saved search

    Args:
        saved_search_id: UUID of the saved search to update
        saved_search_data: Partial update data
        current_user: Authenticated user (injected)

    Returns:
        Updated SavedSearch object

    Raises:
        HTTPException 404: Saved search not found
        HTTPException 403: Saved search belongs to another user
    """
    # Fetch existing saved search
    try:
        result = await db.execute(
            select(SavedSearchORM).where(
                SavedSearchORM.id == uuid.UUID(saved_search_id)
            )
        )
        item = result.scalar_one_or_none()
    except Exception as e:
        logger.error(
            "Failed to fetch saved search for update %s: %s", saved_search_id, e
        )
        raise HTTPException(
            status_code=500, detail=_safe_error("fetching saved search", e)
        ) from e

    if item is None:
        raise HTTPException(status_code=404, detail="Saved search not found")

    # Verify ownership
    if str(item.user_id) != current_user["id"]:
        raise HTTPException(
            status_code=403, detail="Not authorized to update this saved search"
        )

    # Build update dict with only non-None values
    update_dict = {k: v for k, v in saved_search_data.dict().items() if v is not None}

    if not update_dict:
        # No updates provided, return existing saved search
        return SavedSearch(**_row_to_dict(item))

    # Apply updates
    for key, value in update_dict.items():
        setattr(item, key, value)
    item.updated_at = datetime.now(timezone.utc)

    try:
        await db.flush()
        await db.refresh(item)
    except Exception as e:
        logger.error("Failed to update saved search %s: %s", saved_search_id, e)
        raise HTTPException(
            status_code=500, detail=_safe_error("saved search update", e)
        ) from e

    return SavedSearch(**_row_to_dict(item))


@router.delete("/saved-searches/{saved_search_id}")
async def delete_saved_search(
    saved_search_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Delete a saved search.

    - Verifies the saved search belongs to the current user
    - Permanently deletes the saved search

    Args:
        saved_search_id: UUID of the saved search to delete
        current_user: Authenticated user (injected)

    Returns:
        Success message

    Raises:
        HTTPException 404: Saved search not found
        HTTPException 403: Saved search belongs to another user
    """
    # Fetch existing saved search
    try:
        result = await db.execute(
            select(SavedSearchORM).where(
                SavedSearchORM.id == uuid.UUID(saved_search_id)
            )
        )
        item = result.scalar_one_or_none()
    except Exception as e:
        logger.error(
            "Failed to fetch saved search for delete %s: %s", saved_search_id, e
        )
        raise HTTPException(
            status_code=500, detail=_safe_error("fetching saved search", e)
        ) from e

    if item is None:
        raise HTTPException(status_code=404, detail="Saved search not found")

    # Verify ownership
    if str(item.user_id) != current_user["id"]:
        raise HTTPException(
            status_code=403, detail="Not authorized to delete this saved search"
        )

    # Perform delete
    try:
        await db.delete(item)
        await db.flush()
    except Exception as e:
        logger.error("Failed to delete saved search %s: %s", saved_search_id, e)
        raise HTTPException(
            status_code=500, detail=_safe_error("saved search deletion", e)
        ) from e

    return {"status": "deleted", "message": "Saved search successfully deleted"}


# ============================================================================
# Search History
# ============================================================================


@router.get("/search-history", response_model=SearchHistoryList)
async def list_search_history(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Get user's recent search history.

    Returns the most recent searches executed by the current user,
    ordered by execution time (most recent first).

    Args:
        limit: Maximum number of history entries to return (default: 20, max: 50)

    Returns:
        SearchHistoryList with recent search history entries
    """
    # Cap limit at 50 (database auto-cleans to 50 anyway)
    limit = min(limit, 50)

    try:
        result = await db.execute(
            select(SearchHistory)
            .where(SearchHistory.user_id == uuid.UUID(current_user["id"]))
            .order_by(SearchHistory.executed_at.desc())
            .limit(limit)
        )
        rows = list(result.scalars().all())

        history_entries = [
            SearchHistoryEntry(
                id=str(row.id),
                user_id=str(row.user_id),
                query_config=row.query_config or {},
                executed_at=row.executed_at,
                result_count=row.result_count or 0,
            )
            for row in rows
        ]

        return SearchHistoryList(
            history=history_entries, total_count=len(history_entries)
        )

    except Exception as e:
        logger.error("Failed to fetch search history: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("search history retrieval", e),
        ) from e


@router.post(
    "/search-history",
    response_model=SearchHistoryEntry,
    status_code=status.HTTP_201_CREATED,
)
async def record_search_history(
    history_data: SearchHistoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Record a search in the user's history.

    This endpoint is called automatically when searches are executed,
    allowing users to re-run recent searches from their history.

    The database trigger automatically cleans up old entries,
    keeping only the 50 most recent searches per user.

    Args:
        history_data: Search configuration and result count to record

    Returns:
        SearchHistoryEntry with the created history record
    """
    now = datetime.now(timezone.utc)
    item = SearchHistory(
        user_id=uuid.UUID(current_user["id"]),
        query_config=history_data.query_config,
        result_count=history_data.result_count,
        executed_at=now,
    )

    try:
        db.add(item)
        await db.flush()
        await db.refresh(item)
    except Exception as e:
        logger.error("Failed to record search history: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("search history recording", e),
        ) from e

    return SearchHistoryEntry(
        id=str(item.id),
        user_id=str(item.user_id),
        query_config=item.query_config or {},
        executed_at=item.executed_at,
        result_count=item.result_count or 0,
    )


@router.delete("/search-history/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_search_history_entry(
    entry_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Delete a specific search history entry.

    Users can only delete their own history entries.

    Args:
        entry_id: UUID of the history entry to delete
    """
    try:
        # Verify entry exists and belongs to user
        result = await db.execute(
            select(SearchHistory).where(
                SearchHistory.id == uuid.UUID(entry_id),
                SearchHistory.user_id == uuid.UUID(current_user["id"]),
            )
        )
        item = result.scalar_one_or_none()

        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Search history entry not found",
            )

        # Delete the entry
        await db.delete(item)
        await db.flush()

        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete search history entry: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("search history deletion", e),
        ) from e


@router.delete("/search-history", status_code=status.HTTP_204_NO_CONTENT)
async def clear_search_history(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Clear all search history for the current user.

    This permanently deletes all search history entries for the user.
    """
    try:
        await db.execute(
            delete(SearchHistory).where(
                SearchHistory.user_id == uuid.UUID(current_user["id"])
            )
        )
        await db.flush()

        return None

    except Exception as e:
        logger.error("Failed to clear search history: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("search history clearing", e),
        ) from e
