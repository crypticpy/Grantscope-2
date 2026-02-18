"""GrantScope2 API - FastAPI backend for Austin Strategic Research System.

Slim app-factory module.  All endpoint logic lives in ``app.routers.*``;
scheduled background jobs live in ``app.scheduler``.
"""

import asyncio
import logging
import os
import uuid as _uuid
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.gzip import GZipMiddleware

from app.auth import authenticate_user, create_access_token, get_current_user
from app.database import get_db
from app.models.db.user import User
from app.security import setup_security
from app.scheduler import start_scheduler, shutdown_scheduler

# Routers
from app.routers.health import router as health_router
from app.routers.users import router as users_router
from app.routers.search import router as search_router
from app.routers.notifications import router as notifications_router
from app.routers.chat import router as chat_router
from app.routers.cards import router as cards_router
from app.routers.card_subresources import router as card_subresources_router
from app.routers.card_review import router as card_review_router
from app.routers.card_export import router as card_export_router
from app.routers.workstreams import router as workstreams_router
from app.routers.workstream_kanban import router as workstream_kanban_router
from app.routers.workstream_scans import router as workstream_scans_router
from app.routers.briefs import router as briefs_router
from app.routers.analytics import router as analytics_router
from app.routers.discovery import router as discovery_router
from app.routers.research import router as research_router
from app.routers.classification import router as classification_router
from app.routers.ai_helpers import router as ai_helpers_router
from app.routers.pattern_insights import router as pattern_insights_router
from app.routers.admin import router as admin_router
from app.routers.feeds import router as feeds_router
from app.routers.proposals import router as proposals_router
from app.routers.wizard import router as wizard_router

# New feature routers (SQLAlchemy-based)
from app.routers.checklist import router as checklist_router
from app.routers.budget import router as budget_router
from app.routers.attachments import router as attachments_router
from app.routers.exports import router as exports_router
from app.routers.collaboration import router as collaboration_router
from app.routers.applications import router as applications_router
from app.routers.dashboard import router as dashboard_router
from app.routers.reference import router as reference_router

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CORS helpers
# ---------------------------------------------------------------------------


def _build_allowed_origins() -> list[str]:
    """Return validated CORS origins based on ENVIRONMENT."""
    environment = os.getenv("ENVIRONMENT", "development").lower()

    if environment == "production":
        default = "https://grantscope2.vercel.app,https://grantscope2-frontend-beta.vercel.app"
        raw = os.getenv("ALLOWED_ORIGINS", default).split(",")
        origins: list[str] = []
        for origin in raw:
            origin = origin.strip()
            if not origin:
                continue
            if not origin.startswith("https://"):
                print(
                    f"[CORS] WARNING: Rejecting non-HTTPS origin in production: {origin}"
                )
                continue
            if "localhost" in origin or "127.0.0.1" in origin:
                print(
                    f"[CORS] WARNING: Rejecting localhost origin in production: {origin}"
                )
                continue
            origins.append(origin)
        if not origins:
            origins = ["https://grantscope2.vercel.app"]
            print(
                "[CORS] WARNING: No valid origins configured, using default production origin"
            )
    else:
        default = "http://localhost:3000,http://localhost:5173,http://localhost:5174"
        raw = os.getenv("ALLOWED_ORIGINS", default).split(",")
        origins = [o.strip() for o in raw if o.strip()]

    if not origins:
        raise ValueError(
            "CORS configuration error: No valid allowed origins configured"
        )

    print(f"[CORS] Environment: {environment}")
    print(f"[CORS] Allowed origins: {origins}")
    return origins


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Manage application lifecycle -- startup and shutdown."""
    enable_scheduler = os.getenv(
        "GRANTSCOPE_ENABLE_SCHEDULER", "false"
    ).strip().lower() in ("1", "true", "yes", "y", "on")

    if enable_scheduler:
        start_scheduler()
    else:
        logger.info(
            "Scheduler disabled (set GRANTSCOPE_ENABLE_SCHEDULER=true to enable)"
        )

    # Start embedded worker for processing discovery runs, research tasks, etc.
    worker_task = None
    enable_worker = os.getenv("GRANTSCOPE_EMBED_WORKER", "true").strip().lower() in (
        "1",
        "true",
        "yes",
        "y",
        "on",
    )

    if enable_worker:
        from app.worker import GrantScopeWorker

        _embedded_worker = GrantScopeWorker()
        worker_task = asyncio.create_task(_embedded_worker.run())
        logger.info("Embedded worker started within web process")

    logger.info("GrantScope2 API started")
    yield

    if worker_task and _embedded_worker:
        _embedded_worker.request_stop()
        try:
            await asyncio.wait_for(worker_task, timeout=5.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            worker_task.cancel()
        logger.info("Embedded worker stopped")

    shutdown_scheduler()
    logger.info("GrantScope2 API shutdown complete")


# ---------------------------------------------------------------------------
# Auth request / response models
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    email: str
    password: str


# ---------------------------------------------------------------------------
# Inline auth routes (added directly to the app, no separate router file)
# ---------------------------------------------------------------------------


def _register_auth_routes(application: FastAPI) -> None:
    """Register ``/api/v1/auth/*`` endpoints on *application*."""

    @application.post("/api/v1/auth/login")
    async def login(body: LoginRequest):
        user = authenticate_user(body.email, body.password)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        token = create_access_token(user)
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": user,
        }

    @application.get("/api/v1/auth/me")
    async def auth_me(
        user=Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        """Return current user profile, enriched with DB-stored fields."""
        try:
            user_uuid = _uuid.UUID(user["id"])
            result = await db.execute(
                select(
                    User.profile_completed_at,
                    User.profile_step,
                    User.department_id,
                    User.title,
                ).where(User.id == user_uuid)
            )
            row = result.one_or_none()
            if row:
                enriched = {**user}
                if row.profile_completed_at:
                    enriched["profile_completed_at"] = (
                        row.profile_completed_at.isoformat()
                    )
                if row.profile_step is not None:
                    enriched["profile_step"] = row.profile_step
                if row.department_id:
                    enriched["department_id"] = row.department_id
                if row.title:
                    enriched["title"] = row.title
                return enriched
        except Exception as e:
            logger.warning("Failed to enrich auth/me from DB: %s", e)
        return user


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """Build and return the fully-configured FastAPI application."""
    allowed_origins = _build_allowed_origins()

    application = FastAPI(
        title="GrantScope2 API",
        description="Austin Strategic Research & Intelligence System",
        version="1.0.0",
        lifespan=lifespan,
    )

    # --- Middleware (order matters) ---
    application.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
    )
    application.add_middleware(GZipMiddleware, minimum_size=500)

    # Security headers, rate limiting, request-size limits
    setup_security(application, allowed_origins)

    # --- Inline auth endpoints ---
    _register_auth_routes(application)

    # --- Routers ---
    application.include_router(health_router)
    application.include_router(users_router)
    application.include_router(search_router)
    application.include_router(notifications_router)
    application.include_router(chat_router)
    application.include_router(cards_router)
    application.include_router(card_subresources_router)
    application.include_router(card_review_router)
    application.include_router(card_export_router)
    # Workstream routers also serve /me/programs/* aliases for grant-oriented URLs
    application.include_router(workstreams_router)
    application.include_router(workstream_kanban_router)
    application.include_router(workstream_scans_router)
    application.include_router(briefs_router)
    application.include_router(analytics_router)
    application.include_router(discovery_router)
    application.include_router(research_router)
    application.include_router(classification_router)
    application.include_router(ai_helpers_router)
    application.include_router(pattern_insights_router)
    application.include_router(admin_router)
    application.include_router(feeds_router)
    application.include_router(proposals_router)
    application.include_router(wizard_router)

    # New feature routers (SQLAlchemy-based)
    application.include_router(checklist_router)
    application.include_router(budget_router)
    application.include_router(attachments_router)
    application.include_router(exports_router)
    application.include_router(collaboration_router)
    application.include_router(applications_router)
    application.include_router(dashboard_router)
    application.include_router(reference_router)

    return application


# Module-level app instance (used by ``uvicorn app.main:app``)
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
