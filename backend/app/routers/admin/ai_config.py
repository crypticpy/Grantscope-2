"""AI configuration admin endpoints.

Manage AI model settings, view available Azure OpenAI deployments, and
retrieve AI usage statistics.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, text
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

_AI_CONFIG_KEYS = {
    "ai.model_deployment",
    "ai.temperature",
    "ai.max_tokens",
    "ai.max_tool_rounds",
    "ai.max_online_searches",
    "ai.chat_rate_limit",
    "ai.embedding_deployment",
    "ai.mini_deployment",
}


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class AIConfigUpdate(BaseModel):
    """Request body for updating AI configuration.

    All fields are optional -- only supplied keys are written.
    """

    model_deployment: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=256, le=32768)
    max_tool_rounds: Optional[int] = Field(None, ge=1, le=50)
    max_online_searches: Optional[int] = Field(None, ge=0, le=20)
    chat_rate_limit: Optional[int] = Field(None, ge=1, le=1000)
    embedding_deployment: Optional[str] = None
    mini_deployment: Optional[str] = None


# Mapping from request field -> system_settings key
_FIELD_TO_KEY: Dict[str, str] = {
    "model_deployment": "ai.model_deployment",
    "temperature": "ai.temperature",
    "max_tokens": "ai.max_tokens",
    "max_tool_rounds": "ai.max_tool_rounds",
    "max_online_searches": "ai.max_online_searches",
    "chat_rate_limit": "ai.chat_rate_limit",
    "embedding_deployment": "ai.embedding_deployment",
    "mini_deployment": "ai.mini_deployment",
}

# Reverse mapping for building response dicts
_KEY_TO_FIELD: Dict[str, str] = {v: k for k, v in _FIELD_TO_KEY.items()}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _read_ai_config(db: AsyncSession) -> dict:
    """Read all AI configuration keys from system_settings."""
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key.in_(_AI_CONFIG_KEYS))
    )
    settings = result.scalars().all()
    lookup: Dict[str, Any] = {s.key: s.value for s in settings}

    return {
        "model_deployment": lookup.get("ai.model_deployment"),
        "temperature": lookup.get("ai.temperature"),
        "max_tokens": lookup.get("ai.max_tokens"),
        "max_tool_rounds": lookup.get("ai.max_tool_rounds"),
        "max_online_searches": lookup.get("ai.max_online_searches"),
        "chat_rate_limit": lookup.get("ai.chat_rate_limit"),
        "embedding_deployment": lookup.get("ai.embedding_deployment"),
        "mini_deployment": lookup.get("ai.mini_deployment"),
    }


# ---------------------------------------------------------------------------
# GET /admin/ai/config
# ---------------------------------------------------------------------------


@router.get("/admin/ai/config")
async def get_ai_config(
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(require_admin),
):
    """Read current AI settings from system_settings.

    Returns model deployment, temperature, token limits, tool round limits,
    online search limits, and chat rate limit configuration.
    """
    try:
        return await _read_ai_config(db)
    except Exception as e:
        logger.error("Failed to read AI config: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("AI config retrieval", e),
        ) from e


# ---------------------------------------------------------------------------
# PUT /admin/ai/config
# ---------------------------------------------------------------------------


@router.put("/admin/ai/config")
async def update_ai_config(
    body: AIConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Update AI settings.

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

        return await _read_ai_config(db)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update AI config: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("AI config update", e),
        ) from e


# ---------------------------------------------------------------------------
# GET /admin/ai/models
# ---------------------------------------------------------------------------


@router.get("/admin/ai/models")
async def list_ai_models(
    _current_user: dict = Depends(require_admin),
):
    """List available Azure OpenAI deployments from environment variables.

    Returns the configured chat, mini, and embedding model deployments.
    """
    models: list[dict] = []

    # Primary chat model
    chat_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
    if chat_deployment:
        models.append(
            {
                "name": chat_deployment,
                "type": "chat",
                "deployment_id": chat_deployment,
                "source": "AZURE_OPENAI_DEPLOYMENT",
            }
        )

    # Mini / fast chat model
    mini_deployment = os.getenv("AZURE_OPENAI_MINI_DEPLOYMENT", "")
    if mini_deployment:
        models.append(
            {
                "name": mini_deployment,
                "type": "chat",
                "deployment_id": mini_deployment,
                "source": "AZURE_OPENAI_MINI_DEPLOYMENT",
            }
        )

    # Embedding model
    embedding_deployment = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "")
    if embedding_deployment:
        models.append(
            {
                "name": embedding_deployment,
                "type": "embedding",
                "deployment_id": embedding_deployment,
                "source": "AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
            }
        )

    return {"models": models}


# ---------------------------------------------------------------------------
# GET /admin/ai/usage
# ---------------------------------------------------------------------------


@router.get("/admin/ai/usage")
async def ai_usage_stats(
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(require_admin),
):
    """AI usage statistics from research_tasks.

    Returns task counts grouped by type for the last 24 hours, 7 days, and
    30 days.
    """
    try:
        usage_sql = text(
            """
            SELECT
                -- 24-hour window
                count(*) FILTER (
                    WHERE created_at >= now() - interval '24 hours'
                ) AS total_24h,
                count(*) FILTER (
                    WHERE created_at >= now() - interval '24 hours'
                    AND status = 'completed'
                ) AS completed_24h,
                count(*) FILTER (
                    WHERE created_at >= now() - interval '24 hours'
                    AND status = 'failed'
                ) AS failed_24h,

                -- 7-day window
                count(*) FILTER (
                    WHERE created_at >= now() - interval '7 days'
                ) AS total_7d,
                count(*) FILTER (
                    WHERE created_at >= now() - interval '7 days'
                    AND status = 'completed'
                ) AS completed_7d,
                count(*) FILTER (
                    WHERE created_at >= now() - interval '7 days'
                    AND status = 'failed'
                ) AS failed_7d,

                -- 30-day window
                count(*) FILTER (
                    WHERE created_at >= now() - interval '30 days'
                ) AS total_30d,
                count(*) FILTER (
                    WHERE created_at >= now() - interval '30 days'
                    AND status = 'completed'
                ) AS completed_30d,
                count(*) FILTER (
                    WHERE created_at >= now() - interval '30 days'
                    AND status = 'failed'
                ) AS failed_30d
            FROM research_tasks
        """
        )
        row = (await db.execute(usage_sql)).one()

        # By-type breakdown for each window
        by_type_sql = text(
            """
            SELECT
                task_type,
                count(*) FILTER (
                    WHERE created_at >= now() - interval '24 hours'
                ) AS count_24h,
                count(*) FILTER (
                    WHERE created_at >= now() - interval '7 days'
                ) AS count_7d,
                count(*) FILTER (
                    WHERE created_at >= now() - interval '30 days'
                ) AS count_30d
            FROM research_tasks
            WHERE created_at >= now() - interval '30 days'
            GROUP BY task_type
            ORDER BY count_30d DESC
        """
        )
        type_rows = (await db.execute(by_type_sql)).mappings().all()

        by_type_24h = {r["task_type"]: r["count_24h"] for r in type_rows}
        by_type_7d = {r["task_type"]: r["count_7d"] for r in type_rows}
        by_type_30d = {r["task_type"]: r["count_30d"] for r in type_rows}

        return {
            "period_24h": {
                "total": row.total_24h,
                "completed": row.completed_24h,
                "failed": row.failed_24h,
                "by_type": by_type_24h,
            },
            "period_7d": {
                "total": row.total_7d,
                "completed": row.completed_7d,
                "failed": row.failed_7d,
                "by_type": by_type_7d,
            },
            "period_30d": {
                "total": row.total_30d,
                "completed": row.completed_30d,
                "failed": row.failed_30d,
                "by_type": by_type_30d,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to compute AI usage stats: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("AI usage stats retrieval", e),
        ) from e
