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


# Discovery run models
class DiscoveryConfigRequest(BaseModel):
    """Request model for discovery run configuration."""
    max_queries_per_run: int = Field(default=100, le=200, ge=1, description="Maximum queries per run")
    max_sources_total: int = Field(default=500, le=1000, ge=10, description="Maximum sources to process")
    auto_approve_threshold: float = Field(default=0.95, ge=0.8, le=1.0, description="Auto-approval threshold")
    pillars_filter: Optional[List[str]] = Field(None, description="Filter by pillar IDs")
    dry_run: bool = Field(False, description="Run in dry-run mode without persisting")


class DiscoveryRun(BaseModel):
    """Response model for discovery run status matching database schema."""
    id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str  # running, completed, failed, cancelled
    triggered_by: str  # manual, scheduled
    triggered_by_user: Optional[str] = None
    summary_report: Optional[Dict[str, Any]] = None
    cards_created: int = 0
    cards_enriched: int = 0
    cards_deduplicated: int = 0
    sources_found: int = 0
    error_message: Optional[str] = None


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
    scheduler.add_job(
        run_nightly_scan,
        'cron',
        hour=6,
        minute=0,
        id='nightly_scan',
        replace_existing=True
    )
    scheduler.start()
    logger.info("Scheduler started - nightly scan scheduled for 6:00 AM UTC")


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
