"""Admin router package -- aggregates all admin sub-routers."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["admin"])

# Phase 0: Migrated endpoints from monolithic admin.py
from .taxonomy import router as taxonomy_router
from .source_ratings import router as source_ratings_router
from .domain_reputation import router as domain_reputation_router
from .velocity import router as velocity_router
from .settings import router as settings_router

router.include_router(taxonomy_router)
router.include_router(source_ratings_router)
router.include_router(domain_reputation_router)
router.include_router(velocity_router)
router.include_router(settings_router)

# Phase 1: Core backend APIs
from .users import router as users_router
from .monitoring import router as monitoring_router
from .jobs import router as jobs_router

router.include_router(users_router)
router.include_router(monitoring_router)
router.include_router(jobs_router)
