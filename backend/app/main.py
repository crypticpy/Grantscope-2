"""
Foresight API - FastAPI backend for Austin Strategic Research System
"""

import logging
import os
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, Depends, HTTPException, status, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
import io
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, validator
import uuid
from dotenv import load_dotenv
from supabase import create_client, Client
from postgrest.exceptions import APIError
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Azure OpenAI provider - centralized client configuration
from app.openai_provider import (
    azure_openai_client,
    azure_openai_embedding_client,
    get_chat_deployment,
    get_chat_mini_deployment,
    get_embedding_deployment,
)

# Security module import
from app.security import (
    setup_security,
    get_rate_limiter,
    rate_limit_sensitive,
    rate_limit_auth,
    rate_limit_discovery,
    log_security_event,
    get_client_ip,
)

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Research service import
from app.research_service import ResearchService

# Executive brief service import
from app.brief_service import ExecutiveBriefService
from app.models.brief import (
    ExecutiveBriefResponse,
    BriefGenerateResponse,
    BriefStatusResponse,
    BriefVersionsResponse,
    BriefVersionListItem,
)

# Search models import
from app.models.search import (
    AdvancedSearchRequest,
    SearchFilters,
    AdvancedSearchResponse,
    SearchResultItem,
    SavedSearchCreate,
    SavedSearchUpdate,
    SavedSearch,
    SavedSearchList,
    SearchHistoryEntry,
    SearchHistoryCreate,
    SearchHistoryList,
)

# Export service and models import
from app.export_service import ExportService
from app.models.export import (
    ExportFormat,
    CardExportData,
    EXPORT_CONTENT_TYPES,
    get_export_filename,
)

# Analytics models import
from app.models.analytics import (
    VelocityDataPoint,
    VelocityResponse,
    PillarCoverageItem,
    PillarCoverageResponse,
    InsightItem,
    InsightsResponse,
    # Comprehensive analytics models
    StageDistribution,
    HorizonDistribution,
    TrendingTopic,
    SourceStats,
    DiscoveryStats,
    WorkstreamEngagement,
    FollowStats,
    SystemWideStats,
    UserFollowItem,
    PopularCard,
    UserEngagementComparison,
    PillarAffinity,
    PersonalStats,
)

# History models import for trend visualization
from app.models.history import (
    ScoreHistory,
    ScoreHistoryResponse,
    StageHistory,
    StageHistoryList,
    RelatedCard,
    RelatedCardsList,
    CardData,
    CardComparisonItem,
    CardComparisonResponse,
)

# Initialize FastAPI app
app = FastAPI(
    title="Foresight API",
    description="Austin Strategic Research & Intelligence System",
    version="1.0.0"
)

# =============================================================================
# CORS Configuration
# =============================================================================
# Environment-aware CORS: production uses strict HTTPS origins only,
# development allows localhost for local development workflows.

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()

# Configure allowed origins based on environment
if ENVIRONMENT == "production":
    # Production: strict HTTPS origins only
    default_origins = "https://foresight.vercel.app"
    ALLOWED_ORIGINS_RAW = os.getenv("ALLOWED_ORIGINS", default_origins).split(",")

    # Validate production origins: must be HTTPS, no localhost
    ALLOWED_ORIGINS = []
    for origin in ALLOWED_ORIGINS_RAW:
        origin = origin.strip()
        if not origin:
            continue
        if not origin.startswith("https://"):
            print(f"[CORS] WARNING: Rejecting non-HTTPS origin in production: {origin}")
            continue
        if "localhost" in origin or "127.0.0.1" in origin:
            print(f"[CORS] WARNING: Rejecting localhost origin in production: {origin}")
            continue
        ALLOWED_ORIGINS.append(origin)

    # Fail-safe: ensure at least the default production origin is present
    if not ALLOWED_ORIGINS:
        ALLOWED_ORIGINS = ["https://foresight.vercel.app"]
        print("[CORS] WARNING: No valid origins configured, using default production origin")
else:
    # Development: allow localhost for local development
    default_origins = "http://localhost:3000,http://localhost:5173,http://localhost:5174"
    ALLOWED_ORIGINS_RAW = os.getenv("ALLOWED_ORIGINS", default_origins).split(",")

    # Clean and validate development origins
    ALLOWED_ORIGINS = [origin.strip() for origin in ALLOWED_ORIGINS_RAW if origin.strip()]

# Reject empty configuration (should never happen due to defaults, but safety check)
if not ALLOWED_ORIGINS:
    raise ValueError("CORS configuration error: No valid allowed origins configured")

# Log CORS configuration at startup
print(f"[CORS] Environment: {ENVIRONMENT}")
print(f"[CORS] Allowed origins: {ALLOWED_ORIGINS}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)

# GZip compression middleware for mobile optimization
# Compresses responses larger than 500 bytes to reduce bandwidth usage
app.add_middleware(GZipMiddleware, minimum_size=500)

# =============================================================================
# Security Middleware Setup
# =============================================================================
# Configure rate limiting, security headers, request size limits, and secure error handling
# This MUST be called after CORS middleware is added (order matters)
setup_security(app, ALLOWED_ORIGINS)

# Get the rate limiter instance for use in endpoint decorators
limiter = get_rate_limiter()


# Security
security = HTTPBearer()

# Initialize clients
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_ANON_KEY")
supabase_service_key = os.getenv("SUPABASE_SERVICE_KEY")

if not all([supabase_url, supabase_key, supabase_service_key]):
    raise ValueError("Missing required Supabase environment variables")

supabase: Client = create_client(supabase_url, supabase_service_key)

# =============================================================================
# Supabase helpers
# =============================================================================

def _is_missing_supabase_table_error(exc: Exception, table_name: str) -> bool:
    """Best-effort detection for missing PostgREST table errors."""
    try:
        if isinstance(exc, APIError):
            message = f"{exc.message or ''} {exc.details or ''}".lower()
        else:
            message = str(exc).lower()
    except Exception:
        return False

    table = table_name.lower()
    if table not in message:
        return False

    return any(
        marker in message
        for marker in (
            "could not find the table",
            "schema cache",
            "does not exist",
            "relation",
            "undefined_table",
        )
    )

# Azure OpenAI client is initialized in openai_provider module (fail-fast on missing config)
# Use azure_openai_client for chat completions
# Use azure_openai_embedding_client for embeddings (uses different API version)
openai_client = azure_openai_client

# Initialize scheduler for nightly jobs
scheduler = AsyncIOScheduler()

# Pydantic models
class UserProfile(BaseModel):
    id: str
    email: str
    display_name: Optional[str] = None
    department: Optional[str] = None
    role: Optional[str] = None
    preferences: Dict[str, Any] = {}

class Card(BaseModel):
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
    status: str = "active"
    created_at: datetime
    updated_at: datetime

class CardCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200, description="Card name")
    summary: Optional[str] = Field(None, max_length=2000, description="Card summary")
    description: Optional[str] = Field(None, max_length=10000, description="Detailed description")
    pillar_id: Optional[str] = Field(None, pattern=r"^[A-Z]{2}$", description="Pillar code (e.g., CH, MC)")
    goal_id: Optional[str] = Field(None, pattern=r"^[A-Z]{2}\.\d+$", description="Goal code (e.g., CH.1)")
    anchor_id: Optional[str] = None
    stage_id: Optional[str] = None
    horizon: Optional[str] = Field(None, pattern=r"^H[123]$", description="Horizon (H1, H2, H3)")

    @validator('name')
    def name_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Name cannot be empty or whitespace')
        return v.strip()

class Workstream(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    pillar_ids: Optional[List[str]] = []
    goal_ids: Optional[List[str]] = []
    stage_ids: Optional[List[str]] = []
    horizon: Optional[str] = None
    keywords: Optional[List[str]] = []
    is_active: bool = True
    auto_add: bool = False
    created_at: datetime

class WorkstreamCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Workstream name")
    description: Optional[str] = Field(None, max_length=1000, description="Workstream description")
    pillar_ids: Optional[List[str]] = Field(default=[], description="Filter by pillar IDs")
    goal_ids: Optional[List[str]] = Field(default=[], description="Filter by goal IDs")
    stage_ids: Optional[List[str]] = Field(default=[], description="Filter by stage IDs")
    horizon: Optional[str] = Field("ALL", pattern=r"^(H[123]|ALL)$", description="Horizon filter")
    keywords: Optional[List[str]] = Field(default=[], max_items=20, description="Search keywords")
    auto_add: bool = False

    @validator('name')
    def name_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Name cannot be empty or whitespace')
        return v.strip()

    @validator('keywords')
    def keywords_must_be_valid(cls, v):
        if v:
            # Clean and deduplicate keywords
            cleaned = list(set(kw.strip().lower() for kw in v if kw and kw.strip()))
            return cleaned[:20]  # Max 20 keywords
        return []


class WorkstreamUpdate(BaseModel):
    """Partial update model for workstreams - all fields optional"""
    name: Optional[str] = None
    description: Optional[str] = None
    pillar_ids: Optional[List[str]] = None
    goal_ids: Optional[List[str]] = None
    stage_ids: Optional[List[str]] = None
    horizon: Optional[str] = None
    keywords: Optional[List[str]] = None
    is_active: Optional[bool] = None
    auto_add: Optional[bool] = None


# ============================================================================
# Workstream Kanban Card Models
# ============================================================================

# Valid status values for workstream cards (Kanban columns)
VALID_WORKSTREAM_CARD_STATUSES = {"inbox", "screening", "research", "brief", "watching", "archived"}


class WorkstreamCardBase(BaseModel):
    """Base model for workstream card data."""
    id: str
    workstream_id: str
    card_id: str
    added_by: str
    added_at: datetime
    status: str = "inbox"
    position: int = 0
    notes: Optional[str] = None
    reminder_at: Optional[datetime] = None
    added_from: str = "manual"
    updated_at: Optional[datetime] = None


class WorkstreamCardWithDetails(BaseModel):
    """Workstream card with full card details for display."""
    id: str
    workstream_id: str
    card_id: str
    added_by: str
    added_at: datetime
    status: str
    position: int
    notes: Optional[str] = None
    reminder_at: Optional[datetime] = None
    added_from: str
    updated_at: Optional[datetime] = None
    # Card details
    card: Optional[Dict[str, Any]] = None


class WorkstreamCardCreate(BaseModel):
    """Request model for adding a card to a workstream."""
    card_id: str = Field(..., description="UUID of the card to add")
    status: Optional[str] = Field("inbox", description="Initial status (column)")
    notes: Optional[str] = Field(None, max_length=5000, description="Optional notes")

    @validator('card_id')
    def validate_card_id_format(cls, v):
        """Validate UUID format for card_id."""
        import re
        uuid_pattern = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            re.IGNORECASE
        )
        if not uuid_pattern.match(v):
            raise ValueError('Invalid UUID format for card_id')
        return v

    @validator('status')
    def validate_status(cls, v):
        """Validate status is a valid Kanban column."""
        if v and v not in VALID_WORKSTREAM_CARD_STATUSES:
            raise ValueError(f"Invalid status. Must be one of: {', '.join(sorted(VALID_WORKSTREAM_CARD_STATUSES))}")
        return v or "inbox"


class WorkstreamCardUpdate(BaseModel):
    """Request model for updating a workstream card."""
    status: Optional[str] = Field(None, description="New status (column)")
    position: Optional[int] = Field(None, ge=0, description="New position in column")
    notes: Optional[str] = Field(None, max_length=5000, description="Card notes")
    reminder_at: Optional[str] = Field(None, description="Reminder timestamp (ISO format)")

    @validator('status')
    def validate_status(cls, v):
        """Validate status is a valid Kanban column."""
        if v and v not in VALID_WORKSTREAM_CARD_STATUSES:
            raise ValueError(f"Invalid status. Must be one of: {', '.join(sorted(VALID_WORKSTREAM_CARD_STATUSES))}")
        return v


class WorkstreamCardsGroupedResponse(BaseModel):
    """Response model for cards grouped by status (Kanban view)."""
    inbox: List[WorkstreamCardWithDetails] = []
    screening: List[WorkstreamCardWithDetails] = []
    research: List[WorkstreamCardWithDetails] = []
    brief: List[WorkstreamCardWithDetails] = []
    watching: List[WorkstreamCardWithDetails] = []
    archived: List[WorkstreamCardWithDetails] = []


class AutoPopulateResponse(BaseModel):
    """Response model for auto-populate results."""
    added: int = Field(..., description="Number of cards added")
    cards: List[WorkstreamCardWithDetails] = Field(default=[], description="Cards that were added")


class Note(BaseModel):
    id: str
    content: str
    is_private: bool = False
    created_at: datetime

class NoteCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000, description="Note content")
    is_private: bool = False

    @validator('content')
    def content_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Note content cannot be empty')
        return v.strip()


# Research task models
VALID_TASK_TYPES = {"update", "deep_research", "workstream_analysis"}

class ResearchTaskCreate(BaseModel):
    """Request model for creating a research task."""
    card_id: Optional[str] = Field(None, description="Card ID for card-based research")
    workstream_id: Optional[str] = Field(None, description="Workstream ID for workstream analysis")
    task_type: str = Field(..., description="One of: update, deep_research, workstream_analysis")

    @validator('task_type')
    def task_type_must_be_valid(cls, v):
        if v not in VALID_TASK_TYPES:
            raise ValueError(f"Invalid task_type. Must be one of: {', '.join(VALID_TASK_TYPES)}")
        return v

    @validator('card_id', 'workstream_id')
    def validate_uuid_format(cls, v):
        if v is not None:
            import re
            uuid_pattern = re.compile(
                r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
                re.IGNORECASE
            )
            if not uuid_pattern.match(v):
                raise ValueError('Invalid UUID format')
        return v


class ResearchTask(BaseModel):
    """Response model for research task status."""
    id: str
    user_id: str
    card_id: Optional[str] = None
    workstream_id: Optional[str] = None
    task_type: str
    status: str
    query: Optional[str] = None
    result_summary: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# ============================================================================
# Card Review Workflow Models
# ============================================================================

class CardReviewRequest(BaseModel):
    """Request model for reviewing a discovered card."""
    action: str = Field(..., pattern=r"^(approve|reject|edit_approve)$", description="Review action: approve, reject, or edit_approve")
    updates: Optional[Dict[str, Any]] = Field(None, description="Card field updates (for edit_approve action)")
    reason: Optional[str] = Field(None, max_length=1000, description="Reason for rejection or edit notes")


def get_discovery_max_queries():
    """Get max queries from environment."""
    return int(os.getenv("DISCOVERY_MAX_QUERIES", "100"))

def get_discovery_max_sources():
    """Get max sources from environment."""
    return int(os.getenv("DISCOVERY_MAX_SOURCES_TOTAL", "500"))


class DiscoveryConfigRequest(BaseModel):
    """Request model for discovery run configuration."""
    max_queries_per_run: Optional[int] = Field(None, le=200, ge=1, description="Maximum queries per run (defaults to DISCOVERY_MAX_QUERIES env var)")
    max_sources_total: Optional[int] = Field(None, le=1000, ge=10, description="Maximum sources to process (defaults to DISCOVERY_MAX_SOURCES_TOTAL env var)")
    auto_approve_threshold: float = Field(default=0.95, ge=0.8, le=1.0, description="Auto-approval threshold")
    pillars_filter: Optional[List[str]] = Field(None, description="Filter by pillar IDs")
    dry_run: bool = Field(False, description="Run in dry-run mode without persisting")


class BulkReviewRequest(BaseModel):
    """Request model for bulk card review operations."""
    card_ids: List[str] = Field(..., min_items=1, max_items=100, description="List of card IDs to review")
    action: str = Field(..., pattern=r"^(approve|reject)$", description="Bulk action: approve or reject")
    reason: Optional[str] = Field(None, max_length=500, description="Optional reason for bulk action")


class CardDismissRequest(BaseModel):
    """Request model for user card dismissal."""
    reason: Optional[str] = Field(None, max_length=500, description="Optional reason for dismissal")


class DiscoveryRun(BaseModel):
    """Response model for discovery run status matching database schema."""
    id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str  # running, completed, failed, cancelled
    triggered_by: str  # manual, scheduled, api
    triggered_by_user: Optional[str] = None
    # Discovery metrics
    pillars_scanned: Optional[List[str]] = None
    priorities_scanned: Optional[List[str]] = None
    queries_generated: Optional[int] = None
    sources_found: int = 0
    sources_relevant: Optional[int] = None
    cards_created: int = 0
    cards_enriched: int = 0
    cards_deduplicated: int = 0
    # Cost and reporting
    estimated_cost: Optional[float] = None
    summary_report: Optional[Dict[str, Any]] = None
    # Error handling
    error_message: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    # Timestamps
    created_at: Optional[datetime] = None


class BlockedTopic(BaseModel):
    """Response model for blocked discovery topics."""
    id: str
    topic_pattern: str
    reason: str
    blocked_by_count: int
    created_at: datetime


class SimilarCard(BaseModel):
    """Response model for similar cards."""
    id: str
    name: str
    summary: Optional[str] = None
    similarity: float
    pillar_id: Optional[str] = None


# ============================================================================
# Classification Validation Models
# ============================================================================

# Valid pillar codes for classification validation
# Must match PILLAR_DEFINITIONS in query_generator.py
VALID_PILLAR_CODES = {"CH", "EW", "HG", "HH", "MC", "PS"}

class ValidationSubmission(BaseModel):
    """Request model for submitting ground truth classification labels."""
    card_id: str = Field(..., description="UUID of the card being validated")
    ground_truth_pillar: str = Field(
        ...,
        pattern=r"^[A-Z]{2}$",
        description="Ground truth pillar code (CH, EW, HG, HH, MC, PS)"
    )
    reviewer_id: str = Field(..., min_length=1, description="Identifier for the reviewer")
    notes: Optional[str] = Field(None, max_length=1000, description="Optional reviewer notes")

    @validator('card_id')
    def validate_card_id_format(cls, v):
        """Validate UUID format for card_id."""
        import re
        uuid_pattern = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            re.IGNORECASE
        )
        if not uuid_pattern.match(v):
            raise ValueError('Invalid UUID format for card_id')
        return v

    @validator('ground_truth_pillar')
    def validate_pillar_code(cls, v):
        """Validate pillar code is in allowed list."""
        if v not in VALID_PILLAR_CODES:
            raise ValueError(f"Invalid pillar code. Must be one of: {', '.join(sorted(VALID_PILLAR_CODES))}")
        return v


class ValidationSubmissionResponse(BaseModel):
    """Response model for validation submission."""
    id: str
    card_id: str
    ground_truth_pillar: str
    predicted_pillar: Optional[str] = None
    is_correct: Optional[bool] = None
    reviewer_id: str
    notes: Optional[str] = None
    created_at: datetime


# ============================================================================
# Processing Metrics Models
# ============================================================================

class SourceCategoryMetrics(BaseModel):
    """Metrics for a single source category."""
    category: str
    sources_fetched: int = 0
    articles_processed: int = 0
    cards_generated: int = 0
    errors: int = 0


class DiscoveryRunMetrics(BaseModel):
    """Aggregated metrics for discovery runs."""
    total_runs: int = 0
    completed_runs: int = 0
    failed_runs: int = 0
    avg_cards_per_run: float = 0.0
    avg_sources_per_run: float = 0.0
    total_cards_created: int = 0
    total_cards_enriched: int = 0


class ResearchTaskMetrics(BaseModel):
    """Aggregated metrics for research tasks."""
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    queued_tasks: int = 0
    processing_tasks: int = 0
    avg_processing_time_seconds: Optional[float] = None


class ClassificationMetrics(BaseModel):
    """Classification accuracy metrics."""
    total_validations: int = 0
    correct_count: int = 0
    accuracy_percentage: Optional[float] = None
    target_accuracy: float = 85.0
    meets_target: bool = False


class ProcessingMetrics(BaseModel):
    """
    Comprehensive processing metrics for monitoring dashboard.

    Includes:
    - Source diversity metrics (sources fetched per category)
    - Discovery run metrics (runs, cards generated, etc.)
    - Research task metrics (tasks by status, processing time)
    - Classification accuracy metrics
    - Time period information
    """
    # Time range for metrics
    period_start: datetime
    period_end: datetime
    period_days: int = 7

    # Source diversity metrics
    sources_by_category: List[SourceCategoryMetrics] = []
    total_source_categories: int = 0

    # Discovery run metrics
    discovery_runs: DiscoveryRunMetrics = DiscoveryRunMetrics()

    # Research task metrics
    research_tasks: ResearchTaskMetrics = ResearchTaskMetrics()

    # Classification metrics
    classification: ClassificationMetrics = ClassificationMetrics()

    # Card generation summary
    cards_generated_in_period: int = 0
    cards_with_all_scores: int = 0

    # Error summary
    total_errors: int = 0
    error_rate_percentage: Optional[float] = None


# Authentication dependency
async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get current authenticated user with security logging.

    Validates JWT token via Supabase Auth, which handles:
    - Token signature verification
    - Token expiration checking
    - Token revocation status

    Security features:
    - Logs authentication failures with client IP for audit
    - Returns generic error messages to prevent user enumeration
    - Rate limited at the endpoint level
    """
    try:
        token = credentials.credentials

        # Validate token is not empty and has reasonable length
        if not token or len(token) < 20:
            log_security_event("auth_invalid_token_format", request)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )

        # Validate token with Supabase Auth (handles signature, expiration, revocation)
        response = supabase.auth.get_user(token)

        if response.user:
            # Get user profile
            profile_response = supabase.table("users").select("*").eq("id", response.user.id).execute()
            if profile_response.data:
                # Log successful auth for audit trail (info level, not warning)
                logger.debug(f"Authenticated user: {response.user.id}")
                return profile_response.data[0]
            else:
                # User exists in auth but not in users table - potential issue
                logger.warning(f"User profile not found for authenticated user_id: {response.user.id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User profile not found"
                )
        else:
            # Token was valid format but not a valid session
            log_security_event("auth_invalid_session", request)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )

    except HTTPException:
        raise
    except Exception as e:
        # Log the actual error for debugging but return generic message
        log_security_event(
            "auth_error",
            request,
            {"error_type": type(e).__name__, "error_msg": str(e)[:100]}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )

# API Routes

@app.get("/")
async def root():
    """Health check"""
    return {"status": "ok", "message": "Foresight API is running"}

@app.get("/api/v1/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "database": "connected",
            "ai": "available"
        }
    }


@app.get("/api/v1/debug/gpt-researcher")
async def debug_gpt_researcher():
    """Debug GPT Researcher configuration and Azure OpenAI connection. v2"""
    import os

    # Get GPT Researcher relevant env vars
    config_vars = {
        "SMART_LLM": os.getenv("SMART_LLM", "NOT SET"),
        "FAST_LLM": os.getenv("FAST_LLM", "NOT SET"),
        "EMBEDDING": os.getenv("EMBEDDING", "NOT SET"),
        "LLM_PROVIDER": os.getenv("LLM_PROVIDER", "NOT SET"),
        "EMBEDDING_PROVIDER": os.getenv("EMBEDDING_PROVIDER", "NOT SET"),
        "OPENAI_API_VERSION": os.getenv("OPENAI_API_VERSION", "NOT SET"),
        "AZURE_OPENAI_API_VERSION": os.getenv("AZURE_OPENAI_API_VERSION", "NOT SET"),
        "SCRAPER": os.getenv("SCRAPER", "NOT SET"),
        "AZURE_OPENAI_ENDPOINT": os.getenv("AZURE_OPENAI_ENDPOINT", "NOT SET")[:50] + "..." if os.getenv("AZURE_OPENAI_ENDPOINT") else "NOT SET",
        "AZURE_OPENAI_API_KEY": "SET" if os.getenv("AZURE_OPENAI_API_KEY") else "NOT SET",
        "TAVILY_API_KEY": "SET" if os.getenv("TAVILY_API_KEY") else "NOT SET",
        "FIRECRAWL_API_KEY": "SET" if os.getenv("FIRECRAWL_API_KEY") else "NOT SET",
    }

    # Test GPT Researcher config parsing
    gptr_config_status = "unknown"
    gptr_config_error = None
    parsed_config = {}

    try:
        from gpt_researcher.config import Config
        config = Config()
        parsed_config = {
            "fast_llm_provider": getattr(config, 'fast_llm_provider', 'N/A'),
            "fast_llm_model": getattr(config, 'fast_llm_model', 'N/A'),
            "smart_llm_provider": getattr(config, 'smart_llm_provider', 'N/A'),
            "smart_llm_model": getattr(config, 'smart_llm_model', 'N/A'),
            "embedding_provider": getattr(config, 'embedding_provider', 'N/A'),
            "embedding_model": getattr(config, 'embedding_model', 'N/A'),
        }
        gptr_config_status = "parsed"
    except Exception as e:
        gptr_config_status = "error"
        gptr_config_error = str(e)

    # Test LangChain Azure OpenAI connection (FAST + SMART deployments)
    langchain_tests: Dict[str, Any] = {}

    try:
        from langchain_openai import AzureChatOpenAI

        for label, deployment in [
            ("fast", parsed_config.get("fast_llm_model")),
            ("smart", parsed_config.get("smart_llm_model")),
        ]:
            env_key = "FAST_LLM" if label == "fast" else "SMART_LLM"
            deployment = deployment or os.getenv(env_key, "").split(":")[-1]
            try:
                llm = AzureChatOpenAI(
                    azure_deployment=deployment,
                    api_version=os.getenv("OPENAI_API_VERSION", "2024-05-01-preview"),
                    temperature=0,
                    max_tokens=10,
                )

                response = llm.invoke("Say 'hello' in one word")
                langchain_tests[label] = {
                    "status": "success",
                    "deployment": deployment,
                    "response": response.content if hasattr(response, "content") else str(response),
                    "error": None,
                }
            except Exception as e:
                langchain_tests[label] = {
                    "status": "error",
                    "deployment": deployment,
                    "response": None,
                    "error": str(e),
                }
    except Exception as e:
        langchain_tests["import_error"] = {"status": "error", "error": str(e)}

    # Test GPT Researcher internal LLM utility (closest to agent selection path)
    gptr_llm_test: Dict[str, Any] = {"status": "unknown", "error": None, "response": None}
    try:
        from gpt_researcher.config import Config
        from gpt_researcher.utils.llm import create_chat_completion

        cfg = Config()
        gptr_llm_test["provider"] = getattr(cfg, "smart_llm_provider", None)
        gptr_llm_test["model"] = getattr(cfg, "smart_llm_model", None)

        resp = await create_chat_completion(
            model=cfg.smart_llm_model,
            llm_provider=cfg.smart_llm_provider,
            llm_kwargs=cfg.llm_kwargs,
            messages=[{"role": "user", "content": "Reply with exactly: ok"}],
            temperature=0,
            max_tokens=8,
        )
        gptr_llm_test["status"] = "success"
        gptr_llm_test["response"] = resp
    except Exception as e:
        gptr_llm_test["status"] = "error"
        gptr_llm_test["error"] = str(e)

    return {
        "env_vars": config_vars,
        "gptr_config": {
            "status": gptr_config_status,
            "error": gptr_config_error,
            "parsed": parsed_config,
        },
        "langchain_azure_test": langchain_tests,
        "gptr_llm_test": gptr_llm_test,
    }

# User endpoints
@app.get("/api/v1/me", response_model=UserProfile)
async def get_current_user_profile(current_user: dict = Depends(get_current_user)):
    """Get current user profile"""
    return UserProfile(**current_user)

@app.patch("/api/v1/me", response_model=UserProfile)
async def update_user_profile(
    updates: dict,
    current_user: dict = Depends(get_current_user)
):
    """Update user profile"""
    response = supabase.table("users").update(updates).eq("id", current_user["id"]).execute()
    if response.data:
        return UserProfile(**response.data[0])
    else:
        raise HTTPException(status_code=404, detail="User not found")

# Cards endpoints
@app.get("/api/v1/cards", response_model=List[Card])
async def get_cards(
    limit: int = 20,
    offset: int = 0,
    pillar_id: Optional[str] = None,
    stage_id: Optional[str] = None,
    horizon: Optional[str] = None,
    search: Optional[str] = None
):
    """Get cards with filtering"""
    query = supabase.table("cards").select("*").eq("status", "active")
    
    if pillar_id:
        query = query.eq("pillar_id", pillar_id)
    if stage_id:
        query = query.eq("stage_id", stage_id)
    if horizon:
        query = query.eq("horizon", horizon)
    
    response = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    
    return [Card(**card) for card in response.data]


# NOTE: This route MUST be before /cards/{card_id} to avoid route matching issues
@app.get("/api/v1/cards/pending-review")
async def get_pending_review_cards(
    current_user: dict = Depends(get_current_user),
    limit: int = 20,
    offset: int = 0,
    pillar_id: Optional[str] = None
):
    """
    Get cards pending review.

    Returns discovered cards that need human review, ordered by AI confidence
    (descending) and discovery date.
    """
    # Backward-compatible: include draft cards even if `review_status` wasn't set correctly.
    query = (
        supabase.table("cards")
        .select("*")
        .neq("review_status", "rejected")
        .or_("review_status.in.(discovered,pending_review),status.eq.draft")
    )

    if pillar_id:
        query = query.eq("pillar_id", pillar_id)

    response = query.order(
        "ai_confidence", desc=True
    ).order(
        "discovered_at", desc=True
    ).order(
        "created_at", desc=True
    ).range(offset, offset + limit - 1).execute()

    return response.data


@app.get("/api/v1/cards/{card_id}", response_model=Card)
async def get_card(card_id: uuid.UUID):
    """Get specific card"""
    response = supabase.table("cards").select("*").eq("id", str(card_id)).execute()
    if response.data:
        return Card(**response.data[0])
    else:
        raise HTTPException(status_code=404, detail="Card not found")

@app.post("/api/v1/cards", response_model=Card)
async def create_card(
    card_data: CardCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create new card"""
    # Generate slug from name
    slug = card_data.name.lower().replace(" ", "-").replace(":", "").replace("/", "-")
    
    card_dict = card_data.dict()
    card_dict.update({
        "slug": slug,
        "created_by": current_user["id"],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    })
    
    response = supabase.table("cards").insert(card_dict).execute()
    if response.data:
        return Card(**response.data[0])
    else:
        raise HTTPException(status_code=400, detail="Failed to create card")

@app.post("/api/v1/cards/search")
async def search_cards(
    request: AdvancedSearchRequest
):
    """
    Advanced search for intelligence cards with filtering and vector similarity.

    Supports:
    - Text query with optional vector (semantic) search
    - Filters: pillar_ids, stage_ids, date_range, score_thresholds
    - Pagination with limit and offset

    Returns cards sorted by relevance with search metadata.
    """
    try:
        results = []
        search_type = "vector" if request.use_vector_search and request.query else "text"

        # Vector search path
        if request.use_vector_search and request.query:
            try:
                # Get embedding for search query (uses embedding client with specific API version)
                embedding_response = azure_openai_embedding_client.embeddings.create(
                    model=get_embedding_deployment(),
                    input=request.query
                )
                query_embedding = embedding_response.data[0].embedding

                # Search using vector similarity
                search_response = supabase.rpc(
                    "search_cards",
                    {
                        "query_embedding": query_embedding,
                        "match_threshold": 0.5,
                        "match_count": request.limit + request.offset + 100  # Get extra for filtering
                    }
                ).execute()

                # Process results with similarity scores
                for item in search_response.data or []:
                    item["search_relevance"] = item.get("similarity", 0.0)
                results = search_response.data or []

            except Exception as vector_error:
                logger.warning(f"Vector search failed, falling back to text: {vector_error}")
                search_type = "text"
                results = []

        # Text search path (or fallback)
        if search_type == "text" or (not request.use_vector_search and request.query):
            search_type = "text"
            query_builder = supabase.table("cards").select("*")

            if request.query:
                # Text search on name and summary
                query_builder = query_builder.or_(
                    f"name.ilike.%{request.query}%,summary.ilike.%{request.query}%"
                )

            response = query_builder.limit(request.limit + request.offset + 100).execute()
            results = response.data or []

            # Add placeholder relevance for text search
            for item in results:
                item["search_relevance"] = None

        # If no query provided, fetch all cards (for filter-only searches)
        if not request.query:
            search_type = "filter"
            response = supabase.table("cards").select("*").limit(
                request.limit + request.offset + 100
            ).execute()
            results = response.data or []

        # Apply filters
        if request.filters:
            results = _apply_search_filters(results, request.filters)

        # Get total count before pagination
        total_count = len(results)

        # Apply pagination
        results = results[request.offset:request.offset + request.limit]

        # Convert to response format
        result_items = [
            SearchResultItem(
                id=item.get("id", ""),
                name=item.get("name", ""),
                slug=item.get("slug", ""),
                summary=item.get("summary"),
                description=item.get("description"),
                pillar_id=item.get("pillar_id"),
                goal_id=item.get("goal_id"),
                anchor_id=item.get("anchor_id"),
                stage_id=item.get("stage_id"),
                horizon=item.get("horizon"),
                novelty_score=item.get("novelty_score"),
                maturity_score=item.get("maturity_score"),
                impact_score=item.get("impact_score"),
                relevance_score=item.get("relevance_score"),
                velocity_score=item.get("velocity_score"),
                risk_score=item.get("risk_score"),
                opportunity_score=item.get("opportunity_score"),
                status=item.get("status"),
                created_at=item.get("created_at"),
                updated_at=item.get("updated_at"),
                search_relevance=item.get("search_relevance"),
                match_highlights=_extract_highlights(item, request.query) if request.query else None
            )
            for item in results
        ]

        return AdvancedSearchResponse(
            results=result_items,
            total_count=total_count,
            query=request.query,
            filters_applied=request.filters,
            search_type=search_type
        )

    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


def _apply_search_filters(results: List[Dict[str, Any]], filters: SearchFilters) -> List[Dict[str, Any]]:
    """Apply advanced filters to search results."""
    filtered = results

    # Filter by pillar_ids
    if filters.pillar_ids:
        filtered = [r for r in filtered if r.get("pillar_id") in filters.pillar_ids]

    # Filter by goal_ids
    if filters.goal_ids:
        filtered = [r for r in filtered if r.get("goal_id") in filters.goal_ids]

    # Filter by stage_ids
    if filters.stage_ids:
        filtered = [r for r in filtered if r.get("stage_id") in filters.stage_ids]

    # Filter by horizon
    if filters.horizon and filters.horizon != "ALL":
        filtered = [r for r in filtered if r.get("horizon") == filters.horizon]

    # Filter by status
    if filters.status:
        filtered = [r for r in filtered if r.get("status") == filters.status]

    # Filter by date range
    if filters.date_range:
        if filters.date_range.start:
            start_str = filters.date_range.start.isoformat()
            filtered = [
                r for r in filtered
                if r.get("created_at") and r["created_at"][:10] >= start_str
            ]
        if filters.date_range.end:
            end_str = filters.date_range.end.isoformat()
            filtered = [
                r for r in filtered
                if r.get("created_at") and r["created_at"][:10] <= end_str
            ]

    # Filter by score thresholds
    if filters.score_thresholds:
        filtered = _apply_score_filters(filtered, filters.score_thresholds)

    return filtered


def _apply_score_filters(results: List[Dict[str, Any]], thresholds) -> List[Dict[str, Any]]:
    """Apply score threshold filters to results."""
    filtered = results

    score_fields = [
        ("impact_score", thresholds.impact_score),
        ("relevance_score", thresholds.relevance_score),
        ("novelty_score", thresholds.novelty_score),
        ("maturity_score", thresholds.maturity_score),
        ("velocity_score", thresholds.velocity_score),
        ("risk_score", thresholds.risk_score),
        ("opportunity_score", thresholds.opportunity_score),
    ]

    for field_name, threshold in score_fields:
        if threshold:
            if threshold.min is not None:
                filtered = [
                    r for r in filtered
                    if r.get(field_name) is not None and r[field_name] >= threshold.min
                ]
            if threshold.max is not None:
                filtered = [
                    r for r in filtered
                    if r.get(field_name) is not None and r[field_name] <= threshold.max
                ]

    return filtered


def _extract_highlights(item: Dict[str, Any], query: str) -> Optional[List[str]]:
    """Extract text snippets containing the search query."""
    if not query:
        return None

    highlights = []
    query_lower = query.lower()

    # Check name
    name = item.get("name", "") or ""
    if query_lower in name.lower():
        highlights.append(name)

    # Check summary and extract snippet
    summary = item.get("summary", "") or ""
    if query_lower in summary.lower():
        # Find position and extract context
        pos = summary.lower().find(query_lower)
        start = max(0, pos - 50)
        end = min(len(summary), pos + len(query) + 50)
        snippet = ("..." if start > 0 else "") + summary[start:end] + ("..." if end < len(summary) else "")
        highlights.append(snippet)

    return highlights if highlights else None


# ============================================================================
# SCORE HISTORY TRACKING HELPER
# ============================================================================

# Define all score fields for tracking
SCORE_FIELDS = [
    "novelty_score",
    "maturity_score",
    "impact_score",
    "relevance_score",
    "velocity_score",
    "risk_score",
    "opportunity_score",
]


def _record_score_history(
    old_card_data: Dict[str, Any],
    new_card_data: Dict[str, Any],
    card_id: str
) -> bool:
    """
    Record score history to card_score_history table if any scores have changed.

    Compares old and new card data and inserts a new history record if at least
    one score value has changed. This enables temporal trend tracking.

    Args:
        old_card_data: Card data before the update
        new_card_data: Card data after the update
        card_id: UUID of the card being tracked

    Returns:
        True if a history record was inserted, False otherwise
    """
    # Check if any score has changed
    scores_changed = False
    for field in SCORE_FIELDS:
        old_value = old_card_data.get(field)
        new_value = new_card_data.get(field)
        if old_value != new_value:
            scores_changed = True
            break

    if not scores_changed:
        logger.debug(f"No score changes detected for card {card_id}, skipping history record")
        return False

    try:
        # Prepare the history record with new scores
        now = datetime.now().isoformat()
        history_record = {
            "id": str(uuid.uuid4()),
            "card_id": card_id,
            "recorded_at": now,
            "novelty_score": new_card_data.get("novelty_score"),
            "maturity_score": new_card_data.get("maturity_score"),
            "impact_score": new_card_data.get("impact_score"),
            "relevance_score": new_card_data.get("relevance_score"),
            "velocity_score": new_card_data.get("velocity_score"),
            "risk_score": new_card_data.get("risk_score"),
            "opportunity_score": new_card_data.get("opportunity_score"),
        }

        # Insert the history record
        supabase.table("card_score_history").insert(history_record).execute()
        logger.info(f"Recorded score history for card {card_id}")
        return True

    except Exception as e:
        # Log error but don't fail the main operation
        logger.error(f"Failed to record score history for card {card_id}: {e}")
        return False


def _record_stage_history(
    old_card_data: Dict[str, Any],
    new_card_data: Dict[str, Any],
    card_id: str,
    user_id: Optional[str] = None,
    trigger: str = "manual",
    reason: Optional[str] = None
) -> bool:
    """
    Record stage transition to card_timeline table if stage or horizon has changed.

    Creates a timeline entry with event_type='stage_changed' and includes both
    old and new stage/horizon values for tracking maturity progression.

    Args:
        old_card_data: Card data before the update
        new_card_data: Card data after the update
        card_id: UUID of the card being tracked
        user_id: Optional user ID who triggered the change
        trigger: What triggered the change (manual, api, auto-calculated)
        reason: Optional explanation for the stage change

    Returns:
        True if a history record was inserted, False otherwise
    """
    old_stage = old_card_data.get("stage_id")
    new_stage = new_card_data.get("stage_id")
    old_horizon = old_card_data.get("horizon")
    new_horizon = new_card_data.get("horizon")

    # Check if stage or horizon changed
    if old_stage == new_stage and old_horizon == new_horizon:
        logger.debug(f"No stage/horizon changes detected for card {card_id}")
        return False

    try:
        now = datetime.now().isoformat()
        timeline_entry = {
            "card_id": card_id,
            "event_type": "stage_changed",
            "description": f"Stage changed from {old_stage or 'none'} to {new_stage or 'none'}",
            "user_id": user_id,
            "old_stage_id": int(old_stage) if old_stage else None,
            "new_stage_id": int(new_stage) if new_stage else None,
            "old_horizon": old_horizon,
            "new_horizon": new_horizon,
            "trigger": trigger,
            "reason": reason,
            "metadata": {
                "old_stage_id": old_stage,
                "new_stage_id": new_stage,
                "old_horizon": old_horizon,
                "new_horizon": new_horizon,
            },
            "created_at": now
        }

        supabase.table("card_timeline").insert(timeline_entry).execute()
        logger.info(f"Recorded stage transition for card {card_id}: {old_stage} -> {new_stage}")
        return True

    except Exception as e:
        # Log error but don't fail the main operation
        logger.error(f"Failed to record stage history for card {card_id}: {e}")
        return False


# Card relationships
@app.get("/api/v1/cards/{card_id}/sources")
async def get_card_sources(card_id: str):
    """Get sources for a card"""
    response = supabase.table("sources").select("*").eq("card_id", card_id).order("relevance_score", desc=True).execute()
    return response.data

@app.get("/api/v1/cards/{card_id}/timeline")
async def get_card_timeline(card_id: str):
    """Get timeline for a card"""
    response = supabase.table("card_timeline").select("*").eq("card_id", card_id).order("created_at", desc=True).execute()
    return response.data


@app.get("/api/v1/cards/{card_id}/score-history", response_model=ScoreHistoryResponse)
async def get_card_score_history(
    card_id: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Get historical score data for a card to enable trend visualization.

    Returns a list of score snapshots ordered by recorded_at (most recent first),
    containing all 7 score dimensions (maturity, velocity, novelty, impact,
    relevance, risk, opportunity) for each timestamp.

    Args:
        card_id: UUID of the card to get score history for
        start_date: Optional filter to get records from this date onwards
        end_date: Optional filter to get records up to this date

    Returns:
        ScoreHistoryResponse with list of ScoreHistory records and metadata
    """
    # First verify the card exists
    card_response = supabase.table("cards").select("id").eq("id", card_id).execute()
    if not card_response.data:
        raise HTTPException(status_code=404, detail="Card not found")

    # Build query for score history
    query = supabase.table("card_score_history").select("*").eq("card_id", card_id)

    # Apply date filters if provided
    if start_date:
        query = query.gte("recorded_at", start_date.isoformat())
    if end_date:
        query = query.lte("recorded_at", end_date.isoformat())

    # Execute query ordered by recorded_at descending
    response = query.order("recorded_at", desc=True).execute()

    # Convert to ScoreHistory models
    history_records = [ScoreHistory(**record) for record in response.data] if response.data else []

    return ScoreHistoryResponse(
        history=history_records,
        card_id=card_id,
        total_count=len(history_records),
        start_date=start_date,
        end_date=end_date
    )


@app.get("/api/v1/cards/{card_id}/stage-history", response_model=StageHistoryList)
async def get_card_stage_history(
    card_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get maturity stage transition history for a card.

    Returns a list of stage transitions ordered by changed_at (most recent first),
    tracking maturity stage progression through stages 1-8 and horizon shifts
    (H3 → H2 → H1).

    The data is sourced from the card_timeline table, filtered to only include
    'stage_changed' event types.

    Args:
        card_id: UUID of the card to get stage history for

    Returns:
        StageHistoryList with stage transition records and metadata
    """
    # First verify the card exists
    card_response = supabase.table("cards").select("id").eq("id", card_id).execute()
    if not card_response.data:
        raise HTTPException(status_code=404, detail="Card not found")

    # Query card_timeline for stage change events
    # Filter by event_type='stage_changed' to get only stage transitions
    response = supabase.table("card_timeline").select(
        "id, card_id, created_at, old_stage_id, new_stage_id, old_horizon, new_horizon, trigger, reason"
    ).eq("card_id", card_id).eq("event_type", "stage_changed").order("created_at", desc=True).execute()

    # Convert to StageHistory models, mapping created_at to changed_at
    history_records = []
    if response.data:
        for record in response.data:
            # Skip records that don't have stage change data
            if record.get("new_stage_id") is None:
                continue

            history_records.append(StageHistory(
                id=record["id"],
                card_id=record["card_id"],
                changed_at=record["created_at"],  # Map created_at to changed_at
                old_stage_id=record.get("old_stage_id"),
                new_stage_id=record["new_stage_id"],
                old_horizon=record.get("old_horizon"),
                new_horizon=record.get("new_horizon", "H3"),  # Default to H3 if not set
                trigger=record.get("trigger"),
                reason=record.get("reason")
            ))

    return StageHistoryList(
        history=history_records,
        total_count=len(history_records),
        card_id=card_id
    )


@app.get("/api/v1/cards/{card_id}/related", response_model=RelatedCardsList)
async def get_related_cards(
    card_id: str,
    limit: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """
    Get cards related to the specified card for concept network visualization.

    Returns cards connected to the source card through the card_relationships table,
    including relationship metadata (type and strength) for edge visualization.
    Relationships are bidirectional - cards appear whether they are source or target.

    Args:
        card_id: UUID of the source card to get relationships for
        limit: Maximum number of related cards to return (default: 20)

    Returns:
        RelatedCardsList with related card details and relationship metadata
    """
    # First verify the card exists
    card_response = supabase.table("cards").select("id").eq("id", card_id).execute()
    if not card_response.data:
        raise HTTPException(status_code=404, detail="Card not found")

    # Query relationships where this card is either source or target
    # Get relationships where card is the source
    source_response = supabase.table("card_relationships").select(
        "id, source_card_id, target_card_id, relationship_type, strength, created_at"
    ).eq("source_card_id", card_id).limit(limit).execute()

    # Get relationships where card is the target
    target_response = supabase.table("card_relationships").select(
        "id, source_card_id, target_card_id, relationship_type, strength, created_at"
    ).eq("target_card_id", card_id).limit(limit).execute()

    # Combine and deduplicate relationships
    all_relationships = []
    seen_relationship_ids = set()

    for rel in (source_response.data or []) + (target_response.data or []):
        if rel["id"] not in seen_relationship_ids:
            seen_relationship_ids.add(rel["id"])
            all_relationships.append(rel)

    # If no relationships found, return empty list
    if not all_relationships:
        return RelatedCardsList(
            related_cards=[],
            total_count=0,
            source_card_id=card_id
        )

    # Get the related card IDs (the "other" card in each relationship)
    related_card_ids = set()
    for rel in all_relationships:
        if rel["source_card_id"] == card_id:
            related_card_ids.add(rel["target_card_id"])
        else:
            related_card_ids.add(rel["source_card_id"])

    # Fetch full card details for all related cards
    cards_response = supabase.table("cards").select(
        "id, name, slug, summary, pillar_id, stage_id, horizon"
    ).in_("id", list(related_card_ids)).execute()

    # Create a lookup map for cards
    cards_map = {card["id"]: card for card in (cards_response.data or [])}

    # Build the related cards list with relationship context
    related_cards = []
    for rel in all_relationships:
        # Determine which card is the "related" one (not the source card_id)
        if rel["source_card_id"] == card_id:
            related_id = rel["target_card_id"]
        else:
            related_id = rel["source_card_id"]

        # Get the card details
        card_data = cards_map.get(related_id)
        if not card_data:
            # Skip if card doesn't exist (orphaned relationship)
            continue

        related_cards.append(RelatedCard(
            id=card_data["id"],
            name=card_data["name"],
            slug=card_data["slug"],
            summary=card_data.get("summary"),
            pillar_id=card_data.get("pillar_id"),
            stage_id=card_data.get("stage_id"),
            horizon=card_data.get("horizon"),
            relationship_type=rel["relationship_type"],
            relationship_strength=rel.get("strength"),
            relationship_id=rel["id"]
        ))

    # Limit the results to the specified limit
    related_cards = related_cards[:limit]

    return RelatedCardsList(
        related_cards=related_cards,
        total_count=len(related_cards),
        source_card_id=card_id
    )


@app.get("/api/v1/cards/compare", response_model=CardComparisonResponse)
async def compare_cards(
    card_ids: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Compare two cards side-by-side with their historical data.

    Returns parallel data for both cards including metadata, score history,
    and stage history to enable synchronized timeline charts and comparative
    metrics visualization.

    Args:
        card_ids: Comma-separated list of exactly 2 card UUIDs (e.g., "id1,id2")
        start_date: Optional filter for score history start date
        end_date: Optional filter for score history end date

    Returns:
        CardComparisonResponse with parallel data for both cards

    Raises:
        400: If card_ids doesn't contain exactly 2 IDs
        404: If either card is not found
    """
    # Parse and validate card_ids
    ids = [id.strip() for id in card_ids.split(",") if id.strip()]
    if len(ids) != 2:
        raise HTTPException(
            status_code=400,
            detail="Exactly 2 card IDs must be provided (comma-separated)"
        )

    card_id_1, card_id_2 = ids

    # Helper function to fetch all data for a single card (synchronous)
    def fetch_card_comparison_data(card_id: str) -> CardComparisonItem:
        # Fetch card data
        card_response = supabase.table("cards").select(
            "id, name, slug, summary, pillar_id, goal_id, stage_id, horizon, "
            "maturity_score, velocity_score, novelty_score, impact_score, "
            "relevance_score, risk_score, opportunity_score, created_at, updated_at"
        ).eq("id", card_id).execute()

        if not card_response.data:
            raise HTTPException(status_code=404, detail=f"Card not found: {card_id}")

        card_data = CardData(**card_response.data[0])

        # Fetch score history
        score_query = supabase.table("card_score_history").select("*").eq("card_id", card_id)
        if start_date:
            score_query = score_query.gte("recorded_at", start_date.isoformat())
        if end_date:
            score_query = score_query.lte("recorded_at", end_date.isoformat())
        score_response = score_query.order("recorded_at", desc=True).execute()

        score_history = [ScoreHistory(**record) for record in score_response.data] if score_response.data else []

        # Fetch stage history from card_timeline
        stage_response = supabase.table("card_timeline").select(
            "id, card_id, created_at, old_stage_id, new_stage_id, old_horizon, new_horizon, trigger, reason"
        ).eq("card_id", card_id).eq("event_type", "stage_changed").order("created_at", desc=True).execute()

        stage_history = []
        if stage_response.data:
            for record in stage_response.data:
                if record.get("new_stage_id") is None:
                    continue
                stage_history.append(StageHistory(
                    id=record["id"],
                    card_id=record["card_id"],
                    changed_at=record["created_at"],
                    old_stage_id=record.get("old_stage_id"),
                    new_stage_id=record["new_stage_id"],
                    old_horizon=record.get("old_horizon"),
                    new_horizon=record.get("new_horizon", "H3"),
                    trigger=record.get("trigger"),
                    reason=record.get("reason")
                ))

        return CardComparisonItem(
            card=card_data,
            score_history=score_history,
            stage_history=stage_history
        )

    # Fetch data for both cards in parallel using asyncio.gather with to_thread
    # This allows concurrent execution of the synchronous Supabase operations
    try:
        card1_data, card2_data = await asyncio.gather(
            asyncio.to_thread(fetch_card_comparison_data, card_id_1),
            asyncio.to_thread(fetch_card_comparison_data, card_id_2)
        )
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Error fetching comparison data: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch comparison data")

    return CardComparisonResponse(
        card1=card1_data,
        card2=card2_data,
        comparison_generated_at=datetime.now()
    )


@app.post("/api/v1/cards/{card_id}/follow")
async def follow_card(
    card_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Follow a card"""
    response = supabase.table("card_follows").insert({
        "user_id": current_user["id"],
        "card_id": card_id
    }).execute()
    return {"status": "followed"}

@app.delete("/api/v1/cards/{card_id}/follow")
async def unfollow_card(
    card_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Unfollow a card"""
    response = supabase.table("card_follows").delete().eq("user_id", current_user["id"]).eq("card_id", card_id).execute()
    return {"status": "unfollowed"}

@app.get("/api/v1/me/following")
async def get_following_cards(current_user: dict = Depends(get_current_user)):
    """Get cards followed by current user"""
    response = supabase.table("card_follows").select("""
        *,
        cards!inner(*)
    """).eq("user_id", current_user["id"]).execute()
    return response.data

# Notes endpoints
@app.get("/api/v1/cards/{card_id}/notes")
async def get_card_notes(card_id: str, current_user: dict = Depends(get_current_user)):
    """Get notes for a card"""
    response = supabase.table("card_notes").select("*").eq("card_id", card_id).or_(
        f"user_id.eq.{current_user['id']},is_private.eq.false"
    ).order("created_at", desc=True).execute()
    return [Note(**note) for note in response.data]

@app.post("/api/v1/cards/{card_id}/notes")
async def create_note(
    card_id: str,
    note_data: NoteCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create note for a card"""
    note_dict = note_data.dict()
    note_dict.update({
        "user_id": current_user["id"],
        "card_id": card_id,
        "created_at": datetime.now().isoformat()
    })
    
    response = supabase.table("card_notes").insert(note_dict).execute()
    if response.data:
        return Note(**response.data[0])
    else:
        raise HTTPException(status_code=400, detail="Failed to create note")


# ============================================================================
# Card Export Endpoints
# ============================================================================

@app.get("/api/v1/cards/{card_id}/export/{format}")
async def export_card(
    card_id: str,
    format: str,
    include_charts: bool = True,
    current_user: dict = Depends(get_current_user)
):
    """
    Export a single card in the specified format.

    Supported formats:
    - pdf: Portable Document Format with charts and full details
    - pptx: PowerPoint presentation with formatted slides
    - csv: Comma-Separated Values for data analysis

    Args:
        card_id: UUID of the card to export
        format: Export format (pdf, pptx, csv)
        include_charts: Whether to include visualizations (PDF/PPTX only)

    Returns:
        FileResponse for PDF/PPTX, StreamingResponse for CSV
    """
    # Validate format
    format_lower = format.lower()
    try:
        export_format = ExportFormat(format_lower)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid export format: {format}. Supported formats: pdf, pptx, csv"
        )

    # Fetch card from database with joined reference data
    response = supabase.table("cards").select(
        "*, pillars(name), goals(name), stages(name)"
    ).eq("id", card_id).single().execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Card not found: {card_id}"
        )

    card_data = response.data

    # Extract joined names
    pillar_name = card_data.get("pillars", {}).get("name") if card_data.get("pillars") else None
    goal_name = card_data.get("goals", {}).get("name") if card_data.get("goals") else None
    stage_name = card_data.get("stages", {}).get("name") if card_data.get("stages") else None

    # Fetch latest completed deep research report for this card
    research_report = None
    research_reports = []
    try:
        research_response = supabase.table("research_tasks").select(
            "id, task_type, result_summary, completed_at"
        ).eq("card_id", card_id).eq("status", "completed").eq(
            "task_type", "deep_research"
        ).order("completed_at", desc=True).limit(3).execute()

        if research_response.data:
            for task in research_response.data:
                if task.get("result_summary", {}).get("report_preview"):
                    research_reports.append({
                        "completed_at": task.get("completed_at"),
                        "report": task["result_summary"]["report_preview"]
                    })
            # Use the most recent report as the main one
            if research_reports:
                research_report = research_reports[0]["report"]
    except Exception as e:
        logger.warning(f"Failed to fetch research reports for export: {e}")

    # Create CardExportData from raw data with enriched names and research
    try:
        export_data = CardExportData(
            id=card_data["id"],
            name=card_data["name"],
            slug=card_data.get("slug", ""),
            summary=card_data.get("summary"),
            description=card_data.get("description"),
            pillar_id=card_data.get("pillar_id"),
            pillar_name=pillar_name,
            goal_id=card_data.get("goal_id"),
            goal_name=goal_name,
            anchor_id=card_data.get("anchor_id"),
            stage_id=card_data.get("stage_id"),
            stage_name=stage_name,
            horizon=card_data.get("horizon"),
            novelty_score=card_data.get("novelty_score"),
            maturity_score=card_data.get("maturity_score"),
            impact_score=card_data.get("impact_score"),
            relevance_score=card_data.get("relevance_score"),
            velocity_score=card_data.get("velocity_score"),
            risk_score=card_data.get("risk_score"),
            opportunity_score=card_data.get("opportunity_score"),
            status=card_data.get("status"),
            created_at=card_data.get("created_at"),
            updated_at=card_data.get("updated_at"),
            deep_research_report=research_report,
        )
    except Exception as e:
        logger.error(f"Failed to create CardExportData: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to prepare card data for export"
        )

    # Initialize export service
    export_service = ExportService(supabase)

    # Generate export based on format
    try:
        if export_format == ExportFormat.PDF:
            file_path = await export_service.generate_pdf(export_data, include_charts=include_charts)
            filename = get_export_filename(export_data.name, export_format)
            content_type = EXPORT_CONTENT_TYPES[export_format]

            # Return file response (FastAPI handles cleanup with FileResponse)
            return FileResponse(
                path=file_path,
                filename=filename,
                media_type=content_type,
                background=None  # File will be cleaned up after response is sent
            )

        elif export_format == ExportFormat.PPTX:
            file_path = await export_service.generate_pptx(export_data, include_charts=include_charts)
            filename = get_export_filename(export_data.name, export_format)
            content_type = EXPORT_CONTENT_TYPES[export_format]

            return FileResponse(
                path=file_path,
                filename=filename,
                media_type=content_type,
                background=None
            )

        elif export_format == ExportFormat.CSV:
            csv_content = await export_service.generate_csv(export_data)
            filename = get_export_filename(export_data.name, export_format)
            content_type = EXPORT_CONTENT_TYPES[export_format]

            # Return streaming response for CSV
            return StreamingResponse(
                io.BytesIO(csv_content.encode('utf-8')),
                media_type=content_type,
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"'
                }
            )

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported export format: {format}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Export generation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate export: {str(e)}"
        )


# ============================================================================
# Workstream Export Endpoints
# ============================================================================

@app.get("/api/v1/workstreams/{workstream_id}/export/{format}")
async def export_workstream_report(
    workstream_id: str,
    format: str,
    current_user: dict = Depends(get_current_user),
    include_charts: bool = True,
    max_cards: int = 50
):
    """
    Export a workstream report in the specified format.

    Generates a comprehensive report containing all cards associated with
    the workstream, including summary statistics and visualizations.

    Supported formats:
    - pdf: PDF document with charts and card details
    - pptx: PowerPoint presentation with slides for each card

    Note: CSV export is not supported for workstream reports.
    Use individual card exports for CSV data.

    Args:
        workstream_id: UUID of the workstream to export
        format: Export format ('pdf' or 'pptx')
        current_user: Authenticated user (injected)
        include_charts: Whether to include chart visualizations (default: True)
        max_cards: Maximum number of cards to include (default: 50, max: 100)

    Returns:
        FileResponse with the generated export file

    Raises:
        HTTPException 400: Invalid export format
        HTTPException 403: Not authorized to export this workstream
        HTTPException 404: Workstream not found
        HTTPException 500: Export generation failed
    """
    from pathlib import Path

    # Validate format (only pdf and pptx supported for workstream exports)
    format_lower = format.lower()
    if format_lower not in ["pdf", "pptx"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid export format '{format}'. Workstream reports support 'pdf' or 'pptx' formats only. Use individual card export for CSV."
        )

    # Validate max_cards
    if max_cards < 1 or max_cards > 100:
        max_cards = min(max(max_cards, 1), 100)

    # Verify workstream exists and belongs to user
    ws_response = supabase.table("workstreams").select("*").eq("id", workstream_id).execute()
    if not ws_response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workstream not found"
        )

    workstream = ws_response.data[0]

    # Verify ownership
    if workstream.get("user_id") != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to export this workstream"
        )

    # Initialize export service
    export_service = ExportService(supabase)

    # Get export format enum
    export_format = ExportFormat.PDF if format_lower == "pdf" else ExportFormat.PPTX

    # Generate export file path
    export_path = None

    try:
        if format_lower == "pdf":
            # Generate PDF report
            export_path = await export_service.generate_workstream_pdf(
                workstream_id=workstream_id,
                include_charts=include_charts,
                max_cards=max_cards
            )
        else:
            # Generate PowerPoint report
            # First fetch workstream and cards for PPTX generation
            workstream_data, cards = await export_service.get_workstream_cards(
                workstream_id=workstream_id,
                max_cards=max_cards
            )

            if not workstream_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Workstream not found"
                )

            export_path = await export_service.generate_workstream_pptx(
                workstream=workstream_data,
                cards=cards,
                include_charts=include_charts,
                include_card_details=True
            )

        # Verify file was created
        if not export_path or not Path(export_path).exists():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Export generation failed - file not created"
            )

        # Generate filename for download
        workstream_name = workstream.get("name", "workstream-report")
        filename = get_export_filename(workstream_name, export_format)

        # Get content type
        content_type = EXPORT_CONTENT_TYPES.get(export_format, "application/octet-stream")

        logger.info(f"Workstream export generated: {workstream_id} as {format_lower}")

        # Return file response
        # Note: FileResponse will handle file cleanup after sending
        return FileResponse(
            path=export_path,
            filename=filename,
            media_type=content_type,
            background=None  # Let FileResponse handle the response
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Failed to generate workstream export: {str(e)}")
        # Clean up temp file if it was created
        if export_path and Path(export_path).exists():
            try:
                Path(export_path).unlink()
            except Exception:
                pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export generation failed: {str(e)}"
        )


# ============================================================================
# Card Review Workflow Endpoints
# ============================================================================

@app.get("/api/v1/discovery/pending/count")
async def get_pending_review_count(
    current_user: dict = Depends(get_current_user)
):
    """
    Get count of cards pending review.

    Returns the total number of cards with review_status in
    ('discovered', 'pending_review').

    Returns:
        Object with count field
    """
    response = (
        supabase.table("cards")
        .select("id", count="exact")
        .neq("review_status", "rejected")
        .or_("review_status.in.(discovered,pending_review),status.eq.draft")
        .execute()
    )

    return {"count": response.count or 0}


@app.post("/api/v1/cards/{card_id}/review")
async def review_card(
    card_id: str,
    review_data: CardReviewRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Review a discovered card.

    Actions:
    - approve: Set review_status to 'active', card becomes live
    - reject: Set review_status to 'rejected', record rejection metadata
    - edit_approve: Apply field updates, then set to 'active'

    Args:
        card_id: UUID of the card to review
        review_data: Review action and optional updates/reason

    Returns:
        Updated card data

    Raises:
        HTTPException 404: Card not found
        HTTPException 400: Invalid action or missing required fields
    """
    # Verify card exists
    card_check = supabase.table("cards").select("*").eq("id", card_id).execute()
    if not card_check.data:
        raise HTTPException(status_code=404, detail="Card not found")

    card = card_check.data[0]
    now = datetime.now().isoformat()

    if review_data.action == "approve":
        # Approve the card - set it to active
        update_data = {
            "review_status": "active",
            "status": "active",
            "reviewed_at": now,
            "reviewed_by": current_user["id"],
            "updated_at": now
        }

    elif review_data.action == "reject":
        # Reject the card
        update_data = {
            "review_status": "rejected",
            "rejected_at": now,
            "rejected_by": current_user["id"],
            "rejection_reason": review_data.reason,
            "updated_at": now
        }

    elif review_data.action == "edit_approve":
        # Apply updates then approve
        if not review_data.updates:
            raise HTTPException(
                status_code=400,
                detail="Updates required for edit_approve action"
            )

        # Allowed fields for editing
        allowed_fields = {
            "name", "summary", "description", "pillar_id", "goal_id",
            "anchor_id", "stage_id", "horizon", "novelty_score",
            "maturity_score", "impact_score", "relevance_score"
        }

        # Filter updates to only allowed fields
        update_data = {
            k: v for k, v in review_data.updates.items()
            if k in allowed_fields
        }

        # Add approval metadata
        update_data.update({
            "review_status": "active",
            "status": "active",
            "reviewed_at": now,
            "reviewed_by": current_user["id"],
            "review_notes": review_data.reason,
            "updated_at": now
        })

        # Update slug if name changed
        if "name" in update_data:
            update_data["slug"] = update_data["name"].lower().replace(" ", "-").replace(":", "").replace("/", "-")

    else:
        raise HTTPException(status_code=400, detail="Invalid review action")

    # Perform the update
    response = supabase.table("cards").update(update_data).eq("id", card_id).execute()

    if response.data:
        updated_card = response.data[0]

        # Log the review action to card timeline
        timeline_entry = {
            "card_id": card_id,
            "event_type": f"review_{review_data.action}",
            "description": f"Card {review_data.action}d by reviewer",
            "user_id": current_user["id"],
            "metadata": {
                "action": review_data.action,
                "reason": review_data.reason,
                "updates_applied": list(update_data.keys()) if review_data.action == "edit_approve" else None
            },
            "created_at": now
        }
        supabase.table("card_timeline").insert(timeline_entry).execute()

        # Track score and stage history for edit_approve actions
        if review_data.action == "edit_approve":
            # Record score history if any score fields changed
            _record_score_history(
                old_card_data=card,
                new_card_data=updated_card,
                card_id=card_id
            )

            # Record stage history if stage or horizon changed
            _record_stage_history(
                old_card_data=card,
                new_card_data=updated_card,
                card_id=card_id,
                user_id=current_user.get("id"),
                trigger="review",
                reason=review_data.reason
            )

        return updated_card
    else:
        raise HTTPException(status_code=400, detail="Failed to update card")


@app.post("/api/v1/cards/bulk-review")
@limiter.limit("10/minute")
async def bulk_review_cards(
    request: Request,
    bulk_data: BulkReviewRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Bulk approve or reject multiple cards using batch operations.

    Processes up to 100 cards in a single request using atomic batch updates.
    Cards are verified first, then updated in a single query for consistency.

    Args:
        bulk_data: List of card IDs and action to apply

    Returns:
        Summary with processed count and any failures
    """
    now = datetime.now().isoformat()
    card_ids = bulk_data.card_ids
    failed = []

    try:
        # Step 1: Verify all cards exist in a single query
        existing_cards = supabase.table("cards").select("id").in_("id", card_ids).execute()
        existing_ids = {card["id"] for card in existing_cards.data} if existing_cards.data else set()

        # Identify cards that don't exist
        missing_ids = set(card_ids) - existing_ids
        for missing_id in missing_ids:
            failed.append({"id": missing_id, "error": "Card not found"})

        # Get the list of valid card IDs to process
        valid_ids = list(existing_ids)

        if not valid_ids:
            return {
                "processed": 0,
                "failed": failed
            }

        # Step 2: Prepare update data based on action
        if bulk_data.action == "approve":
            update_data = {
                "review_status": "active",
                "status": "active",
                "reviewed_at": now,
                "reviewed_by": current_user["id"],
                "updated_at": now
            }
        else:  # reject
            update_data = {
                "review_status": "rejected",
                "rejected_at": now,
                "rejected_by": current_user["id"],
                "rejection_reason": bulk_data.reason,
                "updated_at": now
            }

        # Step 3: Batch update all valid cards in a single query
        update_response = supabase.table("cards").update(update_data).in_("id", valid_ids).execute()

        if not update_response.data:
            # If batch update fails entirely, mark all as failed
            for card_id in valid_ids:
                failed.append({"id": card_id, "error": "Batch update failed"})
            return {
                "processed": 0,
                "failed": failed
            }

        # Get the IDs that were actually updated
        updated_ids = [card["id"] for card in update_response.data]
        processed_count = len(updated_ids)

        # Check for any cards that weren't updated (shouldn't happen but handle gracefully)
        not_updated = set(valid_ids) - set(updated_ids)
        for card_id in not_updated:
            failed.append({"id": card_id, "error": "Update did not apply"})

        # Step 4: Batch insert timeline entries for all successfully updated cards
        if updated_ids:
            timeline_entries = [
                {
                    "card_id": card_id,
                    "event_type": f"bulk_review_{bulk_data.action}",
                    "description": f"Card bulk {bulk_data.action}d",
                    "user_id": current_user["id"],
                    "metadata": {"bulk_action": True, "reason": bulk_data.reason},
                    "created_at": now
                }
                for card_id in updated_ids
            ]
            # Insert all timeline entries in a single batch
            supabase.table("card_timeline").insert(timeline_entries).execute()

        return {
            "processed": processed_count,
            "failed": failed
        }

    except Exception as e:
        # If an unexpected error occurs, report it with context
        return {
            "processed": 0,
            "failed": [{"id": "batch_operation", "error": str(e)}]
        }


@app.post("/api/v1/cards/{card_id}/dismiss")
async def dismiss_card(
    card_id: str,
    dismiss_data: Optional[CardDismissRequest] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Dismiss a card for the current user (soft-delete).

    Creates a user_card_dismissals record. If the card has been dismissed
    by 3 or more users, it gets added to discovery_blocks.

    Args:
        card_id: UUID of the card to dismiss
        dismiss_data: Optional reason for dismissal

    Returns:
        Dismissal status and block status if applicable
    """
    # Verify card exists
    card_check = supabase.table("cards").select("id, name").eq("id", card_id).execute()
    if not card_check.data:
        raise HTTPException(status_code=404, detail="Card not found")

    card = card_check.data[0]
    now = datetime.now().isoformat()

    # Check if user already dismissed this card
    existing = supabase.table("user_card_dismissals").select("id").eq(
        "user_id", current_user["id"]
    ).eq("card_id", card_id).execute()

    if existing.data:
        raise HTTPException(status_code=400, detail="Card already dismissed by user")

    # Create dismissal record
    dismissal_record = {
        "user_id": current_user["id"],
        "card_id": card_id,
        "reason": dismiss_data.reason if dismiss_data else None,
        "dismissed_at": now
    }
    supabase.table("user_card_dismissals").insert(dismissal_record).execute()

    # Check total dismissal count for this card
    dismissal_count = supabase.table("user_card_dismissals").select(
        "id", count="exact"
    ).eq("card_id", card_id).execute()

    blocked = False
    if dismissal_count.count >= 3:
        # Add to discovery_blocks if not already blocked
        block_check = supabase.table("discovery_blocks").select("id").eq(
            "card_id", card_id
        ).execute()

        if not block_check.data:
            block_record = {
                "card_id": card_id,
                "topic_pattern": card["name"].lower(),
                "reason": "Dismissed by multiple users",
                "blocked_by_count": dismissal_count.count,
                "created_at": now
            }
            supabase.table("discovery_blocks").insert(block_record).execute()
            blocked = True
            logger.info(f"Card {card_id} blocked from discovery after {dismissal_count.count} dismissals")

    return {
        "status": "dismissed",
        "card_id": card_id,
        "blocked": blocked,
        "total_dismissals": dismissal_count.count
    }


@app.get("/api/v1/cards/{card_id}/similar", response_model=List[SimilarCard])
async def get_similar_cards(
    card_id: str,
    limit: int = 5
):
    """
    Get cards similar to the specified card.

    Uses vector similarity search via the find_similar_cards RPC function
    to find semantically similar cards.

    Args:
        card_id: UUID of the source card
        limit: Maximum number of similar cards to return (default: 5)

    Returns:
        List of similar cards with similarity scores
    """
    # Get the source card's embedding
    card_check = supabase.table("cards").select("id, name, embedding").eq("id", card_id).execute()
    if not card_check.data:
        raise HTTPException(status_code=404, detail="Card not found")

    card = card_check.data[0]

    if not card.get("embedding"):
        # Fallback: return empty list if no embedding
        logger.warning(f"Card {card_id} has no embedding for similarity search")
        return []

    try:
        # Use RPC function for vector similarity search
        response = supabase.rpc(
            "match_cards_by_embedding",
            {
                "query_embedding": card["embedding"],
                "match_threshold": 0.7,
                "match_count": limit + 1  # +1 to exclude self
            }
        ).execute()

        # Filter out the source card itself
        similar_cards = [
            SimilarCard(
                id=c["id"],
                name=c["name"],
                summary=c.get("summary"),
                similarity=c["similarity"],
                pillar_id=c.get("pillar_id")
            )
            for c in response.data
            if c["id"] != card_id
        ][:limit]

        return similar_cards

    except Exception as e:
        logger.error(f"Similar cards search failed: {str(e)}")
        # Fallback to simple text-based similarity
        return []


@app.get("/api/v1/discovery/blocked-topics", response_model=List[BlockedTopic])
async def list_blocked_topics(
    current_user: dict = Depends(get_current_user),
    limit: int = 50,
    offset: int = 0
):
    """
    List blocked discovery topics.

    Returns topics that have been blocked from discovery, either due to
    multiple user dismissals or manual blocking.

    Args:
        limit: Maximum number of blocked topics to return (default: 50)
        offset: Number of topics to skip for pagination

    Returns:
        List of blocked topic records
    """
    response = supabase.table("discovery_blocks").select("*").order(
        "created_at", desc=True
    ).range(offset, offset + limit - 1).execute()

    return [BlockedTopic(**block) for block in response.data]


# ============================================================================
# Classification Validation Endpoints
# ============================================================================

@app.post(
    "/api/v1/validation/submit",
    response_model=ValidationSubmissionResponse,
    status_code=status.HTTP_201_CREATED
)
async def submit_validation_label(
    submission: ValidationSubmission,
    current_user: dict = Depends(get_current_user)
):
    """
    Submit a ground truth classification label for a card.

    Allows reviewers to provide the correct pillar classification for a card,
    enabling accuracy tracking and model improvement. The submission is compared
    against the card's predicted pillar to determine classification correctness.

    Args:
        submission: Validation submission with card_id, ground_truth_pillar, and reviewer_id

    Returns:
        The created validation record with correctness determination

    Raises:
        HTTPException 404: Card not found
        HTTPException 400: Duplicate validation by same reviewer for same card
    """
    now = datetime.now().isoformat()

    # Verify the card exists and get its predicted pillar
    card_check = supabase.table("cards").select("id, pillar_id").eq(
        "id", submission.card_id
    ).execute()

    if not card_check.data:
        raise HTTPException(status_code=404, detail="Card not found")

    card = card_check.data[0]
    predicted_pillar = card.get("pillar_id")

    # Check for duplicate validation by same reviewer
    existing_check = supabase.table("classification_validations").select("id").eq(
        "card_id", submission.card_id
    ).eq("reviewer_id", submission.reviewer_id).execute()

    if existing_check.data:
        raise HTTPException(
            status_code=400,
            detail="Validation already exists for this card by this reviewer"
        )

    # Determine if classification is correct
    is_correct = (
        predicted_pillar == submission.ground_truth_pillar
        if predicted_pillar else None
    )

    # Create validation record
    validation_record = {
        "card_id": submission.card_id,
        "ground_truth_pillar": submission.ground_truth_pillar,
        "predicted_pillar": predicted_pillar,
        "is_correct": is_correct,
        "reviewer_id": submission.reviewer_id,
        "notes": submission.notes,
        "created_at": now,
        "created_by": current_user["id"]
    }

    response = supabase.table("classification_validations").insert(
        validation_record
    ).execute()

    if not response.data:
        raise HTTPException(status_code=500, detail="Failed to create validation record")

    logger.info(
        f"Validation submitted for card {submission.card_id}: "
        f"ground_truth={submission.ground_truth_pillar}, "
        f"predicted={predicted_pillar}, is_correct={is_correct}"
    )

    return ValidationSubmissionResponse(**response.data[0])


@app.get("/api/v1/validation/stats")
async def get_validation_stats(
    current_user: dict = Depends(get_current_user)
):
    """
    Get classification validation statistics.

    Returns aggregate statistics on classification accuracy based on
    submitted ground truth labels.

    Returns:
        Dictionary with total validations, correct count, accuracy percentage
    """
    # Get all validations with correctness determined
    validations_response = supabase.table("classification_validations").select(
        "is_correct"
    ).not_.is_("is_correct", "null").execute()

    if not validations_response.data:
        return {
            "total_validations": 0,
            "correct_count": 0,
            "incorrect_count": 0,
            "accuracy_percentage": None,
            "target_accuracy": 85.0
        }

    total = len(validations_response.data)
    correct = sum(1 for v in validations_response.data if v["is_correct"])
    incorrect = total - correct
    accuracy = (correct / total * 100) if total > 0 else 0

    return {
        "total_validations": total,
        "correct_count": correct,
        "incorrect_count": incorrect,
        "accuracy_percentage": round(accuracy, 2),
        "target_accuracy": 85.0,
        "meets_target": accuracy >= 85.0
    }


@app.get("/api/v1/validation/pending")
async def get_cards_pending_validation(
    current_user: dict = Depends(get_current_user),
    limit: int = 20,
    offset: int = 0
):
    """
    Get cards that need validation (have predictions but no ground truth labels).

    Returns active cards with pillar_id set but no corresponding validation record,
    prioritized by creation date (newest first).

    Args:
        limit: Maximum number of cards to return (default: 20)
        offset: Number of cards to skip for pagination

    Returns:
        List of cards needing validation
    """
    # Get cards with predictions
    cards_response = supabase.table("cards").select(
        "id, name, summary, pillar_id, created_at"
    ).eq("status", "active").not_.is_("pillar_id", "null").order(
        "created_at", desc=True
    ).range(offset, offset + limit - 1).execute()

    if not cards_response.data:
        return []

    # Get card IDs that already have validations
    card_ids = [c["id"] for c in cards_response.data]
    validated_response = supabase.table("classification_validations").select(
        "card_id"
    ).in_("card_id", card_ids).execute()

    validated_ids = {v["card_id"] for v in validated_response.data} if validated_response.data else set()

    # Filter to only cards without validations
    pending_cards = [c for c in cards_response.data if c["id"] not in validated_ids]

    return pending_cards


@app.get("/api/v1/validation/accuracy", response_model=ClassificationMetrics)
async def get_classification_accuracy(
    current_user: dict = Depends(get_current_user),
    days: Optional[int] = None
):
    """
    Compute classification accuracy from validation data.

    Returns detailed accuracy metrics based on submitted ground truth labels,
    including overall accuracy, per-pillar breakdown, and target achievement status.

    The target accuracy is 85% for production-quality classification.

    Args:
        days: Optional number of days to look back (default: all time)

    Returns:
        ClassificationMetrics with:
        - total_validations: Total number of validations with correctness determined
        - correct_count: Number of correct classifications
        - accuracy_percentage: Accuracy as percentage (0-100)
        - target_accuracy: Target accuracy threshold (85%)
        - meets_target: Boolean indicating if target is met

    Note:
        Only validations where is_correct is not null are included in accuracy
        computation. Cards without predicted pillars are excluded.
    """
    from datetime import timedelta

    # Build query for validations with correctness determined
    query = supabase.table("classification_validations").select(
        "is_correct, ground_truth_pillar, predicted_pillar, created_at"
    ).not_.is_("is_correct", "null")

    # Apply date filter if specified
    if days is not None and days > 0:
        period_start = (datetime.now() - timedelta(days=days)).isoformat()
        query = query.gte("created_at", period_start)

    validations_response = query.execute()

    if not validations_response.data:
        # No validations yet - return empty metrics
        return ClassificationMetrics(
            total_validations=0,
            correct_count=0,
            accuracy_percentage=None,
            target_accuracy=85.0,
            meets_target=False
        )

    # Compute accuracy metrics
    total_validations = len(validations_response.data)
    correct_count = sum(1 for v in validations_response.data if v.get("is_correct"))
    accuracy_percentage = (correct_count / total_validations * 100) if total_validations > 0 else None

    logger.info(
        f"Classification accuracy computed: {correct_count}/{total_validations} "
        f"({accuracy_percentage:.2f}% accuracy)" if accuracy_percentage else
        f"Classification accuracy: No validations available"
    )

    return ClassificationMetrics(
        total_validations=total_validations,
        correct_count=correct_count,
        accuracy_percentage=round(accuracy_percentage, 2) if accuracy_percentage else None,
        target_accuracy=85.0,
        meets_target=accuracy_percentage >= 85.0 if accuracy_percentage else False
    )


@app.get("/api/v1/validation/accuracy/by-pillar")
async def get_accuracy_by_pillar(
    current_user: dict = Depends(get_current_user),
    days: Optional[int] = None
):
    """
    Get classification accuracy broken down by pillar.

    Provides per-pillar accuracy metrics to identify which strategic pillars
    have higher or lower classification accuracy, enabling targeted improvement.

    Args:
        days: Optional number of days to look back (default: all time)

    Returns:
        Dictionary with:
        - overall: Overall ClassificationMetrics
        - by_pillar: Dict mapping pillar codes to accuracy metrics
        - confusion_summary: Summary of common misclassifications
    """
    from datetime import timedelta
    from collections import defaultdict

    # Build query for validations with correctness determined
    query = supabase.table("classification_validations").select(
        "is_correct, ground_truth_pillar, predicted_pillar, created_at"
    ).not_.is_("is_correct", "null")

    # Apply date filter if specified
    if days is not None and days > 0:
        period_start = (datetime.now() - timedelta(days=days)).isoformat()
        query = query.gte("created_at", period_start)

    validations_response = query.execute()

    if not validations_response.data:
        return {
            "overall": {
                "total_validations": 0,
                "correct_count": 0,
                "accuracy_percentage": None,
                "target_accuracy": 85.0,
                "meets_target": False
            },
            "by_pillar": {},
            "confusion_summary": []
        }

    # Compute overall metrics
    total_validations = len(validations_response.data)
    correct_count = sum(1 for v in validations_response.data if v.get("is_correct"))
    accuracy_percentage = (correct_count / total_validations * 100) if total_validations > 0 else None

    # Compute per-pillar metrics
    pillar_stats = defaultdict(lambda: {"total": 0, "correct": 0})
    confusion_pairs = defaultdict(int)

    for v in validations_response.data:
        ground_truth = v.get("ground_truth_pillar")
        predicted = v.get("predicted_pillar")
        is_correct = v.get("is_correct")

        if ground_truth:
            pillar_stats[ground_truth]["total"] += 1
            if is_correct:
                pillar_stats[ground_truth]["correct"] += 1
            elif predicted:
                # Track confusion pairs
                confusion_pairs[(predicted, ground_truth)] += 1

    # Format per-pillar results
    by_pillar = {}
    for pillar, stats in pillar_stats.items():
        pillar_accuracy = (stats["correct"] / stats["total"] * 100) if stats["total"] > 0 else None
        by_pillar[pillar] = {
            "total_validations": stats["total"],
            "correct_count": stats["correct"],
            "accuracy_percentage": round(pillar_accuracy, 2) if pillar_accuracy else None,
            "meets_target": pillar_accuracy >= 85.0 if pillar_accuracy else False
        }

    # Format confusion summary (top misclassifications)
    confusion_summary = [
        {
            "predicted": pred,
            "actual": actual,
            "count": count
        }
        for (pred, actual), count in sorted(
            confusion_pairs.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]  # Top 10 confusion pairs
    ]

    return {
        "overall": {
            "total_validations": total_validations,
            "correct_count": correct_count,
            "accuracy_percentage": round(accuracy_percentage, 2) if accuracy_percentage else None,
            "target_accuracy": 85.0,
            "meets_target": accuracy_percentage >= 85.0 if accuracy_percentage else False
        },
        "by_pillar": by_pillar,
        "confusion_summary": confusion_summary
    }


# ============================================================================
# Processing Metrics Endpoints
# ============================================================================

@app.get("/api/v1/metrics/processing", response_model=ProcessingMetrics)
async def get_processing_metrics(
    current_user: dict = Depends(get_current_user),
    days: int = 7
):
    """
    Get comprehensive processing metrics for monitoring dashboard.

    Returns aggregated metrics including:
    - Source diversity (sources fetched per category)
    - Discovery run statistics (completed, failed, cards generated)
    - Research task statistics (by status, avg processing time)
    - Classification accuracy metrics
    - Card generation summary

    Args:
        days: Number of days to look back for metrics (default: 7)

    Returns:
        ProcessingMetrics object with all aggregated metrics
    """
    from datetime import timedelta

    # Calculate time range
    period_end = datetime.now()
    period_start = period_end - timedelta(days=days)
    period_start_iso = period_start.isoformat()

    # -------------------------------------------------------------------------
    # Discovery Run Metrics
    # -------------------------------------------------------------------------
    discovery_runs_response = supabase.table("discovery_runs").select(
        "id, status, cards_created, cards_enriched, sources_found, sources_relevant, summary_report, started_at, completed_at"
    ).gte("started_at", period_start_iso).execute()

    discovery_runs_data = discovery_runs_response.data or []

    completed_runs = [r for r in discovery_runs_data if r.get("status") == "completed"]
    failed_runs = [r for r in discovery_runs_data if r.get("status") == "failed"]

    total_cards_created = sum(r.get("cards_created", 0) or 0 for r in discovery_runs_data)
    total_cards_enriched = sum(r.get("cards_enriched", 0) or 0 for r in discovery_runs_data)
    total_sources = sum(r.get("sources_found", 0) or 0 for r in discovery_runs_data)

    avg_cards_per_run = (
        total_cards_created / len(completed_runs) if completed_runs else 0.0
    )
    avg_sources_per_run = (
        total_sources / len(discovery_runs_data) if discovery_runs_data else 0.0
    )

    discovery_metrics = DiscoveryRunMetrics(
        total_runs=len(discovery_runs_data),
        completed_runs=len(completed_runs),
        failed_runs=len(failed_runs),
        avg_cards_per_run=round(avg_cards_per_run, 2),
        avg_sources_per_run=round(avg_sources_per_run, 2),
        total_cards_created=total_cards_created,
        total_cards_enriched=total_cards_enriched
    )

    # Extract source category metrics from discovery run summary_report
    sources_by_category: Dict[str, SourceCategoryMetrics] = {}
    for run in discovery_runs_data:
        report = run.get("summary_report") or {}
        categories_data = report.get("sources_by_category", {})
        for category, count in categories_data.items():
            if category not in sources_by_category:
                sources_by_category[category] = SourceCategoryMetrics(
                    category=category,
                    sources_fetched=0,
                    articles_processed=0,
                    cards_generated=0,
                    errors=0
                )
            sources_by_category[category].sources_fetched += count if isinstance(count, int) else 0

    # -------------------------------------------------------------------------
    # Research Task Metrics
    # -------------------------------------------------------------------------
    research_tasks_response = supabase.table("research_tasks").select(
        "id, status, started_at, completed_at"
    ).gte("created_at", period_start_iso).execute()

    research_tasks_data = research_tasks_response.data or []

    completed_tasks = [t for t in research_tasks_data if t.get("status") == "completed"]
    failed_tasks = [t for t in research_tasks_data if t.get("status") == "failed"]
    queued_tasks = [t for t in research_tasks_data if t.get("status") == "queued"]
    processing_tasks = [t for t in research_tasks_data if t.get("status") == "processing"]

    # Calculate average processing time for completed tasks
    processing_times = []
    for task in completed_tasks:
        started = task.get("started_at")
        completed = task.get("completed_at")
        if started and completed:
            try:
                start_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(completed.replace("Z", "+00:00"))
                processing_times.append((end_dt - start_dt).total_seconds())
            except (ValueError, TypeError):
                pass

    avg_processing_time = (
        sum(processing_times) / len(processing_times) if processing_times else None
    )

    research_metrics = ResearchTaskMetrics(
        total_tasks=len(research_tasks_data),
        completed_tasks=len(completed_tasks),
        failed_tasks=len(failed_tasks),
        queued_tasks=len(queued_tasks),
        processing_tasks=len(processing_tasks),
        avg_processing_time_seconds=round(avg_processing_time, 2) if avg_processing_time else None
    )

    # -------------------------------------------------------------------------
    # Classification Accuracy Metrics
    # -------------------------------------------------------------------------
    validations_response = supabase.table("classification_validations").select(
        "is_correct"
    ).not_.is_("is_correct", "null").execute()

    validations_data = validations_response.data or []
    total_validations = len(validations_data)
    correct_count = sum(1 for v in validations_data if v.get("is_correct"))
    accuracy = (correct_count / total_validations * 100) if total_validations > 0 else None

    classification_metrics = ClassificationMetrics(
        total_validations=total_validations,
        correct_count=correct_count,
        accuracy_percentage=round(accuracy, 2) if accuracy else None,
        target_accuracy=85.0,
        meets_target=accuracy >= 85.0 if accuracy else False
    )

    # -------------------------------------------------------------------------
    # Card Generation Summary
    # -------------------------------------------------------------------------
    cards_response = supabase.table("cards").select(
        "id, impact_score, velocity_score, novelty_score, risk_score", count="exact"
    ).gte("created_at", period_start_iso).execute()

    cards_data = cards_response.data or []
    cards_generated = len(cards_data)

    # Count cards with all 4 scoring dimensions
    cards_with_all_scores = sum(
        1 for c in cards_data
        if c.get("impact_score") is not None
        and c.get("velocity_score") is not None
        and c.get("novelty_score") is not None
        and c.get("risk_score") is not None
    )

    # -------------------------------------------------------------------------
    # Error Summary
    # -------------------------------------------------------------------------
    total_errors = len(failed_runs) + len(failed_tasks)
    total_operations = len(discovery_runs_data) + len(research_tasks_data)
    error_rate = (total_errors / total_operations * 100) if total_operations > 0 else None

    # -------------------------------------------------------------------------
    # Build Response
    # -------------------------------------------------------------------------
    return ProcessingMetrics(
        period_start=period_start,
        period_end=period_end,
        period_days=days,
        sources_by_category=list(sources_by_category.values()),
        total_source_categories=len(sources_by_category),
        discovery_runs=discovery_metrics,
        research_tasks=research_metrics,
        classification=classification_metrics,
        cards_generated_in_period=cards_generated,
        cards_with_all_scores=cards_with_all_scores,
        total_errors=total_errors,
        error_rate_percentage=round(error_rate, 2) if error_rate else None
    )


# ============================================================================
# Analytics Endpoints
# ============================================================================

# Pillar definitions for analytics (matches database pillars table)
ANALYTICS_PILLAR_DEFINITIONS = {
    "CH": "Community Health",
    "MC": "Mobility & Connectivity",
    "HS": "Housing & Economic Stability",
    "EC": "Economic Development",
    "ES": "Environmental Sustainability",
    "CE": "Cultural & Entertainment"
}


@app.get("/api/v1/analytics/pillar-coverage", response_model=PillarCoverageResponse)
async def get_pillar_coverage(
    current_user: dict = Depends(get_current_user),
    start_date: Optional[str] = Query(None, description="Start date filter (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date filter (ISO format)"),
    stage_id: Optional[str] = Query(None, description="Filter by maturity stage")
):
    """
    Get activity distribution across strategic pillars.

    Returns counts and percentages for all 6 strategic pillars (CH, EW, HG, HH, MC, PS),
    showing how cards are distributed across the organization's strategic focus areas.

    Args:
        start_date: Optional start date filter (ISO format)
        end_date: Optional end date filter (ISO format)
        stage_id: Optional maturity stage filter

    Returns:
        PillarCoverageResponse with pillar distribution data
    """
    try:
        # Build query for active cards with velocity_score for avg calculation
        query = supabase.table("cards").select(
            "pillar_id, velocity_score"
        ).eq("status", "active")

        # Apply date filters if provided
        if start_date:
            query = query.gte("created_at", start_date)
        if end_date:
            query = query.lte("created_at", end_date)

        # Apply stage filter if provided
        if stage_id:
            query = query.eq("stage_id", stage_id)

        response = query.execute()
        cards_data = response.data or []

        # Count cards per pillar and sum velocity scores
        pillar_counts: Dict[str, int] = {}
        pillar_velocity_sums: Dict[str, float] = {}
        for pillar_code in ANALYTICS_PILLAR_DEFINITIONS.keys():
            pillar_counts[pillar_code] = 0
            pillar_velocity_sums[pillar_code] = 0.0

        # Also count cards with null/unknown pillar
        unassigned_count = 0
        for card in cards_data:
            pillar_id = card.get("pillar_id")
            if pillar_id and pillar_id in ANALYTICS_PILLAR_DEFINITIONS:
                pillar_counts[pillar_id] += 1
                velocity = card.get("velocity_score")
                if velocity is not None:
                    pillar_velocity_sums[pillar_id] += velocity
            else:
                unassigned_count += 1

        total_cards = len(cards_data)

        # Build response data with percentages and average velocity
        coverage_data = []
        for pillar_code, pillar_name in ANALYTICS_PILLAR_DEFINITIONS.items():
            count = pillar_counts[pillar_code]
            percentage = (count / total_cards * 100) if total_cards > 0 else 0.0
            avg_velocity = (
                pillar_velocity_sums[pillar_code] / count
                if count > 0 else None
            )
            coverage_data.append(
                PillarCoverageItem(
                    pillar_code=pillar_code,
                    pillar_name=pillar_name,
                    count=count,
                    percentage=round(percentage, 2),
                    avg_velocity=round(avg_velocity, 2) if avg_velocity is not None else None
                )
            )

        # Sort by count descending for better visualization
        coverage_data.sort(key=lambda x: x.count, reverse=True)

        logger.info(
            f"Pillar coverage: {total_cards} cards analyzed, "
            f"{unassigned_count} unassigned"
        )

        return PillarCoverageResponse(
            data=coverage_data,
            total_cards=total_cards,
            period_start=start_date,
            period_end=end_date
        )

    except Exception as e:
        logger.error(f"Failed to get pillar coverage: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get pillar coverage: {str(e)}"
        )


# Strategic Insights Prompt for AI Generation
INSIGHTS_GENERATION_PROMPT = """You are a strategic foresight analyst for the City of Austin municipal government.

Based on the following top emerging trends from our horizon scanning system, generate concise strategic insights for city leadership.

TRENDS DATA:
{trends_data}

For each trend, provide a strategic insight that:
1. Explains the key implications for municipal operations
2. Identifies potential opportunities or risks
3. Suggests actionable next steps for city planners

Respond with JSON:
{{
  "insights": [
    {{
      "trend_name": "Name of the trend",
      "insight": "2-3 sentence strategic insight for city leadership"
    }}
  ]
}}

Keep each insight concise (2-3 sentences) and actionable. Focus on municipal relevance."""


def _compute_card_data_hash(cards: list) -> str:
    """Compute a hash of card data to detect changes for cache invalidation."""
    import hashlib
    data_str = "|".join([
        f"{c.get('id', '')}:{c.get('velocity_score', 0)}:{c.get('impact_score', 0)}"
        for c in sorted(cards, key=lambda x: x.get('id', ''))
    ])
    return hashlib.md5(data_str.encode()).hexdigest()


@app.get("/api/v1/analytics/insights", response_model=InsightsResponse)
async def get_analytics_insights(
    pillar_id: Optional[str] = Query(None, pattern=r"^[A-Z]{2}$", description="Filter by pillar code"),
    limit: int = Query(5, ge=1, le=10, description="Number of insights to generate"),
    force_refresh: bool = Query(False, description="Force regeneration, bypassing cache"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get AI-generated strategic insights for top emerging trends.

    Returns insights for the highest-scoring active cards, optionally filtered by pillar.
    Uses OpenAI to generate strategic insights based on trend data.
    
    Implements 24-hour caching to avoid redundant API calls:
    - Cache key: pillar_id + limit + date
    - Cache invalidated: when top card scores change significantly
    - Force refresh: use force_refresh=true to bypass cache

    If AI service is unavailable, returns an error message with empty insights list.
    """
    import json
    from datetime import date as date_type, timedelta
    
    try:
        # -------------------------------------------------------------------------
        # Step 1: Fetch top cards (needed for both cache check and generation)
        # -------------------------------------------------------------------------
        query = supabase.table("cards").select(
            "id, name, summary, pillar_id, horizon, velocity_score, impact_score, relevance_score, novelty_score"
        ).eq("status", "active")

        if pillar_id:
            query = query.eq("pillar_id", pillar_id)

        response = query.order("velocity_score", desc=True).limit(limit * 2).execute()

        if not response.data:
            return InsightsResponse(
                insights=[],
                generated_at=datetime.now(),
                ai_available=True,
                period_analyzed="No active cards found"
            )

        # Calculate combined scores and sort
        cards_with_scores = []
        for card in response.data:
            velocity = card.get("velocity_score") or 0
            impact = card.get("impact_score") or 0
            relevance = card.get("relevance_score") or 0
            novelty = card.get("novelty_score") or 0
            combined_score = (velocity + impact + relevance + novelty) / 4
            cards_with_scores.append({**card, "combined_score": combined_score})

        cards_with_scores.sort(key=lambda x: x["combined_score"], reverse=True)
        top_cards = cards_with_scores[:limit]

        if not top_cards:
            return InsightsResponse(
                insights=[],
                generated_at=datetime.now(),
                ai_available=True
            )

        # Compute hash for cache validation
        current_hash = _compute_card_data_hash(top_cards)
        top_card_ids = [c["id"] for c in top_cards]

        # -------------------------------------------------------------------------
        # Step 2: Check cache (unless force_refresh)
        # -------------------------------------------------------------------------
        if not force_refresh:
            try:
                cache_response = supabase.table("cached_insights").select(
                    "insights_json, generated_at, card_data_hash"
                ).eq(
                    "pillar_filter", pillar_id
                ).eq(
                    "insight_limit", limit
                ).eq(
                    "cache_date", date_type.today().isoformat()
                ).gt(
                    "expires_at", datetime.now().isoformat()
                ).limit(1).execute()

                if cache_response.data:
                    cached = cache_response.data[0]
                    # Validate cache - check if underlying data changed
                    if cached.get("card_data_hash") == current_hash:
                        logger.info(f"Serving cached insights for pillar={pillar_id}, limit={limit}")
                        cached_json = cached["insights_json"]
                        
                        # Reconstruct response from cached JSON
                        cached_insights = [
                            InsightItem(**item) for item in cached_json.get("insights", [])
                        ]
                        return InsightsResponse(
                            insights=cached_insights,
                            generated_at=datetime.fromisoformat(cached["generated_at"].replace("Z", "+00:00")),
                            ai_available=cached_json.get("ai_available", True),
                            period_analyzed=cached_json.get("period_analyzed"),
                            fallback_message=cached_json.get("fallback_message")
                        )
                    else:
                        logger.info("Cache invalidated - card data changed")
            except Exception as cache_err:
                # Cache check failed - proceed to generate
                logger.warning(f"Cache lookup failed: {cache_err}")

        # -------------------------------------------------------------------------
        # Step 3: Generate new insights via AI
        # -------------------------------------------------------------------------
        start_time = datetime.now()
        
        trends_data = "\n".join([
            f"- {card['name']}: {card.get('summary', 'No summary available')[:200]} "
            f"(Pillar: {card.get('pillar_id', 'N/A')}, Horizon: {card.get('horizon', 'N/A')}, "
            f"Score: {card['combined_score']:.1f})"
            for card in top_cards
        ])

        ai_available = True
        fallback_message = None
        insights = []

        try:
            prompt = INSIGHTS_GENERATION_PROMPT.format(trends_data=trends_data)

            ai_response = openai_client.chat.completions.create(
                model=get_chat_mini_deployment(),
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=1000,
                timeout=30
            )

            result = json.loads(ai_response.choices[0].message.content)

            for i, insight_data in enumerate(result.get("insights", [])):
                if i < len(top_cards):
                    card = top_cards[i]
                    insights.append(InsightItem(
                        trend_name=insight_data.get("trend_name", card["name"]),
                        score=card["combined_score"],
                        insight=insight_data.get("insight", ""),
                        pillar_id=card.get("pillar_id"),
                        card_id=card.get("id"),
                        velocity_score=card.get("velocity_score")
                    ))

        except Exception as ai_error:
            logger.warning(f"AI insights generation failed: {str(ai_error)}")
            ai_available = False
            fallback_message = "AI insights temporarily unavailable. Showing trend summaries instead."

            insights = [
                InsightItem(
                    trend_name=card["name"],
                    score=card["combined_score"],
                    insight=card.get("summary", "No summary available")[:300] if card.get("summary") else "Strategic analysis pending.",
                    pillar_id=card.get("pillar_id"),
                    card_id=card.get("id"),
                    velocity_score=card.get("velocity_score")
                )
                for card in top_cards
            ]

        generation_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        generated_at = datetime.now()
        period_analyzed = f"Top {len(top_cards)} trending cards" + (f" in {pillar_id}" if pillar_id else "")

        # -------------------------------------------------------------------------
        # Step 4: Store in cache
        # -------------------------------------------------------------------------
        try:
            cache_json = {
                "insights": [i.dict() for i in insights],
                "ai_available": ai_available,
                "period_analyzed": period_analyzed,
                "fallback_message": fallback_message
            }
            
            # Upsert cache entry
            supabase.table("cached_insights").upsert({
                "pillar_filter": pillar_id,
                "insight_limit": limit,
                "cache_date": date_type.today().isoformat(),
                "insights_json": cache_json,
                "top_card_ids": top_card_ids,
                "card_data_hash": current_hash,
                "ai_model_used": get_chat_mini_deployment() if ai_available else None,
                "generation_time_ms": generation_time_ms,
                "generated_at": generated_at.isoformat(),
                "expires_at": (generated_at + timedelta(hours=24)).isoformat()
            }, on_conflict="pillar_filter,insight_limit,cache_date").execute()
            
            logger.info(f"Cached insights for pillar={pillar_id}, limit={limit}, took {generation_time_ms}ms")
        except Exception as cache_err:
            logger.warning(f"Failed to cache insights: {cache_err}")

        return InsightsResponse(
            insights=insights,
            generated_at=generated_at,
            ai_available=ai_available,
            period_analyzed=period_analyzed,
            fallback_message=fallback_message
        )

    except Exception as e:
        logger.error(f"Analytics insights endpoint failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Weekly Discovery Scheduler
# ============================================================================

async def run_weekly_discovery():
    """
    Run weekly automated discovery.

    Scheduled to run every Sunday at 2:00 AM UTC. Executes a full
    discovery run with default configuration across all pillars.
    """
    logger.info("Starting weekly discovery run...")

    try:
        # Get system user for automated tasks
        system_user = supabase.table("users").select("id").limit(1).execute()
        user_id = system_user.data[0]["id"] if system_user.data else None

        if not user_id:
            logger.warning("Weekly discovery: No system user found, skipping")
            return

        # Create discovery run with default config
        run_id = str(uuid.uuid4())
        config = DiscoveryConfigRequest()  # Default values

        run_record = {
            "id": run_id,
            "status": "running",
            "triggered_by": "scheduled",
            "triggered_by_user": user_id,
            "cards_created": 0,
            "cards_enriched": 0,
            "cards_deduplicated": 0,
            "sources_found": 0,
            "started_at": datetime.now().isoformat(),
            "summary_report": {"stage": "queued", "config": config.dict()}
        }

        supabase.table("discovery_runs").insert(run_record).execute()

        logger.info(f"Weekly discovery run queued: {run_id}")

    except Exception as e:
        logger.error(f"Weekly discovery failed: {str(e)}")


# Workstreams endpoints
@app.get("/api/v1/me/workstreams")
async def get_user_workstreams(current_user: dict = Depends(get_current_user)):
    """Get user's workstreams"""
    response = supabase.table("workstreams").select("*").eq("user_id", current_user["id"]).order("created_at", desc=True).execute()
    return [Workstream(**ws) for ws in response.data]

@app.post("/api/v1/me/workstreams")
async def create_workstream(
    workstream_data: WorkstreamCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create new workstream"""
    ws_dict = workstream_data.dict()
    ws_dict.update({
        "user_id": current_user["id"],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    })

    response = supabase.table("workstreams").insert(ws_dict).execute()
    if response.data:
        return Workstream(**response.data[0])
    else:
        raise HTTPException(status_code=400, detail="Failed to create workstream")


@app.patch("/api/v1/me/workstreams/{workstream_id}", response_model=Workstream)
async def update_workstream(
    workstream_id: str,
    workstream_data: WorkstreamUpdate,
    current_user: dict = Depends(get_current_user)
):
    """
    Update an existing workstream.

    - Verifies the workstream belongs to the current user
    - Accepts partial updates (any field can be updated)
    - Returns the updated workstream

    Args:
        workstream_id: UUID of the workstream to update
        workstream_data: Partial update data
        current_user: Authenticated user (injected)

    Returns:
        Updated Workstream object

    Raises:
        HTTPException 404: Workstream not found
        HTTPException 403: Workstream belongs to another user
    """
    # First check if workstream exists
    ws_check = supabase.table("workstreams").select("*").eq("id", workstream_id).execute()
    if not ws_check.data:
        raise HTTPException(status_code=404, detail="Workstream not found")

    # Verify ownership
    if ws_check.data[0]["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to update this workstream")

    # Build update dict with only non-None values
    update_dict = {k: v for k, v in workstream_data.dict().items() if v is not None}

    if not update_dict:
        # No updates provided, return existing workstream
        return Workstream(**ws_check.data[0])

    # Add updated_at timestamp
    update_dict["updated_at"] = datetime.now().isoformat()

    # Perform update
    response = supabase.table("workstreams").update(update_dict).eq("id", workstream_id).execute()
    if response.data:
        return Workstream(**response.data[0])
    else:
        raise HTTPException(status_code=400, detail="Failed to update workstream")


@app.delete("/api/v1/me/workstreams/{workstream_id}")
async def delete_workstream(
    workstream_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a workstream.

    - Verifies the workstream belongs to the current user
    - Permanently deletes the workstream

    Args:
        workstream_id: UUID of the workstream to delete
        current_user: Authenticated user (injected)

    Returns:
        Success message

    Raises:
        HTTPException 404: Workstream not found
        HTTPException 403: Workstream belongs to another user
    """
    # First check if workstream exists
    ws_check = supabase.table("workstreams").select("*").eq("id", workstream_id).execute()
    if not ws_check.data:
        raise HTTPException(status_code=404, detail="Workstream not found")

    # Verify ownership
    if ws_check.data[0]["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to delete this workstream")

    # Perform delete
    response = supabase.table("workstreams").delete().eq("id", workstream_id).execute()

    return {"status": "deleted", "message": "Workstream successfully deleted"}


@app.get("/api/v1/me/workstreams/{workstream_id}/feed")
async def get_workstream_feed(
    workstream_id: str,
    current_user: dict = Depends(get_current_user),
    limit: int = 20,
    offset: int = 0
):
    """
    Get cards for a workstream with filtering support.

    Filters cards based on workstream configuration:
    - pillar_ids: Filter by pillar IDs
    - goal_ids: Filter by goal IDs
    - stage_ids: Filter by stage IDs
    - horizon: Filter by horizon (H1, H2, H3, ALL)
    - keywords: Search card name/summary/description for keywords

    Args:
        workstream_id: UUID of the workstream
        current_user: Authenticated user (injected)
        limit: Maximum number of cards to return (default: 20)
        offset: Number of cards to skip for pagination (default: 0)

    Returns:
        List of Card objects matching workstream filters

    Raises:
        HTTPException 404: Workstream not found or not owned by user
    """
    # Verify workstream belongs to user
    ws_response = supabase.table("workstreams").select("*").eq("id", workstream_id).eq("user_id", current_user["id"]).execute()
    if not ws_response.data:
        raise HTTPException(status_code=404, detail="Workstream not found")

    workstream = ws_response.data[0]

    # Build query based on workstream filters
    query = supabase.table("cards").select("*").eq("status", "active")

    # Filter by pillar_ids
    if workstream.get("pillar_ids"):
        query = query.in_("pillar_id", workstream["pillar_ids"])

    # Filter by goal_ids
    if workstream.get("goal_ids"):
        query = query.in_("goal_id", workstream["goal_ids"])

    # Note: stage_ids filter applied in Python because card stage_id format
    # is "5_implementing" while workstream stores ["4", "5", "6"]

    # Filter by horizon (skip if ALL)
    if workstream.get("horizon") and workstream["horizon"] != "ALL":
        query = query.eq("horizon", workstream["horizon"])

    response = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    cards = response.data or []

    # Apply stage filtering (extract number prefix from stage_id like "5_implementing")
    stage_ids = workstream.get("stage_ids", [])
    if stage_ids:
        filtered_by_stage = []
        for card in cards:
            card_stage_id = card.get("stage_id") or ""
            stage_num = card_stage_id.split("_")[0] if "_" in card_stage_id else card_stage_id
            if stage_num in stage_ids:
                filtered_by_stage.append(card)
        cards = filtered_by_stage

    # Apply keyword filtering in Python (PostgREST doesn't support OR across multiple text columns easily)
    keywords = workstream.get("keywords", [])
    if keywords:
        filtered_cards = []
        for card in cards:
            card_text = " ".join([
                (card.get("name") or "").lower(),
                (card.get("summary") or "").lower(),
                (card.get("description") or "").lower()
            ])
            # Check if any keyword matches (case-insensitive)
            if any(keyword.lower() in card_text for keyword in keywords):
                filtered_cards.append(card)
        return filtered_cards

    return cards


# ============================================================================
# Workstream Kanban Card Endpoints
# ============================================================================

@app.get("/api/v1/me/workstreams/{workstream_id}/cards", response_model=WorkstreamCardsGroupedResponse)
async def get_workstream_cards(
    workstream_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get all cards in a workstream grouped by status (Kanban view).

    Returns cards organized into columns:
    - inbox: Newly added cards awaiting review
    - screening: Cards being screened for relevance
    - research: Cards actively being researched
    - brief: Cards with completed briefs
    - watching: Cards being monitored for updates
    - archived: Archived cards

    Each card includes full card details joined from the cards table.

    Args:
        workstream_id: UUID of the workstream
        current_user: Authenticated user (injected)

    Returns:
        WorkstreamCardsGroupedResponse with cards grouped by status

    Raises:
        HTTPException 404: Workstream not found or not owned by user
    """
    # Verify workstream belongs to user
    ws_response = supabase.table("workstreams").select("id, user_id").eq("id", workstream_id).execute()
    if not ws_response.data:
        raise HTTPException(status_code=404, detail="Workstream not found")

    if ws_response.data[0]["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to access this workstream")

    # Fetch all cards with joined card details, ordered by position
    cards_response = supabase.table("workstream_cards").select(
        "*, cards(*)"
    ).eq("workstream_id", workstream_id).order("position").execute()

    # Group cards by status
    grouped = {
        "inbox": [],
        "screening": [],
        "research": [],
        "brief": [],
        "watching": [],
        "archived": []
    }

    for item in cards_response.data or []:
        card_status = item.get("status", "inbox")
        if card_status not in grouped:
            card_status = "inbox"

        card_with_details = WorkstreamCardWithDetails(
            id=item["id"],
            workstream_id=item["workstream_id"],
            card_id=item["card_id"],
            added_by=item["added_by"],
            added_at=item["added_at"],
            status=item.get("status", "inbox"),
            position=item.get("position", 0),
            notes=item.get("notes"),
            reminder_at=item.get("reminder_at"),
            added_from=item.get("added_from", "manual"),
            updated_at=item.get("updated_at"),
            card=item.get("cards")
        )
        grouped[card_status].append(card_with_details)

    return WorkstreamCardsGroupedResponse(**grouped)


@app.post("/api/v1/me/workstreams/{workstream_id}/cards", response_model=WorkstreamCardWithDetails)
async def add_card_to_workstream(
    workstream_id: str,
    card_data: WorkstreamCardCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Add a card to a workstream.

    The card will be added with the specified status (defaults to 'inbox')
    and positioned at the end of that column.

    Args:
        workstream_id: UUID of the workstream
        card_data: Card addition request (card_id, optional status/notes)
        current_user: Authenticated user (injected)

    Returns:
        WorkstreamCardWithDetails with the created card association

    Raises:
        HTTPException 404: Workstream or card not found
        HTTPException 403: Not authorized
        HTTPException 409: Card already in workstream
    """
    # Verify workstream belongs to user
    ws_response = supabase.table("workstreams").select("id, user_id").eq("id", workstream_id).execute()
    if not ws_response.data:
        raise HTTPException(status_code=404, detail="Workstream not found")

    if ws_response.data[0]["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to add cards to this workstream")

    # Verify card exists
    card_response = supabase.table("cards").select("*").eq("id", card_data.card_id).execute()
    if not card_response.data:
        raise HTTPException(status_code=404, detail="Card not found")

    # Check if card is already in workstream
    existing = supabase.table("workstream_cards").select("id").eq(
        "workstream_id", workstream_id
    ).eq("card_id", card_data.card_id).execute()
    if existing.data:
        raise HTTPException(status_code=409, detail="Card is already in this workstream")

    # Get max position for the target status column
    status = card_data.status or "inbox"
    position_response = supabase.table("workstream_cards").select("position").eq(
        "workstream_id", workstream_id
    ).eq("status", status).order("position", desc=True).limit(1).execute()

    next_position = 0
    if position_response.data:
        next_position = position_response.data[0]["position"] + 1

    # Create workstream card record
    now = datetime.now().isoformat()
    new_card = {
        "workstream_id": workstream_id,
        "card_id": card_data.card_id,
        "added_by": current_user["id"],
        "added_at": now,
        "status": status,
        "position": next_position,
        "notes": card_data.notes,
        "added_from": "manual",
        "updated_at": now
    }

    result = supabase.table("workstream_cards").insert(new_card).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to add card to workstream")

    inserted = result.data[0]
    return WorkstreamCardWithDetails(
        id=inserted["id"],
        workstream_id=inserted["workstream_id"],
        card_id=inserted["card_id"],
        added_by=inserted["added_by"],
        added_at=inserted["added_at"],
        status=inserted.get("status", "inbox"),
        position=inserted.get("position", 0),
        notes=inserted.get("notes"),
        reminder_at=inserted.get("reminder_at"),
        added_from=inserted.get("added_from", "manual"),
        updated_at=inserted.get("updated_at"),
        card=card_response.data[0]
    )


@app.patch("/api/v1/me/workstreams/{workstream_id}/cards/{card_id}", response_model=WorkstreamCardWithDetails)
async def update_workstream_card(
    workstream_id: str,
    card_id: str,
    update_data: WorkstreamCardUpdate,
    current_user: dict = Depends(get_current_user)
):
    """
    Update a workstream card's status, position, notes, or reminder.

    When changing status (moving to a different column), the card is placed
    at the end of the new column unless a specific position is provided.

    Args:
        workstream_id: UUID of the workstream
        card_id: UUID of the card
        update_data: Update request (status, position, notes, reminder_at)
        current_user: Authenticated user (injected)

    Returns:
        WorkstreamCardWithDetails with updated data

    Raises:
        HTTPException 404: Workstream or card not found
        HTTPException 403: Not authorized
    """
    # Verify workstream belongs to user
    ws_response = supabase.table("workstreams").select("id, user_id").eq("id", workstream_id).execute()
    if not ws_response.data:
        raise HTTPException(status_code=404, detail="Workstream not found")

    if ws_response.data[0]["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to update cards in this workstream")

    # Fetch the workstream card by its junction table ID (card_id param is actually workstream_card.id)
    # The frontend passes the workstream_card junction table ID, not the underlying card UUID
    wsc_response = supabase.table("workstream_cards").select("*, cards(*)").eq(
        "workstream_id", workstream_id
    ).eq("id", card_id).execute()

    if not wsc_response.data:
        raise HTTPException(status_code=404, detail="Card not found in this workstream")

    existing = wsc_response.data[0]
    workstream_card_id = existing["id"]

    # Build update dict
    update_dict = {"updated_at": datetime.now().isoformat()}

    if update_data.status is not None:
        # If status changed, recalculate position
        if update_data.status != existing.get("status"):
            # Get max position in new column
            position_response = supabase.table("workstream_cards").select("position").eq(
                "workstream_id", workstream_id
            ).eq("status", update_data.status).order("position", desc=True).limit(1).execute()

            next_position = 0
            if position_response.data:
                next_position = position_response.data[0]["position"] + 1

            update_dict["status"] = update_data.status
            update_dict["position"] = update_data.position if update_data.position is not None else next_position
        else:
            update_dict["status"] = update_data.status
            if update_data.position is not None:
                update_dict["position"] = update_data.position
    elif update_data.position is not None:
        update_dict["position"] = update_data.position

    if update_data.notes is not None:
        update_dict["notes"] = update_data.notes

    if update_data.reminder_at is not None:
        update_dict["reminder_at"] = update_data.reminder_at

    # Perform update
    result = supabase.table("workstream_cards").update(update_dict).eq("id", workstream_card_id).execute()

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to update workstream card")

    updated = result.data[0]

    # Re-fetch with card details for response
    final_response = supabase.table("workstream_cards").select("*, cards(*)").eq(
        "id", workstream_card_id
    ).execute()

    if not final_response.data:
        raise HTTPException(status_code=500, detail="Failed to retrieve updated card")

    item = final_response.data[0]
    return WorkstreamCardWithDetails(
        id=item["id"],
        workstream_id=item["workstream_id"],
        card_id=item["card_id"],
        added_by=item["added_by"],
        added_at=item["added_at"],
        status=item.get("status", "inbox"),
        position=item.get("position", 0),
        notes=item.get("notes"),
        reminder_at=item.get("reminder_at"),
        added_from=item.get("added_from", "manual"),
        updated_at=item.get("updated_at"),
        card=item.get("cards")
    )


@app.delete("/api/v1/me/workstreams/{workstream_id}/cards/{card_id}")
async def remove_card_from_workstream(
    workstream_id: str,
    card_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Remove a card from a workstream.

    This only removes the association; the card itself is not deleted.

    Args:
        workstream_id: UUID of the workstream
        card_id: UUID of the card
        current_user: Authenticated user (injected)

    Returns:
        Success message

    Raises:
        HTTPException 404: Workstream or card not found
        HTTPException 403: Not authorized
    """
    # Verify workstream belongs to user
    ws_response = supabase.table("workstreams").select("id, user_id").eq("id", workstream_id).execute()
    if not ws_response.data:
        raise HTTPException(status_code=404, detail="Workstream not found")

    if ws_response.data[0]["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to remove cards from this workstream")

    # Check card exists in workstream (card_id param is actually workstream_card.id - the junction table ID)
    existing = supabase.table("workstream_cards").select("id").eq(
        "workstream_id", workstream_id
    ).eq("id", card_id).execute()

    if not existing.data:
        raise HTTPException(status_code=404, detail="Card not found in this workstream")

    # Delete the association
    supabase.table("workstream_cards").delete().eq(
        "workstream_id", workstream_id
    ).eq("id", card_id).execute()

    return {"status": "removed", "message": "Card removed from workstream"}


@app.post("/api/v1/me/workstreams/{workstream_id}/cards/{card_id}/deep-dive", response_model=ResearchTask)
async def trigger_card_deep_dive(
    workstream_id: str,
    card_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Trigger deep research for a card in the workstream.

    Creates a research task with task_type='deep_research' for the specified card.
    The research runs asynchronously; poll GET /research/{task_id} for status.

    Rate limited to 2 deep research requests per card per day.

    Args:
        workstream_id: UUID of the workstream
        card_id: UUID of the card
        current_user: Authenticated user (injected)

    Returns:
        ResearchTask with the created task details

    Raises:
        HTTPException 404: Workstream or card not found
        HTTPException 403: Not authorized
        HTTPException 429: Daily rate limit exceeded
    """
    # Verify workstream belongs to user
    ws_response = supabase.table("workstreams").select("id, user_id").eq("id", workstream_id).execute()
    if not ws_response.data:
        raise HTTPException(status_code=404, detail="Workstream not found")

    if ws_response.data[0]["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to access this workstream")

    # Verify card exists in workstream (card_id param is actually workstream_card.id - the junction table ID)
    wsc_response = supabase.table("workstream_cards").select("id, card_id").eq(
        "workstream_id", workstream_id
    ).eq("id", card_id).execute()

    if not wsc_response.data:
        raise HTTPException(status_code=404, detail="Card not found in this workstream")

    # Get the actual underlying card UUID for research
    actual_card_id = wsc_response.data[0]["card_id"]

    # Check rate limit for deep research
    service = ResearchService(supabase, openai_client)
    if not await service.check_rate_limit(actual_card_id):
        raise HTTPException(status_code=429, detail="Daily deep research limit reached (2 per card)")

    # Create research task using the actual underlying card UUID
    task_record = {
        "user_id": current_user["id"],
        "card_id": actual_card_id,
        "task_type": "deep_research",
        "status": "queued"
    }

    task_result = supabase.table("research_tasks").insert(task_record).execute()

    if not task_result.data:
        raise HTTPException(status_code=500, detail="Failed to create research task")

    task = task_result.data[0]

    # Task execution is handled by the background worker (see `app.worker`).
    return ResearchTask(**task)


@app.post("/api/v1/me/workstreams/{workstream_id}/cards/{card_id}/quick-update", response_model=ResearchTask)
async def trigger_card_quick_update(
    workstream_id: str,
    card_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Trigger a quick 5-source update for a card in the workstream.

    Creates a research task with task_type='quick_update' for the specified card.
    This is a lighter-weight research update compared to deep_research.
    The research runs asynchronously; poll GET /research/{task_id} for status.

    Args:
        workstream_id: UUID of the workstream
        card_id: UUID of the workstream card (junction table ID)
        current_user: Authenticated user (injected)

    Returns:
        ResearchTask with the created task details

    Raises:
        HTTPException 404: Workstream or card not found
        HTTPException 403: Not authorized
    """
    # Verify workstream belongs to user
    ws_response = supabase.table("workstreams").select("id, user_id").eq("id", workstream_id).execute()
    if not ws_response.data:
        raise HTTPException(status_code=404, detail="Workstream not found")

    if ws_response.data[0]["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to access this workstream")

    # Verify card exists in workstream (card_id param is actually workstream_card.id - the junction table ID)
    wsc_response = supabase.table("workstream_cards").select("id, card_id").eq(
        "workstream_id", workstream_id
    ).eq("id", card_id).execute()

    if not wsc_response.data:
        raise HTTPException(status_code=404, detail="Card not found in this workstream")

    # Get the actual underlying card UUID for research
    actual_card_id = wsc_response.data[0]["card_id"]

    # Create research task using the actual underlying card UUID
    # task_type='quick_update' signals the worker to do a lighter 5-source update
    task_record = {
        "user_id": current_user["id"],
        "card_id": actual_card_id,
        "task_type": "quick_update",
        "status": "queued"
    }

    task_result = supabase.table("research_tasks").insert(task_record).execute()

    if not task_result.data:
        raise HTTPException(status_code=500, detail="Failed to create research task")

    task = task_result.data[0]

    # Task execution is handled by the background worker (see `app.worker`).
    return ResearchTask(**task)


@app.post("/api/v1/me/workstreams/{workstream_id}/cards/{card_id}/check-updates", response_model=ResearchTask)
async def trigger_card_check_updates(
    workstream_id: str,
    card_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Check for updates on a watched card.

    This is an alias for quick-update, used by the kanban board's "Check for Updates"
    action on cards in the Watching column. Creates a research task with task_type='quick_update'.

    Args:
        workstream_id: UUID of the workstream
        card_id: UUID of the workstream card (junction table ID)
        current_user: Authenticated user (injected)

    Returns:
        ResearchTask with the created task details

    Raises:
        HTTPException 404: Workstream or card not found
        HTTPException 403: Not authorized
    """
    # Delegate to the quick-update implementation
    return await trigger_card_quick_update(workstream_id, card_id, current_user)


class WorkstreamResearchStatus(BaseModel):
    """Research status for a card in a workstream."""
    card_id: str = Field(..., description="UUID of the underlying card")
    task_id: str = Field(..., description="UUID of the research task")
    task_type: str = Field(..., description="Type of research (quick_update, deep_research)")
    status: str = Field(..., description="Task status (queued, processing, completed, failed)")
    started_at: Optional[datetime] = Field(None, description="When research started")
    completed_at: Optional[datetime] = Field(None, description="When research completed")


class WorkstreamResearchStatusResponse(BaseModel):
    """Response containing active research tasks for a workstream's cards."""
    tasks: List[WorkstreamResearchStatus] = Field(default=[], description="Active research tasks")


@app.get("/api/v1/me/workstreams/{workstream_id}/research-status", response_model=WorkstreamResearchStatusResponse)
async def get_workstream_research_status(
    workstream_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get active research tasks for cards in a workstream.

    Returns all research tasks (queued, processing) and recently completed tasks (last hour)
    for cards that are in the specified workstream. Used to show research progress indicators.

    Args:
        workstream_id: UUID of the workstream
        current_user: Authenticated user (injected)

    Returns:
        WorkstreamResearchStatusResponse with list of active tasks

    Raises:
        HTTPException 404: Workstream not found
        HTTPException 403: Not authorized
    """
    # Verify workstream belongs to user
    ws_response = supabase.table("workstreams").select("id, user_id").eq("id", workstream_id).execute()
    if not ws_response.data:
        raise HTTPException(status_code=404, detail="Workstream not found")

    if ws_response.data[0]["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to access this workstream")

    # Get all card_ids in this workstream
    wsc_response = supabase.table("workstream_cards").select("card_id").eq(
        "workstream_id", workstream_id
    ).execute()

    if not wsc_response.data:
        return WorkstreamResearchStatusResponse(tasks=[])

    card_ids = [item["card_id"] for item in wsc_response.data if item.get("card_id")]
    
    # If no valid card_ids, return empty response
    if not card_ids:
        return WorkstreamResearchStatusResponse(tasks=[])

    # Get research tasks for these cards that are:
    # - Currently active (queued or processing)
    # - Recently completed/failed (within last hour for feedback)
    try:
        one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

        # Query active tasks
        active_tasks = supabase.table("research_tasks").select(
            "id, card_id, task_type, status, started_at, completed_at"
        ).in_("card_id", card_ids).in_(
            "status", ["queued", "processing"]
        ).execute()

        # Query recently completed tasks
        recent_tasks = supabase.table("research_tasks").select(
            "id, card_id, task_type, status, started_at, completed_at"
        ).in_("card_id", card_ids).in_(
            "status", ["completed", "failed"]
        ).gte("completed_at", one_hour_ago).execute()
    except Exception as e:
        logger.warning(f"Error querying research tasks: {e}")
        return WorkstreamResearchStatusResponse(tasks=[])

    # Combine and format results
    all_tasks = (active_tasks.data or []) + (recent_tasks.data or [])

    # Deduplicate by card_id, keeping the most recent task per card
    task_by_card: Dict[str, dict] = {}
    for task in all_tasks:
        card_id = task["card_id"]
        if card_id not in task_by_card:
            task_by_card[card_id] = task
        else:
            # Keep the more recent task (prefer active over completed)
            existing = task_by_card[card_id]
            if task["status"] in ["queued", "processing"]:
                task_by_card[card_id] = task
            elif existing["status"] not in ["queued", "processing"]:
                # Both are completed/failed - keep most recent by completed_at
                if task.get("completed_at", "") > existing.get("completed_at", ""):
                    task_by_card[card_id] = task

    result_tasks = [
        WorkstreamResearchStatus(
            card_id=t["card_id"],
            task_id=t["id"],
            task_type=t["task_type"],
            status=t["status"],
            started_at=t.get("started_at"),
            completed_at=t.get("completed_at")
        )
        for t in task_by_card.values()
    ]

    return WorkstreamResearchStatusResponse(tasks=result_tasks)


class FilterPreviewRequest(BaseModel):
    """Request model for filter preview (estimate matching cards)."""
    pillar_ids: List[str] = Field(default=[], description="List of pillar codes to filter by")
    goal_ids: List[str] = Field(default=[], description="List of goal codes to filter by")
    stage_ids: List[str] = Field(default=[], description="List of stage numbers to filter by")
    horizon: Optional[str] = Field(default=None, description="Horizon filter (H1, H2, H3, or ALL)")
    keywords: List[str] = Field(default=[], description="Keywords to match in card content")


class FilterPreviewResponse(BaseModel):
    """Response model for filter preview."""
    estimated_count: int = Field(..., description="Estimated number of matching cards")
    sample_cards: List[dict] = Field(default=[], description="Sample of matching cards (up to 5)")


@app.post("/api/v1/cards/filter-preview", response_model=FilterPreviewResponse)
async def preview_filter_count(
    filters: FilterPreviewRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Preview how many cards match the given filter criteria.

    This is a lightweight endpoint for showing estimated matches while
    creating/editing workstreams. Does not modify any data.

    Args:
        filters: Filter criteria (pillars, goals, stages, horizon, keywords)
        current_user: Authenticated user (injected)

    Returns:
        FilterPreviewResponse with estimated count and sample cards
    """
    # Build base query for active cards
    query = supabase.table("cards").select("id, name, pillar_id, horizon, stage_id").eq("status", "active")

    # Apply filters
    if filters.pillar_ids:
        query = query.in_("pillar_id", filters.pillar_ids)

    if filters.goal_ids:
        query = query.in_("goal_id", filters.goal_ids)

    if filters.horizon and filters.horizon != "ALL":
        query = query.eq("horizon", filters.horizon)

    # Fetch cards (limit to reasonable amount for performance)
    response = query.order("created_at", desc=True).limit(500).execute()
    cards = response.data or []

    # Apply stage filtering client-side
    if filters.stage_ids:
        filtered_by_stage = []
        for card in cards:
            card_stage_id = card.get("stage_id") or ""
            stage_num = card_stage_id.split("_")[0] if "_" in card_stage_id else card_stage_id
            if stage_num in filters.stage_ids:
                filtered_by_stage.append(card)
        cards = filtered_by_stage

    # Apply keyword filtering (need to fetch full text for this)
    if filters.keywords:
        # Fetch full card data for keyword matching
        if cards:
            card_ids = [c["id"] for c in cards]
            full_response = supabase.table("cards").select("id, name, summary, description, pillar_id, horizon, stage_id").in_("id", card_ids).execute()
            full_cards = full_response.data or []

            filtered_cards = []
            for card in full_cards:
                card_text = " ".join([
                    (card.get("name") or "").lower(),
                    (card.get("summary") or "").lower(),
                    (card.get("description") or "").lower()
                ])
                if any(keyword.lower() in card_text for keyword in filters.keywords):
                    filtered_cards.append(card)
            cards = filtered_cards

    # Build response
    sample_cards = [
        {"id": c["id"], "name": c["name"], "pillar_id": c.get("pillar_id"), "horizon": c.get("horizon")}
        for c in cards[:5]
    ]

    return FilterPreviewResponse(
        estimated_count=len(cards),
        sample_cards=sample_cards
    )


@app.post("/api/v1/me/workstreams/{workstream_id}/auto-populate", response_model=AutoPopulateResponse)
async def auto_populate_workstream(
    workstream_id: str,
    current_user: dict = Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=50, description="Maximum cards to add")
):
    """
    Auto-populate workstream with matching cards.

    Finds cards matching the workstream's filter criteria (pillars, goals, stages,
    horizon, keywords) that are not already in the workstream, and adds them
    to the 'inbox' column.

    Args:
        workstream_id: UUID of the workstream
        current_user: Authenticated user (injected)
        limit: Maximum number of cards to add (default: 20, max: 50)

    Returns:
        AutoPopulateResponse with count and details of added cards

    Raises:
        HTTPException 404: Workstream not found
        HTTPException 403: Not authorized
    """
    # Verify workstream belongs to user
    ws_response = supabase.table("workstreams").select("*").eq("id", workstream_id).eq("user_id", current_user["id"]).execute()
    if not ws_response.data:
        raise HTTPException(status_code=404, detail="Workstream not found")

    workstream = ws_response.data[0]

    # Get existing card IDs in workstream
    existing_response = supabase.table("workstream_cards").select("card_id").eq(
        "workstream_id", workstream_id
    ).execute()
    existing_card_ids = {item["card_id"] for item in existing_response.data or []}

    # Build query based on workstream filters
    query = supabase.table("cards").select("*").eq("status", "active")

    # Apply filters
    if workstream.get("pillar_ids"):
        query = query.in_("pillar_id", workstream["pillar_ids"])

    if workstream.get("goal_ids"):
        query = query.in_("goal_id", workstream["goal_ids"])

    # Note: stage_ids filter is applied client-side because card stage_id format
    # is "5_implementing" while workstream stores ["4", "5", "6"]
    # We need to extract the number prefix for comparison

    if workstream.get("horizon") and workstream["horizon"] != "ALL":
        query = query.eq("horizon", workstream["horizon"])

    # Fetch more cards than limit to account for filtering
    fetch_limit = min(limit * 3, 100)
    response = query.order("created_at", desc=True).limit(fetch_limit).execute()
    cards = response.data or []

    # Apply stage filtering (extract number prefix from stage_id like "5_implementing")
    stage_ids = workstream.get("stage_ids", [])
    if stage_ids:
        filtered_by_stage = []
        for card in cards:
            card_stage_id = card.get("stage_id") or ""
            # Extract number prefix (e.g., "5" from "5_implementing")
            stage_num = card_stage_id.split("_")[0] if "_" in card_stage_id else card_stage_id
            if stage_num in stage_ids:
                filtered_by_stage.append(card)
        cards = filtered_by_stage

    # Apply keyword filtering
    keywords = workstream.get("keywords", [])
    if keywords:
        filtered_cards = []
        for card in cards:
            card_text = " ".join([
                (card.get("name") or "").lower(),
                (card.get("summary") or "").lower(),
                (card.get("description") or "").lower()
            ])
            if any(keyword.lower() in card_text for keyword in keywords):
                filtered_cards.append(card)
        cards = filtered_cards

    # Filter out cards already in workstream
    candidates = [c for c in cards if c["id"] not in existing_card_ids][:limit]

    if not candidates:
        return AutoPopulateResponse(added=0, cards=[])

    # Get current max position in inbox
    position_response = supabase.table("workstream_cards").select("position").eq(
        "workstream_id", workstream_id
    ).eq("status", "inbox").order("position", desc=True).limit(1).execute()

    start_position = 0
    if position_response.data:
        start_position = position_response.data[0]["position"] + 1

    # Add cards to workstream
    now = datetime.now().isoformat()
    new_records = []
    for idx, card in enumerate(candidates):
        new_records.append({
            "workstream_id": workstream_id,
            "card_id": card["id"],
            "added_by": current_user["id"],
            "added_at": now,
            "status": "inbox",
            "position": start_position + idx,
            "added_from": "auto",
            "updated_at": now
        })

    # Insert all records
    result = supabase.table("workstream_cards").insert(new_records).execute()

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to auto-populate workstream")

    # Build response with card details
    added_cards = []
    card_map = {c["id"]: c for c in candidates}
    for item in result.data:
        added_cards.append(WorkstreamCardWithDetails(
            id=item["id"],
            workstream_id=item["workstream_id"],
            card_id=item["card_id"],
            added_by=item["added_by"],
            added_at=item["added_at"],
            status=item.get("status", "inbox"),
            position=item.get("position", 0),
            notes=item.get("notes"),
            reminder_at=item.get("reminder_at"),
            added_from=item.get("added_from", "auto"),
            updated_at=item.get("updated_at"),
            card=card_map.get(item["card_id"])
        ))

    logger.info(f"Auto-populated workstream {workstream_id} with {len(added_cards)} cards")

    return AutoPopulateResponse(added=len(added_cards), cards=added_cards)


# Executive Brief endpoints
@app.post("/api/v1/me/workstreams/{workstream_id}/cards/{card_id}/brief", response_model=BriefGenerateResponse)
async def generate_executive_brief(
    workstream_id: str,
    card_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Generate a new version of an executive brief for a card in a workstream.

    Creates a new brief version that runs asynchronously.
    Each call creates a new version (v1, v2, v3, etc.).
    Poll GET .../brief/status for completion status.

    Args:
        workstream_id: UUID of the workstream
        card_id: UUID of the card
        current_user: Authenticated user (injected)

    Returns:
        BriefGenerateResponse with brief ID, version, and pending status

    Raises:
        HTTPException 404: Workstream or card not found
        HTTPException 403: Not authorized to access workstream
    """
    # Verify workstream belongs to user
    ws_response = supabase.table("workstreams").select("id, user_id").eq("id", workstream_id).execute()
    if not ws_response.data:
        raise HTTPException(status_code=404, detail="Workstream not found")

    if ws_response.data[0]["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to access this workstream")

    # Verify card exists in workstream and get the workstream_cards record
    wsc_response = supabase.table("workstream_cards").select("id, card_id").eq(
        "workstream_id", workstream_id
    ).eq("card_id", card_id).execute()

    if not wsc_response.data:
        raise HTTPException(status_code=404, detail="Card not found in this workstream")

    workstream_card_id = wsc_response.data[0]["id"]

    # Create brief service
    brief_service = ExecutiveBriefService(supabase, openai_client)

    try:
        # Check if there's a brief currently generating
        existing_brief = await brief_service.get_brief_by_workstream_card(workstream_card_id)

        if existing_brief and existing_brief.get("status") in ("pending", "generating"):
            # Don't allow generating while another is in progress
            return BriefGenerateResponse(
                id=existing_brief["id"],
                status=existing_brief["status"],
                version=existing_brief.get("version", 1),
                message="Brief generation already in progress"
            )

        # Get the last completed brief to determine new sources
        last_completed = await brief_service.get_latest_completed_brief(workstream_card_id)
        since_timestamp = None
        sources_since_previous = None

        if last_completed and last_completed.get("generated_at"):
            since_timestamp = last_completed["generated_at"]
            # Count new sources since last brief
            new_source_count = await brief_service.count_new_sources(card_id, since_timestamp)
            sources_since_previous = {
                "count": new_source_count,
                "since_version": last_completed.get("version", 1),
                "since_date": since_timestamp
            }

        # Create the brief record with pending status (auto-increments version)
        brief_record = await brief_service.create_brief_record(
            workstream_card_id=workstream_card_id,
            card_id=card_id,
            user_id=current_user["id"],
            sources_since_previous=sources_since_previous
        )

        brief_id = brief_record["id"]
        brief_version = brief_record.get("version", 1)

        return BriefGenerateResponse(
            id=brief_id,
            status="pending",
            version=brief_version,
            message=f"Brief v{brief_version} queued for generation"
        )

    except Exception as e:
        logger.error(f"Failed to initiate brief generation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start brief generation: {str(e)}")


@app.get("/api/v1/me/workstreams/{workstream_id}/cards/{card_id}/brief", response_model=ExecutiveBriefResponse)
async def get_executive_brief(
    workstream_id: str,
    card_id: str,
    version: Optional[int] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Get an executive brief for a card in a workstream.

    Returns the latest version by default, or a specific version if provided.
    Returns 404 if no brief exists.

    Args:
        workstream_id: UUID of the workstream
        card_id: UUID of the card
        version: Optional version number (defaults to latest)
        current_user: Authenticated user (injected)

    Returns:
        ExecutiveBriefResponse with full brief content

    Raises:
        HTTPException 404: Workstream, card, or brief not found
        HTTPException 403: Not authorized to access workstream
    """
    # Verify workstream belongs to user
    ws_response = supabase.table("workstreams").select("id, user_id").eq("id", workstream_id).execute()
    if not ws_response.data:
        raise HTTPException(status_code=404, detail="Workstream not found")

    if ws_response.data[0]["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to access this workstream")

    # Verify card exists in workstream and get the workstream_cards record
    wsc_response = supabase.table("workstream_cards").select("id").eq(
        "workstream_id", workstream_id
    ).eq("card_id", card_id).execute()

    if not wsc_response.data:
        raise HTTPException(status_code=404, detail="Card not found in this workstream")

    workstream_card_id = wsc_response.data[0]["id"]

    # Fetch the brief (latest or specific version)
    brief_service = ExecutiveBriefService(supabase, openai_client)
    brief = await brief_service.get_brief_by_workstream_card(workstream_card_id, version=version)

    if not brief:
        if version:
            raise HTTPException(status_code=404, detail=f"Brief version {version} not found")
        raise HTTPException(status_code=404, detail="No brief found for this card")

    return ExecutiveBriefResponse(**brief)


@app.get("/api/v1/me/workstreams/{workstream_id}/cards/{card_id}/brief/versions", response_model=BriefVersionsResponse)
async def get_brief_versions(
    workstream_id: str,
    card_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get all versions of executive briefs for a card in a workstream.

    Returns a list of all brief versions, ordered by version number descending.

    Args:
        workstream_id: UUID of the workstream
        card_id: UUID of the card
        current_user: Authenticated user (injected)

    Returns:
        BriefVersionsResponse with list of all versions

    Raises:
        HTTPException 404: Workstream or card not found
        HTTPException 403: Not authorized to access workstream
    """
    # Verify workstream belongs to user
    ws_response = supabase.table("workstreams").select("id, user_id").eq("id", workstream_id).execute()
    if not ws_response.data:
        raise HTTPException(status_code=404, detail="Workstream not found")

    if ws_response.data[0]["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to access this workstream")

    # Verify card exists in workstream and get the workstream_cards record
    wsc_response = supabase.table("workstream_cards").select("id").eq(
        "workstream_id", workstream_id
    ).eq("card_id", card_id).execute()

    if not wsc_response.data:
        raise HTTPException(status_code=404, detail="Card not found in this workstream")

    workstream_card_id = wsc_response.data[0]["id"]

    # Fetch all versions
    brief_service = ExecutiveBriefService(supabase, openai_client)
    versions = await brief_service.get_brief_versions(workstream_card_id)

    # Convert to response model
    version_items = [
        BriefVersionListItem(
            id=v["id"],
            version=v.get("version", 1),
            status=v["status"],
            summary=v.get("summary"),
            sources_since_previous=v.get("sources_since_previous"),
            generated_at=v.get("generated_at"),
            created_at=v["created_at"],
            model_used=v.get("model_used")
        )
        for v in versions
    ]

    return BriefVersionsResponse(
        workstream_card_id=workstream_card_id,
        card_id=card_id,
        total_versions=len(version_items),
        versions=version_items
    )


@app.get("/api/v1/me/workstreams/{workstream_id}/cards/{card_id}/brief/status", response_model=BriefStatusResponse)
async def get_brief_status(
    workstream_id: str,
    card_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get the status of brief generation for a card.

    Used for polling during async brief generation.
    Returns status, summary (if complete), or error (if failed).

    Args:
        workstream_id: UUID of the workstream
        card_id: UUID of the card
        current_user: Authenticated user (injected)

    Returns:
        BriefStatusResponse with generation status

    Raises:
        HTTPException 404: Workstream, card, or brief not found
        HTTPException 403: Not authorized to access workstream
    """
    # Verify workstream belongs to user
    ws_response = supabase.table("workstreams").select("id, user_id").eq("id", workstream_id).execute()
    if not ws_response.data:
        raise HTTPException(status_code=404, detail="Workstream not found")

    if ws_response.data[0]["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to access this workstream")

    # Verify card exists in workstream and get the workstream_cards record
    wsc_response = supabase.table("workstream_cards").select("id").eq(
        "workstream_id", workstream_id
    ).eq("card_id", card_id).execute()

    if not wsc_response.data:
        raise HTTPException(status_code=404, detail="Card not found in this workstream")

    workstream_card_id = wsc_response.data[0]["id"]

    # Fetch the most recent brief
    brief_service = ExecutiveBriefService(supabase, openai_client)
    brief = await brief_service.get_brief_by_workstream_card(workstream_card_id)

    if not brief:
        raise HTTPException(status_code=404, detail="No brief found for this card")

    # Build progress message based on status
    progress_message = None
    if brief["status"] == "pending":
        progress_message = "Brief generation queued..."
    elif brief["status"] == "generating":
        progress_message = "Generating executive brief..."

    return BriefStatusResponse(
        id=brief["id"],
        status=brief["status"],
        version=brief.get("version", 1),
        summary=brief.get("summary"),
        error_message=brief.get("error_message"),
        generated_at=brief.get("generated_at"),
        progress_message=progress_message
    )


@app.get("/api/v1/me/workstreams/{workstream_id}/cards/{card_id}/brief/export/{format}")
async def export_brief(
    workstream_id: str,
    card_id: str,
    format: str,
    version: Optional[int] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Export an executive brief in the specified format.

    Exports the brief content (not the original card) as a PDF or PowerPoint
    presentation formatted for executive communication.

    Args:
        workstream_id: UUID of the workstream
        card_id: UUID of the card
        format: Export format (pdf or pptx)
        version: Optional version number to export (defaults to latest)
        current_user: Authenticated user (injected)

    Returns:
        FileResponse with the exported brief document

    Raises:
        HTTPException 400: Invalid export format
        HTTPException 404: Workstream, card, or brief not found
        HTTPException 403: Not authorized to access workstream
    """
    # Validate format
    format_lower = format.lower()
    if format_lower not in ("pdf", "pptx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid export format: {format}. Supported formats: pdf, pptx"
        )

    # Verify workstream belongs to user
    ws_response = supabase.table("workstreams").select("id, user_id").eq("id", workstream_id).execute()
    if not ws_response.data:
        raise HTTPException(status_code=404, detail="Workstream not found")

    if ws_response.data[0]["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to access this workstream")

    # Verify card exists in workstream and get the workstream_cards record
    wsc_response = supabase.table("workstream_cards").select("id").eq(
        "workstream_id", workstream_id
    ).eq("card_id", card_id).execute()

    if not wsc_response.data:
        raise HTTPException(status_code=404, detail="Card not found in this workstream")

    workstream_card_id = wsc_response.data[0]["id"]

    # Fetch the brief
    brief_service = ExecutiveBriefService(supabase, openai_client)
    brief = await brief_service.get_brief_by_workstream_card(workstream_card_id, version=version)

    if not brief:
        raise HTTPException(status_code=404, detail="No brief found for this card")

    if brief["status"] != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Brief is not yet complete. Please wait for generation to finish."
        )

    # Fetch card info for the export (including classification)
    card_response = supabase.table("cards").select(
        "name, pillar_id, horizon, stage_id"
    ).eq("id", card_id).single().execute()
    
    card_name = "Unknown Card"
    classification = {}
    if card_response.data:
        card_name = card_response.data.get("name", "Unknown Card")
        # Build classification info for professional PDF
        classification = {
            "pillar": card_response.data.get("pillar_id"),
            "horizon": card_response.data.get("horizon"),
            "stage": card_response.data.get("stage_id"),
        }

    # Generate export using ExportService
    export_service = ExportService(supabase)

    try:
        # Parse generated_at if present
        generated_at = None
        if brief.get("generated_at"):
            from datetime import datetime
            if isinstance(brief["generated_at"], str):
                generated_at = datetime.fromisoformat(brief["generated_at"].replace("Z", "+00:00"))
            else:
                generated_at = brief["generated_at"]

        if format_lower == "pdf":
            # Use professional PDF with logo, branding, and AI disclosure
            file_path = await export_service.generate_professional_brief_pdf(
                brief_title=card_name,
                card_name=card_name,
                executive_summary=brief.get("summary", ""),
                content_markdown=brief.get("content_markdown", ""),
                generated_at=generated_at,
                version=brief.get("version", 1),
                classification=classification
            )
            content_type = "application/pdf"
            extension = "pdf"
        else:
            file_path = await export_service.generate_brief_pptx(
                brief_title=card_name,
                card_name=card_name,
                executive_summary=brief.get("summary", ""),
                content_markdown=brief.get("content_markdown", ""),
                generated_at=generated_at,
                version=brief.get("version", 1),
                classification=classification,
                use_gamma=True  # Try Gamma.app first, fallback to local
            )
            content_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            extension = "pptx"

        # Generate safe filename
        safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in card_name)
        safe_name = safe_name[:50]  # Limit length
        version_str = f"_v{brief.get('version', 1)}" if brief.get('version', 1) > 1 else ""
        filename = f"Brief_{safe_name}{version_str}.{extension}"

        return FileResponse(
            path=file_path,
            filename=filename,
            media_type=content_type,
            background=None
        )

    except Exception as e:
        logger.error(f"Brief export generation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate export: {str(e)}"
        )


# =============================================================================
# Card Assets Endpoint
# =============================================================================

class CardAsset(BaseModel):
    """Represents a generated asset (brief, research report, export) for a card."""
    id: str
    type: str  # 'brief', 'research', 'pdf_export', 'pptx_export'
    title: str
    created_at: str
    version: Optional[int] = None
    file_size: Optional[int] = None
    download_count: Optional[int] = None
    ai_generated: bool = True
    ai_model: Optional[str] = None
    status: str = "ready"  # 'ready', 'generating', 'failed'
    metadata: Optional[dict] = None


class CardAssetsResponse(BaseModel):
    """Response containing all assets for a card."""
    card_id: str
    assets: List[CardAsset]
    total_count: int


@app.get("/api/v1/cards/{card_id}/assets", response_model=CardAssetsResponse)
async def get_card_assets(
    card_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get all generated assets for a card.
    
    Returns a list of all briefs, research reports, and exports
    associated with the card across all workstreams.
    
    Args:
        card_id: UUID of the card
        current_user: Authenticated user (injected)
    
    Returns:
        CardAssetsResponse with list of assets
    
    Raises:
        HTTPException 404: Card not found
    """
    try:
        # Verify card exists
        card_response = supabase.table("cards").select("id, name").eq("id", card_id).execute()
        if not card_response.data:
            raise HTTPException(status_code=404, detail="Card not found")
        
        card_name = card_response.data[0].get("name", "Unknown Card")
        assets = []
        
        # 1. Fetch executive briefs for this card
        briefs_response = supabase.table("executive_briefs").select(
            "id, version, status, summary, generated_at, model_used, created_at"
        ).eq("card_id", card_id).order("created_at", desc=True).execute()
        
        for brief in briefs_response.data or []:
            # Map status
            brief_status = "ready" if brief.get("status") == "completed" else brief.get("status", "ready")
            if brief_status == "generating":
                brief_status = "generating"
            elif brief_status in ("pending", "failed"):
                brief_status = "failed" if brief_status == "failed" else "ready"
            
            title = f"Executive Brief v{brief.get('version', 1)}"
            if brief.get("summary"):
                # Truncate summary for title if needed
                summary_preview = brief["summary"][:50] + "..." if len(brief.get("summary", "")) > 50 else brief.get("summary", "")
                title = f"Executive Brief v{brief.get('version', 1)}"
            
            assets.append(CardAsset(
                id=brief["id"],
                type="brief",
                title=title,
                created_at=brief.get("generated_at") or brief.get("created_at"),
                version=brief.get("version", 1),
                ai_generated=True,
                ai_model=brief.get("model_used"),
                status=brief_status,
                metadata={
                    "summary_preview": brief.get("summary", "")[:200] if brief.get("summary") else None
                }
            ))
        
        # 2. Fetch research tasks (deep research reports)
        research_response = supabase.table("research_tasks").select(
            "id, task_type, status, result_summary, completed_at, created_at"
        ).eq("card_id", card_id).order("created_at", desc=True).execute()
        
        for task in research_response.data or []:
            # Only include completed or failed tasks as assets
            if task.get("status") not in ("completed", "failed"):
                continue
            
            task_type = task.get("task_type", "research")
            if task_type == "deep_research":
                asset_type = "research"
                title = "Strategic Intelligence Report"
            elif task_type == "update":
                asset_type = "research"
                title = "Quick Update Report"
            else:
                asset_type = "research"
                title = f"{task_type.replace('_', ' ').title()} Report"
            
            result = task.get("result_summary", {}) or {}
            
            assets.append(CardAsset(
                id=task["id"],
                type=asset_type,
                title=title,
                created_at=task.get("completed_at") or task.get("created_at"),
                ai_generated=True,
                status="ready" if task.get("status") == "completed" else "failed",
                metadata={
                    "task_type": task_type,
                    "sources_found": result.get("sources_found"),
                    "sources_added": result.get("sources_added"),
                }
            ))
        
        # Sort all assets by created_at descending
        assets.sort(key=lambda x: x.created_at or "", reverse=True)
        
        return CardAssetsResponse(
            card_id=card_id,
            assets=assets,
            total_count=len(assets)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching card assets: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch card assets: {str(e)}"
        )


# Taxonomy endpoints
@app.get("/api/v1/taxonomy")
async def get_taxonomy():
    """Get all taxonomy data"""
    pillars = supabase.table("pillars").select("*").order("name").execute()
    goals = supabase.table("goals").select("*").order("pillar_id", "sort_order").execute()
    anchors = supabase.table("anchors").select("*").order("name").execute()
    stages = supabase.table("stages").select("*").order("sort_order").execute()
    
    return {
        "pillars": pillars.data,
        "goals": goals.data,
        "anchors": anchors.data,
        "stages": stages.data
    }

# Admin endpoints
@app.post("/api/v1/admin/scan")
@limiter.limit("3/minute")
async def trigger_manual_scan(request: Request, current_user: dict = Depends(get_current_user)):
    """
    Manually trigger content scan for all active cards.

    This triggers a quick update research task for cards that haven't been
    updated in the last 24 hours. Limited to admin users.

    Note: In production, add admin role check here.
    """
    try:
        # Get cards that need updates (not updated in last 24 hours)
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(hours=24)).isoformat()

        cards_result = supabase.table("cards").select("id, name").eq(
            "status", "active"
        ).lt("updated_at", cutoff).limit(10).execute()

        if not cards_result.data:
            return {"status": "skipped", "message": "No cards need updating", "cards_queued": 0}

        # Queue update tasks for each card
        tasks_created = 0
        for card in cards_result.data:
            task_record = {
                "user_id": current_user["id"],
                "card_id": card["id"],
                "task_type": "update",
                "status": "queued"
            }
            result = supabase.table("research_tasks").insert(task_record).execute()
            if result.data:
                tasks_created += 1
                logger.info(f"Queued update task for card: {card['name']}")

        return {
            "status": "scan_triggered",
            "message": f"Queued {tasks_created} update tasks",
            "cards_queued": tasks_created
        }

    except Exception as e:
        logger.error(f"Manual scan failed: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ============================================================================
# Research endpoints
# ============================================================================

@app.post("/api/v1/research", response_model=ResearchTask)
@limiter.limit("5/minute")
async def create_research_task(
    request: Request,
    task_data: ResearchTaskCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Create and execute a research task.

    Task types:
    - update: Quick refresh with 5-10 new sources
    - deep_research: Comprehensive research with 15-20 sources (limited to 2/day/card)
    - workstream_analysis: Research based on workstream keywords

    Returns immediately with task ID. Poll GET /research/{task_id} for status.
    """
    # Validate input
    if not task_data.card_id and not task_data.workstream_id:
        raise HTTPException(status_code=400, detail="Either card_id or workstream_id required")

    if task_data.task_type not in ["update", "deep_research", "workstream_analysis"]:
        raise HTTPException(status_code=400, detail="Invalid task_type. Use: update, deep_research, workstream_analysis")

    # Check rate limit for deep research
    if task_data.task_type == "deep_research" and task_data.card_id:
        service = ResearchService(supabase, openai_client)
        if not await service.check_rate_limit(task_data.card_id):
            raise HTTPException(status_code=429, detail="Daily deep research limit reached (2 per card)")

    # Create task record
    task_record = {
        "user_id": current_user["id"],
        "task_type": task_data.task_type,
        "status": "queued"
    }

    if task_data.card_id:
        task_record["card_id"] = task_data.card_id
    if task_data.workstream_id:
        task_record["workstream_id"] = task_data.workstream_id

    task_result = supabase.table("research_tasks").insert(task_record).execute()

    if not task_result.data:
        raise HTTPException(status_code=500, detail="Failed to create research task")

    task = task_result.data[0]
    task_id = task["id"]

    # Execute research in background (non-blocking)
    # Task execution is handled by the background worker (see `app.worker`).

    return ResearchTask(**task)


async def execute_research_task_background(
    task_id: str,
    task_data: ResearchTaskCreate,
    user_id: str
):
    """
    Background task to execute research.

    Updates task status through lifecycle: queued -> processing -> completed/failed

    Research Pipeline (hybrid approach):
    1. Discovery: GPT Researcher with municipal-focused queries
    2. Triage: Quick relevance check (gpt-4o-mini)
    3. Analysis: Full classification and scoring (gpt-4o)
    4. Matching: Vector similarity to existing cards
    5. Storage: Persist with entities for graph building
    """
    service = ResearchService(supabase, openai_client)

    try:
        def _get_timeout_seconds(task_type: str) -> int:
            defaults = {
                "update": 15 * 60,
                "deep_research": 45 * 60,
                "workstream_analysis": 45 * 60,
            }
            env_keys = {
                "update": "RESEARCH_TASK_TIMEOUT_UPDATE_SECONDS",
                "deep_research": "RESEARCH_TASK_TIMEOUT_DEEP_RESEARCH_SECONDS",
                "workstream_analysis": "RESEARCH_TASK_TIMEOUT_WORKSTREAM_ANALYSIS_SECONDS",
            }
            env_key = env_keys.get(task_type)
            if env_key:
                try:
                    return int(os.getenv(env_key, str(defaults.get(task_type, 45 * 60))))
                except ValueError:
                    return defaults.get(task_type, 45 * 60)
            return defaults.get(task_type, 45 * 60)

        # Update status to processing
        now = datetime.now(timezone.utc).isoformat()
        supabase.table("research_tasks").update({
            "status": "processing",
            "started_at": now,
            "result_summary": {
                "stage": f"running:{task_data.task_type}",
                "heartbeat_at": now,
            }
        }).eq("id", task_id).execute()

        timeout_seconds = _get_timeout_seconds(task_data.task_type)

        # Execute based on task type
        if task_data.task_type == "update":
            result = await asyncio.wait_for(
                service.execute_update(task_data.card_id, task_id),
                timeout=timeout_seconds
            )
        elif task_data.task_type == "deep_research":
            result = await asyncio.wait_for(
                service.execute_deep_research(task_data.card_id, task_id),
                timeout=timeout_seconds
            )
        elif task_data.task_type == "workstream_analysis":
            result = await asyncio.wait_for(
                service.execute_workstream_analysis(
                    task_data.workstream_id, task_id, user_id
                ),
                timeout=timeout_seconds
            )
        else:
            raise ValueError(f"Unknown task type: {task_data.task_type}")

        # Convert ResearchResult dataclass to dict for storage
        result_summary = {
            "sources_found": result.sources_found,
            "sources_relevant": result.sources_relevant,
            "sources_added": result.sources_added,
            "cards_matched": result.cards_matched,
            "cards_created": result.cards_created,
            "entities_extracted": result.entities_extracted,
            "cost_estimate": result.cost_estimate,
            "report_preview": result.report_preview,  # Full research report text
        }

        # Update as completed
        supabase.table("research_tasks").update({
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "result_summary": result_summary
        }).eq("id", task_id).execute()

    except asyncio.TimeoutError:
        # Update as failed (timeout)
        supabase.table("research_tasks").update({
            "status": "failed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "error_message": f"Research task timed out while {task_data.task_type} was running"
        }).eq("id", task_id).execute()

    except Exception as e:
        # Update as failed
        supabase.table("research_tasks").update({
            "status": "failed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "error_message": str(e)
        }).eq("id", task_id).execute()


@app.get("/api/v1/research/{task_id}", response_model=ResearchTask)
async def get_research_task(
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get research task status.

    Use this endpoint to poll for task completion after creating a research task.
    Status values: queued, processing, completed, failed
    """
    result = supabase.table("research_tasks").select("*").eq(
        "id", task_id
    ).eq("user_id", current_user["id"]).single().execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Research task not found")

    task = result.data

    def _parse_dt(value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            dt = value
        else:
            try:
                dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except ValueError:
                return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _get_timeout_seconds(task_type: str, status: str) -> int:
        if status == "queued":
            try:
                return int(os.getenv("RESEARCH_TASK_QUEUED_TIMEOUT_SECONDS", "900"))
            except ValueError:
                return 900
        defaults = {
            "update": 15 * 60,
            "deep_research": 45 * 60,
            "workstream_analysis": 45 * 60,
        }
        env_keys = {
            "update": "RESEARCH_TASK_TIMEOUT_UPDATE_SECONDS",
            "deep_research": "RESEARCH_TASK_TIMEOUT_DEEP_RESEARCH_SECONDS",
            "workstream_analysis": "RESEARCH_TASK_TIMEOUT_WORKSTREAM_ANALYSIS_SECONDS",
        }
        env_key = env_keys.get(task_type)
        if env_key:
            try:
                return int(os.getenv(env_key, str(defaults.get(task_type, 45 * 60))))
            except ValueError:
                return defaults.get(task_type, 45 * 60)
        return defaults.get(task_type, 45 * 60)

    def _maybe_fail_stale_task(task_row: Dict[str, Any]) -> Dict[str, Any]:
        status_val = task_row.get("status")
        if status_val not in ("queued", "processing"):
            return task_row

        summary = task_row.get("result_summary") or {}
        heartbeat_dt = _parse_dt(summary.get("heartbeat_at")) if isinstance(summary, dict) else None

        base_dt = None
        if status_val == "processing":
            base_dt = heartbeat_dt or _parse_dt(task_row.get("started_at")) or _parse_dt(task_row.get("created_at"))
        else:
            base_dt = _parse_dt(task_row.get("created_at"))

        if not base_dt:
            return task_row

        timeout_seconds = _get_timeout_seconds(task_row.get("task_type", ""), status_val)
        age_seconds = (datetime.now(timezone.utc) - base_dt).total_seconds()

        if age_seconds <= timeout_seconds:
            return task_row

        age_minutes = int(age_seconds // 60)
        error_message = (
            f"Research task stalled (no progress for ~{age_minutes} minutes). "
            "This can happen if the server restarts mid-task. Please retry."
        )

        new_summary = dict(summary) if isinstance(summary, dict) else {}
        new_summary.update({
            "timed_out": True,
            "timed_out_at": datetime.now(timezone.utc).isoformat(),
            "timeout_seconds": timeout_seconds,
        })

        updates = {
            "status": "failed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "error_message": error_message,
            "result_summary": new_summary,
        }

        try:
            supabase.table("research_tasks").update(updates).eq("id", task_id).eq("user_id", current_user["id"]).execute()
            task_row.update(updates)
        except Exception:
            # If we can't update, return original task row.
            return task_row

        return task_row

    task = _maybe_fail_stale_task(task)

    return ResearchTask(**task)


@app.get("/api/v1/me/research-tasks", response_model=List[ResearchTask])
async def list_research_tasks(
    current_user: dict = Depends(get_current_user),
    limit: int = 10
):
    """
    List user's recent research tasks.

    Returns the most recent tasks, ordered by creation date descending.
    """
    result = supabase.table("research_tasks").select("*").eq(
        "user_id", current_user["id"]
    ).order("created_at", desc=True).limit(limit).execute()

    return [ResearchTask(**t) for t in result.data]


# ============================================================================
# Discovery endpoints
# ============================================================================

@app.get("/api/v1/discovery/config")
async def get_discovery_config(current_user: dict = Depends(get_current_user)):
    """
    Get current discovery configuration defaults.

    Returns environment-configured defaults for discovery runs.
    Frontend can use this to display current limits.
    """
    return {
        "max_queries_per_run": get_discovery_max_queries(),
        "max_sources_total": get_discovery_max_sources(),
        "max_sources_per_query": int(os.getenv("DISCOVERY_MAX_SOURCES_PER_QUERY", "10")),
        "auto_approve_threshold": 0.95,
        "similarity_threshold": 0.92
    }


@app.post("/api/v1/discovery/run", response_model=DiscoveryRun)
@limiter.limit("3/minute")
async def trigger_discovery_run(
    request: Request,
    config: DiscoveryConfigRequest = DiscoveryConfigRequest(),
    current_user: dict = Depends(get_current_user)
):
    """
    Trigger a new discovery run.

    Creates a discovery run record and starts the discovery process in the background.

    Returns immediately with run ID. Poll GET /discovery/runs/{run_id} for status.
    """
    try:
        # Apply env defaults for any unset values
        resolved_config = {
            "max_queries_per_run": config.max_queries_per_run or get_discovery_max_queries(),
            "max_sources_total": config.max_sources_total or get_discovery_max_sources(),
            "auto_approve_threshold": config.auto_approve_threshold,
            "pillars_filter": config.pillars_filter,
            "dry_run": config.dry_run
        }

        # Create discovery run record with resolved config
        run_record = {
            "status": "running",
            "triggered_by": "manual",
            "triggered_by_user": current_user["id"],
            "summary_report": {
                "stage": "queued",
                "config": resolved_config
            },
            "cards_created": 0,
            "cards_enriched": 0,
            "cards_deduplicated": 0,
            "sources_found": 0,
            "started_at": datetime.now().isoformat()
        }

        result = supabase.table("discovery_runs").insert(run_record).execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create discovery run")

        run = result.data[0]
        run_id = run["id"]

        # Discovery execution is handled by the background worker (see `app.worker`).

        return DiscoveryRun(**run)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger discovery run: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger discovery run: {str(e)}")


async def execute_discovery_run_background(
    run_id: str,
    config: DiscoveryConfigRequest,
    user_id: str
):
    """
    Background task to execute discovery run using DiscoveryService.

    Updates run status through lifecycle: running -> completed/failed
    """
    from .discovery_service import DiscoveryService, DiscoveryConfig

    try:
        logger.info(f"Starting discovery run {run_id}")

        # Convert API config to service config
        discovery_config = DiscoveryConfig(
            max_queries_per_run=config.max_queries_per_run,
            max_sources_total=config.max_sources_total,
            auto_approve_threshold=config.auto_approve_threshold,
            pillars_filter=config.pillars_filter or [],
            dry_run=config.dry_run
        )

        # Execute discovery using the service (pass existing run_id to avoid duplicate)
        service = DiscoveryService(supabase, openai_client, triggered_by_user_id=user_id)
        result = await service.execute_discovery_run(discovery_config, existing_run_id=run_id)

        # Update the run record with results (service already updates its own record,
        # but we update the one we created in the endpoint)
        supabase.table("discovery_runs").update({
            "status": result.status.value,
            "completed_at": datetime.now().isoformat(),
            "queries_generated": result.queries_generated,
            "sources_found": result.sources_discovered,
            "sources_relevant": result.sources_triaged,
            "cards_created": len(result.cards_created),
            "cards_enriched": len(result.cards_enriched),
            "cards_deduplicated": result.sources_duplicate,
            "estimated_cost": result.estimated_cost,
        }).eq("id", run_id).execute()

        logger.info(f"Discovery run {run_id} completed: {len(result.cards_created)} cards created, {len(result.cards_enriched)} enriched")

    except Exception as e:
        logger.error(f"Discovery run {run_id} failed: {str(e)}", exc_info=True)
        # Update as failed
        supabase.table("discovery_runs").update({
            "status": "failed",
            "completed_at": datetime.now().isoformat(),
            "error_message": str(e)
        }).eq("id", run_id).execute()


@app.get("/api/v1/discovery/runs/{run_id}", response_model=DiscoveryRun)
async def get_discovery_run(
    run_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get discovery run status.

    Use this endpoint to poll for run completion after triggering a discovery run.
    Status values: running, completed, failed, cancelled
    """
    result = supabase.table("discovery_runs").select("*").eq(
        "id", run_id
    ).single().execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Discovery run not found")

    return DiscoveryRun(**result.data)


@app.get("/api/v1/discovery/runs", response_model=List[DiscoveryRun])
async def list_discovery_runs(
    current_user: dict = Depends(get_current_user),
    limit: int = 20
):
    """
    List recent discovery runs.

    Returns the most recent runs, ordered by start time descending.
    """
    result = supabase.table("discovery_runs").select("*").order(
        "started_at", desc=True
    ).limit(limit).execute()

    return [DiscoveryRun(**r) for r in result.data]


@app.post("/api/v1/discovery/runs/{run_id}/cancel")
async def cancel_discovery_run(
    run_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Cancel a running discovery run.

    Only runs with status 'running' can be cancelled.
    """
    # Get current run status
    response = supabase.table("discovery_runs").select("*").eq("id", run_id).execute()

    if not response.data:
        raise HTTPException(status_code=404, detail="Discovery run not found")

    run = response.data[0]

    # Check if run can be cancelled
    if run["status"] != "running":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel run with status '{run['status']}'. Only 'running' runs can be cancelled."
        )

    # Update status to cancelled
    update_response = supabase.table("discovery_runs").update({
        "status": "cancelled",
        "completed_at": datetime.now().isoformat(),
        "error_message": f"Cancelled by user {current_user['id']}"
    }).eq("id", run_id).execute()

    if update_response.data:
        logger.info(f"Discovery run {run_id} cancelled by user {current_user['id']}")
        return DiscoveryRun(**update_response.data[0])
    else:
        raise HTTPException(status_code=500, detail="Failed to cancel discovery run")


# =============================================================================
# Saved Searches API
# =============================================================================

@app.get("/api/v1/saved-searches", response_model=SavedSearchList)
async def list_saved_searches(
    current_user: dict = Depends(get_current_user)
):
    """
    List all saved searches for the current user.

    Returns saved searches ordered by last_used_at descending (most recently used first).
    """
    try:
        response = supabase.table("saved_searches").select("*").eq(
            "user_id", current_user["id"]
        ).order("last_used_at", desc=True).execute()
    except Exception as e:
        if _is_missing_supabase_table_error(e, "saved_searches"):
            logger.warning("saved_searches table missing; returning empty list")
            return SavedSearchList(saved_searches=[], total_count=0)
        logger.error(f"Failed to list saved searches: {e}")
        raise HTTPException(status_code=500, detail="Failed to list saved searches")

    saved_searches = [SavedSearch(**ss) for ss in (response.data or [])]
    return SavedSearchList(
        saved_searches=saved_searches,
        total_count=len(saved_searches)
    )


@app.post("/api/v1/saved-searches", response_model=SavedSearch, status_code=status.HTTP_201_CREATED)
async def create_saved_search(
    saved_search_data: SavedSearchCreate,
    current_user: dict = Depends(get_current_user)
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
        "updated_at": now
    }

    try:
        response = supabase.table("saved_searches").insert(ss_dict).execute()
    except Exception as e:
        if _is_missing_supabase_table_error(e, "saved_searches"):
            raise HTTPException(status_code=503, detail="Saved searches are not configured (missing saved_searches table)")
        logger.error(f"Failed to create saved search: {e}")
        raise HTTPException(status_code=500, detail="Failed to create saved search")
    if response.data:
        return SavedSearch(**response.data[0])
    else:
        raise HTTPException(status_code=400, detail="Failed to create saved search")


@app.get("/api/v1/saved-searches/{saved_search_id}", response_model=SavedSearch)
async def get_saved_search(
    saved_search_id: str,
    current_user: dict = Depends(get_current_user)
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
        response = supabase.table("saved_searches").select("*").eq(
            "id", saved_search_id
        ).execute()
    except Exception as e:
        if _is_missing_supabase_table_error(e, "saved_searches"):
            raise HTTPException(status_code=503, detail="Saved searches are not configured (missing saved_searches table)")
        logger.error(f"Failed to fetch saved search {saved_search_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch saved search")

    if not response.data:
        raise HTTPException(status_code=404, detail="Saved search not found")

    saved_search = response.data[0]

    # Verify ownership
    if saved_search["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to access this saved search")

    # Update last_used_at timestamp
    try:
        update_response = supabase.table("saved_searches").update({
            "last_used_at": datetime.now().isoformat()
        }).eq("id", saved_search_id).execute()
    except Exception as e:
        if _is_missing_supabase_table_error(e, "saved_searches"):
            raise HTTPException(status_code=503, detail="Saved searches are not configured (missing saved_searches table)")
        logger.error(f"Failed to update saved search last_used_at {saved_search_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update saved search")

    if update_response.data:
        return SavedSearch(**update_response.data[0])
    else:
        return SavedSearch(**saved_search)


@app.patch("/api/v1/saved-searches/{saved_search_id}", response_model=SavedSearch)
async def update_saved_search(
    saved_search_id: str,
    saved_search_data: SavedSearchUpdate,
    current_user: dict = Depends(get_current_user)
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
        ss_check = supabase.table("saved_searches").select("*").eq(
            "id", saved_search_id
        ).execute()
    except Exception as e:
        if _is_missing_supabase_table_error(e, "saved_searches"):
            raise HTTPException(status_code=503, detail="Saved searches are not configured (missing saved_searches table)")
        logger.error(f"Failed to fetch saved search for update {saved_search_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch saved search")

    if not ss_check.data:
        raise HTTPException(status_code=404, detail="Saved search not found")

    # Verify ownership
    if ss_check.data[0]["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to update this saved search")

    # Build update dict with only non-None values
    update_dict = {k: v for k, v in saved_search_data.dict().items() if v is not None}

    if not update_dict:
        # No updates provided, return existing saved search
        return SavedSearch(**ss_check.data[0])

    # Add updated_at timestamp
    update_dict["updated_at"] = datetime.now().isoformat()

    # Perform update
    try:
        response = supabase.table("saved_searches").update(update_dict).eq(
            "id", saved_search_id
        ).execute()
    except Exception as e:
        if _is_missing_supabase_table_error(e, "saved_searches"):
            raise HTTPException(status_code=503, detail="Saved searches are not configured (missing saved_searches table)")
        logger.error(f"Failed to update saved search {saved_search_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update saved search")

    if response.data:
        return SavedSearch(**response.data[0])
    else:
        raise HTTPException(status_code=400, detail="Failed to update saved search")


@app.delete("/api/v1/saved-searches/{saved_search_id}")
async def delete_saved_search(
    saved_search_id: str,
    current_user: dict = Depends(get_current_user)
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
        ss_check = supabase.table("saved_searches").select("*").eq(
            "id", saved_search_id
        ).execute()
    except Exception as e:
        if _is_missing_supabase_table_error(e, "saved_searches"):
            raise HTTPException(status_code=503, detail="Saved searches are not configured (missing saved_searches table)")
        logger.error(f"Failed to fetch saved search for delete {saved_search_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch saved search")

    if not ss_check.data:
        raise HTTPException(status_code=404, detail="Saved search not found")

    # Verify ownership
    if ss_check.data[0]["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to delete this saved search")

    # Perform delete
    try:
        supabase.table("saved_searches").delete().eq("id", saved_search_id).execute()
    except Exception as e:
        if _is_missing_supabase_table_error(e, "saved_searches"):
            raise HTTPException(status_code=503, detail="Saved searches are not configured (missing saved_searches table)")
        logger.error(f"Failed to delete saved search {saved_search_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete saved search")

    return {"status": "deleted", "message": "Saved search successfully deleted"}


# Add scheduler for nightly jobs
def start_scheduler():
    """Start the APScheduler for background jobs"""
    # Prevent duplicate scheduler starts (e.g., web + worker misconfiguration).
    try:
        if scheduler.running:
            logger.info("Scheduler already running; skipping start")
            return
    except Exception:
        # Defensive: if scheduler doesn't expose `running`, continue.
        pass

    # Nightly content scan at 6:00 AM UTC
    scheduler.add_job(
        run_nightly_scan,
        'cron',
        hour=6,
        minute=0,
        id='nightly_scan',
        replace_existing=True
    )

    # Weekly discovery run - Sunday at 2:00 AM UTC
    scheduler.add_job(
        run_weekly_discovery,
        'cron',
        day_of_week='sun',
        hour=2,
        minute=0,
        id='weekly_discovery',
        replace_existing=True
    )

    scheduler.start()
    logger.info("Scheduler started - nightly scan at 6:00 AM UTC, weekly discovery Sundays at 2:00 AM UTC")


async def run_nightly_scan():
    """
    Run nightly content scan for all active cards.

    This automatically queues update research tasks for cards that
    haven't been updated recently. Runs at 6 AM UTC daily.
    """
    logger.info("Starting nightly scan...")

    try:
        from datetime import timedelta

        # Get cards that need updates (not updated in last 48 hours)
        cutoff = (datetime.now() - timedelta(hours=48)).isoformat()

        cards_result = supabase.table("cards").select("id, name").eq(
            "status", "active"
        ).lt("updated_at", cutoff).limit(20).execute()

        if not cards_result.data:
            logger.info("Nightly scan: No cards need updating")
            return

        # Get system user for automated tasks (or use first admin)
        system_user = supabase.table("users").select("id").limit(1).execute()
        user_id = system_user.data[0]["id"] if system_user.data else None

        if not user_id:
            logger.warning("Nightly scan: No system user found, skipping")
            return

        # Queue update tasks
        service = ResearchService(supabase, openai_client)
        tasks_queued = 0

        for card in cards_result.data:
            try:
                # Create task record
                task_record = {
                    "user_id": user_id,
                    "card_id": card["id"],
                    "task_type": "update",
                    "status": "queued"
                }
                task_result = supabase.table("research_tasks").insert(task_record).execute()

                if task_result.data:
                    tasks_queued += 1
                    logger.info(f"Nightly scan: Queued update for '{card['name']}'")

            except Exception as e:
                logger.error(f"Nightly scan: Failed to queue task for card {card['id']}: {e}")

        logger.info(f"Nightly scan complete: {tasks_queued} tasks queued")

    except Exception as e:
        logger.error(f"Nightly scan failed: {str(e)}")


# ============================================================================
# Search History endpoints
# ============================================================================

@app.get("/api/v1/search-history", response_model=SearchHistoryList)
async def list_search_history(
    current_user: dict = Depends(get_current_user),
    limit: int = 20
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
        response = supabase.table("search_history").select("*").eq(
            "user_id", current_user["id"]
        ).order(
            "executed_at", desc=True
        ).limit(limit).execute()

        history_entries = [
            SearchHistoryEntry(
                id=entry["id"],
                user_id=entry["user_id"],
                query_config=entry.get("query_config", {}),
                executed_at=entry["executed_at"],
                result_count=entry.get("result_count", 0)
            )
            for entry in response.data or []
        ]

        return SearchHistoryList(
            history=history_entries,
            total_count=len(history_entries)
        )

    except Exception as e:
        if _is_missing_supabase_table_error(e, "search_history"):
            logger.warning("search_history table missing; returning empty list")
            return SearchHistoryList(history=[], total_count=0)
        logger.error(f"Failed to fetch search history: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch search history: {str(e)}"
        )


@app.post("/api/v1/search-history", response_model=SearchHistoryEntry, status_code=status.HTTP_201_CREATED)
async def record_search_history(
    history_data: SearchHistoryCreate,
    current_user: dict = Depends(get_current_user)
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
            "executed_at": datetime.now().isoformat()
        }

        response = supabase.table("search_history").insert(history_record).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to record search history"
            )

        entry = response.data[0]
        return SearchHistoryEntry(
            id=entry["id"],
            user_id=entry["user_id"],
            query_config=entry.get("query_config", {}),
            executed_at=entry["executed_at"],
            result_count=entry.get("result_count", 0)
        )

    except HTTPException:
        raise
    except Exception as e:
        if _is_missing_supabase_table_error(e, "search_history"):
            raise HTTPException(status_code=503, detail="Search history is not configured (missing search_history table)")
        logger.error(f"Failed to record search history: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record search history: {str(e)}"
        )


@app.delete("/api/v1/search-history/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_search_history_entry(
    entry_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a specific search history entry.

    Users can only delete their own history entries.

    Args:
        entry_id: UUID of the history entry to delete
    """
    try:
        # Verify entry exists and belongs to user
        check_response = supabase.table("search_history").select("id").eq(
            "id", entry_id
        ).eq("user_id", current_user["id"]).execute()

        if not check_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Search history entry not found"
            )

        # Delete the entry
        supabase.table("search_history").delete().eq(
            "id", entry_id
        ).eq("user_id", current_user["id"]).execute()

        return None

    except HTTPException:
        raise
    except Exception as e:
        if _is_missing_supabase_table_error(e, "search_history"):
            raise HTTPException(status_code=503, detail="Search history is not configured (missing search_history table)")
        logger.error(f"Failed to delete search history entry: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete search history entry: {str(e)}"
        )


@app.delete("/api/v1/search-history", status_code=status.HTTP_204_NO_CONTENT)
async def clear_search_history(
    current_user: dict = Depends(get_current_user)
):
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
            raise HTTPException(status_code=503, detail="Search history is not configured (missing search_history table)")
        logger.error(f"Failed to clear search history: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear search history: {str(e)}"
        )


@app.get("/api/v1/analytics/velocity", response_model=VelocityResponse)
async def get_trend_velocity(
    pillar_id: Optional[str] = None,
    stage_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Get trend velocity analytics over time.

    Returns time-series data showing trend momentum, including:
    - Daily/weekly velocity aggregations
    - Week-over-week comparison
    - Card counts per time period

    Query parameters:
    - pillar_id: Filter by strategic pillar code (CH, EW, HG, HH, MC, PS)
    - stage_id: Filter by maturity stage ID
    - start_date: Start date in ISO format (YYYY-MM-DD)
    - end_date: End date in ISO format (YYYY-MM-DD)

    Returns:
        VelocityResponse with time-series velocity data
    """
    from datetime import timedelta
    from collections import defaultdict

    try:
        # Default to last 30 days if no date range specified
        if not end_date:
            end_dt = datetime.now()
            end_date = end_dt.strftime("%Y-%m-%d")
        else:
            end_dt = datetime.fromisoformat(end_date)

        if not start_date:
            start_dt = end_dt - timedelta(days=30)
            start_date = start_dt.strftime("%Y-%m-%d")
        else:
            start_dt = datetime.fromisoformat(start_date)

        # Validate date range
        if start_dt > end_dt:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_date must be before or equal to end_date"
            )

        # Build query for cards
        query = supabase.table("cards").select(
            "id, velocity_score, created_at, updated_at, pillar_id, stage_id"
        ).eq("status", "active")

        # Apply filters
        if pillar_id:
            if pillar_id not in ANALYTICS_PILLAR_DEFINITIONS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid pillar_id. Must be one of: {', '.join(ANALYTICS_PILLAR_DEFINITIONS.keys())}"
                )
            query = query.eq("pillar_id", pillar_id)

        if stage_id:
            query = query.eq("stage_id", stage_id)

        # Filter by date range on created_at
        query = query.gte("created_at", f"{start_date}T00:00:00")
        query = query.lte("created_at", f"{end_date}T23:59:59")

        response = query.order("created_at", desc=False).execute()

        cards = response.data or []
        total_cards = len(cards)

        # Aggregate velocity data by date
        daily_data = defaultdict(lambda: {"velocity_sum": 0, "count": 0, "scores": []})

        for card in cards:
            # Extract date from created_at
            created_at = card.get("created_at", "")
            if created_at:
                date_str = created_at[:10]  # YYYY-MM-DD
                velocity = card.get("velocity_score")
                if velocity is not None:
                    daily_data[date_str]["velocity_sum"] += velocity
                    daily_data[date_str]["scores"].append(velocity)
                daily_data[date_str]["count"] += 1

        # Convert to VelocityDataPoint list
        velocity_data = []
        for date_str in sorted(daily_data.keys()):
            day_info = daily_data[date_str]
            avg_velocity = None
            if day_info["scores"]:
                avg_velocity = round(sum(day_info["scores"]) / len(day_info["scores"]), 2)

            velocity_data.append(VelocityDataPoint(
                date=date_str,
                velocity=day_info["velocity_sum"],
                count=day_info["count"],
                avg_velocity_score=avg_velocity
            ))

        # Calculate week-over-week change
        week_over_week_change = None
        if len(velocity_data) >= 14:
            # Get last 7 days and previous 7 days
            last_week_data = velocity_data[-7:]
            prev_week_data = velocity_data[-14:-7]

            last_week_total = sum(d.velocity for d in last_week_data)
            prev_week_total = sum(d.velocity for d in prev_week_data)

            if prev_week_total > 0:
                week_over_week_change = round(
                    ((last_week_total - prev_week_total) / prev_week_total) * 100,
                    2
                )
            elif last_week_total > 0:
                week_over_week_change = 100.0  # Infinite increase represented as 100%

        return VelocityResponse(
            data=velocity_data,
            count=len(velocity_data),
            period_start=start_date,
            period_end=end_date,
            week_over_week_change=week_over_week_change,
            total_cards_analyzed=total_cards
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch velocity analytics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch velocity analytics: {str(e)}"
        )


# ============================================================================
# Comprehensive Analytics Endpoints
# ============================================================================

# Stage name mapping
STAGE_NAMES = {
    "1": "Concept",
    "2": "Exploring", 
    "3": "Pilot",
    "4": "PoC",
    "5": "Implementing",
    "6": "Scaling",
    "7": "Mature",
    "8": "Declining",
}

# Horizon labels
HORIZON_LABELS = {
    "H1": "Near-term (0-2 years)",
    "H2": "Mid-term (2-5 years)",
    "H3": "Long-term (5+ years)",
}


@app.get("/api/v1/analytics/system-stats", response_model=SystemWideStats)
async def get_system_wide_stats(
    current_user: dict = Depends(get_current_user)
):
    """
    Get comprehensive system-wide analytics.
    
    Returns aggregated statistics about:
    - Total cards, sources, and discovery activity
    - Distribution by pillar, stage, and horizon
    - Trending topics and hot categories
    - Workstream and follow engagement metrics
    """
    from datetime import timedelta
    from collections import Counter
    
    try:
        now = datetime.now()
        one_week_ago = now - timedelta(days=7)
        one_month_ago = now - timedelta(days=30)
        
        # -------------------------------------------------------------------------
        # Core Card Stats
        # -------------------------------------------------------------------------
        
        # Total cards
        total_cards_resp = supabase.table("cards").select("id", count="exact").execute()
        total_cards = total_cards_resp.count or 0
        
        # Active cards
        active_cards_resp = supabase.table("cards").select("id", count="exact").eq("status", "active").execute()
        active_cards = active_cards_resp.count or 0
        
        # Cards this week
        cards_week_resp = supabase.table("cards").select("id", count="exact").gte(
            "created_at", one_week_ago.isoformat()
        ).execute()
        cards_this_week = cards_week_resp.count or 0
        
        # Cards this month
        cards_month_resp = supabase.table("cards").select("id", count="exact").gte(
            "created_at", one_month_ago.isoformat()
        ).execute()
        cards_this_month = cards_month_resp.count or 0
        
        # -------------------------------------------------------------------------
        # Cards by Pillar
        # -------------------------------------------------------------------------
        
        pillar_resp = supabase.table("cards").select("pillar_id, velocity_score").eq("status", "active").execute()
        pillar_data = pillar_resp.data or []
        
        pillar_counts = Counter()
        pillar_velocity = {}
        for card in pillar_data:
            p = card.get("pillar_id")
            if p:
                pillar_counts[p] += 1
                if p not in pillar_velocity:
                    pillar_velocity[p] = []
                if card.get("velocity_score"):
                    pillar_velocity[p].append(card["velocity_score"])
        
        cards_by_pillar = []
        for code, name in ANALYTICS_PILLAR_DEFINITIONS.items():
            count = pillar_counts.get(code, 0)
            pct = (count / active_cards * 100) if active_cards > 0 else 0
            avg_vel = None
            if pillar_velocity.get(code):
                avg_vel = round(sum(pillar_velocity[code]) / len(pillar_velocity[code]), 1)
            cards_by_pillar.append(PillarCoverageItem(
                pillar_code=code,
                pillar_name=name,
                count=count,
                percentage=round(pct, 1),
                avg_velocity=avg_vel
            ))
        
        # -------------------------------------------------------------------------
        # Cards by Stage
        # -------------------------------------------------------------------------
        
        stage_resp = supabase.table("cards").select("stage_id").eq("status", "active").execute()
        stage_data = stage_resp.data or []
        
        stage_counts = Counter()
        for card in stage_data:
            s = card.get("stage_id")
            if s:
                # Normalize stage_id - extract number from formats like "4_proof", "5_implementing"
                stage_str = str(s)
                stage_num = stage_str.split("_")[0] if "_" in stage_str else stage_str.replace("Stage ", "").strip()
                stage_counts[stage_num] += 1
        
        cards_by_stage = []
        for stage_id, stage_name in STAGE_NAMES.items():
            count = stage_counts.get(stage_id, 0)
            pct = (count / active_cards * 100) if active_cards > 0 else 0
            cards_by_stage.append(StageDistribution(
                stage_id=stage_id,
                stage_name=stage_name,
                count=count,
                percentage=round(pct, 1)
            ))
        
        # -------------------------------------------------------------------------
        # Cards by Horizon
        # -------------------------------------------------------------------------
        
        horizon_resp = supabase.table("cards").select("horizon").eq("status", "active").execute()
        horizon_data = horizon_resp.data or []
        
        horizon_counts = Counter()
        for card in horizon_data:
            h = card.get("horizon")
            if h:
                horizon_counts[h] += 1
        
        cards_by_horizon = []
        for horizon, label in HORIZON_LABELS.items():
            count = horizon_counts.get(horizon, 0)
            pct = (count / active_cards * 100) if active_cards > 0 else 0
            cards_by_horizon.append(HorizonDistribution(
                horizon=horizon,
                label=label,
                count=count,
                percentage=round(pct, 1)
            ))
        
        # -------------------------------------------------------------------------
        # Trending Pillars (based on recent card creation)
        # -------------------------------------------------------------------------
        
        recent_pillar_resp = supabase.table("cards").select("pillar_id, velocity_score").gte(
            "created_at", one_week_ago.isoformat()
        ).eq("status", "active").execute()
        recent_pillar_data = recent_pillar_resp.data or []
        
        recent_pillar_counts = Counter()
        recent_pillar_velocity = {}
        for card in recent_pillar_data:
            p = card.get("pillar_id")
            if p:
                recent_pillar_counts[p] += 1
                if p not in recent_pillar_velocity:
                    recent_pillar_velocity[p] = []
                if card.get("velocity_score"):
                    recent_pillar_velocity[p].append(card["velocity_score"])
        
        trending_pillars = []
        for code, count in recent_pillar_counts.most_common(6):
            name = ANALYTICS_PILLAR_DEFINITIONS.get(code, code)
            avg_vel = None
            if recent_pillar_velocity.get(code):
                avg_vel = round(sum(recent_pillar_velocity[code]) / len(recent_pillar_velocity[code]), 1)
            # Determine trend by comparing to historical average
            historical_count = pillar_counts.get(code, 0)
            weekly_avg = historical_count / 4 if historical_count > 0 else 0  # Rough 4-week avg
            trend = "stable"
            if count > weekly_avg * 1.5:
                trend = "up"
            elif count < weekly_avg * 0.5:
                trend = "down"
            trending_pillars.append(TrendingTopic(
                name=name,
                count=count,
                trend=trend,
                velocity_avg=avg_vel
            ))
        
        # -------------------------------------------------------------------------
        # Hot Topics (high velocity cards recently updated)
        # -------------------------------------------------------------------------
        
        hot_cards_resp = supabase.table("cards").select(
            "name, velocity_score"
        ).eq("status", "active").gte(
            "velocity_score", 70
        ).order("velocity_score", desc=True).limit(5).execute()
        hot_cards_data = hot_cards_resp.data or []
        
        hot_topics = []
        for card in hot_cards_data:
            hot_topics.append(TrendingTopic(
                name=card.get("name", "Unknown"),
                count=1,
                trend="up",
                velocity_avg=card.get("velocity_score")
            ))
        
        # -------------------------------------------------------------------------
        # Source Statistics
        # -------------------------------------------------------------------------
        
        # Total sources
        try:
            sources_resp = supabase.table("sources").select("id, source_type, created_at", count="exact").execute()
            total_sources = sources_resp.count or 0
            sources_data = sources_resp.data or []
            
            # Sources this week
            sources_week = sum(1 for s in sources_data if s.get("created_at") and 
                              datetime.fromisoformat(s["created_at"].replace("Z", "+00:00")).replace(tzinfo=None) > one_week_ago)
            
            # Sources by type
            source_types = Counter()
            for s in sources_data:
                st = s.get("source_type") or "unknown"
                source_types[st] += 1
            
            source_stats = SourceStats(
                total_sources=total_sources,
                sources_this_week=sources_week,
                sources_by_type=dict(source_types)
            )
        except Exception as e:
            logger.warning(f"Could not fetch source stats: {e}")
            source_stats = SourceStats()
        
        # -------------------------------------------------------------------------
        # Discovery Statistics
        # -------------------------------------------------------------------------
        
        try:
            # Discovery runs
            discovery_resp = supabase.table("discovery_runs").select(
                "id, cards_created, started_at, status"
            ).execute()
            discovery_data = discovery_resp.data or []
            
            total_runs = len(discovery_data)
            completed_runs = [r for r in discovery_data if r.get("status") == "completed"]
            runs_week = sum(1 for r in discovery_data if r.get("started_at") and 
                           datetime.fromisoformat(r["started_at"].replace("Z", "+00:00")).replace(tzinfo=None) > one_week_ago)
            
            total_discovered = sum(r.get("cards_created", 0) for r in completed_runs)
            avg_per_run = total_discovered / len(completed_runs) if completed_runs else 0
            
            # Search history count
            try:
                search_resp = supabase.table("search_history").select("id, executed_at", count="exact").execute()
                total_searches = search_resp.count or 0
                search_data = search_resp.data or []
                searches_week = sum(1 for s in search_data if s.get("executed_at") and 
                                   datetime.fromisoformat(s["executed_at"].replace("Z", "+00:00")).replace(tzinfo=None) > one_week_ago)
            except Exception:
                total_searches = 0
                searches_week = 0
            
            discovery_stats = DiscoveryStats(
                total_discovery_runs=total_runs,
                runs_this_week=runs_week,
                total_searches=total_searches,
                searches_this_week=searches_week,
                cards_discovered=total_discovered,
                avg_cards_per_run=round(avg_per_run, 1)
            )
        except Exception as e:
            logger.warning(f"Could not fetch discovery stats: {e}")
            discovery_stats = DiscoveryStats()
        
        # -------------------------------------------------------------------------
        # Workstream Engagement
        # -------------------------------------------------------------------------
        
        try:
            # Total workstreams
            ws_resp = supabase.table("workstreams").select("id, updated_at", count="exact").execute()
            total_workstreams = ws_resp.count or 0
            ws_data = ws_resp.data or []
            
            # Active workstreams (updated in last 30 days)
            active_workstreams = sum(1 for w in ws_data if w.get("updated_at") and 
                                    datetime.fromisoformat(w["updated_at"].replace("Z", "+00:00")).replace(tzinfo=None) > one_month_ago)
            
            # Unique cards in workstreams
            ws_cards_resp = supabase.table("workstream_cards").select("card_id").execute()
            ws_cards_data = ws_cards_resp.data or []
            unique_cards_in_ws = len(set(c.get("card_id") for c in ws_cards_data if c.get("card_id")))
            
            avg_cards_per_ws = len(ws_cards_data) / total_workstreams if total_workstreams > 0 else 0
            
            workstream_engagement = WorkstreamEngagement(
                total_workstreams=total_workstreams,
                active_workstreams=active_workstreams,
                unique_cards_in_workstreams=unique_cards_in_ws,
                avg_cards_per_workstream=round(avg_cards_per_ws, 1)
            )
        except Exception as e:
            logger.warning(f"Could not fetch workstream stats: {e}")
            workstream_engagement = WorkstreamEngagement()
        
        # -------------------------------------------------------------------------
        # Follow Statistics
        # -------------------------------------------------------------------------
        
        try:
            # Total follows
            follows_resp = supabase.table("card_follows").select("card_id, user_id").execute()
            follows_data = follows_resp.data or []
            
            total_follows = len(follows_data)
            unique_cards_followed = len(set(f.get("card_id") for f in follows_data if f.get("card_id")))
            unique_users_following = len(set(f.get("user_id") for f in follows_data if f.get("user_id")))
            
            # Most followed cards
            card_follow_counts = Counter(f.get("card_id") for f in follows_data if f.get("card_id"))
            top_followed = card_follow_counts.most_common(5)
            
            # Get card names for top followed
            most_followed_cards = []
            if top_followed:
                top_card_ids = [c[0] for c in top_followed]
                cards_info = supabase.table("cards").select("id, name").in_("id", top_card_ids).execute()
                cards_map = {c["id"]: c["name"] for c in (cards_info.data or [])}
                
                for card_id, count in top_followed:
                    most_followed_cards.append({
                        "card_id": card_id,
                        "card_name": cards_map.get(card_id, "Unknown"),
                        "follower_count": count
                    })
            
            follow_stats = FollowStats(
                total_follows=total_follows,
                unique_cards_followed=unique_cards_followed,
                unique_users_following=unique_users_following,
                most_followed_cards=most_followed_cards
            )
        except Exception as e:
            logger.warning(f"Could not fetch follow stats: {e}")
            follow_stats = FollowStats()
        
        # -------------------------------------------------------------------------
        # Build Response
        # -------------------------------------------------------------------------
        
        return SystemWideStats(
            total_cards=total_cards,
            active_cards=active_cards,
            cards_this_week=cards_this_week,
            cards_this_month=cards_this_month,
            cards_by_pillar=cards_by_pillar,
            cards_by_stage=cards_by_stage,
            cards_by_horizon=cards_by_horizon,
            trending_pillars=trending_pillars,
            hot_topics=hot_topics,
            source_stats=source_stats,
            discovery_stats=discovery_stats,
            workstream_engagement=workstream_engagement,
            follow_stats=follow_stats,
            generated_at=now
        )
        
    except Exception as e:
        logger.error(f"Failed to fetch system-wide stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch system-wide stats: {str(e)}"
        )


@app.get("/api/v1/analytics/personal-stats", response_model=PersonalStats)
async def get_personal_stats(
    current_user: dict = Depends(get_current_user)
):
    """
    Get personal analytics for the current user.
    
    Returns:
    - Cards the user is following
    - Comparison to community engagement
    - Pillar affinity analysis
    - Popular cards the user isn't following (social discovery)
    """
    from datetime import timedelta
    from collections import Counter
    
    try:
        user_id = current_user["id"]
        now = datetime.now()
        one_week_ago = now - timedelta(days=7)
        
        # -------------------------------------------------------------------------
        # User's Follows
        # -------------------------------------------------------------------------
        
        user_follows_resp = supabase.table("card_follows").select(
            "card_id, priority, created_at, cards(id, name, pillar_id, horizon, velocity_score)"
        ).eq("user_id", user_id).execute()
        user_follows_data = user_follows_resp.data or []
        
        # Get follower counts for each card
        all_follows_resp = supabase.table("card_follows").select("card_id").execute()
        all_follows_data = all_follows_resp.data or []
        card_follower_counts = Counter(f.get("card_id") for f in all_follows_data if f.get("card_id"))
        
        user_card_ids = set()
        following = []
        for f in user_follows_data:
            card = f.get("cards", {})
            if not card:
                continue
            card_id = card.get("id") or f.get("card_id")
            user_card_ids.add(card_id)
            
            followed_at = f.get("created_at")
            if followed_at:
                try:
                    followed_at = datetime.fromisoformat(followed_at.replace("Z", "+00:00"))
                except:
                    followed_at = now
            else:
                followed_at = now
            
            following.append(UserFollowItem(
                card_id=card_id,
                card_name=card.get("name", "Unknown"),
                pillar_id=card.get("pillar_id"),
                horizon=card.get("horizon"),
                velocity_score=card.get("velocity_score"),
                followed_at=followed_at,
                priority=f.get("priority", "medium"),
                follower_count=card_follower_counts.get(card_id, 1)
            ))
        
        total_following = len(following)
        
        # -------------------------------------------------------------------------
        # Engagement Comparison
        # -------------------------------------------------------------------------
        
        # Get all users' follow counts
        users_resp = supabase.table("users").select("id").execute()
        all_users = users_resp.data or []
        total_users = len(all_users)
        
        # User follow counts per user
        user_follow_counts = Counter(f.get("user_id") for f in all_follows_data if f.get("user_id"))
        all_follow_counts = list(user_follow_counts.values()) or [0]
        avg_follows = sum(all_follow_counts) / len(all_follow_counts) if all_follow_counts else 0
        
        # User workstreams
        user_ws_resp = supabase.table("workstreams").select("id", count="exact").eq("user_id", user_id).execute()
        user_workstream_count = user_ws_resp.count or 0
        
        # All workstreams per user
        all_ws_resp = supabase.table("workstreams").select("user_id").execute()
        ws_per_user = Counter(w.get("user_id") for w in (all_ws_resp.data or []) if w.get("user_id"))
        all_ws_counts = list(ws_per_user.values()) or [0]
        avg_workstreams = sum(all_ws_counts) / len(all_ws_counts) if all_ws_counts else 0
        
        # Calculate percentiles
        user_follows_count = user_follow_counts.get(user_id, 0)
        follows_below = sum(1 for c in all_follow_counts if c < user_follows_count)
        user_percentile_follows = (follows_below / len(all_follow_counts) * 100) if all_follow_counts else 0
        
        ws_below = sum(1 for c in all_ws_counts if c < user_workstream_count)
        user_percentile_workstreams = (ws_below / len(all_ws_counts) * 100) if all_ws_counts else 0
        
        engagement = UserEngagementComparison(
            user_follow_count=user_follows_count,
            avg_community_follows=round(avg_follows, 1),
            user_workstream_count=user_workstream_count,
            avg_community_workstreams=round(avg_workstreams, 1),
            user_percentile_follows=round(user_percentile_follows, 1),
            user_percentile_workstreams=round(user_percentile_workstreams, 1)
        )
        
        # -------------------------------------------------------------------------
        # Pillar Affinity
        # -------------------------------------------------------------------------
        
        # User's pillar distribution
        user_pillar_counts = Counter()
        for f in following:
            if f.pillar_id:
                user_pillar_counts[f.pillar_id] += 1
        
        # Community pillar distribution from all follows
        community_pillar_counts = Counter()
        # Get pillar for all followed cards
        all_card_ids = list(set(f.get("card_id") for f in all_follows_data if f.get("card_id")))
        if all_card_ids:
            cards_pillar_resp = supabase.table("cards").select("id, pillar_id").in_("id", all_card_ids).execute()
            card_pillars = {c["id"]: c.get("pillar_id") for c in (cards_pillar_resp.data or [])}
            for f in all_follows_data:
                card_id = f.get("card_id")
                pillar = card_pillars.get(card_id)
                if pillar:
                    community_pillar_counts[pillar] += 1
        
        total_community_follows = sum(community_pillar_counts.values()) or 1
        
        pillar_affinity = []
        for code, name in ANALYTICS_PILLAR_DEFINITIONS.items():
            user_count = user_pillar_counts.get(code, 0)
            user_pct = (user_count / total_following * 100) if total_following > 0 else 0
            community_pct = (community_pillar_counts.get(code, 0) / total_community_follows * 100)
            affinity = user_pct - community_pct  # Positive = more interested than avg
            
            pillar_affinity.append(PillarAffinity(
                pillar_code=code,
                pillar_name=name,
                user_count=user_count,
                user_percentage=round(user_pct, 1),
                community_percentage=round(community_pct, 1),
                affinity_score=round(affinity, 1)
            ))
        
        # Sort by affinity score descending
        pillar_affinity.sort(key=lambda x: x.affinity_score, reverse=True)
        
        # -------------------------------------------------------------------------
        # Popular Cards Not Followed (Social Discovery)
        # -------------------------------------------------------------------------
        
        # Get most popular cards that user doesn't follow
        popular_card_ids = [cid for cid, count in card_follower_counts.most_common(20) 
                           if cid not in user_card_ids and count >= 2][:10]
        
        popular_not_followed = []
        if popular_card_ids:
            popular_cards_resp = supabase.table("cards").select(
                "id, name, summary, pillar_id, horizon, velocity_score"
            ).in_("id", popular_card_ids).eq("status", "active").execute()
            
            for card in (popular_cards_resp.data or []):
                card_id = card.get("id")
                popular_not_followed.append(PopularCard(
                    card_id=card_id,
                    card_name=card.get("name", "Unknown"),
                    summary=card.get("summary", "")[:200],
                    pillar_id=card.get("pillar_id"),
                    horizon=card.get("horizon"),
                    velocity_score=card.get("velocity_score"),
                    follower_count=card_follower_counts.get(card_id, 0),
                    is_followed_by_user=False
                ))
        
        # -------------------------------------------------------------------------
        # Recently Popular (new follows in last week)
        # -------------------------------------------------------------------------
        
        # This would require timestamp on card_follows - using created_at if available
        recent_follows_resp = supabase.table("card_follows").select("card_id, created_at").execute()
        recent_follows_data = recent_follows_resp.data or []
        
        recent_card_counts = Counter()
        for f in recent_follows_data:
            created_at = f.get("created_at")
            if created_at:
                try:
                    dt = datetime.fromisoformat(created_at.replace("Z", "+00:00")).replace(tzinfo=None)
                    if dt > one_week_ago:
                        recent_card_counts[f.get("card_id")] += 1
                except:
                    pass
        
        recently_popular_ids = [cid for cid, count in recent_card_counts.most_common(10) 
                                if cid not in user_card_ids and count >= 1][:5]
        
        recently_popular = []
        if recently_popular_ids:
            recent_cards_resp = supabase.table("cards").select(
                "id, name, summary, pillar_id, horizon, velocity_score"
            ).in_("id", recently_popular_ids).eq("status", "active").execute()
            
            for card in (recent_cards_resp.data or []):
                card_id = card.get("id")
                recently_popular.append(PopularCard(
                    card_id=card_id,
                    card_name=card.get("name", "Unknown"),
                    summary=card.get("summary", "")[:200],
                    pillar_id=card.get("pillar_id"),
                    horizon=card.get("horizon"),
                    velocity_score=card.get("velocity_score"),
                    follower_count=recent_card_counts.get(card_id, 0),
                    is_followed_by_user=False
                ))
        
        # -------------------------------------------------------------------------
        # User Workstream Stats
        # -------------------------------------------------------------------------
        
        user_ws_cards_resp = supabase.table("workstream_cards").select(
            "card_id, workstreams!inner(user_id)"
        ).eq("workstreams.user_id", user_id).execute()
        cards_in_workstreams = len(set(c.get("card_id") for c in (user_ws_cards_resp.data or []) if c.get("card_id")))
        
        # -------------------------------------------------------------------------
        # Build Response
        # -------------------------------------------------------------------------
        
        return PersonalStats(
            following=following,
            total_following=total_following,
            engagement=engagement,
            pillar_affinity=pillar_affinity,
            popular_not_followed=popular_not_followed,
            recently_popular=recently_popular,
            workstream_count=user_workstream_count,
            cards_in_workstreams=cards_in_workstreams,
            generated_at=now
        )
        
    except Exception as e:
        logger.error(f"Failed to fetch personal stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch personal stats: {str(e)}"
        )


# Lifecycle management
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle - startup and shutdown"""
    # Startup
    enable_scheduler = os.getenv("FORESIGHT_ENABLE_SCHEDULER", "false").strip().lower() in ("1", "true", "yes", "y", "on")
    if enable_scheduler:
        start_scheduler()
    else:
        logger.info("Scheduler disabled (set FORESIGHT_ENABLE_SCHEDULER=true to enable)")
    logger.info("Foresight API started")
    yield
    # Shutdown
    try:
        if getattr(scheduler, "running", False):
            scheduler.shutdown()
    except Exception:
        pass
    logger.info("Foresight API shutdown complete")


# Update app with lifespan
app.router.lifespan_context = lifespan


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
