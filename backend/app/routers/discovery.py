"""Discovery pipeline router -- SQLAlchemy 2.0 async."""

import logging
import os
import uuid
from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, update, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import (
    get_db,
    get_current_user_hardcoded,
    _safe_error,
    openai_client,
    limiter,
)
from app.models.discovery_models import (
    DiscoveryConfigRequest,
    DiscoveryRun as DiscoveryRunSchema,
    get_discovery_max_queries,
    get_discovery_max_sources,
)
from app.models.db.card import Card
from app.models.db.card_extras import CardSnapshot
from app.models.db.workstream import Workstream, WorkstreamCard
from app.models.db.discovery import DiscoveryRun, DiscoverySchedule
from app.models.db.user import User
from app.alignment_service import AlignmentService
from app.discovery_service import DiscoveryService
from app.helpers.workstream_utils import _filter_cards_for_workstream

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["discovery"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_dict(obj, skip_cols=None) -> dict:
    """Convert an ORM model instance to a plain dict, serialising special types."""
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
# Auto-distribution helper (uses its own session)
# ---------------------------------------------------------------------------


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

    from app.database import async_session_factory

    if async_session_factory is None:
        logger.warning("No database session factory – skipping auto-distribution")
        return

    async with async_session_factory() as db:
        try:
            # Fetch the new cards
            uuid_ids = [uuid.UUID(cid) for cid in new_card_ids]
            stmt = select(Card).where(Card.id.in_(uuid_ids))
            result = await db.execute(stmt)
            card_rows = result.scalars().all()
            new_cards = [_row_to_dict(c) for c in card_rows]
            if not new_cards:
                return

            # Fetch all active workstreams with auto_add enabled
            ws_stmt = (
                select(Workstream)
                .where(Workstream.auto_add == True)  # noqa: E712
                .where(Workstream.is_active == True)  # noqa: E712
            )
            ws_result = await db.execute(ws_stmt)
            workstream_rows = ws_result.scalars().all()
            workstreams = [_row_to_dict(ws) for ws in workstream_rows]
            if not workstreams:
                logger.info("No active workstreams with auto_add enabled")
                return

            total_distributed = 0

            for ws in workstreams:
                try:
                    ws_uuid = uuid.UUID(ws["id"])

                    # Get existing card IDs in this workstream to avoid duplicates
                    existing_stmt = select(WorkstreamCard.card_id).where(
                        WorkstreamCard.workstream_id == ws_uuid
                    )
                    existing_result = await db.execute(existing_stmt)
                    existing_card_ids = {str(row[0]) for row in existing_result.all()}

                    # Filter new cards against workstream criteria using shared helper
                    non_duplicate_cards = [
                        c for c in new_cards if c["id"] not in existing_card_ids
                    ]
                    matching_cards = _filter_cards_for_workstream(
                        ws, non_duplicate_cards
                    )

                    if not matching_cards:
                        continue

                    # Get current max position in inbox for this workstream
                    pos_stmt = (
                        select(WorkstreamCard.position)
                        .where(WorkstreamCard.workstream_id == ws_uuid)
                        .where(WorkstreamCard.status == "inbox")
                        .order_by(desc(WorkstreamCard.position))
                        .limit(1)
                    )
                    pos_result = await db.execute(pos_stmt)
                    pos_row = pos_result.scalar_one_or_none()
                    start_position = (pos_row + 1) if pos_row is not None else 0

                    # Insert matching cards into workstream inbox
                    now = datetime.now(timezone.utc)
                    for idx, card in enumerate(matching_cards):
                        wc = WorkstreamCard(
                            workstream_id=ws_uuid,
                            card_id=uuid.UUID(card["id"]),
                            added_by=(
                                uuid.UUID(ws["user_id"]) if ws.get("user_id") else None
                            ),
                            added_at=now,
                            status="inbox",
                            position=start_position + idx,
                            added_from="auto_discovery",
                            updated_at=now,
                        )
                        db.add(wc)

                    total_distributed += len(matching_cards)
                    logger.info(
                        f"Auto-added {len(matching_cards)} cards to workstream "
                        f"'{ws['id']}' (auto_discovery)"
                    )

                except Exception as e:
                    logger.error(
                        f"Failed to distribute cards to workstream {ws.get('id')}: {e}"
                    )
                    continue

            await db.commit()

            logger.info(
                f"Post-discovery distribution complete: {total_distributed} cards "
                f"distributed across {len(workstreams)} auto_add workstreams"
            )

        except Exception as e:
            await db.rollback()
            logger.error(f"Auto-distribution transaction failed: {e}")


# ---------------------------------------------------------------------------
# Background discovery runner
# ---------------------------------------------------------------------------


async def execute_discovery_run_background(
    run_id: str, config: DiscoveryConfigRequest, user_id: str
):
    """
    Background task to execute discovery run using DiscoveryService.

    Updates run status through lifecycle: running -> completed/failed
    """
    from app.discovery_service import DiscoveryService, DiscoveryConfig
    from app.database import async_session_factory

    if async_session_factory is None:
        logger.error("No database session factory – cannot run discovery")
        return

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
        async with async_session_factory() as db:
            service = DiscoveryService(db, openai_client, triggered_by_user_id=user_id)
            result = await service.execute_discovery_run(
                discovery_config, existing_run_id=run_id
            )

        # Update the run record with results
        async with async_session_factory() as db:
            try:
                run_uuid = uuid.UUID(run_id)
                stmt = (
                    update(DiscoveryRun)
                    .where(DiscoveryRun.id == run_uuid)
                    .values(
                        status=result.status.value,
                        completed_at=datetime.now(timezone.utc),
                        queries_generated=result.queries_generated,
                        sources_found=result.sources_discovered,
                        sources_relevant=result.sources_triaged,
                        cards_created=len(result.cards_created),
                        cards_enriched=len(result.cards_enriched),
                        cards_deduplicated=result.sources_duplicate,
                        estimated_cost=result.estimated_cost,
                    )
                )
                await db.execute(stmt)
                await db.commit()
            except Exception:
                await db.rollback()
                raise

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
        try:
            async with async_session_factory() as db:
                run_uuid = uuid.UUID(run_id)
                stmt = (
                    update(DiscoveryRun)
                    .where(DiscoveryRun.id == run_uuid)
                    .values(
                        status="failed",
                        completed_at=datetime.now(timezone.utc),
                        error_message=str(e),
                    )
                )
                await db.execute(stmt)
                await db.commit()
        except Exception as update_err:
            logger.error(f"Failed to mark discovery run as failed: {update_err}")


# ============================================================================
# Weekly Discovery Scheduler
# ============================================================================


async def run_weekly_discovery():
    """
    Run weekly automated discovery.

    Scheduled to run every Sunday at 2:00 AM UTC. Executes a full
    discovery run with default configuration across all pillars.
    """
    from app.database import async_session_factory

    logger.info("Starting weekly discovery run...")

    if async_session_factory is None:
        logger.error("No database session factory – cannot run weekly discovery")
        return

    try:
        async with async_session_factory() as db:
            # Get system user for automated tasks
            user_stmt = select(User.id).limit(1)
            user_result = await db.execute(user_stmt)
            user_row = user_result.scalar_one_or_none()

            if not user_row:
                logger.warning("Weekly discovery: No system user found, skipping")
                return

            user_id = str(user_row)

            # Create discovery run with default config
            config = DiscoveryConfigRequest()  # Default values

            run = DiscoveryRun(
                status="running",
                triggered_by="scheduled",
                triggered_by_user=uuid.UUID(user_id),
                cards_created=0,
                cards_enriched=0,
                cards_deduplicated=0,
                sources_found=0,
                started_at=datetime.now(timezone.utc),
                summary_report={"stage": "queued", "config": config.dict()},
            )
            db.add(run)
            await db.commit()
            await db.refresh(run)

            logger.info(f"Weekly discovery run queued: {run.id}")

    except Exception as e:
        logger.error(f"Weekly discovery failed: {str(e)}")


# ============================================================================
# Routes
# ============================================================================


@router.get("/discovery/config")
async def get_discovery_config(
    current_user: dict = Depends(get_current_user_hardcoded),
):
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


@router.post("/discovery/run", response_model=DiscoveryRunSchema)
@limiter.limit("3/minute")
async def trigger_discovery_run(
    request: Request,
    config: DiscoveryConfigRequest = DiscoveryConfigRequest(),
    current_user: dict = Depends(get_current_user_hardcoded),
    db: AsyncSession = Depends(get_db),
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
        run = DiscoveryRun(
            status="running",
            triggered_by="manual",
            triggered_by_user=uuid.UUID(current_user["id"]),
            summary_report={"stage": "queued", "config": resolved_config},
            cards_created=0,
            cards_enriched=0,
            cards_deduplicated=0,
            sources_found=0,
            started_at=datetime.now(timezone.utc),
        )
        db.add(run)
        await db.flush()
        await db.refresh(run)

        run_dict = _row_to_dict(run)

        # Discovery execution is handled by the background worker (see `app.worker`).

        return DiscoveryRunSchema(**run_dict)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger discovery run: {str(e)}")
        raise HTTPException(
            status_code=500, detail=_safe_error("discovery run trigger", e)
        ) from e


@router.get("/discovery/runs/{run_id}", response_model=DiscoveryRunSchema)
async def get_discovery_run(
    run_id: str,
    current_user: dict = Depends(get_current_user_hardcoded),
    db: AsyncSession = Depends(get_db),
):
    """
    Get discovery run status.

    Use this endpoint to poll for run completion after triggering a discovery run.
    Status values: running, completed, failed, cancelled
    """
    try:
        stmt = select(DiscoveryRun).where(DiscoveryRun.id == uuid.UUID(run_id))
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=_safe_error("get discovery run", e)
        ) from e

    if not row:
        raise HTTPException(status_code=404, detail="Discovery run not found")

    return DiscoveryRunSchema(**_row_to_dict(row))


@router.get("/discovery/runs", response_model=List[DiscoveryRunSchema])
async def list_discovery_runs(
    current_user: dict = Depends(get_current_user_hardcoded),
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """
    List recent discovery runs.

    Returns the most recent runs, ordered by start time descending.
    """
    try:
        stmt = select(DiscoveryRun).order_by(desc(DiscoveryRun.started_at)).limit(limit)
        result = await db.execute(stmt)
        rows = result.scalars().all()
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=_safe_error("list discovery runs", e)
        ) from e

    return [DiscoveryRunSchema(**_row_to_dict(r)) for r in rows]


@router.post("/discovery/runs/{run_id}/cancel")
async def cancel_discovery_run(
    run_id: str,
    current_user: dict = Depends(get_current_user_hardcoded),
    db: AsyncSession = Depends(get_db),
):
    """
    Cancel a running discovery run.

    Only runs with status 'running' can be cancelled.
    """
    try:
        run_uuid = uuid.UUID(run_id)
        stmt = select(DiscoveryRun).where(DiscoveryRun.id == run_uuid)
        result = await db.execute(stmt)
        run = result.scalar_one_or_none()
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=_safe_error("cancel discovery run", e)
        ) from e

    if not run:
        raise HTTPException(status_code=404, detail="Discovery run not found")

    # Check if run can be cancelled
    if run.status != "running":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel run with status '{run.status}'. Only 'running' runs can be cancelled.",
        )

    # Update status to cancelled
    try:
        run.status = "cancelled"
        run.completed_at = datetime.now(timezone.utc)
        run.error_message = f"Cancelled by user {current_user['id']}"
        await db.flush()
        await db.refresh(run)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=_safe_error("cancel discovery run update", e)
        ) from e

    logger.info(f"Discovery run {run_id} cancelled by user {current_user['id']}")
    return DiscoveryRunSchema(**_row_to_dict(run))


@router.post("/discovery/recover")
@limiter.limit("1/hour")
async def recover_cards(
    request: Request,
    current_user: dict = Depends(get_current_user_hardcoded),
    db: AsyncSession = Depends(get_db),
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
            db=db,
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
    current_user: dict = Depends(get_current_user_hardcoded),
    db: AsyncSession = Depends(get_db),
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
            db=db,
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


@router.post("/discovery/recover-analyzed")
@limiter.limit("3/hour")
async def recover_analyzed_errors(
    request: Request,
    current_user: dict = Depends(get_current_user_hardcoded),
    db: AsyncSession = Depends(get_db),
    date_start: str = "2025-12-01",
    date_end: str = "2026-02-01",
):
    """Recover sources that already passed triage+analysis but failed at card creation.

    Unlike /reprocess (which re-runs triage from scratch), this endpoint uses
    the existing analysis data to skip triage and feed directly to the signal agent.
    """
    from app.recovery_service import recover_analyzed_errors as _recover

    try:
        result = await _recover(
            db=db,
            date_start=date_start,
            date_end=date_end,
            triggered_by_user_id=current_user["id"],
        )
        return result
    except Exception as e:
        logger.error(f"Recovery of analyzed errors failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=_safe_error("analyzed error recovery", e)
        )


@router.post("/discovery/enrich")
@limiter.limit("3/hour")
async def enrich_weak_signals(
    request: Request,
    current_user: dict = Depends(get_current_user_hardcoded),
    db: AsyncSession = Depends(get_db),
    min_sources: int = 3,
    max_new_sources_per_card: int = 5,
):
    """Enrich signals that have fewer than min_sources with additional web sources.

    Uses Tavily web search to find supporting articles for each weak signal,
    then stores them as supporting sources.
    """
    from app.enrichment_service import enrich_weak_signals as _enrich

    try:
        result = await _enrich(
            db=db,
            min_sources=min_sources,
            max_new_sources_per_card=max_new_sources_per_card,
            triggered_by_user_id=current_user["id"],
        )
        return result
    except Exception as e:
        logger.error(f"Enrichment failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=_safe_error("signal enrichment", e))


@router.post("/discovery/enrich-profiles")
@limiter.limit("30/hour")
async def enrich_profiles(
    request: Request,
    current_user: dict = Depends(get_current_user_hardcoded),
    db: AsyncSession = Depends(get_db),
    max_cards: int = 50,
):
    """Batch-generate rich signal profiles for cards with blank/thin descriptions."""
    from app.enrichment_service import enrich_signal_profiles

    try:
        result = await enrich_signal_profiles(
            db=db,
            max_cards=max_cards,
            triggered_by_user_id=current_user["id"],
        )
        return result
    except Exception as e:
        logger.error(f"Profile enrichment failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=_safe_error("profile enrichment", e)
        )


# ============================================================================
# Card Snapshots -- version history for description/summary
# ============================================================================


@router.get("/cards/{card_id}/snapshots")
async def list_card_snapshots(
    card_id: str,
    field_name: str = "description",
    current_user: dict = Depends(get_current_user_hardcoded),
    db: AsyncSession = Depends(get_db),
):
    """List all snapshots for a card field, newest first."""
    try:
        card_uuid = uuid.UUID(card_id)
        stmt = (
            select(
                CardSnapshot.id,
                CardSnapshot.field_name,
                CardSnapshot.content_length,
                CardSnapshot.trigger,
                CardSnapshot.created_at,
                CardSnapshot.created_by,
            )
            .where(CardSnapshot.card_id == card_uuid)
            .where(CardSnapshot.field_name == field_name)
            .order_by(desc(CardSnapshot.created_at))
            .limit(50)
        )
        result = await db.execute(stmt)
        rows = result.all()

        snapshots = []
        for row in rows:
            snap = {
                "id": str(row.id) if isinstance(row.id, uuid.UUID) else row.id,
                "field_name": row.field_name,
                "content_length": row.content_length,
                "trigger": row.trigger,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "created_by": str(row.created_by) if row.created_by else None,
            }
            snapshots.append(snap)

        return {"snapshots": snapshots, "card_id": card_id}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=_safe_error("list card snapshots", e)
        ) from e


@router.get("/cards/{card_id}/snapshots/{snapshot_id}")
async def get_card_snapshot(
    card_id: str,
    snapshot_id: str,
    current_user: dict = Depends(get_current_user_hardcoded),
    db: AsyncSession = Depends(get_db),
):
    """Get full content of a specific snapshot."""
    try:
        stmt = (
            select(CardSnapshot)
            .where(CardSnapshot.id == uuid.UUID(snapshot_id))
            .where(CardSnapshot.card_id == uuid.UUID(card_id))
        )
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=_safe_error("get card snapshot", e)
        ) from e

    if not row:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return _row_to_dict(row)


@router.post("/cards/{card_id}/snapshots/{snapshot_id}/restore")
async def restore_card_snapshot(
    card_id: str,
    snapshot_id: str,
    current_user: dict = Depends(get_current_user_hardcoded),
    db: AsyncSession = Depends(get_db),
):
    """Restore a card field from a snapshot. Saves current value as a new snapshot first."""
    try:
        card_uuid = uuid.UUID(card_id)
        snap_uuid = uuid.UUID(snapshot_id)

        # Get the snapshot to restore
        snap_stmt = (
            select(CardSnapshot)
            .where(CardSnapshot.id == snap_uuid)
            .where(CardSnapshot.card_id == card_uuid)
        )
        snap_result = await db.execute(snap_stmt)
        snapshot = snap_result.scalar_one_or_none()

        if not snapshot:
            raise HTTPException(status_code=404, detail="Snapshot not found")

        field_name = snapshot.field_name
        restore_content = snapshot.content

        # Get current card value
        card_stmt = select(Card).where(Card.id == card_uuid)
        card_result = await db.execute(card_stmt)
        card = card_result.scalar_one_or_none()

        if not card:
            raise HTTPException(status_code=404, detail="Card not found")

        current_content = getattr(card, field_name, "") or ""
        now = datetime.now(timezone.utc)

        # Save current content as a snapshot before overwriting
        if current_content and len(current_content) > 10:
            backup_snap = CardSnapshot(
                card_id=card_uuid,
                field_name=field_name,
                content=current_content,
                content_length=len(current_content),
                trigger="restore",
                created_at=now,
                created_by=current_user.get("id", "user"),
            )
            db.add(backup_snap)

        # Restore the old content
        setattr(card, field_name, restore_content)
        card.updated_at = now
        await db.flush()

        logger.info(
            f"Card {card_id} {field_name} restored from snapshot {snapshot_id} "
            f"by user {current_user.get('id')}"
        )

        return {
            "restored": True,
            "field_name": field_name,
            "snapshot_id": snapshot_id,
            "content_length": len(restore_content),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=_safe_error("restore card snapshot", e)
        ) from e


# ============================================================================
# Discovery Schedule Management
# ============================================================================


class DiscoveryScheduleResponse(BaseModel):
    """Response model for discovery schedule settings."""

    id: str
    name: str
    enabled: bool = True
    cron_expression: Optional[str] = None
    timezone: Optional[str] = None
    interval_hours: int = 24
    max_search_queries_per_run: int = 20
    pillars_to_scan: Optional[List[str]] = None
    process_rss_first: bool = True
    last_run_at: Optional[str] = None
    next_run_at: Optional[str] = None
    last_run_status: Optional[str] = None
    last_run_summary: Optional[dict] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        extra = "allow"


class DiscoveryScheduleUpdate(BaseModel):
    """Request model for updating discovery schedule settings."""

    enabled: Optional[bool] = None
    cron_expression: Optional[str] = Field(
        None, description="Cron expression (for display/reference)"
    )
    interval_hours: Optional[int] = Field(
        None, ge=1, le=168, description="Run interval in hours"
    )
    max_search_queries_per_run: Optional[int] = Field(None, ge=1, le=200)
    pillars_to_scan: Optional[List[str]] = Field(
        None, description="Pillar codes to scan: CH, MC, HS, EC, ES, CE"
    )
    process_rss_first: Optional[bool] = None
    next_run_at: Optional[str] = Field(
        None, description="Override next run time (ISO 8601)"
    )


@router.get("/discovery/schedule", response_model=DiscoveryScheduleResponse)
async def get_discovery_schedule(
    current_user: dict = Depends(get_current_user_hardcoded),
    db: AsyncSession = Depends(get_db),
):
    """Get the current discovery schedule settings.

    Returns the default (or only) schedule configuration that controls
    automated discovery runs in the background worker.
    """
    try:
        stmt = (
            select(DiscoverySchedule)
            .order_by(asc(DiscoverySchedule.created_at))
            .limit(1)
        )
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="No discovery schedule configured. Run the migration first.",
            )

        return DiscoveryScheduleResponse(**_row_to_dict(row))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get discovery schedule: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=_safe_error("get discovery schedule", e)
        ) from e


@router.put("/discovery/schedule", response_model=DiscoveryScheduleResponse)
async def update_discovery_schedule(
    body: DiscoveryScheduleUpdate,
    current_user: dict = Depends(get_current_user_hardcoded),
    db: AsyncSession = Depends(get_db),
):
    """Update discovery schedule settings.

    Accepts partial updates. Only provided fields are changed.
    Use this to enable/disable the schedule, change the interval,
    adjust which pillars are scanned, or override the next run time.
    """
    try:
        # Get existing schedule
        stmt = (
            select(DiscoverySchedule)
            .order_by(asc(DiscoverySchedule.created_at))
            .limit(1)
        )
        result = await db.execute(stmt)
        schedule = result.scalar_one_or_none()

        if not schedule:
            raise HTTPException(
                status_code=404,
                detail="No discovery schedule configured. Run the migration first.",
            )

        # Build update dict from non-None fields
        update_data = body.dict(exclude_none=True)
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")

        # Apply updates to the ORM object
        for key, value in update_data.items():
            setattr(schedule, key, value)
        schedule.updated_at = datetime.now(timezone.utc)

        await db.flush()
        await db.refresh(schedule)

        logger.info(
            f"Discovery schedule updated by user {current_user['id']}",
            extra={
                "schedule_id": str(schedule.id),
                "updated_fields": list(update_data.keys()),
            },
        )

        return DiscoveryScheduleResponse(**_row_to_dict(schedule))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update discovery schedule: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=_safe_error("update discovery schedule", e)
        ) from e


# ============================================================================
# Alignment / Matching
# ============================================================================


class AlignmentScoreResponse(BaseModel):
    fit_score: int
    amount_score: int
    competition_score: int
    readiness_score: int
    urgency_score: int
    probability_score: int
    overall_score: int
    explanation: Dict[str, str] = {}
    recommended_action: str


class MatchResult(BaseModel):
    card_id: str
    card_name: str
    card_summary: Optional[str] = None
    grantor: Optional[str] = None
    funding_amount_min: Optional[float] = None
    funding_amount_max: Optional[float] = None
    deadline: Optional[str] = None
    grant_type: Optional[str] = None
    alignment: AlignmentScoreResponse


class MatchesResponse(BaseModel):
    program_id: str
    total_scored: int
    matches: List[MatchResult]


class AutoMatchResponse(BaseModel):
    program_id: str
    cards_scored: int
    cards_added: int
    card_ids: List[str]


@router.post("/align/{card_id}/{program_id}", response_model=AlignmentScoreResponse)
async def score_grant_against_program(
    card_id: str,
    program_id: str,
    current_user: dict = Depends(get_current_user_hardcoded),
    db: AsyncSession = Depends(get_db),
):
    """Score a grant card against a program (workstream) for alignment.

    Returns a multi-factor alignment score showing how well the grant
    matches the program's goals, capacity, and timeline.
    """
    try:
        # Fetch card
        card_stmt = select(Card).where(Card.id == uuid.UUID(card_id))
        card_result = await db.execute(card_stmt)
        card_row = card_result.scalar_one_or_none()
        if not card_row:
            raise HTTPException(status_code=404, detail="Card not found")
        card = _row_to_dict(card_row)

        # Fetch workstream and verify ownership
        ws_stmt = select(Workstream).where(Workstream.id == uuid.UUID(program_id))
        ws_result = await db.execute(ws_stmt)
        ws_row = ws_result.scalar_one_or_none()
        if not ws_row:
            raise HTTPException(status_code=404, detail="Workstream not found")
        workstream = _row_to_dict(ws_row)

        if workstream.get("user_id") != current_user["id"]:
            raise HTTPException(
                status_code=403, detail="You do not own this workstream"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=_safe_error("alignment scoring lookup", e)
        ) from e

    try:
        service = AlignmentService()
        result = await service.score_grant_against_program(card, workstream)
        return result
    except Exception as e:
        logger.error(f"Alignment scoring failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=_safe_error("alignment scoring", e)
        ) from e


@router.get("/me/programs/{program_id}/matches", response_model=MatchesResponse)
@router.get("/me/workstreams/{program_id}/matches", response_model=MatchesResponse)
async def get_program_matches(
    program_id: str,
    current_user: dict = Depends(get_current_user_hardcoded),
    db: AsyncSession = Depends(get_db),
):
    """Get top matching grants for a program (workstream).

    Scores active grant cards against the workstream and returns
    the top 20 matches sorted by overall alignment score.
    """
    try:
        # Fetch workstream and verify ownership
        ws_stmt = select(Workstream).where(Workstream.id == uuid.UUID(program_id))
        ws_result = await db.execute(ws_stmt)
        ws_row = ws_result.scalar_one_or_none()
        if not ws_row:
            raise HTTPException(status_code=404, detail="Workstream not found")
        workstream = _row_to_dict(ws_row)

        if workstream.get("user_id") != current_user["id"]:
            raise HTTPException(
                status_code=403, detail="You do not own this workstream"
            )

        # Fetch active cards with grant fields (status active)
        now_iso = datetime.now(timezone.utc).isoformat()
        cards_stmt = (
            select(Card)
            .where(Card.status == "active")
            .order_by(desc(Card.created_at))
            .limit(50)
        )
        cards_result = await db.execute(cards_stmt)
        card_rows = cards_result.scalars().all()
        cards = [_row_to_dict(c) for c in card_rows]

        # Filter: deadline is null or >= now
        eligible_cards = [
            c
            for c in cards
            if c.get("deadline") is None or c.get("deadline") >= now_iso
        ]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=_safe_error("program matches lookup", e)
        ) from e

    try:
        service = AlignmentService()
        scored = await service.score_grants_for_program(eligible_cards, workstream)
    except Exception as e:
        logger.error(f"Batch alignment scoring failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=_safe_error("batch alignment scoring", e)
        ) from e

    # scored is list[tuple[dict, AlignmentResult]] already sorted by overall_score
    top_matches = scored[:20]

    matches = []
    for card_data, alignment_result in top_matches:
        matches.append(
            MatchResult(
                card_id=card_data.get("id", ""),
                card_name=card_data.get("name", ""),
                card_summary=card_data.get("summary"),
                grantor=card_data.get("grantor"),
                funding_amount_min=card_data.get("funding_amount_min"),
                funding_amount_max=card_data.get("funding_amount_max"),
                deadline=card_data.get("deadline"),
                grant_type=card_data.get("grant_type"),
                alignment=AlignmentScoreResponse(
                    fit_score=alignment_result.fit_score,
                    amount_score=alignment_result.amount_score,
                    competition_score=alignment_result.competition_score,
                    readiness_score=alignment_result.readiness_score,
                    urgency_score=alignment_result.urgency_score,
                    probability_score=alignment_result.probability_score,
                    overall_score=alignment_result.overall_score,
                    explanation=alignment_result.explanation,
                    recommended_action=alignment_result.recommended_action,
                ),
            )
        )

    return MatchesResponse(
        program_id=program_id,
        total_scored=len(eligible_cards),
        matches=matches,
    )


@router.post("/me/programs/{program_id}/auto-match", response_model=AutoMatchResponse)
@router.post(
    "/me/workstreams/{program_id}/auto-match", response_model=AutoMatchResponse
)
async def auto_match_program(
    program_id: str,
    current_user: dict = Depends(get_current_user_hardcoded),
    db: AsyncSession = Depends(get_db),
):
    """Auto-add top matching grants to a program's pipeline.

    Scores recent active cards against the workstream and automatically
    adds cards with overall_score >= 60 to the workstream_cards table
    with status 'discovered'. Skips cards already in the workstream.
    """
    try:
        program_uuid = uuid.UUID(program_id)

        # Fetch workstream and verify ownership
        ws_stmt = select(Workstream).where(Workstream.id == program_uuid)
        ws_result = await db.execute(ws_stmt)
        ws_row = ws_result.scalar_one_or_none()
        if not ws_row:
            raise HTTPException(status_code=404, detail="Workstream not found")
        workstream = _row_to_dict(ws_row)

        if workstream.get("user_id") != current_user["id"]:
            raise HTTPException(
                status_code=403, detail="You do not own this workstream"
            )

        # Fetch active cards
        now_iso = datetime.now(timezone.utc).isoformat()
        cards_stmt = (
            select(Card)
            .where(Card.status == "active")
            .order_by(desc(Card.created_at))
            .limit(50)
        )
        cards_result = await db.execute(cards_stmt)
        card_rows = cards_result.scalars().all()
        cards = [_row_to_dict(c) for c in card_rows]

        eligible_cards = [
            c
            for c in cards
            if c.get("deadline") is None or c.get("deadline") >= now_iso
        ]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=_safe_error("auto-match lookup", e)
        ) from e

    try:
        service = AlignmentService()
        scored = await service.score_grants_for_program(eligible_cards, workstream)
    except Exception as e:
        logger.error(f"Auto-match scoring failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=_safe_error("auto-match scoring", e)
        ) from e

    # Filter to cards with overall_score >= 60
    # scored is list[tuple[dict, AlignmentResult]]
    qualifying = [
        (card, result) for card, result in scored if result.overall_score >= 60
    ]

    try:
        # Get existing card IDs in this workstream to avoid duplicates
        existing_stmt = select(WorkstreamCard.card_id).where(
            WorkstreamCard.workstream_id == program_uuid
        )
        existing_result = await db.execute(existing_stmt)
        existing_card_ids = {str(row[0]) for row in existing_result.all()}

        # Build insert records for new qualifying cards
        now = datetime.now(timezone.utc)
        new_card_ids = []
        for card_data, _alignment_result in qualifying:
            cid = card_data.get("id", "")
            if cid and cid not in existing_card_ids:
                new_card_ids.append(cid)
                wc = WorkstreamCard(
                    workstream_id=program_uuid,
                    card_id=uuid.UUID(cid),
                    added_by=uuid.UUID(current_user["id"]),
                    added_at=now,
                    status="discovered",
                    added_from="auto_match",
                    updated_at=now,
                )
                db.add(wc)

        if new_card_ids:
            await db.flush()
            logger.info(
                f"Auto-match added {len(new_card_ids)} cards to workstream {program_id}"
            )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=_safe_error("auto-match insert", e)
        ) from e

    return AutoMatchResponse(
        program_id=program_id,
        cards_scored=len(eligible_cards),
        cards_added=len(new_card_ids),
        card_ids=new_card_ids,
    )
