"""Search & source configuration admin endpoints.

Manage search provider settings, source weights, dedup thresholds, and test
source provider connectivity.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.admin_deps import require_admin
from app.deps import get_db, _safe_error
from app.models.db.system_settings import SystemSetting

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Keys managed by this router
# ---------------------------------------------------------------------------

_SEARCH_KEYS = {
    "search.provider",
    "search.online_search_enabled",
    "search.max_results",
    "search.timeout_seconds",
}

_DISCOVERY_KEYS = {
    "discovery.source_weights",
    "discovery.dedup_threshold",
    "discovery.source_categories",
    "discovery.max_sources_per_run",
}

_ALL_CONFIG_KEYS = _SEARCH_KEYS | _DISCOVERY_KEYS


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class SourceConfigUpdate(BaseModel):
    """Request body for updating source / search configuration.

    All fields are optional -- only supplied keys are written.
    """

    search_provider: Optional[Literal["auto", "searxng", "serper", "tavily"]] = None
    online_search_enabled: Optional[bool] = None
    max_results: Optional[int] = Field(None, ge=1, le=1000)
    timeout_seconds: Optional[int] = Field(None, ge=1, le=300)
    source_weights: Optional[Dict[str, Any]] = None
    dedup_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    source_categories: Optional[list] = None
    max_sources_per_run: Optional[int] = Field(None, ge=1, le=10000)


# Mapping from request field -> system_settings key
_FIELD_TO_KEY: Dict[str, str] = {
    "search_provider": "search.provider",
    "online_search_enabled": "search.online_search_enabled",
    "max_results": "search.max_results",
    "timeout_seconds": "search.timeout_seconds",
    "source_weights": "discovery.source_weights",
    "dedup_threshold": "discovery.dedup_threshold",
    "source_categories": "discovery.source_categories",
    "max_sources_per_run": "discovery.max_sources_per_run",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _read_config(db: AsyncSession) -> dict:
    """Read all source/search configuration keys from system_settings."""
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key.in_(_ALL_CONFIG_KEYS))
    )
    settings = result.scalars().all()
    lookup: Dict[str, Any] = {s.key: s.value for s in settings}

    return {
        "search_provider": lookup.get("search.provider"),
        "online_search_enabled": lookup.get("search.online_search_enabled"),
        "max_results": lookup.get("search.max_results"),
        "timeout_seconds": lookup.get("search.timeout_seconds"),
        "source_weights": lookup.get("discovery.source_weights"),
        "dedup_threshold": lookup.get("discovery.dedup_threshold"),
        "source_categories": lookup.get("discovery.source_categories"),
        "max_sources_per_run": lookup.get("discovery.max_sources_per_run"),
    }


# ---------------------------------------------------------------------------
# GET /admin/sources/config
# ---------------------------------------------------------------------------


@router.get("/admin/sources/config")
async def get_sources_config(
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(require_admin),
):
    """Read current source and search configuration from system_settings."""
    try:
        return await _read_config(db)
    except Exception as e:
        logger.error("Failed to read sources config: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("sources config retrieval", e),
        ) from e


# ---------------------------------------------------------------------------
# PUT /admin/sources/config
# ---------------------------------------------------------------------------


@router.put("/admin/sources/config")
async def update_sources_config(
    body: SourceConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Update source and search configuration settings.

    Only keys present in the request body are written (upsert into
    system_settings).  Returns the full updated config.
    """
    try:
        now = datetime.now(timezone.utc)
        updates = body.model_dump(exclude_none=True)

        if not updates:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No configuration values provided",
            )

        for field_name, value in updates.items():
            settings_key = _FIELD_TO_KEY.get(field_name)
            if not settings_key:
                continue

            stmt = pg_insert(SystemSetting).values(
                key=settings_key,
                value=value,
                updated_by=current_user["id"],
                updated_at=now,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["key"],
                set_={
                    "value": value,
                    "updated_by": current_user["id"],
                    "updated_at": now,
                },
            )
            await db.execute(stmt)

        await db.commit()

        return await _read_config(db)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update sources config: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("sources config update", e),
        ) from e


# ---------------------------------------------------------------------------
# GET /admin/sources/health
# ---------------------------------------------------------------------------


@router.get("/admin/sources/health")
async def sources_health(
    _current_user: dict = Depends(require_admin),
):
    """Test source provider connectivity and API key availability.

    Returns a list of providers with their health status:
    ``healthy``, ``degraded``, or ``offline``.
    """
    providers: list[dict] = []

    # -- SearXNG ----------------------------------------------------------
    searxng_url = os.getenv("SEARXNG_BASE_URL", "")
    if searxng_url:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{searxng_url.rstrip('/')}/healthz")
                if resp.status_code < 400:
                    providers.append(
                        {
                            "name": "searxng",
                            "status": "healthy",
                            "message": f"Reachable at {searxng_url}",
                        }
                    )
                else:
                    providers.append(
                        {
                            "name": "searxng",
                            "status": "degraded",
                            "message": f"HTTP {resp.status_code} from {searxng_url}",
                        }
                    )
        except Exception as exc:
            providers.append(
                {
                    "name": "searxng",
                    "status": "offline",
                    "message": f"Connection failed: {type(exc).__name__}",
                }
            )
    else:
        providers.append(
            {
                "name": "searxng",
                "status": "offline",
                "message": "SEARXNG_BASE_URL not configured",
            }
        )

    # -- Serper API key ---------------------------------------------------
    serper_key = os.getenv("SERPER_API_KEY", "")
    providers.append(
        {
            "name": "serper",
            "status": "healthy" if serper_key else "offline",
            "message": "API key configured" if serper_key else "SERPER_API_KEY not set",
        }
    )

    # -- Tavily API key ---------------------------------------------------
    tavily_key = os.getenv("TAVILY_API_KEY", "")
    providers.append(
        {
            "name": "tavily",
            "status": "healthy" if tavily_key else "offline",
            "message": "API key configured" if tavily_key else "TAVILY_API_KEY not set",
        }
    )

    # -- SAM.gov API key --------------------------------------------------
    sam_key = os.getenv("SAM_GOV_API_KEY", "")
    providers.append(
        {
            "name": "sam_gov",
            "status": "healthy" if sam_key else "offline",
            "message": "API key configured" if sam_key else "SAM_GOV_API_KEY not set",
        }
    )

    return {"providers": providers}
