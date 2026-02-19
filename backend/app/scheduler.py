"""APScheduler scheduled jobs for the GrantScope2 application.

Contains all nightly / weekly background jobs and the scheduler lifecycle
helpers ``start_scheduler()`` and ``shutdown_scheduler()``.
"""

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, update as sa_update

from app.database import async_session_factory
from app.deps import openai_client
from app.helpers.workstream_utils import (
    _build_workstream_scan_config,
    _auto_queue_workstream_scan,
)
from app.models.db.card import Card
from app.models.db.discovery import DiscoveryRun
from app.models.db.research import ResearchTask
from app.models.db.user import User
from app.models.db.workstream import Workstream, WorkstreamScan

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scheduler singleton
# ---------------------------------------------------------------------------
scheduler = AsyncIOScheduler()


# ---------------------------------------------------------------------------
# Scheduled job functions
# ---------------------------------------------------------------------------


async def run_scheduled_workstream_scans():
    """Queue scans for workstreams with auto_scan enabled.

    Checks all active workstreams where auto_scan=true and queues a scan
    if they haven't been scanned in the last 7 days.  Runs daily at 4 AM UTC.

    This bypasses the per-user 2-scans-per-day rate limit since it's
    system-initiated.
    """
    if async_session_factory is None:
        logger.error("Database not configured — cannot run scheduled workstream scans")
        return

    logger.info("Starting scheduled workstream auto-scan check...")

    try:
        async with async_session_factory() as db:
            ws_result = await db.execute(
                select(Workstream).where(
                    Workstream.auto_scan == True, Workstream.is_active == True
                )  # noqa: E712
            )
            workstreams = ws_result.scalars().all()

            if not workstreams:
                logger.info("No active workstreams with auto_scan enabled")
                return

            logger.info(f"Found {len(workstreams)} workstreams with auto_scan enabled")

            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            scans_queued = 0

            for ws in workstreams:
                try:
                    recent_scan_result = await db.execute(
                        select(WorkstreamScan.id)
                        .where(
                            WorkstreamScan.workstream_id == ws.id,
                            WorkstreamScan.created_at >= cutoff,
                            WorkstreamScan.status != "failed",
                        )
                        .limit(1)
                    )
                    recent_scan = recent_scan_result.scalar_one_or_none()

                    if recent_scan:
                        logger.debug(
                            f"Workstream '{ws.name}' ({ws.id}) scanned recently, skipping"
                        )
                        continue

                    ws_keywords = ws.keywords or []
                    ws_pillar_ids = ws.pillar_ids or []
                    if not ws_keywords and not ws_pillar_ids:
                        logger.debug(
                            f"Workstream '{ws.name}' ({ws.id}) has no keywords/pillars, skipping"
                        )
                        continue

                    # Build config dict from ORM object attributes
                    ws_dict = {
                        "id": str(ws.id),
                        "user_id": str(ws.user_id) if ws.user_id else None,
                        "name": ws.name,
                        "keywords": ws.keywords or [],
                        "pillar_ids": ws.pillar_ids or [],
                        "goal_ids": ws.goal_ids or [],
                        "stage_ids": ws.stage_ids or [],
                        "horizon": ws.horizon,
                    }
                    config = _build_workstream_scan_config(
                        ws_dict, "auto_scan_scheduler"
                    )
                    if queued := await _auto_queue_workstream_scan(
                        db, str(ws.id), str(ws.user_id), config
                    ):
                        scans_queued += 1
                        logger.info(
                            f"Queued auto-scan for workstream '{ws.name}' ({ws.id})"
                        )

                except Exception as e:
                    logger.error(
                        f"Failed to queue auto-scan for workstream '{ws.name}' "
                        f"({ws.id}): {e}"
                    )
                    continue

            await db.commit()

        logger.info(
            f"Scheduled workstream auto-scan complete: {scans_queued} scans queued "
            f"out of {len(workstreams)} eligible workstreams"
        )

    except Exception as e:
        logger.error(f"Scheduled workstream auto-scan failed: {e}", exc_info=True)


async def run_nightly_scan():
    """Run nightly content scan for all active cards.

    Automatically queues update research tasks for cards that
    haven't been updated recently.  Runs at 6 AM UTC daily.
    """
    from app.research_service import ResearchService

    if async_session_factory is None:
        logger.error("Database not configured — cannot run nightly scan")
        return

    logger.info("Starting nightly scan...")

    try:
        async with async_session_factory() as db:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=48)

            cards_result = await db.execute(
                select(Card)
                .where(Card.status == "active", Card.updated_at < cutoff)
                .limit(20)
            )
            cards = cards_result.scalars().all()

            if not cards:
                logger.info("Nightly scan: No cards need updating")
                return

            user_result = await db.execute(select(User.id).limit(1))
            user_id_val = user_result.scalar_one_or_none()

            if not user_id_val:
                logger.warning("Nightly scan: No system user found, skipping")
                return

            user_id = str(user_id_val)

            service = ResearchService(db, openai_client)  # noqa: F841
            tasks_queued = 0

            for card in cards:
                try:
                    task_obj = ResearchTask(
                        user_id=user_id_val,
                        card_id=card.id,
                        task_type="update",
                        status="queued",
                    )
                    db.add(task_obj)
                    await db.flush()

                    tasks_queued += 1
                    logger.info(f"Nightly scan: Queued update for '{card.name}'")

                except Exception as e:
                    logger.error(
                        f"Nightly scan: Failed to queue task for card {card.id}: {e}"
                    )

            await db.commit()

        logger.info(f"Nightly scan complete: {tasks_queued} tasks queued")

    except Exception as e:
        logger.error(f"Nightly scan failed: {str(e)}")


async def run_weekly_discovery():
    """Run weekly automated discovery.

    Scheduled every Sunday at 2:00 AM UTC.  Executes a full discovery
    run with default configuration across all pillars.
    """
    from app.models.discovery_models import DiscoveryConfigRequest

    if async_session_factory is None:
        logger.error("Database not configured — cannot run weekly discovery")
        return

    logger.info("Starting weekly discovery run...")

    try:
        async with async_session_factory() as db:
            user_result = await db.execute(select(User.id).limit(1))
            user_id_val = user_result.scalar_one_or_none()

            if not user_id_val:
                logger.warning("Weekly discovery: No system user found, skipping")
                return

            user_id = str(user_id_val)

            run_id = str(uuid.uuid4())
            config = DiscoveryConfigRequest()

            new_run = DiscoveryRun(
                id=uuid.UUID(run_id),
                status="running",
                triggered_by="scheduled",
                triggered_by_user=user_id_val,
                cards_created=0,
                cards_enriched=0,
                cards_deduplicated=0,
                sources_found=0,
                started_at=datetime.now(timezone.utc),
                summary_report={"stage": "queued", "config": config.dict()},
            )
            db.add(new_run)
            await db.commit()

        logger.info(f"Weekly discovery run queued: {run_id}")

    except Exception as e:
        logger.error(f"Weekly discovery failed: {str(e)}")


async def run_nightly_reputation_aggregation():
    """Recalculate domain reputation composite scores.

    Runs at 5:30 AM UTC daily, before the 6:00 AM nightly content scan,
    so that reputation scores are fresh when the scanner evaluates new sources.
    """
    from app import domain_reputation_service

    if async_session_factory is None:
        logger.error("Database not configured — cannot run reputation aggregation")
        return

    logger.info("Starting nightly domain reputation aggregation...")
    try:
        async with async_session_factory() as db:
            result = await domain_reputation_service.recalculate_all(db)
            await db.commit()

        domains_updated = result.get("domains_updated", 0)
        if errors := result.get("errors", []):
            logger.warning(
                "Nightly reputation aggregation completed with %d errors: %s",
                len(errors),
                "; ".join(errors[:5]),
            )
        logger.info(
            "Nightly reputation aggregation complete: %d domains updated",
            domains_updated,
        )
    except Exception as e:
        logger.error("Nightly reputation aggregation failed: %s", str(e))


async def run_nightly_sqi_recalculation():
    """Recalculate Source Quality Index (SQI) for all cards.

    Runs at 6:30 AM UTC daily, after the nightly scan and reputation
    aggregation so fresh sources and domain reputations are reflected.
    """
    from app import quality_service

    if async_session_factory is None:
        logger.error("Database not configured — cannot run SQI recalculation")
        return

    logger.info("Starting nightly SQI recalculation...")
    try:
        async with async_session_factory() as db:
            result = await quality_service.recalculate_all_cards(db)
            await db.commit()

        cards_succeeded = result.get("cards_succeeded", 0)
        cards_failed = result.get("cards_failed", 0)
        if errors := result.get("errors", []):
            logger.warning(
                "Nightly SQI recalculation completed with %d card errors: %s",
                cards_failed,
                "; ".join(errors[:5]),
            )
        logger.info(
            "Nightly SQI recalculation complete: %d cards succeeded, %d failed",
            cards_succeeded,
            cards_failed,
        )
    except Exception as e:
        logger.error("Nightly SQI recalculation failed: %s", str(e))


async def run_nightly_pattern_detection():
    """Run cross-signal pattern detection.

    Runs at 7:00 AM UTC daily, after SQI recalculation so that embeddings
    and quality scores are fresh.
    """
    from app.pattern_detection_service import PatternDetectionService

    if async_session_factory is None:
        logger.error("Database not configured — cannot run pattern detection")
        return

    logger.info("Starting nightly pattern detection...")
    try:
        async with async_session_factory() as db:
            service = PatternDetectionService(db, openai_client)
            result = await service.run_detection()
            await db.commit()

        logger.info(
            "Nightly pattern detection complete: %d insights stored (analyzed %d cards)",
            result.get("insights_stored", 0),
            result.get("cards_analyzed", 0),
        )
    except Exception as e:
        logger.error("Nightly pattern detection failed: %s", str(e))


async def run_nightly_velocity_calculation():
    """Calculate velocity trends for all active cards.

    Runs at 7:30 AM UTC daily, after pattern detection so all source
    data is up to date.
    """
    from app.velocity_service import calculate_velocity_trends

    if async_session_factory is None:
        logger.error("Database not configured — cannot run velocity calculation")
        return

    logger.info("Starting nightly velocity calculation...")
    try:
        async with async_session_factory() as db:
            result = await calculate_velocity_trends(db)
            await db.commit()

        logger.info(
            "Nightly velocity calculation complete: %d / %d cards updated",
            result.get("updated", 0),
            result.get("total", 0),
        )
    except Exception as e:
        logger.error("Nightly velocity calculation failed: %s", str(e))


async def run_digest_batch():
    """Process all users who are due for a digest email.

    Runs daily at 8:00 AM UTC. For weekly digests, the job checks
    each user's configured digest_day.  For daily digests, it runs
    every day.
    """
    from app.digest_service import DigestService

    if async_session_factory is None:
        logger.error("Database not configured — cannot run digest batch")
        return

    logger.info("Starting scheduled digest batch processing...")
    try:
        async with async_session_factory() as db:
            digest_service = DigestService(db, openai_client)
            stats = await digest_service.run_digest_batch()
            await db.commit()

        logger.info(f"Digest batch complete: {stats}")
    except Exception as e:
        logger.error(f"Digest batch processing failed: {e}")


async def run_nightly_description_enrichment():
    """Enrich cards with thin descriptions via AI analysis.

    Runs at 3:00 AM UTC daily, before the workstream auto-scan at 4:00 AM.
    Queues up to 20 card_analysis tasks for cards whose description is
    missing or shorter than 1600 characters.
    """
    from app.enrichment_service import enrich_thin_descriptions

    if async_session_factory is None:
        logger.warning("No DB session factory — skipping description enrichment")
        return

    logger.info("Starting nightly description enrichment...")
    try:
        async with async_session_factory() as db:
            stats = await enrich_thin_descriptions(db, max_cards=500)
            await db.commit()
            logger.info("Scheduled description enrichment complete: %s", stats)
    except Exception:
        logger.exception("Scheduled description enrichment failed")


async def scan_grants():
    """Scan Grants.gov and SAM.gov for new grant opportunities.

    Runs every 6 hours.  Creates a discovery run that the worker will
    pick up and execute through the standard discovery pipeline.  The
    config hints which source categories to prioritise via
    ``source_categories``.
    """
    if async_session_factory is None:
        logger.error("Database not configured — cannot run grant scan")
        return

    logger.info("Starting scheduled grant scan...")

    try:
        async with async_session_factory() as db:
            user_result = await db.execute(select(User.id).limit(1))
            user_id_val = user_result.scalar_one_or_none()

            if not user_id_val:
                logger.warning("Grant scan: No system user found, skipping")
                return

            run_id = str(uuid.uuid4())
            config_data = {
                "source_categories": ["grants_gov", "sam_gov"],
                "dry_run": False,
            }

            new_run = DiscoveryRun(
                id=uuid.UUID(run_id),
                status="running",
                triggered_by="scheduled",
                triggered_by_user=user_id_val,
                cards_created=0,
                cards_enriched=0,
                cards_deduplicated=0,
                sources_found=0,
                started_at=datetime.now(timezone.utc),
                summary_report={
                    "stage": "queued",
                    "config": config_data,
                    "job": "scan_grants",
                },
            )
            db.add(new_run)
            await db.commit()

        logger.info(f"Grant scan discovery run queued: {run_id}")

    except Exception as e:
        logger.error(f"Grant scan failed: {str(e)}")


# ---------------------------------------------------------------------------
# Lifecycle helpers
# ---------------------------------------------------------------------------


async def _apply_persisted_job_settings():
    """Pause APScheduler jobs that admins have disabled via the admin panel.

    Called as a fire-and-forget task right after ``scheduler.start()`` so
    that the persisted disabled state survives process restarts.
    """
    if async_session_factory is None:
        return
    try:
        async with async_session_factory() as db:
            settings = await get_setting(db, "scheduler_jobs", {})
            if not isinstance(settings, dict):
                return
            for job_id, enabled in settings.items():
                if not enabled:
                    job = scheduler.get_job(job_id)
                    if job:
                        scheduler.pause_job(job_id)
                        logger.info(
                            "Paused disabled job '%s' on startup (persisted setting)",
                            job_id,
                        )
    except Exception as exc:
        logger.warning("Failed to reapply scheduler job settings on startup: %s", exc)


def start_scheduler():
    """Start the APScheduler for background jobs."""
    try:
        if scheduler.running:
            logger.info("Scheduler already running; skipping start")
            return
    except Exception:
        pass

    # Daily description enrichment at 3:00 AM UTC
    scheduler.add_job(
        run_nightly_description_enrichment,
        "cron",
        hour=3,
        minute=0,
        id="enrich_thin_descriptions",
        name="Enrich thin card descriptions",
        max_instances=1,
        replace_existing=True,
    )

    # Daily auto-scan for workstreams with auto_scan=true at 4:00 AM UTC
    scheduler.add_job(
        run_scheduled_workstream_scans,
        "cron",
        hour=4,
        minute=0,
        id="scheduled_workstream_scans",
        replace_existing=True,
    )

    # Nightly domain reputation aggregation at 5:30 AM UTC
    scheduler.add_job(
        run_nightly_reputation_aggregation,
        "cron",
        hour=5,
        minute=30,
        id="nightly_reputation_aggregation",
        replace_existing=True,
    )

    # Nightly content scan at 6:00 AM UTC
    scheduler.add_job(
        run_nightly_scan,
        "cron",
        hour=6,
        minute=0,
        id="nightly_scan",
        replace_existing=True,
    )

    # Nightly SQI recalculation at 6:30 AM UTC
    scheduler.add_job(
        run_nightly_sqi_recalculation,
        "cron",
        hour=6,
        minute=30,
        id="nightly_sqi_recalculation",
        replace_existing=True,
    )

    # Weekly discovery run - Sunday at 2:00 AM UTC
    scheduler.add_job(
        run_weekly_discovery,
        "cron",
        day_of_week="sun",
        hour=2,
        minute=0,
        id="weekly_discovery",
        replace_existing=True,
    )

    # Nightly cross-signal pattern detection at 7:00 AM UTC
    scheduler.add_job(
        run_nightly_pattern_detection,
        "cron",
        hour=7,
        minute=0,
        id="nightly_pattern_detection",
        replace_existing=True,
    )

    # Nightly velocity trend calculation at 7:30 AM UTC
    scheduler.add_job(
        run_nightly_velocity_calculation,
        "cron",
        hour=7,
        minute=30,
        id="nightly_velocity_calculation",
        replace_existing=True,
    )

    # Daily email digest batch at 8:00 AM UTC
    scheduler.add_job(
        run_digest_batch,
        "cron",
        hour=8,
        minute=0,
        id="daily_digest_batch",
        replace_existing=True,
    )

    # Grant opportunity scan every 6 hours (0:00, 6:00, 12:00, 18:00 UTC)
    scheduler.add_job(
        scan_grants,
        "interval",
        hours=6,
        id="scan_grants",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(
        "Scheduler started - description enrichment at 3:00 AM UTC, "
        "workstream auto-scans at 4:00 AM UTC, "
        "reputation aggregation at 5:30 AM UTC, "
        "nightly scan at 6:00 AM UTC, SQI recalculation at 6:30 AM UTC, "
        "pattern detection at 7:00 AM UTC, "
        "velocity calculation at 7:30 AM UTC, "
        "digest batch at 8:00 AM UTC, "
        "weekly discovery Sundays at 2:00 AM UTC, "
        "grant scan every 6 hours"
    )

    # Reapply persisted enable/disable state so that admin-disabled jobs
    # are paused in APScheduler immediately (not just checked at runtime).
    import asyncio

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_apply_persisted_job_settings())
    except RuntimeError:
        pass  # No running loop (shouldn't happen in lifespan context)


def shutdown_scheduler():
    """Gracefully shut down the scheduler if it is running."""
    try:
        if getattr(scheduler, "running", False):
            scheduler.shutdown()
    except Exception:
        pass
