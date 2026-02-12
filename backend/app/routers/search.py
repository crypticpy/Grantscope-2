"""Saved searches and search history router."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status

from app.deps import (
    supabase,
    get_current_user,
    _safe_error,
    _is_missing_supabase_table_error,
)
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


# ============================================================================
# Saved Searches
# ============================================================================


@router.get("/saved-searches", response_model=SavedSearchList)
async def list_saved_searches(current_user: dict = Depends(get_current_user)):
    """
    List all saved searches for the current user.

    Returns saved searches ordered by last_used_at descending (most recently used first).
    """
    try:
        response = (
            supabase.table("saved_searches")
            .select("*")
            .eq("user_id", current_user["id"])
            .order("last_used_at", desc=True)
            .execute()
        )
    except Exception as e:
        if _is_missing_supabase_table_error(e, "saved_searches"):
            logger.warning("saved_searches table missing; returning empty list")
            return SavedSearchList(saved_searches=[], total_count=0)
        logger.error(f"Failed to list saved searches: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to list saved searches"
        ) from e

    saved_searches = [SavedSearch(**ss) for ss in (response.data or [])]
    return SavedSearchList(
        saved_searches=saved_searches, total_count=len(saved_searches)
    )


@router.post(
    "/saved-searches",
    response_model=SavedSearch,
    status_code=status.HTTP_201_CREATED,
)
async def create_saved_search(
    saved_search_data: SavedSearchCreate, current_user: dict = Depends(get_current_user)
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
    now = datetime.now().isoformat()
    ss_dict = {
        "user_id": current_user["id"],
        "name": saved_search_data.name,
        "query_config": saved_search_data.query_config,
        "created_at": now,
        "last_used_at": now,
        "updated_at": now,
    }

    try:
        response = supabase.table("saved_searches").insert(ss_dict).execute()
    except Exception as e:
        if _is_missing_supabase_table_error(e, "saved_searches"):
            raise HTTPException(
                status_code=503,
                detail="Saved searches are not configured (missing saved_searches table)",
            ) from e
        logger.error(f"Failed to create saved search: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to create saved search"
        ) from e
    if response.data:
        return SavedSearch(**response.data[0])
    else:
        raise HTTPException(status_code=400, detail="Failed to create saved search")


@router.get("/saved-searches/{saved_search_id}", response_model=SavedSearch)
async def get_saved_search(
    saved_search_id: str, current_user: dict = Depends(get_current_user)
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
    # Fetch the saved search
    try:
        response = (
            supabase.table("saved_searches")
            .select("*")
            .eq("id", saved_search_id)
            .execute()
        )
    except Exception as e:
        if _is_missing_supabase_table_error(e, "saved_searches"):
            raise HTTPException(
                status_code=503,
                detail="Saved searches are not configured (missing saved_searches table)",
            ) from e
        logger.error(f"Failed to fetch saved search {saved_search_id}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to fetch saved search"
        ) from e

    if not response.data:
        raise HTTPException(status_code=404, detail="Saved search not found")

    saved_search = response.data[0]

    # Verify ownership
    if saved_search["user_id"] != current_user["id"]:
        raise HTTPException(
            status_code=403, detail="Not authorized to access this saved search"
        )

    # Update last_used_at timestamp
    try:
        update_response = (
            supabase.table("saved_searches")
            .update({"last_used_at": datetime.now().isoformat()})
            .eq("id", saved_search_id)
            .execute()
        )
    except Exception as e:
        if _is_missing_supabase_table_error(e, "saved_searches"):
            raise HTTPException(
                status_code=503,
                detail="Saved searches are not configured (missing saved_searches table)",
            ) from e
        logger.error(
            f"Failed to update saved search last_used_at {saved_search_id}: {e}"
        )
        raise HTTPException(
            status_code=500, detail="Failed to update saved search"
        ) from e

    if update_response.data:
        return SavedSearch(**update_response.data[0])
    else:
        return SavedSearch(**saved_search)


@router.patch("/saved-searches/{saved_search_id}", response_model=SavedSearch)
async def update_saved_search(
    saved_search_id: str,
    saved_search_data: SavedSearchUpdate,
    current_user: dict = Depends(get_current_user),
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
    # First check if saved search exists
    try:
        ss_check = (
            supabase.table("saved_searches")
            .select("*")
            .eq("id", saved_search_id)
            .execute()
        )
    except Exception as e:
        if _is_missing_supabase_table_error(e, "saved_searches"):
            raise HTTPException(
                status_code=503,
                detail="Saved searches are not configured (missing saved_searches table)",
            ) from e
        logger.error(f"Failed to fetch saved search for update {saved_search_id}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to fetch saved search"
        ) from e

    if not ss_check.data:
        raise HTTPException(status_code=404, detail="Saved search not found")

    # Verify ownership
    if ss_check.data[0]["user_id"] != current_user["id"]:
        raise HTTPException(
            status_code=403, detail="Not authorized to update this saved search"
        )

    # Build update dict with only non-None values
    update_dict = {k: v for k, v in saved_search_data.dict().items() if v is not None}

    if not update_dict:
        # No updates provided, return existing saved search
        return SavedSearch(**ss_check.data[0])

    # Add updated_at timestamp
    update_dict["updated_at"] = datetime.now().isoformat()

    # Perform update
    try:
        response = (
            supabase.table("saved_searches")
            .update(update_dict)
            .eq("id", saved_search_id)
            .execute()
        )
    except Exception as e:
        if _is_missing_supabase_table_error(e, "saved_searches"):
            raise HTTPException(
                status_code=503,
                detail="Saved searches are not configured (missing saved_searches table)",
            ) from e
        logger.error(f"Failed to update saved search {saved_search_id}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to update saved search"
        ) from e

    if response.data:
        return SavedSearch(**response.data[0])
    else:
        raise HTTPException(status_code=400, detail="Failed to update saved search")


@router.delete("/saved-searches/{saved_search_id}")
async def delete_saved_search(
    saved_search_id: str, current_user: dict = Depends(get_current_user)
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
    # First check if saved search exists
    try:
        ss_check = (
            supabase.table("saved_searches")
            .select("*")
            .eq("id", saved_search_id)
            .execute()
        )
    except Exception as e:
        if _is_missing_supabase_table_error(e, "saved_searches"):
            raise HTTPException(
                status_code=503,
                detail="Saved searches are not configured (missing saved_searches table)",
            ) from e
        logger.error(f"Failed to fetch saved search for delete {saved_search_id}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to fetch saved search"
        ) from e

    if not ss_check.data:
        raise HTTPException(status_code=404, detail="Saved search not found")

    # Verify ownership
    if ss_check.data[0]["user_id"] != current_user["id"]:
        raise HTTPException(
            status_code=403, detail="Not authorized to delete this saved search"
        )

    # Perform delete
    try:
        supabase.table("saved_searches").delete().eq("id", saved_search_id).execute()
    except Exception as e:
        if _is_missing_supabase_table_error(e, "saved_searches"):
            raise HTTPException(
                status_code=503,
                detail="Saved searches are not configured (missing saved_searches table)",
            ) from e
        logger.error(f"Failed to delete saved search {saved_search_id}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to delete saved search"
        ) from e

    return {"status": "deleted", "message": "Saved search successfully deleted"}


# ============================================================================
# Search History
# ============================================================================


@router.get("/search-history", response_model=SearchHistoryList)
async def list_search_history(
    current_user: dict = Depends(get_current_user), limit: int = 20
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
        response = (
            supabase.table("search_history")
            .select("*")
            .eq("user_id", current_user["id"])
            .order("executed_at", desc=True)
            .limit(limit)
            .execute()
        )

        history_entries = [
            SearchHistoryEntry(
                id=entry["id"],
                user_id=entry["user_id"],
                query_config=entry.get("query_config", {}),
                executed_at=entry["executed_at"],
                result_count=entry.get("result_count", 0),
            )
            for entry in response.data or []
        ]

        return SearchHistoryList(
            history=history_entries, total_count=len(history_entries)
        )

    except Exception as e:
        if _is_missing_supabase_table_error(e, "search_history"):
            logger.warning("search_history table missing; returning empty list")
            return SearchHistoryList(history=[], total_count=0)
        logger.error(f"Failed to fetch search history: {str(e)}")
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
    history_data: SearchHistoryCreate, current_user: dict = Depends(get_current_user)
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
    try:
        history_record = {
            "user_id": current_user["id"],
            "query_config": history_data.query_config,
            "result_count": history_data.result_count,
            "executed_at": datetime.now().isoformat(),
        }

        response = supabase.table("search_history").insert(history_record).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to record search history",
            )

        entry = response.data[0]
        return SearchHistoryEntry(
            id=entry["id"],
            user_id=entry["user_id"],
            query_config=entry.get("query_config", {}),
            executed_at=entry["executed_at"],
            result_count=entry.get("result_count", 0),
        )

    except HTTPException:
        raise
    except Exception as e:
        if _is_missing_supabase_table_error(e, "search_history"):
            raise HTTPException(
                status_code=503,
                detail="Search history is not configured (missing search_history table)",
            ) from e
        logger.error(f"Failed to record search history: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("search history recording", e),
        ) from e


@router.delete("/search-history/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_search_history_entry(
    entry_id: str, current_user: dict = Depends(get_current_user)
):
    """
    Delete a specific search history entry.

    Users can only delete their own history entries.

    Args:
        entry_id: UUID of the history entry to delete
    """
    try:
        # Verify entry exists and belongs to user
        check_response = (
            supabase.table("search_history")
            .select("id")
            .eq("id", entry_id)
            .eq("user_id", current_user["id"])
            .execute()
        )

        if not check_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Search history entry not found",
            )

        # Delete the entry
        supabase.table("search_history").delete().eq("id", entry_id).eq(
            "user_id", current_user["id"]
        ).execute()

        return None

    except HTTPException:
        raise
    except Exception as e:
        if _is_missing_supabase_table_error(e, "search_history"):
            raise HTTPException(
                status_code=503,
                detail="Search history is not configured (missing search_history table)",
            ) from e
        logger.error(f"Failed to delete search history entry: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("search history deletion", e),
        ) from e


@router.delete("/search-history", status_code=status.HTTP_204_NO_CONTENT)
async def clear_search_history(current_user: dict = Depends(get_current_user)):
    """
    Clear all search history for the current user.

    This permanently deletes all search history entries for the user.
    """
    try:
        supabase.table("search_history").delete().eq(
            "user_id", current_user["id"]
        ).execute()

        return None

    except Exception as e:
        if _is_missing_supabase_table_error(e, "search_history"):
            raise HTTPException(
                status_code=503,
                detail="Search history is not configured (missing search_history table)",
            ) from e
        logger.error(f"Failed to clear search history: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("search history clearing", e),
        ) from e
