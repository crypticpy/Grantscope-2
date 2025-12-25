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


class ScoreBreakdown(BaseModel):
    """Breakdown of individual scoring factors for discovery queue transparency"""
    novelty_score: float = Field(..., ge=0.0, le=1.0, description="Score based on card recency and newness")
    workstream_relevance_score: float = Field(..., ge=0.0, le=1.0, description="Score based on workstream filter matches")
    pillar_alignment_score: float = Field(..., ge=0.0, le=1.0, description="Score based on user's active workstream pillars")
    followed_context_score: float = Field(..., ge=0.0, le=1.0, description="Score based on similarity to followed cards")


class PersonalizedCard(Card):
    """Card model extended with personalized discovery scoring for the discovery queue"""
    discovery_score: float = Field(..., ge=0.0, description="Combined multi-factor personalization score")
    score_breakdown: Optional[ScoreBreakdown] = Field(None, description="Optional breakdown of scoring factors")


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


# ============================================================================
# DISCOVERY QUEUE SCORING - Import from dedicated module
# ============================================================================
from app.discovery_scoring import (
    calculate_novelty_score,
    calculate_workstream_relevance,
    calculate_pillar_alignment,
    calculate_followed_context,
    calculate_discovery_score,
    NOVELTY_WEIGHT,
    RELEVANCE_WEIGHT,
    ALIGNMENT_WEIGHT,
    CONTEXT_WEIGHT,
)


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
    articles_scraped: int = 0
    articles_processed: int = 0
    articles_enriched: int = 0
    tokens_used: int = 0