"""
Advanced Search Models for Intelligence Cards

This module provides Pydantic models for the advanced search and filtering
functionality, enabling multi-dimensional filtering by pillar, stage,
date range, and score thresholds.

Supports:
- pillar_ids: Filter by strategic pillar codes
- stage_ids: Filter by maturity stage IDs
- date_range: Filter by creation/update date range
- score_thresholds: Filter by min/max score values
"""

from datetime import date, datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator


class DateRange(BaseModel):
    """Date range filter for created_at/updated_at filtering."""
    start: Optional[date] = Field(
        None,
        description="Start date (inclusive) in YYYY-MM-DD format"
    )
    end: Optional[date] = Field(
        None,
        description="End date (inclusive) in YYYY-MM-DD format"
    )

    @validator('end')
    def end_after_start(cls, v, values):
        """Validate that end date is not before start date."""
        if v and values.get('start') and v < values['start']:
            raise ValueError('End date must be after or equal to start date')
        return v


class ScoreThreshold(BaseModel):
    """Min/max threshold for a single score field."""
    min: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Minimum score value (0-100)"
    )
    max: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Maximum score value (0-100)"
    )

    @validator('max')
    def max_gte_min(cls, v, values):
        """Validate that max is not less than min."""
        if v is not None and values.get('min') is not None and v < values['min']:
            raise ValueError('Max must be greater than or equal to min')
        return v


class ScoreThresholds(BaseModel):
    """Collection of score threshold filters."""
    impact_score: Optional[ScoreThreshold] = Field(
        None,
        description="Filter by impact score range"
    )
    relevance_score: Optional[ScoreThreshold] = Field(
        None,
        description="Filter by relevance score range"
    )
    novelty_score: Optional[ScoreThreshold] = Field(
        None,
        description="Filter by novelty score range"
    )
    maturity_score: Optional[ScoreThreshold] = Field(
        None,
        description="Filter by maturity score range"
    )
    velocity_score: Optional[ScoreThreshold] = Field(
        None,
        description="Filter by velocity score range"
    )
    risk_score: Optional[ScoreThreshold] = Field(
        None,
        description="Filter by risk score range"
    )
    opportunity_score: Optional[ScoreThreshold] = Field(
        None,
        description="Filter by opportunity score range"
    )


class SearchFilters(BaseModel):
    """
    Advanced search filters for intelligence cards.

    All filters are optional and combined with AND logic when multiple
    filters are specified.
    """
    pillar_ids: Optional[List[str]] = Field(
        None,
        description="Filter by strategic pillar codes (e.g., ['CH', 'HG'])"
    )
    goal_ids: Optional[List[str]] = Field(
        None,
        description="Filter by goal IDs (e.g., ['CH.1', 'HG.2'])"
    )
    stage_ids: Optional[List[str]] = Field(
        None,
        description="Filter by maturity stage IDs (e.g., ['6_early_adoption'])"
    )
    horizon: Optional[str] = Field(
        None,
        pattern=r"^(H[123]|ALL)$",
        description="Filter by horizon (H1, H2, H3, or ALL)"
    )
    date_range: Optional[DateRange] = Field(
        None,
        description="Filter by created_at date range"
    )
    score_thresholds: Optional[ScoreThresholds] = Field(
        None,
        description="Filter by score value ranges"
    )
    status: Optional[str] = Field(
        None,
        description="Filter by card status (e.g., 'active')"
    )

    @validator('pillar_ids', 'goal_ids', 'stage_ids', pre=True)
    def filter_empty_strings(cls, v):
        """Remove empty strings from filter lists."""
        if v is not None:
            return [item for item in v if item and item.strip()]
        return v


class AdvancedSearchRequest(BaseModel):
    """
    Request model for advanced card search.

    Combines text/semantic search query with optional filters
    for precise card discovery.
    """
    query: Optional[str] = Field(
        None,
        max_length=500,
        description="Search query for text/semantic search"
    )
    filters: Optional[SearchFilters] = Field(
        None,
        description="Advanced filter criteria"
    )
    use_vector_search: bool = Field(
        True,
        description="Use vector similarity search (semantic) vs text search"
    )
    limit: int = Field(
        20,
        ge=1,
        le=100,
        description="Maximum number of results to return"
    )
    offset: int = Field(
        0,
        ge=0,
        description="Number of results to skip for pagination"
    )

    @validator('query')
    def clean_query(cls, v):
        """Clean and validate search query."""
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
        return v


class SearchResultItem(BaseModel):
    """
    Individual search result with relevance score.

    Extends card data with search-specific metadata.
    """
    id: str
    name: str
    slug: str
    summary: Optional[str] = None
    description: Optional[str] = None
    pillar_id: Optional[str] = None
    goal_id: Optional[str] = None
    anchor_id: Optional[str] = None
    stage_id: Optional[str] = None
    horizon: Optional[str] = None
    novelty_score: Optional[int] = None
    maturity_score: Optional[int] = None
    impact_score: Optional[int] = None
    relevance_score: Optional[int] = None
    velocity_score: Optional[int] = None
    risk_score: Optional[int] = None
    opportunity_score: Optional[int] = None
    status: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # Search-specific fields
    search_relevance: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Vector similarity score (0-1) when using semantic search"
    )
    match_highlights: Optional[List[str]] = Field(
        None,
        description="Highlighted text snippets showing query matches"
    )


class AdvancedSearchResponse(BaseModel):
    """
    Response model for advanced search results.

    Includes results, total count, and applied filters for context.
    """
    results: List[SearchResultItem] = Field(
        default_factory=list,
        description="List of matching cards with relevance scores"
    )
    total_count: int = Field(
        0,
        description="Total number of matching cards (before limit)"
    )
    query: Optional[str] = Field(
        None,
        description="The search query that was executed"
    )
    filters_applied: Optional[SearchFilters] = Field(
        None,
        description="Filters that were applied to the search"
    )
    search_type: str = Field(
        "vector",
        description="Type of search performed: 'vector' or 'text'"
    )


# ============================================================================
# Saved Search Models
# ============================================================================

class SavedSearchCreate(BaseModel):
    """
    Request model for creating a saved search.

    Users can save their search configurations with a custom name
    for quick re-execution from the sidebar.
    """
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="User-defined name for the saved search"
    )
    query_config: Dict[str, Any] = Field(
        ...,
        description="Complete search configuration including query and filters"
    )

    @validator('name')
    def validate_name(cls, v):
        """Validate name is not just whitespace."""
        if not v.strip():
            raise ValueError('Saved search name cannot be empty or whitespace')
        return v.strip()


class SavedSearchUpdate(BaseModel):
    """
    Request model for updating a saved search.

    Both name and query_config are optional - only provided fields are updated.
    """
    name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="New name for the saved search"
    )
    query_config: Optional[Dict[str, Any]] = Field(
        None,
        description="Updated search configuration"
    )

    @validator('name')
    def validate_name(cls, v):
        """Validate name is not just whitespace if provided."""
        if v is not None and not v.strip():
            raise ValueError('Saved search name cannot be empty or whitespace')
        return v.strip() if v else v


class SavedSearch(BaseModel):
    """
    Response model for a saved search record.

    Represents a user's saved search configuration retrieved from the database.
    """
    id: str = Field(
        ...,
        description="UUID of the saved search"
    )
    user_id: str = Field(
        ...,
        description="UUID of the user who owns this saved search"
    )
    name: str = Field(
        ...,
        description="User-defined name for the saved search"
    )
    query_config: Dict[str, Any] = Field(
        ...,
        description="Complete search configuration including query and filters"
    )
    created_at: datetime = Field(
        ...,
        description="When the saved search was created"
    )
    last_used_at: datetime = Field(
        ...,
        description="When the saved search was last executed"
    )
    updated_at: Optional[datetime] = Field(
        None,
        description="When the saved search was last modified"
    )


class SavedSearchList(BaseModel):
    """
    Response model for listing saved searches.
    """
    saved_searches: List[SavedSearch] = Field(
        default_factory=list,
        description="List of user's saved searches"
    )
    total_count: int = Field(
        default=0,
        description="Total number of saved searches"
    )


# ============================================================================
# Search History Models
# ============================================================================

class SearchHistoryEntry(BaseModel):
    """
    Response model for a search history record.

    Tracks executed searches for quick re-run access.
    """
    id: str = Field(
        ...,
        description="UUID of the history entry"
    )
    user_id: str = Field(
        ...,
        description="UUID of the user who executed the search"
    )
    query_config: Dict[str, Any] = Field(
        ...,
        description="Search configuration that was executed"
    )
    executed_at: datetime = Field(
        ...,
        description="When the search was executed"
    )
    result_count: int = Field(
        default=0,
        description="Number of results returned by the search"
    )


class SearchHistoryCreate(BaseModel):
    """
    Request model for recording a search in history.

    Internal use - called automatically when searches are executed.
    """
    query_config: Dict[str, Any] = Field(
        ...,
        description="Search configuration that was executed"
    )
    result_count: int = Field(
        default=0,
        ge=0,
        description="Number of results returned"
    )


class SearchHistoryList(BaseModel):
    """
    Response model for listing search history.
    """
    history: List[SearchHistoryEntry] = Field(
        default_factory=list,
        description="List of recent search history entries"
    )
    total_count: int = Field(
        default=0,
        description="Total number of history entries (max 50 per user)"
    )
