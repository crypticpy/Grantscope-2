"""
Foresight API Models

Pydantic models for data validation and serialization.
"""

from .validation import (
    ClassificationValidation,
    ClassificationValidationCreate,
    ClassificationAccuracyMetrics,
    ValidationSummary,
)

from .search import (
    # Filter components
    DateRange,
    ScoreThreshold,
    ScoreThresholds,
    SearchFilters,
    # Search request/response
    AdvancedSearchRequest,
    SearchResultItem,
    AdvancedSearchResponse,
    # Saved searches
    SavedSearchCreate,
    SavedSearchUpdate,
    SavedSearch,
    SavedSearchList,
    # Search history
    SearchHistoryEntry,
    SearchHistoryCreate,
    SearchHistoryList,
)

__all__ = [
    # Validation models
    "ClassificationValidation",
    "ClassificationValidationCreate",
    "ClassificationAccuracyMetrics",
    "ValidationSummary",
    # Search filter components
    "DateRange",
    "ScoreThreshold",
    "ScoreThresholds",
    "SearchFilters",
    # Search request/response
    "AdvancedSearchRequest",
    "SearchResultItem",
    "AdvancedSearchResponse",
    # Saved searches
    "SavedSearchCreate",
    "SavedSearchUpdate",
    "SavedSearch",
    "SavedSearchList",
    # Search history
    "SearchHistoryEntry",
    "SearchHistoryCreate",
    "SearchHistoryList",
]
