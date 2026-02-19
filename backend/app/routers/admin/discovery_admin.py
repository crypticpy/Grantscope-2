"""Discovery pipeline management endpoints -- admin-only.

Provides configuration, run history, manual triggers, block management,
and schedule visibility for the automated discovery pipeline.
"""

import logging
import uuid as _uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, _safe_error, limiter
from app.chat.admin_deps import require_admin
from app.models.db.discovery import (
    DiscoveryRun,
    DiscoveryBlock,
    DiscoverySchedule,
)
from app.models.db.system_settings import SystemSetting
from app.routers.admin._helpers import _row_to_dict

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Discovery configuration key prefix
# ---------------------------------------------------------------------------

DISCOVERY_CONFIG_PREFIX = "discovery."

# Default values for discovery settings when they don't exist in the DB yet
DISCOVERY_DEFAULTS: dict[str, Any] = {
    "discovery.max_queries_per_run": 100,
    "discovery.sources_per_query": 10,
    "discovery.total_cap": 500,
    "discovery.auto_approve_threshold": 0.95,
    "discovery.dry_run": False,
    "discovery.pillars_filter": [],
}


# ---------------------------------------------------------------------------
# Pydantic request schemas
# ---------------------------------------------------------------------------


class DiscoveryConfigUpdate(BaseModel):
    """Request body for updating discovery configuration."""

    settings: dict[str, Any] = Field(
        ...,
        description=(
            "Key-value pairs of discovery settings to update. "
            "Keys should use the 'discovery.' prefix."
        ),
    )


class TriggerDiscoveryRequest(BaseModel):
    """Optional configuration overrides when manually triggering a run."""

    max_queries_per_run: Optional[int] = Field(
        None, ge=1, le=200, description="Override max queries per run"
    )
    max_sources_total: Optional[int] = Field(
        None, ge=10, le=1000, description="Override max sources total"
    )
    auto_approve_threshold: Optional[float] = Field(
        None, ge=0.8, le=1.0, description="Override auto-approval threshold"
    )
    pillars_filter: Optional[list[str]] = Field(
        None, description="Restrict run to specific pillars"
    )
    dry_run: bool = Field(False, description="Run without persisting results")


class CreateBlockRequest(BaseModel):
    """Request body for creating a discovery block."""

    topic: str = Field(
        ..., min_length=1, max_length=500, description="Topic or pattern to block"
    )
    reason: Optional[str] = Field(
        None, max_length=1000, description="Reason for blocking"
    )
    block_type: Optional[str] = Field(
        "topic", description="Block type: topic, domain, or keyword"
    )
    keywords: Optional[list[str]] = Field(
        None, description="Additional keywords for matching"
    )


# ---------------------------------------------------------------------------
# 1. GET /admin/discovery/config
# ---------------------------------------------------------------------------


@router.get("/admin/discovery/config")
async def get_discovery_config(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Return current discovery configuration from system_settings.

    Reads all settings with the ``discovery.`` prefix and merges them
    with defaults so the caller always sees the full set of knobs.
    """
    try:
        result = await db.execute(
            select(SystemSetting).where(
                SystemSetting.key.like(f"{DISCOVERY_CONFIG_PREFIX}%")
            )
        )
        rows = result.scalars().all()

        # Start from defaults, then overlay persisted values
        config: dict[str, Any] = dict(DISCOVERY_DEFAULTS)
        for row in rows:
            config[row.key] = row.value

        return {
            "settings": config,
            "defaults": DISCOVERY_DEFAULTS,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("discovery config retrieval", e),
        ) from e


# ---------------------------------------------------------------------------
# 2. PUT /admin/discovery/config
# ---------------------------------------------------------------------------


@router.put("/admin/discovery/config")
async def update_discovery_config(
    body: DiscoveryConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Update discovery configuration in system_settings.

    Each key in the request body is upserted into the system_settings
    table.  Keys must use the ``discovery.`` prefix.
    """
    try:
        updated_keys: list[str] = []
        now = datetime.now(timezone.utc)

        for key, value in body.settings.items():
            if not key.startswith(DISCOVERY_CONFIG_PREFIX):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Setting key must start with '{DISCOVERY_CONFIG_PREFIX}': {key}",
                )

            # Validate known config keys
            if key == "discovery.max_queries_per_run":
                if not isinstance(value, int) or value < 1:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="discovery.max_queries_per_run must be a positive integer",
                    )
            elif key == "discovery.auto_approve_threshold":
                if not isinstance(value, (int, float)) or value < 0 or value > 1:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="discovery.auto_approve_threshold must be a float between 0 and 1",
                    )
            elif key == "discovery.sources_per_query":
                if not isinstance(value, int) or value < 1:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="discovery.sources_per_query must be a positive integer",
                    )
            elif key == "discovery.total_cap":
                if not isinstance(value, int) or value < 1:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="discovery.total_cap must be a positive integer",
                    )

            result = await db.execute(
                select(SystemSetting).where(SystemSetting.key == key)
            )
            setting = result.scalar_one_or_none()

            if setting:
                setting.value = value
                setting.updated_by = current_user["id"]
                setting.updated_at = now
            else:
                new_setting = SystemSetting(
                    key=key,
                    value=value,
                    description=f"Discovery config: {key}",
                    updated_by=current_user["id"],
                    updated_at=now,
                )
                db.add(new_setting)

            updated_keys.append(key)

        await db.commit()

        logger.info(
            "Discovery config updated by user %s: %s",
            current_user["id"],
            updated_keys,
        )

        return {"updated": updated_keys, "count": len(updated_keys)}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("discovery config update", e),
        ) from e


# ---------------------------------------------------------------------------
# 3. GET /admin/discovery/runs
# ---------------------------------------------------------------------------


@router.get("/admin/discovery/runs")
async def list_discovery_runs(
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    run_status: Optional[str] = Query(
        None, alias="status", description="Filter by run status"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """List recent discovery runs with pagination and optional status filter."""
    try:
        query = select(DiscoveryRun).order_by(DiscoveryRun.started_at.desc())

        if run_status:
            query = query.where(DiscoveryRun.status == run_status)

        # Total count (before pagination)
        count_query = select(func.count()).select_from(DiscoveryRun)
        if run_status:
            count_query = count_query.where(DiscoveryRun.status == run_status)
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Paginated results
        query = query.limit(limit).offset(offset)
        result = await db.execute(query)
        runs = result.scalars().all()

        return {
            "runs": [
                {
                    "id": str(run.id),
                    "status": run.status,
                    "triggered_by": run.triggered_by,
                    "started_at": (
                        run.started_at.isoformat() if run.started_at else None
                    ),
                    "completed_at": (
                        run.completed_at.isoformat() if run.completed_at else None
                    ),
                    "stats": {
                        "queries_generated": run.queries_generated,
                        "sources_found": run.sources_found,
                        "sources_relevant": run.sources_relevant,
                        "cards_created": run.cards_created,
                        "cards_enriched": run.cards_enriched,
                        "cards_deduplicated": run.cards_deduplicated,
                    },
                    "estimated_cost": (
                        float(run.estimated_cost) if run.estimated_cost else None
                    ),
                    "error_message": run.error_message,
                    "created_at": (
                        run.created_at.isoformat() if run.created_at else None
                    ),
                }
                for run in runs
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("discovery runs listing", e),
        ) from e


# ---------------------------------------------------------------------------
# 4. GET /admin/discovery/runs/{run_id}
# ---------------------------------------------------------------------------


@router.get("/admin/discovery/runs/{run_id}")
async def get_discovery_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Return detailed view of a single discovery run."""
    try:
        run_uuid = _uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid run ID format",
        )

    try:
        result = await db.execute(
            select(DiscoveryRun).where(DiscoveryRun.id == run_uuid)
        )
        run = result.scalar_one_or_none()

        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Discovery run '{run_id}' not found",
            )

        # Calculate duration if both timestamps are available
        duration_seconds = None
        if run.started_at and run.completed_at:
            delta = run.completed_at - run.started_at
            duration_seconds = delta.total_seconds()

        return {
            "id": str(run.id),
            "status": run.status,
            "triggered_by": run.triggered_by,
            "triggered_by_user": (
                str(run.triggered_by_user) if run.triggered_by_user else None
            ),
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "duration_seconds": duration_seconds,
            "pillars_scanned": run.pillars_scanned,
            "priorities_scanned": run.priorities_scanned,
            "stats": {
                "queries_generated": run.queries_generated,
                "sources_found": run.sources_found,
                "sources_relevant": run.sources_relevant,
                "cards_created": run.cards_created,
                "cards_enriched": run.cards_enriched,
                "cards_deduplicated": run.cards_deduplicated,
            },
            "estimated_cost": float(run.estimated_cost) if run.estimated_cost else None,
            "summary_report": run.summary_report,
            "quality_stats": run.quality_stats,
            "signal_agent_stats": run.signal_agent_stats,
            "error_message": run.error_message,
            "error_details": run.error_details,
            "created_at": run.created_at.isoformat() if run.created_at else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("discovery run detail", e),
        ) from e


# ---------------------------------------------------------------------------
# 5. POST /admin/discovery/trigger
# ---------------------------------------------------------------------------


@router.post("/admin/discovery/trigger")
@limiter.limit("1/minute")
async def trigger_discovery_run(
    request: Request,
    body: TriggerDiscoveryRequest = TriggerDiscoveryRequest(),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Manually trigger a new discovery run.

    Rate limited to 1 request per minute.  Accepts optional configuration
    overrides in the request body.  Creates a DiscoveryRun record in
    ``running`` status that the worker will pick up and execute.
    """
    try:
        user_id = current_user["id"]

        # Build config dict from overrides
        config_data: dict[str, Any] = {}
        if body.max_queries_per_run is not None:
            config_data["max_queries_per_run"] = body.max_queries_per_run
        if body.max_sources_total is not None:
            config_data["max_sources_total"] = body.max_sources_total
        if body.auto_approve_threshold is not None:
            config_data["auto_approve_threshold"] = body.auto_approve_threshold
        if body.pillars_filter is not None:
            config_data["pillars_filter"] = body.pillars_filter
        config_data["dry_run"] = body.dry_run

        run_id = _uuid.uuid4()
        new_run = DiscoveryRun(
            id=run_id,
            status="queued",
            triggered_by="manual",
            triggered_by_user=user_id,
            cards_created=0,
            cards_enriched=0,
            cards_deduplicated=0,
            sources_found=0,
            started_at=datetime.now(timezone.utc),
            summary_report={"stage": "queued", "config": config_data},
            pillars_scanned=body.pillars_filter or [],
        )
        db.add(new_run)
        await db.commit()

        logger.info(
            "Discovery run %s manually triggered by user %s",
            run_id,
            user_id,
        )

        return {
            "id": str(run_id),
            "status": "queued",
            "triggered_by": "manual",
            "config": config_data,
            "message": "Discovery run queued successfully. The worker will execute it shortly.",
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("discovery run trigger", e),
        ) from e


# ---------------------------------------------------------------------------
# 6. GET /admin/discovery/blocks
# ---------------------------------------------------------------------------


@router.get("/admin/discovery/blocks")
async def list_discovery_blocks(
    include_inactive: bool = Query(False, description="Include inactive blocks"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """List discovery blocks (excluded topics/patterns)."""
    try:
        query = select(DiscoveryBlock).order_by(DiscoveryBlock.created_at.desc())
        if not include_inactive:
            query = query.where(DiscoveryBlock.is_active == True)  # noqa: E712

        result = await db.execute(query)
        blocks = result.scalars().all()

        return {
            "blocks": [
                {
                    "id": str(block.id),
                    "topic": block.topic_name,
                    "reason": block.reason,
                    "block_type": block.block_type,
                    "keywords": block.keywords,
                    "is_active": block.is_active,
                    "blocked_by_count": block.blocked_by_count,
                    "first_blocked_at": (
                        block.first_blocked_at.isoformat()
                        if block.first_blocked_at
                        else None
                    ),
                    "last_blocked_at": (
                        block.last_blocked_at.isoformat()
                        if block.last_blocked_at
                        else None
                    ),
                    "created_at": (
                        block.created_at.isoformat() if block.created_at else None
                    ),
                }
                for block in blocks
            ],
            "total": len(blocks),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("discovery blocks listing", e),
        ) from e


# ---------------------------------------------------------------------------
# 7. POST /admin/discovery/blocks
# ---------------------------------------------------------------------------


@router.post("/admin/discovery/blocks", status_code=status.HTTP_201_CREATED)
async def create_discovery_block(
    body: CreateBlockRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Add a new discovery block (excluded topic/pattern)."""
    try:
        new_block = DiscoveryBlock(
            topic_name=body.topic,
            reason=body.reason,
            block_type=body.block_type or "topic",
            keywords=body.keywords or [],
            is_active=True,
            blocked_by_count=1,
            first_blocked_at=datetime.now(timezone.utc),
            last_blocked_at=datetime.now(timezone.utc),
        )
        db.add(new_block)
        await db.commit()
        await db.refresh(new_block)

        logger.info(
            "Discovery block created by user %s: topic=%s",
            current_user["id"],
            body.topic,
        )

        return {
            "id": str(new_block.id),
            "topic": new_block.topic_name,
            "reason": new_block.reason,
            "block_type": new_block.block_type,
            "keywords": new_block.keywords,
            "is_active": new_block.is_active,
            "created_at": (
                new_block.created_at.isoformat() if new_block.created_at else None
            ),
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("discovery block creation", e),
        ) from e


# ---------------------------------------------------------------------------
# 8. DELETE /admin/discovery/blocks/{block_id}
# ---------------------------------------------------------------------------


@router.delete("/admin/discovery/blocks/{block_id}")
async def delete_discovery_block(
    block_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Remove a discovery block by ID.

    Performs a soft-delete by setting ``is_active`` to False so that
    historical audit data is preserved.
    """
    try:
        block_uuid = _uuid.UUID(block_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid block ID format",
        )

    try:
        result = await db.execute(
            select(DiscoveryBlock).where(DiscoveryBlock.id == block_uuid)
        )
        block = result.scalar_one_or_none()

        if not block:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Discovery block '{block_id}' not found",
            )

        block.is_active = False
        block.updated_at = datetime.now(timezone.utc)
        await db.commit()

        logger.info(
            "Discovery block %s deactivated by user %s",
            block_id,
            current_user["id"],
        )

        return {"id": str(block.id), "status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("discovery block deletion", e),
        ) from e


# ---------------------------------------------------------------------------
# 9. GET /admin/discovery/schedules
# ---------------------------------------------------------------------------


@router.get("/admin/discovery/schedules")
async def list_discovery_schedules(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """List discovery schedules from the discovery_schedule table.

    Also includes workstreams that have ``auto_scan`` enabled, providing
    a unified view of all scheduled discovery activity.
    """
    try:
        # --- Part 1: Dedicated discovery schedules ---
        sched_result = await db.execute(
            select(DiscoverySchedule).order_by(DiscoverySchedule.name)
        )
        schedules = sched_result.scalars().all()

        schedule_list = [
            {
                "id": str(sched.id),
                "type": "discovery_schedule",
                "name": sched.name,
                "enabled": sched.enabled,
                "cron_expression": sched.cron_expression,
                "timezone": sched.timezone,
                "interval_hours": sched.interval_hours,
                "max_search_queries_per_run": sched.max_search_queries_per_run,
                "pillars_to_scan": sched.pillars_to_scan,
                "process_rss_first": sched.process_rss_first,
                "last_run_at": (
                    sched.last_run_at.isoformat() if sched.last_run_at else None
                ),
                "next_run_at": (
                    sched.next_run_at.isoformat() if sched.next_run_at else None
                ),
                "last_run_status": sched.last_run_status,
                "last_run_summary": sched.last_run_summary,
                "created_at": (
                    sched.created_at.isoformat() if sched.created_at else None
                ),
            }
            for sched in schedules
        ]

        # --- Part 2: Workstreams with auto_scan enabled ---
        from app.models.db.workstream import Workstream

        ws_result = await db.execute(
            select(Workstream).where(
                Workstream.auto_scan == True,  # noqa: E712
                Workstream.is_active == True,  # noqa: E712
            )
        )
        workstreams = ws_result.scalars().all()

        workstream_schedules = [
            {
                "id": str(ws.id),
                "type": "workstream_auto_scan",
                "name": ws.name,
                "enabled": True,
                "interval_hours": 168,  # Weekly (7 * 24)
                "keywords": ws.keywords,
                "pillars": ws.pillar_ids or ws.pillars,
                "created_at": (ws.created_at.isoformat() if ws.created_at else None),
            }
            for ws in workstreams
        ]

        return {
            "schedules": schedule_list,
            "workstream_auto_scans": workstream_schedules,
            "total_schedules": len(schedule_list),
            "total_workstream_scans": len(workstream_schedules),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("discovery schedules listing", e),
        ) from e
