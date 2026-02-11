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

from .history import (
    # Score history models
    ScoreHistory,
    ScoreHistoryCreate,
    ScoreHistoryResponse,
)

from .brief import (
    # Executive brief models
    BriefStatusEnum,
    BriefSection,
    ExecutiveBriefCreate,
    ExecutiveBriefResponse,
    BriefGenerateResponse,
    BriefStatusResponse,
    BriefListItem,
    VALID_BRIEF_STATUSES,
)

from .source_rating import (
    # Source rating models
    RelevanceRating,
    SourceRatingCreate,
    SourceRatingResponse,
    SourceRatingAggregate,
)

from .quality import (
    # Quality/SQI models
    QualityTier,
    QualityBreakdown,
    QualityTierFilter,
)

from .domain_reputation import (
    # Domain reputation models
    DomainReputationResponse,
    DomainReputationCreate,
    DomainReputationUpdate,
    TopDomainsResponse,
    DomainReputationList,
)

from .card_creation import (
    # Card creation models
    CreateCardFromTopicRequest,
    CreateCardFromTopicResponse,
    ManualCardCreateRequest,
    KeywordSuggestionResponse,
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
    # Score history models
    "ScoreHistory",
    "ScoreHistoryCreate",
    "ScoreHistoryResponse",
    # Executive brief models
    "BriefStatusEnum",
    "BriefSection",
    "ExecutiveBriefCreate",
    "ExecutiveBriefResponse",
    "BriefGenerateResponse",
    "BriefStatusResponse",
    "BriefListItem",
    "VALID_BRIEF_STATUSES",
    # Source rating models
    "RelevanceRating",
    "SourceRatingCreate",
    "SourceRatingResponse",
    "SourceRatingAggregate",
    # Quality/SQI models
    "QualityTier",
    "QualityBreakdown",
    "QualityTierFilter",
    # Domain reputation models
    "DomainReputationResponse",
    "DomainReputationCreate",
    "DomainReputationUpdate",
    "TopDomainsResponse",
    "DomainReputationList",
    # Card creation models
    "CreateCardFromTopicRequest",
    "CreateCardFromTopicResponse",
    "ManualCardCreateRequest",
    "KeywordSuggestionResponse",
]
