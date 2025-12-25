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

from .export import (
    # Export format enum
    ExportFormat,
    # Chart configuration
    ChartOptions,
    # Card export models
    ExportRequest,
    ExportResponse,
    CardExportData,
    # Workstream export models
    WorkstreamExportRequest,
    WorkstreamExportResponse,
    # Utilities
    EXPORT_CONTENT_TYPES,
    get_export_filename,
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
    # Export models
    "ExportFormat",
    "ChartOptions",
    "ExportRequest",
    "ExportResponse",
    "CardExportData",
    "WorkstreamExportRequest",
    "WorkstreamExportResponse",
    "EXPORT_CONTENT_TYPES",
    "get_export_filename",
]
