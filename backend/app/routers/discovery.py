"""Discovery pipeline router."""

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request

from app.deps import supabase, get_current_user, _safe_error, openai_client, limiter
from app.models.discovery_models import (
    DiscoveryConfigRequest,
    DiscoveryRun,
    get_discovery_max_queries,
    get_discovery_max_sources,
)
from app.discovery_service import DiscoveryService
from app.helpers.workstream_utils import _filter_cards_for_workstream

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["discovery"])


async def _distribute_cards_to_auto_add_workstreams(new_card_ids: List[str]):
    """Distribute newly discovered cards to workstreams with auto_add=true.

    For each active workstream with auto_add enabled, checks if any of the
    newly created cards match the workstream's filter criteria (pillar, goal,
    stage, horizon, keywords). Matching cards are added to the workstream's
    inbox with added_from='auto_discovery'.

    This is a lightweight operation that only checks the new cards from the
    current discovery run, not the full card pool.

    Args:
        new_card_ids: List of card IDs created during this discovery run
    """
    if not new_card_ids:
        return

    logger.info(f"Distributing {len(new_card_ids)} new cards to auto_add workstreams")

    # Fetch the new cards
    cards_response = (
        supabase.table("cards")
        .select("id, pillar_id, goal_id, stage_id, horizon, name, summary, description")
        .in_("id", new_card_ids)
        .execute()
    )
    new_cards = cards_response.data or []
    if not new_cards:
        return

    # Fetch all active workstreams with auto_add enabled
    ws_response = (
        supabase.table("workstreams")
        .select("id, user_id, pillar_ids, goal_ids, stage_ids, horizon, keywords")
        .eq("auto_add", True)
        .eq("is_active", True)
        .execute()
    )
    workstreams = ws_response.data or []
    if not workstreams:
        logger.info("No active workstreams with auto_add enabled")
        return

    total_distributed = 0

    for ws in workstreams:
        try:
            # Get existing card IDs in this workstream to avoid duplicates
            existing_response = (
                supabase.table("workstream_cards")
                .select("card_id")
                .eq("workstream_id", ws["id"])
                .execute()
            )
            existing_card_ids = {
                item["card_id"] for item in existing_response.data or []
            }

            # Filter new cards against workstream criteria using shared helper
            non_duplicate_cards = [
                c for c in new_cards if c["id"] not in existing_card_ids
            ]
            matching_cards = _filter_cards_for_workstream(ws, non_duplicate_cards)

            if not matching_cards:
                continue

            # Get current max position in inbox for this workstream
            pos_response = (
                supabase.table("workstream_cards")
                .select("position")
                .eq("workstream_id", ws["id"])
                .eq("status", "inbox")
                .order("position", desc=True)
                .limit(1)
                .execute()
            )
            start_position = 0
            if pos_response.data:
                start_position = pos_response.data[0]["position"] + 1

            # Insert matching cards into workstream inbox
            now = datetime.now(timezone.utc).isoformat()
            records = [
                {
                    "workstream_id": ws["id"],
                    "card_id": card["id"],
                    "added_by": ws["user_id"],
                    "added_at": now,
                    "status": "inbox",
                    "position": start_position + idx,
                    "added_from": "auto_discovery",
                    "updated_at": now,
                }
                for idx, card in enumerate(matching_cards)
            ]

            supabase.table("workstream_cards").insert(records).execute()
            total_distributed += len(records)
            logger.info(
                f"Auto-added {len(records)} cards to workstream "
                f"'{ws['id']}' (auto_discovery)"
            )

        except Exception as e:
            logger.error(
                f"Failed to distribute cards to workstream {ws.get('id')}: {e}"
            )
            continue

    logger.info(
        f"Post-discovery distribution complete: {total_distributed} cards "
        f"distributed across {len(workstreams)} auto_add workstreams"
    )


async def execute_discovery_run_background(
    run_id: str, config: DiscoveryConfigRequest, user_id: str
):
    """
    Background task to execute discovery run using DiscoveryService.

    Updates run status through lifecycle: running -> completed/failed
    """
    from app.discovery_service import DiscoveryService, DiscoveryConfig

    try:
        logger.info(f"Starting discovery run {run_id}")

        # Convert API config to service config
        discovery_config = DiscoveryConfig(
            max_queries_per_run=config.max_queries_per_run,
            max_sources_total=config.max_sources_total,
            auto_approve_threshold=config.auto_approve_threshold,
            pillars_filter=config.pillars_filter or [],
            dry_run=config.dry_run,
        )

        # Execute discovery using the service (pass existing run_id to avoid duplicate)
        service = DiscoveryService(
            supabase, openai_client, triggered_by_user_id=user_id
        )
        result = await service.execute_discovery_run(
            discovery_config, existing_run_id=run_id
        )

        # Update the run record with results (service already updates its own record,
        # but we update the one we created in the endpoint)
        supabase.table("discovery_runs").update(
            {
                "status": result.status.value,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "queries_generated": result.queries_generated,
                "sources_found": result.sources_discovered,
                "sources_relevant": result.sources_triaged,
                "cards_created": len(result.cards_created),
                "cards_enriched": len(result.cards_enriched),
                "cards_deduplicated": result.sources_duplicate,
                "estimated_cost": result.estimated_cost,
            }
        ).eq("id", run_id).execute()

        logger.info(
            f"Discovery run {run_id} completed: {len(result.cards_created)} cards created, {len(result.cards_enriched)} enriched"
        )

        # --- Post-processing: distribute new cards to auto_add workstreams ---
        if result.cards_created:
            try:
                await _distribute_cards_to_auto_add_workstreams(result.cards_created)
            except Exception as dist_err:
                logger.error(
                    f"Post-discovery card distribution failed (non-fatal): {dist_err}"
                )

    except Exception as e:
        logger.error(f"Discovery run {run_id} failed: {str(e)}", exc_info=True)
        # Update as failed
        supabase.table("discovery_runs").update(
            {
                "status": "failed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "error_message": str(e),
            }
        ).eq("id", run_id).execute()


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
            "status": "running",
            "triggered_by": "scheduled",
            "triggered_by_user": user_id,
            "cards_created": 0,
            "cards_enriched": 0,
            "cards_deduplicated": 0,
            "sources_found": 0,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "summary_report": {"stage": "queued", "config": config.dict()},
        }

        supabase.table("discovery_runs").insert(run_record).execute()

        logger.info(f"Weekly discovery run queued: {run_id}")

    except Exception as e:
        logger.error(f"Weekly discovery failed: {str(e)}")


# ============================================================================
# Routes
# ============================================================================


@router.get("/discovery/config")
async def get_discovery_config(current_user: dict = Depends(get_current_user)):
    """
    Get current discovery configuration defaults.

    Returns environment-configured defaults for discovery runs.
    Frontend can use this to display current limits.
    """
    return {
        "max_queries_per_run": get_discovery_max_queries(),
        "max_sources_total": get_discovery_max_sources(),
        "max_sources_per_query": int(
            os.getenv("DISCOVERY_MAX_SOURCES_PER_QUERY", "10")
        ),
        "auto_approve_threshold": 0.95,
        "similarity_threshold": 0.92,
    }


@router.post("/discovery/run", response_model=DiscoveryRun)
@limiter.limit("3/minute")
async def trigger_discovery_run(
    request: Request,
    config: DiscoveryConfigRequest = DiscoveryConfigRequest(),
    current_user: dict = Depends(get_current_user),
):
    """
    Trigger a new discovery run.

    Creates a discovery run record and starts the discovery process in the background.

    Returns immediately with run ID. Poll GET /discovery/runs/{run_id} for status.
    """
    try:
        # Apply env defaults for any unset values
        resolved_config = {
            "max_queries_per_run": config.max_queries_per_run
            or get_discovery_max_queries(),
            "max_sources_total": config.max_sources_total
            or get_discovery_max_sources(),
            "auto_approve_threshold": config.auto_approve_threshold,
            "pillars_filter": config.pillars_filter,
            "dry_run": config.dry_run,
        }

        # Create discovery run record with resolved config
        run_record = {
            "status": "running",
            "triggered_by": "manual",
            "triggered_by_user": current_user["id"],
            "summary_report": {"stage": "queued", "config": resolved_config},
            "cards_created": 0,
            "cards_enriched": 0,
            "cards_deduplicated": 0,
            "sources_found": 0,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }

        result = supabase.table("discovery_runs").insert(run_record).execute()

        if not result.data:
            raise HTTPException(
                status_code=500, detail="Failed to create discovery run"
            )

        run = result.data[0]
        run_id = run["id"]

        # Discovery execution is handled by the background worker (see `app.worker`).

        return DiscoveryRun(**run)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger discovery run: {str(e)}")
        raise HTTPException(
            status_code=500, detail=_safe_error("discovery run trigger", e)
        ) from e


@router.get("/discovery/runs/{run_id}", response_model=DiscoveryRun)
async def get_discovery_run(
    run_id: str, current_user: dict = Depends(get_current_user)
):
    """
    Get discovery run status.

    Use this endpoint to poll for run completion after triggering a discovery run.
    Status values: running, completed, failed, cancelled
    """
    result = (
        supabase.table("discovery_runs").select("*").eq("id", run_id).single().execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Discovery run not found")

    return DiscoveryRun(**result.data)


@router.get("/discovery/runs", response_model=List[DiscoveryRun])
async def list_discovery_runs(
    current_user: dict = Depends(get_current_user), limit: int = 20
):
    """
    List recent discovery runs.

    Returns the most recent runs, ordered by start time descending.
    """
    result = (
        supabase.table("discovery_runs")
        .select("*")
        .order("started_at", desc=True)
        .limit(limit)
        .execute()
    )

    return [DiscoveryRun(**r) for r in result.data]


@router.post("/discovery/runs/{run_id}/cancel")
async def cancel_discovery_run(
    run_id: str, current_user: dict = Depends(get_current_user)
):
    """
    Cancel a running discovery run.

    Only runs with status 'running' can be cancelled.
    """
    # Get current run status
    response = supabase.table("discovery_runs").select("*").eq("id", run_id).execute()

    if not response.data:
        raise HTTPException(status_code=404, detail="Discovery run not found")

    run = response.data[0]

    # Check if run can be cancelled
    if run["status"] != "running":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel run with status '{run['status']}'. Only 'running' runs can be cancelled.",
        )

    # Update status to cancelled
    update_response = (
        supabase.table("discovery_runs")
        .update(
            {
                "status": "cancelled",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "error_message": f"Cancelled by user {current_user['id']}",
            }
        )
        .eq("id", run_id)
        .execute()
    )

    if update_response.data:
        logger.info(f"Discovery run {run_id} cancelled by user {current_user['id']}")
        return DiscoveryRun(**update_response.data[0])
    else:
        raise HTTPException(status_code=500, detail="Failed to cancel discovery run")


@router.post("/discovery/recover")
@limiter.limit("1/hour")
async def recover_cards(
    request: Request,
    current_user: dict = Depends(get_current_user),
    date_start: str = "2025-12-01",
    date_end: str = "2026-01-01",
):
    """Recover cards from discovered_sources audit trail.

    Finds orphaned sources (cards deleted or never created) in the date range,
    reconstructs ProcessedSource objects, and feeds them through the signal agent
    for intelligent re-grouping into signals.
    """
    from app.recovery_service import recover_cards_from_discovered_sources

    try:
        result = await recover_cards_from_discovered_sources(
            supabase=supabase,
            date_start=date_start,
            date_end=date_end,
            triggered_by_user_id=current_user["id"],
        )
        return result
    except Exception as e:
        logger.error(f"Recovery failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=_safe_error("card recovery", e))


@router.post("/discovery/reprocess")
@limiter.limit("1/hour")
async def reprocess_errored_sources(
    request: Request,
    current_user: dict = Depends(get_current_user),
    date_start: str = "2025-12-01",
    date_end: str = "2026-02-13",
):
    """Re-process errored discovered_sources through the full AI pipeline.

    Takes sources that errored or were filtered during original processing,
    re-runs triage + analysis + embedding, then feeds through the signal agent.
    """
    from app.recovery_service import reprocess_errored_sources as _reprocess

    try:
        result = await _reprocess(
            supabase=supabase,
            date_start=date_start,
            date_end=date_end,
            triggered_by_user_id=current_user["id"],
        )
        return result
    except Exception as e:
        logger.error(f"Reprocess failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=_safe_error("source reprocessing", e)
        )
