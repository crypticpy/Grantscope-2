"""Workstream scan router.

Migrated from Supabase PostgREST to SQLAlchemy 2.0 async.
"""

import json
import logging
import os
import uuid
from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, get_current_user_hardcoded, _safe_error, openai_client
from app.helpers.db_utils import (
    create_workstream_scan_atomic,
    has_active_workstream_scan,
)
from app.models.db.workstream import Workstream, WorkstreamScan
from app.models.workstream import (
    WorkstreamScanResponse,
    WorkstreamScanStatusResponse,
    WorkstreamScanHistoryResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["workstream-scans & program-scans"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_dict(obj, skip_cols=None) -> dict:
    """Convert an ORM model instance to a plain dict with JSON-safe values."""
    skip = skip_cols or set()
    result = {}
    for col in obj.__table__.columns:
        if col.name in skip:
            continue
        value = getattr(obj, col.key, None)
        if isinstance(value, uuid.UUID):
            result[col.name] = str(value)
        elif isinstance(value, (datetime, date)):
            result[col.name] = value.isoformat()
        elif isinstance(value, Decimal):
            result[col.name] = float(value)
        else:
            result[col.name] = value
    return result


# ---------------------------------------------------------------------------
# POST /me/workstreams/{workstream_id}/scan
# POST /me/programs/{workstream_id}/scan
# ---------------------------------------------------------------------------


@router.post(
    "/me/workstreams/{workstream_id}/scan", response_model=WorkstreamScanResponse
)
@router.post("/me/programs/{workstream_id}/scan", response_model=WorkstreamScanResponse)
async def start_workstream_scan(
    workstream_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Start a targeted discovery scan for a workstream.

    Generates queries from workstream keywords and pillars, fetches content
    from all 5 source categories, and creates new cards that are added to
    the global pool and auto-added to the workstream inbox.

    Rate limited to 2 scans per workstream per day.
    Only one scan can be active (queued/running) per workstream at a time.

    Args:
        workstream_id: UUID of the workstream
        db: Async database session (injected)
        current_user: Authenticated user (injected)

    Returns:
        WorkstreamScanResponse with scan_id and queued status

    Raises:
        HTTPException 404: Workstream not found
        HTTPException 403: Not authorized
        HTTPException 409: Scan already in progress
        HTTPException 429: Rate limit exceeded (2 scans/day)
    """
    user_id = current_user["id"]

    # Validate UUID format
    try:
        uuid.UUID(workstream_id)
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail="Invalid workstream ID format"
        ) from e

    # Verify workstream belongs to user
    try:
        result = await db.execute(
            select(Workstream).where(Workstream.id == uuid.UUID(workstream_id))
        )
        ws_row = result.scalars().first()
    except Exception as e:
        logger.error("Error fetching workstream %s: %s", workstream_id, e)
        raise HTTPException(
            status_code=500, detail=_safe_error("workstream lookup", e)
        ) from e

    if not ws_row:
        raise HTTPException(status_code=404, detail="Workstream not found")

    if str(ws_row.user_id) != user_id:
        raise HTTPException(
            status_code=403, detail="Not authorized to access this workstream"
        )

    # Validate workstream has keywords or pillars to scan
    keywords = ws_row.keywords or []
    pillar_ids = ws_row.pillar_ids or []

    if not keywords and not pillar_ids:
        raise HTTPException(
            status_code=400,
            detail="Workstream needs keywords or pillars configured for scanning. Edit the workstream to add search criteria.",
        )

    # Build config for the scan
    config = {
        "workstream_id": workstream_id,
        "user_id": user_id,
        "keywords": keywords,
        "pillar_ids": pillar_ids,
        "horizon": ws_row.horizon or "ALL",
    }

    try:
        # Check if rate limiting is disabled (for testing)
        skip_rate_limit = os.getenv("DISABLE_SCAN_RATE_LIMIT", "").lower() in (
            "true",
            "1",
            "yes",
        )

        if skip_rate_limit:
            # Direct insert without rate limit check
            new_scan = WorkstreamScan(
                workstream_id=uuid.UUID(workstream_id),
                user_id=uuid.UUID(user_id),
                status="queued",
                config=config,
            )
            db.add(new_scan)
            await db.flush()
            scan_id = str(new_scan.id)
        else:
            # Use atomic database function for rate limit + concurrency check
            scan_id = await create_workstream_scan_atomic(
                db, workstream_id, user_id, config
            )
            await db.flush()

        if not scan_id:
            # Determine which check failed for better error message
            is_active = await has_active_workstream_scan(db, workstream_id)

            if is_active:
                raise HTTPException(
                    status_code=409,
                    detail="A scan is already in progress for this workstream. Please wait for it to complete.",
                )
            else:
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded: Maximum 2 scans per workstream per day. Try again tomorrow.",
                )

        logger.info(f"Created workstream scan {scan_id} for workstream {workstream_id}")

        return WorkstreamScanResponse(
            scan_id=scan_id,
            workstream_id=workstream_id,
            status="queued",
            message=f"Scan started for '{ws_row.name}'. New cards will be added to your inbox.",
        )

    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to create workstream scan: {e}")
        raise HTTPException(
            status_code=500, detail=_safe_error("scan initiation", e)
        ) from e


# ---------------------------------------------------------------------------
# GET /me/workstreams/{workstream_id}/scan/status
# GET /me/programs/{workstream_id}/scan/status
# ---------------------------------------------------------------------------


@router.get(
    "/me/workstreams/{workstream_id}/scan/status",
    response_model=WorkstreamScanStatusResponse,
)
@router.get(
    "/me/programs/{workstream_id}/scan/status",
    response_model=WorkstreamScanStatusResponse,
)
async def get_workstream_scan_status(
    workstream_id: str,
    scan_id: Optional[str] = Query(
        None, description="Specific scan ID, or latest if not provided"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Get the status of a workstream scan.

    Returns the latest scan status by default, or a specific scan if scan_id provided.

    Args:
        workstream_id: UUID of the workstream
        scan_id: Optional specific scan ID
        db: Async database session (injected)
        current_user: Authenticated user (injected)

    Returns:
        WorkstreamScanStatusResponse with scan details and results
    """
    user_id = current_user["id"]

    # Verify workstream belongs to user
    try:
        result = await db.execute(
            select(Workstream).where(Workstream.id == uuid.UUID(workstream_id))
        )
        ws_row = result.scalars().first()
    except Exception as e:
        logger.error("Error fetching workstream %s: %s", workstream_id, e)
        raise HTTPException(
            status_code=500, detail=_safe_error("workstream lookup", e)
        ) from e

    if not ws_row:
        raise HTTPException(status_code=404, detail="Workstream not found")
    if str(ws_row.user_id) != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Get scan
    try:
        query = select(WorkstreamScan).where(
            WorkstreamScan.workstream_id == uuid.UUID(workstream_id)
        )

        if scan_id:
            query = query.where(WorkstreamScan.id == uuid.UUID(scan_id))
        else:
            query = query.order_by(WorkstreamScan.created_at.desc()).limit(1)

        result = await db.execute(query)
        scan_row = result.scalars().first()
    except Exception as e:
        logger.error(f"Error querying workstream_scans: {e}")
        raise HTTPException(
            status_code=500, detail=_safe_error("database operation", e)
        ) from e

    if not scan_row:
        # No scans yet -- return a default empty status instead of 404
        return WorkstreamScanStatusResponse(
            scan_id="",
            workstream_id=workstream_id,
            status="idle",
            started_at=None,
            completed_at=None,
            config=None,
            results=None,
            error_message=None,
            created_at="",
        )

    try:
        scan = _row_to_dict(scan_row)

        # Parse JSON fields if they come back as strings
        config_data = scan.get("config")
        if isinstance(config_data, str):
            config_data = json.loads(config_data)
        results_data = scan.get("results")
        if isinstance(results_data, str):
            results_data = json.loads(results_data)

        return WorkstreamScanStatusResponse(
            scan_id=scan["id"],
            workstream_id=scan["workstream_id"],
            status=scan["status"],
            config=config_data,
            results=results_data,
            started_at=scan.get("started_at"),
            completed_at=scan.get("completed_at"),
            error_message=scan.get("error_message"),
            created_at=scan.get("created_at", ""),
        )
    except Exception as e:
        logger.error(f"Error building scan status response: {e}, scan data: {scan}")
        raise HTTPException(
            status_code=500, detail=_safe_error("response processing", e)
        ) from e


# ---------------------------------------------------------------------------
# GET /me/workstreams/{workstream_id}/scan/history
# GET /me/programs/{workstream_id}/scan/history
# ---------------------------------------------------------------------------


@router.get(
    "/me/workstreams/{workstream_id}/scan/history",
    response_model=WorkstreamScanHistoryResponse,
)
@router.get(
    "/me/programs/{workstream_id}/scan/history",
    response_model=WorkstreamScanHistoryResponse,
)
async def get_workstream_scan_history(
    workstream_id: str,
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Get scan history for a workstream.

    Returns recent scans and remaining daily quota.
    """
    user_id = current_user["id"]

    # Verify workstream belongs to user
    try:
        result = await db.execute(
            select(Workstream).where(Workstream.id == uuid.UUID(workstream_id))
        )
        ws_row = result.scalars().first()
    except Exception as e:
        logger.error("Error fetching workstream %s: %s", workstream_id, e)
        raise HTTPException(
            status_code=500, detail=_safe_error("workstream lookup", e)
        ) from e

    if not ws_row:
        raise HTTPException(status_code=404, detail="Workstream not found")
    if str(ws_row.user_id) != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Get scan history
    try:
        result = await db.execute(
            select(WorkstreamScan)
            .where(WorkstreamScan.workstream_id == uuid.UUID(workstream_id))
            .order_by(WorkstreamScan.created_at.desc())
            .limit(limit)
        )
        scan_rows = list(result.scalars().all())
    except Exception as e:
        logger.error("Error querying scan history: %s", e)
        raise HTTPException(
            status_code=500, detail=_safe_error("scan history lookup", e)
        ) from e

    scans = [_row_to_dict(row) for row in scan_rows]

    # Count scans today
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    scans_today = sum(
        bool(s.get("created_at") and s["created_at"] >= today_start.isoformat())
        for s in scans
    )

    def parse_json_field(val):
        if isinstance(val, str):
            try:
                return json.loads(val)
            except (ValueError, TypeError, json.JSONDecodeError):
                return val
        return val

    return WorkstreamScanHistoryResponse(
        scans=[
            WorkstreamScanStatusResponse(
                scan_id=s["id"],
                workstream_id=s["workstream_id"],
                status=s["status"],
                config=parse_json_field(s.get("config")),
                results=parse_json_field(s.get("results")),
                started_at=s.get("started_at"),
                completed_at=s.get("completed_at"),
                error_message=s.get("error_message"),
                created_at=s.get("created_at", ""),
            )
            for s in scans
        ],
        total=len(scans),
        scans_remaining_today=max(0, 2 - scans_today),
    )


# ---------------------------------------------------------------------------
# Background task execution for workstream scans
# ---------------------------------------------------------------------------


async def execute_workstream_scan_background(scan_id: str, config: dict):
    """Execute a workstream scan in background.

    Creates its own database session since this runs outside the
    request lifecycle.
    """
    from app.database import async_session_factory
    from app.workstream_scan_service import WorkstreamScanService, WorkstreamScanConfig

    try:
        if not async_session_factory:
            logger.error(
                "Cannot execute workstream scan %s: database not configured", scan_id
            )
            return

        scan_config = WorkstreamScanConfig(
            workstream_id=config["workstream_id"],
            user_id=config["user_id"],
            scan_id=scan_id,
            keywords=config.get("keywords", []),
            pillar_ids=config.get("pillar_ids", []),
            horizon=config.get("horizon", "ALL"),
        )

        async with async_session_factory() as session:
            service = WorkstreamScanService(session, openai_client)
            result = await service.execute_scan(scan_config)

        logger.info(
            f"Workstream scan {scan_id} completed: "
            f"{len(result.cards_created)} created, {len(result.cards_added_to_workstream)} added to workstream"
        )

    except Exception as e:
        logger.exception(f"Workstream scan {scan_id} failed: {e}")
        # Update scan status to failed using a fresh SQLAlchemy session
        try:
            from sqlalchemy import update as sa_update

            if async_session_factory:
                async with async_session_factory() as session:
                    await session.execute(
                        sa_update(WorkstreamScan)
                        .where(WorkstreamScan.id == uuid.UUID(scan_id))
                        .values(
                            status="failed",
                            error_message=str(e),
                            completed_at=datetime.now(timezone.utc),
                        )
                    )
                    await session.commit()
            else:
                logger.error(
                    "Cannot update scan %s status: database not configured", scan_id
                )
        except Exception as inner_e:
            logger.error(
                "Failed to update scan %s status to failed: %s", scan_id, inner_e
            )
