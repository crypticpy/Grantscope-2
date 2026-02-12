"""Workstream scan router."""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.deps import supabase, get_current_user, _safe_error, openai_client, limiter
from app.models.workstream import (
    WorkstreamScanResponse,
    WorkstreamScanStatusResponse,
    WorkstreamScanHistoryResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["workstream-scans"])


@router.post(
    "/me/workstreams/{workstream_id}/scan", response_model=WorkstreamScanResponse
)
async def start_workstream_scan(
    workstream_id: str, current_user: dict = Depends(get_current_user)
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
    ws_response = (
        supabase.table("workstreams")
        .select("id, user_id, name, keywords, pillar_ids, horizon")
        .eq("id", workstream_id)
        .execute()
    )

    if not ws_response.data:
        raise HTTPException(status_code=404, detail="Workstream not found")

    workstream = ws_response.data[0]
    if workstream["user_id"] != user_id:
        raise HTTPException(
            status_code=403, detail="Not authorized to access this workstream"
        )

    # Validate workstream has keywords or pillars to scan
    keywords = workstream.get("keywords") or []
    pillar_ids = workstream.get("pillar_ids") or []

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
        "horizon": workstream.get("horizon") or "ALL",
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
            scan_record = {
                "workstream_id": workstream_id,
                "user_id": user_id,
                "status": "queued",
                "config": config,
            }
            result = supabase.table("workstream_scans").insert(scan_record).execute()
            scan_id = result.data[0]["id"] if result.data else None
        else:
            # Use atomic database function for rate limit + concurrency check
            result = supabase.rpc(
                "create_workstream_scan_atomic",
                {
                    "p_workstream_id": workstream_id,
                    "p_user_id": user_id,
                    "p_config": json.dumps(config),
                },
            ).execute()
            scan_id = result.data

        if not scan_id:
            # Determine which check failed for better error message
            active_check = supabase.rpc(
                "has_active_workstream_scan", {"p_workstream_id": workstream_id}
            ).execute()

            if active_check.data:
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
            message=f"Scan started for '{workstream['name']}'. New cards will be added to your inbox.",
        )

    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(f"Failed to create workstream scan: {e}")
        raise HTTPException(
            status_code=500, detail=_safe_error("scan initiation", e)
        ) from e


@router.get(
    "/me/workstreams/{workstream_id}/scan/status",
    response_model=WorkstreamScanStatusResponse,
)
async def get_workstream_scan_status(
    workstream_id: str,
    scan_id: Optional[str] = Query(
        None, description="Specific scan ID, or latest if not provided"
    ),
    current_user: dict = Depends(get_current_user),
):
    """
    Get the status of a workstream scan.

    Returns the latest scan status by default, or a specific scan if scan_id provided.

    Args:
        workstream_id: UUID of the workstream
        scan_id: Optional specific scan ID
        current_user: Authenticated user (injected)

    Returns:
        WorkstreamScanStatusResponse with scan details and results
    """
    user_id = current_user["id"]

    # Verify workstream belongs to user
    ws_response = (
        supabase.table("workstreams")
        .select("id, user_id")
        .eq("id", workstream_id)
        .execute()
    )
    if not ws_response.data:
        raise HTTPException(status_code=404, detail="Workstream not found")
    if ws_response.data[0]["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Get scan
    try:
        query = (
            supabase.table("workstream_scans")
            .select("*")
            .eq("workstream_id", workstream_id)
        )

        if scan_id:
            query = query.eq("id", scan_id)
        else:
            query = query.order("created_at", desc=True).limit(1)

        result = query.execute()
    except Exception as e:
        logger.error(f"Error querying workstream_scans: {e}")
        raise HTTPException(
            status_code=500, detail=_safe_error("database operation", e)
        ) from e

    if not result.data:
        # No scans yet — return a default empty status instead of 404
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

    scan = result.data[0]

    try:
        # Parse JSON fields if they come back as strings (Supabase behavior)
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


@router.get(
    "/me/workstreams/{workstream_id}/scan/history",
    response_model=WorkstreamScanHistoryResponse,
)
async def get_workstream_scan_history(
    workstream_id: str,
    limit: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
):
    """
    Get scan history for a workstream.

    Returns recent scans and remaining daily quota.
    """
    user_id = current_user["id"]

    # Verify workstream belongs to user
    ws_response = (
        supabase.table("workstreams")
        .select("id, user_id")
        .eq("id", workstream_id)
        .execute()
    )
    if not ws_response.data:
        raise HTTPException(status_code=404, detail="Workstream not found")
    if ws_response.data[0]["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Get scan history
    result = (
        supabase.table("workstream_scans")
        .select("*")
        .eq("workstream_id", workstream_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )

    scans = result.data or []

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


# Background task execution for workstream scans
async def execute_workstream_scan_background(scan_id: str, config: dict):
    """Execute a workstream scan in background."""
    from app.workstream_scan_service import WorkstreamScanService, WorkstreamScanConfig

    try:
        scan_config = WorkstreamScanConfig(
            workstream_id=config["workstream_id"],
            user_id=config["user_id"],
            scan_id=scan_id,
            keywords=config.get("keywords", []),
            pillar_ids=config.get("pillar_ids", []),
            horizon=config.get("horizon", "ALL"),
        )

        service = WorkstreamScanService(supabase, openai_client)
        result = await service.execute_scan(scan_config)

        logger.info(
            f"Workstream scan {scan_id} completed: "
            f"{len(result.cards_created)} created, {len(result.cards_added_to_workstream)} added to workstream"
        )

    except Exception as e:
        logger.exception(f"Workstream scan {scan_id} failed: {e}")
        # Update scan status to failed
        supabase.table("workstream_scans").update(
            {
                "status": "failed",
                "error_message": str(e),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("id", scan_id).execute()
