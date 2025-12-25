"""
Foresight API - FastAPI backend for Austin Strategic Research System
"""

import logging
import os
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
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
import openai
from apscheduler.schedulers.asyncio import AsyncIOScheduler

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

# CORS middleware - Configure allowed origins from environment
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
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


# Global exception handler to ensure CORS headers on error responses
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Handle all unhandled exceptions and ensure CORS headers are included.

    This prevents CORS errors in the browser when the server returns 500 errors,
    as the CORSMiddleware may not add headers when an exception is raised.
    """
    # Get the origin from the request
    origin = request.headers.get("origin", "")

    # Build response headers - only add CORS if origin is allowed
    headers = {}
    if origin in ALLOWED_ORIGINS:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"

    # Log the error for debugging
    logger.error(f"Unhandled exception: {type(exc).__name__}: {str(exc)}")

    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
        headers=headers
    )


# Security
security = HTTPBearer()

# Initialize clients
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_ANON_KEY")
supabase_service_key = os.getenv("SUPABASE_SERVICE_KEY")
openai_api_key = os.getenv("OPENAI_API_KEY")

if not all([supabase_url, supabase_key, supabase_service_key]):
    raise ValueError("Missing required environment variables")

supabase: Client = create_client(supabase_url, supabase_service_key)
openai_client = openai.OpenAI(api_key=openai_api_key)

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
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current authenticated user"""
    try:
        token = credentials.credentials
        response = supabase.auth.get_user(token)
        if response.user:
            # Get user profile
            profile_response = supabase.table("users").select("*").eq("id", response.user.id).execute()
            if profile_response.data:
                return profile_response.data[0]
            else:
                logger.warning(f"User profile not found for user_id: {response.user.id}")
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User profile not found")
        else:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials")

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
    query = supabase.table("cards").select("*").in_(
        "review_status", ["discovered", "pending_review"]
    )

    if pillar_id:
        query = query.eq("pillar_id", pillar_id)

    response = query.order(
        "ai_confidence", desc=True
    ).order(
        "discovered_at", desc=True
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
                # Get embedding for search query
                embedding_response = openai_client.embeddings.create(
                    model="text-embedding-ada-002",
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

    # Fetch card from database
    response = supabase.table("cards").select("*").eq("id", card_id).single().execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Card not found: {card_id}"
        )

    card_data = response.data

    # Create CardExportData from raw data
    try:
        export_data = CardExportData(
            id=card_data["id"],
            name=card_data["name"],
            slug=card_data.get("slug", ""),
            summary=card_data.get("summary"),
            description=card_data.get("description"),
            pillar_id=card_data.get("pillar_id"),
            goal_id=card_data.get("goal_id"),
            anchor_id=card_data.get("anchor_id"),
            stage_id=card_data.get("stage_id"),
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
    response = supabase.table("cards").select(
        "id", count="exact"
    ).in_(
        "review_status", ["discovered", "pending_review"]
    ).execute()

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
async def bulk_review_cards(
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

# Pillar definitions for analytics (matches VALID_PILLAR_CODES)
ANALYTICS_PILLAR_DEFINITIONS = {
    "CH": "Community Health & Sustainability",
    "EW": "Economic & Workforce Development",
    "HG": "High-Performing Government",
    "HH": "Homelessness & Housing",
    "MC": "Mobility & Critical Infrastructure",
    "PS": "Public Safety"
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


@app.get("/api/v1/analytics/insights", response_model=InsightsResponse)
async def get_analytics_insights(
    pillar_id: Optional[str] = Query(None, pattern=r"^[A-Z]{2}$", description="Filter by pillar code"),
    limit: int = Query(5, ge=1, le=10, description="Number of insights to generate"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get AI-generated strategic insights for top emerging trends.

    Returns insights for the highest-scoring active cards, optionally filtered by pillar.
    Uses OpenAI to generate strategic insights based on trend data.

    If AI service is unavailable, returns an error message with empty insights list.
    """
    try:
        # Build query for top emerging trends
        query = supabase.table("cards").select(
            "id, name, summary, pillar_id, horizon, velocity_score, impact_score, relevance_score, novelty_score"
        ).eq("status", "active")

        # Apply pillar filter if provided
        if pillar_id:
            query = query.eq("pillar_id", pillar_id)

        # Order by combined score (velocity + impact + relevance)
        # Fetch more than needed to ensure we have enough after filtering nulls
        response = query.order("velocity_score", desc=True).limit(limit * 2).execute()

        if not response.data:
            return InsightsResponse(
                insights=[],
                generated_at=datetime.now(),
                ai_available=True
            )

        # Filter cards with valid scores and calculate combined score
        cards_with_scores = []
        for card in response.data:
            velocity = card.get("velocity_score") or 0
            impact = card.get("impact_score") or 0
            relevance = card.get("relevance_score") or 0
            novelty = card.get("novelty_score") or 0
            combined_score = (velocity + impact + relevance + novelty) / 4

            cards_with_scores.append({
                **card,
                "combined_score": combined_score
            })

        # Sort by combined score and take top N
        cards_with_scores.sort(key=lambda x: x["combined_score"], reverse=True)
        top_cards = cards_with_scores[:limit]

        if not top_cards:
            return InsightsResponse(
                insights=[],
                generated_at=datetime.now(),
                ai_available=True
            )

        # Format trends data for the prompt
        trends_data = "\n".join([
            f"- {card['name']}: {card.get('summary', 'No summary available')[:200]} "
            f"(Pillar: {card.get('pillar_id', 'N/A')}, Horizon: {card.get('horizon', 'N/A')}, "
            f"Score: {card['combined_score']:.1f})"
            for card in top_cards
        ])

        try:
            # Generate insights using OpenAI
            prompt = INSIGHTS_GENERATION_PROMPT.format(trends_data=trends_data)

            ai_response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=1000,
                timeout=30
            )

            import json
            result = json.loads(ai_response.choices[0].message.content)

            # Build response with card metadata
            insights = []
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

            return InsightsResponse(
                insights=insights,
                generated_at=datetime.now(),
                ai_available=True
            )

        except Exception as ai_error:
            # AI service failed - return fallback with error message
            logger.warning(f"AI insights generation failed: {str(ai_error)}")

            # Return basic insights without AI generation
            fallback_insights = [
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

            return InsightsResponse(
                insights=fallback_insights,
                generated_at=datetime.now(),
                ai_available=False,
                fallback_message="Insights temporarily unavailable. Showing trend summaries instead."
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
            "summary_report": {"config": config.dict()}
        }

        supabase.table("discovery_runs").insert(run_record).execute()

        # Execute discovery (pass existing run_id to avoid duplicate record)
        await execute_discovery_run_background(run_id, config, user_id)

        logger.info(f"Weekly discovery run {run_id} completed")

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

    # Filter by stage_ids
    if workstream.get("stage_ids"):
        query = query.in_("stage_id", workstream["stage_ids"])

    # Filter by horizon (skip if ALL)
    if workstream.get("horizon") and workstream["horizon"] != "ALL":
        query = query.eq("horizon", workstream["horizon"])

    response = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    cards = response.data

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
async def trigger_manual_scan(current_user: dict = Depends(get_current_user)):
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
async def create_research_task(
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
    asyncio.create_task(
        execute_research_task_background(task_id, task_data, current_user["id"])
    )

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
        # Update status to processing
        supabase.table("research_tasks").update({
            "status": "processing",
            "started_at": datetime.now().isoformat()
        }).eq("id", task_id).execute()

        # Execute based on task type
        if task_data.task_type == "update":
            result = await service.execute_update(task_data.card_id, task_id)
        elif task_data.task_type == "deep_research":
            result = await service.execute_deep_research(task_data.card_id, task_id)
        elif task_data.task_type == "workstream_analysis":
            result = await service.execute_workstream_analysis(
                task_data.workstream_id, task_id, user_id
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
            "completed_at": datetime.now().isoformat(),
            "result_summary": result_summary
        }).eq("id", task_id).execute()

    except Exception as e:
        # Update as failed
        supabase.table("research_tasks").update({
            "status": "failed",
            "completed_at": datetime.now().isoformat(),
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

    return ResearchTask(**result.data)


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
async def trigger_discovery_run(
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

        # Execute discovery in background (non-blocking)
        asyncio.create_task(
            execute_discovery_run_background(run_id, config, current_user["id"])
        )

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
        service = DiscoveryService(supabase, openai_client)
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
            "summary_report": {"markdown": result.summary_report, "errors": result.errors}
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
    response = supabase.table("saved_searches").select("*").eq(
        "user_id", current_user["id"]
    ).order("last_used_at", desc=True).execute()

    saved_searches = [SavedSearch(**ss) for ss in response.data]
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

    response = supabase.table("saved_searches").insert(ss_dict).execute()
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
    response = supabase.table("saved_searches").select("*").eq(
        "id", saved_search_id
    ).execute()

    if not response.data:
        raise HTTPException(status_code=404, detail="Saved search not found")

    saved_search = response.data[0]

    # Verify ownership
    if saved_search["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to access this saved search")

    # Update last_used_at timestamp
    update_response = supabase.table("saved_searches").update({
        "last_used_at": datetime.now().isoformat()
    }).eq("id", saved_search_id).execute()

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
    ss_check = supabase.table("saved_searches").select("*").eq(
        "id", saved_search_id
    ).execute()

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
    response = supabase.table("saved_searches").update(update_dict).eq(
        "id", saved_search_id
    ).execute()

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
    ss_check = supabase.table("saved_searches").select("*").eq(
        "id", saved_search_id
    ).execute()

    if not ss_check.data:
        raise HTTPException(status_code=404, detail="Saved search not found")

    # Verify ownership
    if ss_check.data[0]["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to delete this saved search")

    # Perform delete
    supabase.table("saved_searches").delete().eq("id", saved_search_id).execute()

    return {"status": "deleted", "message": "Saved search successfully deleted"}


# Add scheduler for nightly jobs
def start_scheduler():
    """Start the APScheduler for background jobs"""
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
                    task_id = task_result.data[0]["id"]
                    # Execute in background
                    asyncio.create_task(
                        execute_research_task_background(
                            task_id,
                            ResearchTaskCreate(card_id=card["id"], task_type="update"),
                            user_id
                        )
                    )
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




# Lifecycle management
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle - startup and shutdown"""
    # Startup
    start_scheduler()
    logger.info("Foresight API started")
    yield
    # Shutdown
    scheduler.shutdown()
    logger.info("Foresight API shutdown complete")


# Update app with lifespan
app.router.lifespan_context = lifespan


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
