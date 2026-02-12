"""APScheduler scheduled jobs for the Foresight application.

Contains all nightly / weekly background jobs and the scheduler lifecycle
helpers ``start_scheduler()`` and ``shutdown_scheduler()``.
"""

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.deps import supabase, openai_client
from app.helpers.workstream_utils import (
    _build_workstream_scan_config,
    _auto_queue_workstream_scan,
)

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
    logger.info("Starting scheduled workstream auto-scan check...")

    try:
        ws_response = (
            supabase.table("workstreams")
            .select(
                "id, user_id, name, keywords, pillar_ids, goal_ids, stage_ids, horizon"
            )
            .eq("auto_scan", True)
            .eq("is_active", True)
            .execute()
        )

        workstreams = ws_response.data or []
        if not workstreams:
            logger.info("No active workstreams with auto_scan enabled")
            return

        logger.info(f"Found {len(workstreams)} workstreams with auto_scan enabled")

        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        scans_queued = 0

        for ws in workstreams:
            try:
                recent_scans = (
                    supabase.table("workstream_scans")
                    .select("id")
                    .eq("workstream_id", ws["id"])
                    .gte("created_at", cutoff)
                    .neq("status", "failed")
                    .limit(1)
                    .execute()
                )

                if recent_scans.data:
                    logger.debug(
                        f"Workstream '{ws['name']}' ({ws['id']}) scanned recently, skipping"
                    )
                    continue

                ws_keywords = ws.get("keywords") or []
                ws_pillar_ids = ws.get("pillar_ids") or []
                if not ws_keywords and not ws_pillar_ids:
                    logger.debug(
                        f"Workstream '{ws['name']}' ({ws['id']}) has no keywords/pillars, skipping"
                    )
                    continue

                config = _build_workstream_scan_config(ws, "auto_scan_scheduler")
                if queued := _auto_queue_workstream_scan(
                    supabase, ws["id"], ws["user_id"], config
                ):
                    scans_queued += 1
                    logger.info(
                        f"Queued auto-scan for workstream '{ws['name']}' ({ws['id']})"
                    )

            except Exception as e:
                logger.error(
                    f"Failed to queue auto-scan for workstream '{ws.get('name', 'unknown')}' "
                    f"({ws.get('id', 'unknown')}): {e}"
                )
                continue

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

    logger.info("Starting nightly scan...")

    try:
        cutoff = (datetime.now() - timedelta(hours=48)).isoformat()

        cards_result = (
            supabase.table("cards")
            .select("id, name")
            .eq("status", "active")
            .lt("updated_at", cutoff)
            .limit(20)
            .execute()
        )

        if not cards_result.data:
            logger.info("Nightly scan: No cards need updating")
            return

        system_user = supabase.table("users").select("id").limit(1).execute()
        user_id = system_user.data[0]["id"] if system_user.data else None

        if not user_id:
            logger.warning("Nightly scan: No system user found, skipping")
            return

        service = ResearchService(supabase, openai_client)  # noqa: F841
        tasks_queued = 0

        for card in cards_result.data:
            try:
                task_record = {
                    "user_id": user_id,
                    "card_id": card["id"],
                    "task_type": "update",
                    "status": "queued",
                }
                task_result = (
                    supabase.table("research_tasks").insert(task_record).execute()
                )

                if task_result.data:
                    tasks_queued += 1
                    logger.info(f"Nightly scan: Queued update for '{card['name']}'")

            except Exception as e:
                logger.error(
                    f"Nightly scan: Failed to queue task for card {card['id']}: {e}"
                )

        logger.info(f"Nightly scan complete: {tasks_queued} tasks queued")

    except Exception as e:
        logger.error(f"Nightly scan failed: {str(e)}")


async def run_weekly_discovery():
    """Run weekly automated discovery.

    Scheduled every Sunday at 2:00 AM UTC.  Executes a full discovery
    run with default configuration across all pillars.
    """
    from app.models.discovery_models import DiscoveryConfigRequest

    logger.info("Starting weekly discovery run...")

    try:
        system_user = supabase.table("users").select("id").limit(1).execute()
        user_id = system_user.data[0]["id"] if system_user.data else None

        if not user_id:
            logger.warning("Weekly discovery: No system user found, skipping")
            return

        run_id = str(uuid.uuid4())
        config = DiscoveryConfigRequest()

        run_record = {
            "id": run_id,
            "status": "running",
            "triggered_by": "scheduled",
            "triggered_by_user": user_id,
            "cards_created": 0,
            "cards_enriched": 0,
            "cards_deduplicated": 0,
            "sources_found": 0,
            "started_at": datetime.now().isoformat(),
            "summary_report": {"stage": "queued", "config": config.dict()},
        }

        supabase.table("discovery_runs").insert(run_record).execute()
        logger.info(f"Weekly discovery run queued: {run_id}")

    except Exception as e:
        logger.error(f"Weekly discovery failed: {str(e)}")


async def run_nightly_reputation_aggregation():
    """Recalculate domain reputation composite scores.

    Runs at 5:30 AM UTC daily, before the 6:00 AM nightly content scan,
    so that reputation scores are fresh when the scanner evaluates new sources.
    """
    from app import domain_reputation_service

    logger.info("Starting nightly domain reputation aggregation...")
    try:
        result = domain_reputation_service.recalculate_all(supabase)
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

    logger.info("Starting nightly SQI recalculation...")
    try:
        result = quality_service.recalculate_all_cards(supabase)
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

    logger.info("Starting nightly pattern detection...")
    try:
        service = PatternDetectionService(supabase, openai_client)
        result = await service.run_detection()
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

    logger.info("Starting nightly velocity calculation...")
    try:
        result = await calculate_velocity_trends(supabase)
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

    logger.info("Starting scheduled digest batch processing...")
    try:
        digest_service = DigestService(supabase, openai_client)
        stats = await digest_service.run_digest_batch()
        logger.info(f"Digest batch complete: {stats}")
    except Exception as e:
        logger.error(f"Digest batch processing failed: {e}")


# ---------------------------------------------------------------------------
# Lifecycle helpers
# ---------------------------------------------------------------------------


def start_scheduler():
    """Start the APScheduler for background jobs."""
    try:
        if scheduler.running:
            logger.info("Scheduler already running; skipping start")
            return
    except Exception:
        pass

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

    scheduler.start()
    logger.info(
        "Scheduler started - workstream auto-scans at 4:00 AM UTC, "
        "reputation aggregation at 5:30 AM UTC, "
        "nightly scan at 6:00 AM UTC, SQI recalculation at 6:30 AM UTC, "
        "pattern detection at 7:00 AM UTC, "
        "velocity calculation at 7:30 AM UTC, "
        "digest batch at 8:00 AM UTC, "
        "weekly discovery Sundays at 2:00 AM UTC"
    )


def shutdown_scheduler():
    """Gracefully shut down the scheduler if it is running."""
    try:
        if getattr(scheduler, "running", False):
            scheduler.shutdown()
    except Exception:
        pass
