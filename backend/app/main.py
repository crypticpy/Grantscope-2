"""
Foresight API - FastAPI backend for Austin Strategic Research System
"""

import logging
import os
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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


class DiscoveryConfigRequest(BaseModel):
    """Request model for discovery run configuration."""
    max_queries_per_run: int = Field(default=100, le=200, ge=1, description="Maximum queries per run")
    max_sources_total: int = Field(default=500, le=1000, ge=10, description="Maximum sources to process")
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

@app.get("/api/v1/cards/{card_id}", response_model=Card)
async def get_card(card_id: str):
    """Get specific card"""
    response = supabase.table("cards").select("*").eq("id", card_id).execute()
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
    query: str,
    limit: int = 10
):
    """Search cards using vector similarity"""
    try:
        # Get embedding for search query
        embedding_response = openai_client.embeddings.create(
            model="text-embedding-ada-002",
            input=query
        )
        query_embedding = embedding_response.data[0].embedding
        
        # Search using vector similarity
        search_response = supabase.rpc(
            "search_cards",
            {
                "query_embedding": query_embedding,
                "match_threshold": 0.7,
                "match_count": limit
            }
        ).execute()
        
        return search_response.data
    except Exception as e:
        # Fallback to text search
        response = supabase.table("cards").select("*").or_(
            f"name.ilike.%{query}%,summary.ilike.%{query}%"
        ).limit(limit).execute()
        return response.data

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

    Args:
        limit: Maximum number of cards to return (default: 20)
        offset: Number of cards to skip for pagination (default: 0)
        pillar_id: Optional filter by pillar ID

    Returns:
        List of cards with review_status in ('discovered', 'pending_review')
    """
    query = supabase.table("cards").select("*").in_(
        "review_status", ["discovered", "pending_review"]
    )

    if pillar_id:
        query = query.eq("pillar_id", pillar_id)

    # Order by ai_confidence DESC, discovered_at DESC
    response = query.order(
        "ai_confidence", desc=True
    ).order(
        "discovered_at", desc=True
    ).range(offset, offset + limit - 1).execute()

    return response.data


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

        return response.data[0]
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


# ============================================================================
# Discovery Run Management Endpoints
# ============================================================================

@app.post("/api/v1/discovery/run", response_model=DiscoveryRun)
async def trigger_discovery_run(
    config: DiscoveryConfigRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Trigger a manual discovery run.

    Creates a new discovery run with the specified configuration and
    executes it as a background task. Returns immediately with a run_id
    for polling status.

    Args:
        config: Discovery run configuration

    Returns:
        Discovery run record with status 'queued'
    """
    now = datetime.now().isoformat()
    run_id = str(uuid.uuid4())

    # Create discovery run record
    run_record = {
        "id": run_id,
        "status": "queued",
        "config": config.dict(),
        "created_by": current_user["id"],
        "cards_discovered": 0,
        "cards_auto_approved": 0,
        "cards_pending_review": 0,
        "sources_processed": 0,
        "created_at": now
    }

    response = supabase.table("discovery_runs").insert(run_record).execute()

    if not response.data:
        raise HTTPException(status_code=500, detail="Failed to create discovery run")

    # Start discovery in background
    asyncio.create_task(
        execute_discovery_run_background(run_id, config, current_user["id"])
    )

    logger.info(f"Discovery run {run_id} queued by user {current_user['id']}")

    return DiscoveryRun(**response.data[0])


async def execute_discovery_run_background(
    run_id: str,
    config: DiscoveryConfigRequest,
    user_id: str
):
    """
    Background task to execute a discovery run.

    Phases:
    1. Generate search queries based on taxonomy and existing cards
    2. Execute searches across configured sources
    3. Triage and filter results
    4. Create discovered cards (pending review or auto-approved)
    5. Update run status with results
    """
    try:
        # Update status to processing
        supabase.table("discovery_runs").update({
            "status": "processing",
            "started_at": datetime.now().isoformat()
        }).eq("id", run_id).execute()

        # Initialize counters
        cards_discovered = 0
        cards_auto_approved = 0
        cards_pending_review = 0
        sources_processed = 0

        # Get blocked topics to exclude
        blocked_response = supabase.table("discovery_blocks").select("topic_pattern").execute()
        blocked_patterns = [b["topic_pattern"] for b in blocked_response.data]

        # Get taxonomy for query generation
        pillars_query = supabase.table("pillars").select("*")
        if config.pillars_filter:
            pillars_query = pillars_query.in_("id", config.pillars_filter)
        pillars_response = pillars_query.execute()

        # Simulate discovery process (replace with actual implementation)
        # This would typically call ResearchService or a dedicated DiscoveryService
        service = ResearchService(supabase, openai_client)

        for pillar in pillars_response.data:
            if config.dry_run:
                # Dry run - just count what would be processed
                sources_processed += 10
                cards_discovered += 2
                continue

            # Get goals for this pillar
            goals_response = supabase.table("goals").select("*").eq("pillar_id", pillar["id"]).execute()

            for goal in goals_response.data:
                try:
                    # Generate discovery query
                    query = f"{pillar['name']} {goal['name']} Austin strategic initiatives"

                    # Skip blocked topics
                    if any(bp in query.lower() for bp in blocked_patterns):
                        continue

                    # Execute research (limited by config)
                    if sources_processed >= config.max_sources_total:
                        break

                    # Placeholder for actual discovery logic
                    # This would use service.execute_discovery() or similar
                    sources_processed += 5

                    # Check confidence for auto-approval
                    ai_confidence = 0.9  # Placeholder - would come from AI analysis

                    if ai_confidence >= config.auto_approve_threshold:
                        cards_auto_approved += 1
                    else:
                        cards_pending_review += 1

                    cards_discovered += 1

                except Exception as e:
                    logger.error(f"Discovery error for goal {goal['id']}: {str(e)}")

        # Update run as completed
        supabase.table("discovery_runs").update({
            "status": "completed",
            "completed_at": datetime.now().isoformat(),
            "cards_discovered": cards_discovered,
            "cards_auto_approved": cards_auto_approved,
            "cards_pending_review": cards_pending_review,
            "sources_processed": sources_processed
        }).eq("id", run_id).execute()

        logger.info(f"Discovery run {run_id} completed: {cards_discovered} cards discovered")

    except Exception as e:
        logger.error(f"Discovery run {run_id} failed: {str(e)}")
        supabase.table("discovery_runs").update({
            "status": "failed",
            "completed_at": datetime.now().isoformat(),
            "error_message": str(e)
        }).eq("id", run_id).execute()


@app.get("/api/v1/discovery/runs", response_model=List[DiscoveryRun])
async def list_discovery_runs(
    current_user: dict = Depends(get_current_user),
    limit: int = 20,
    offset: int = 0
):
    """
    List discovery runs.

    Returns paginated list of discovery runs ordered by start time descending.

    Args:
        limit: Maximum number of runs to return (default: 20)
        offset: Number of runs to skip for pagination

    Returns:
        List of discovery run records
    """
    response = supabase.table("discovery_runs").select("*").order(
        "started_at", desc=True
    ).range(offset, offset + limit - 1).execute()

    return [DiscoveryRun(**run) for run in response.data]


@app.get("/api/v1/discovery/runs/{run_id}", response_model=DiscoveryRun)
async def get_discovery_run(
    run_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get details of a specific discovery run.

    Args:
        run_id: UUID of the discovery run

    Returns:
        Discovery run record with full details

    Raises:
        HTTPException 404: Discovery run not found
    """
    response = supabase.table("discovery_runs").select("*").eq("id", run_id).execute()

    if not response.data:
        raise HTTPException(status_code=404, detail="Discovery run not found")

    return DiscoveryRun(**response.data[0])


@app.post("/api/v1/discovery/runs/{run_id}/cancel")
async def cancel_discovery_run(
    run_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Cancel a discovery run.

    Only runs with status 'queued' or 'processing' can be cancelled.

    Args:
        run_id: UUID of the discovery run to cancel

    Returns:
        Updated discovery run record

    Raises:
        HTTPException 404: Discovery run not found
        HTTPException 400: Run cannot be cancelled (already completed/failed/cancelled)
    """
    # Get current run status
    response = supabase.table("discovery_runs").select("*").eq("id", run_id).execute()

    if not response.data:
        raise HTTPException(status_code=404, detail="Discovery run not found")

    run = response.data[0]

    # Check if run can be cancelled
    if run["status"] not in ["queued", "processing"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel run with status '{run['status']}'. Only 'queued' or 'processing' runs can be cancelled."
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
            "status": "queued",
            "config": config.dict(),
            "created_by": user_id,
            "cards_discovered": 0,
            "cards_auto_approved": 0,
            "cards_pending_review": 0,
            "sources_processed": 0,
            "created_at": datetime.now().isoformat()
        }

        supabase.table("discovery_runs").insert(run_record).execute()

        # Execute discovery
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
        # Create discovery run record
        run_record = {
            "status": "running",
            "triggered_by": "manual",
            "triggered_by_user": current_user["id"],
            "summary_report": {
                "config": config.dict()
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
    Background task to execute discovery run.

    Updates run status through lifecycle: running -> completed/failed
    """
    try:
        # TODO: Implement actual discovery logic here
        # For now, just mark as completed after a brief delay
        await asyncio.sleep(1)

        # Update as completed
        supabase.table("discovery_runs").update({
            "status": "completed",
            "completed_at": datetime.now().isoformat(),
            "cards_created": 0,
            "cards_enriched": 0,
            "cards_deduplicated": 0,
            "sources_found": 0
        }).eq("id", run_id).execute()

        logger.info(f"Discovery run {run_id} completed")

    except Exception as e:
        logger.error(f"Discovery run {run_id} failed: {str(e)}")
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
