"""
GrantScope2 Background Worker.

This process runs outside the FastAPI web server and executes long-running jobs
that must survive web restarts / scale-to-zero behaviors:
- `research_tasks` (update, deep_research, workstream_analysis)
- `executive_briefs` (pending -> generating -> completed/failed)
- `discovery_runs` (queued via summary_report.stage)
- RSS feed monitoring (check feeds + triage new items every 30 min)
- Scheduled discovery runs (configurable via discovery_schedule table)

Run locally:
  cd backend
  python -m app.worker

Run on Railway as a separate service/process:
  python -m app.worker
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from sqlalchemy import select, update as sa_update

from app.brief_service import ExecutiveBriefService
from app.database import async_session_factory
from app.deps import openai_client
from app.models.db.brief import ExecutiveBrief
from app.models.db.discovery import DiscoveryRun, DiscoverySchedule
from app.models.db.research import ResearchTask
from app.models.db.user import User
from app.models.db.workstream import WorkstreamScan
from app.models.discovery_models import DiscoveryConfigRequest
from app.models.research import ResearchTaskCreate
from app.routers.discovery import execute_discovery_run_background
from app.routers.research import execute_research_task_background
from app.routers.workstream_scans import execute_workstream_scan_background
from app.scheduler import start_scheduler
from app.taxonomy import VALID_PILLAR_CODES
from fastapi import FastAPI
import uvicorn


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _get_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _get_float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


class GrantScopeWorker:
    def __init__(self) -> None:
        self.worker_id = os.getenv("GRANTSCOPE_WORKER_ID") or str(uuid.uuid4())
        self.poll_interval_seconds = _get_float_env(
            "GRANTSCOPE_WORKER_POLL_INTERVAL_SECONDS", 5.0
        )
        self.max_poll_interval_seconds = _get_float_env(
            "GRANTSCOPE_WORKER_MAX_POLL_INTERVAL_SECONDS", 30.0
        )
        self.brief_timeout_seconds = _get_int_env(
            "GRANTSCOPE_BRIEF_TIMEOUT_SECONDS", 30 * 60
        )
        self.discovery_timeout_seconds = _get_int_env(
            "GRANTSCOPE_DISCOVERY_TIMEOUT_SECONDS", 90 * 60
        )
        self.workstream_scan_timeout_seconds = _get_int_env(
            "GRANTSCOPE_WORKSTREAM_SCAN_TIMEOUT_SECONDS", 5 * 60
        )
        self.rss_check_interval_seconds = _get_int_env(
            "GRANTSCOPE_RSS_CHECK_INTERVAL_SECONDS", 30 * 60  # 30 minutes
        )
        self.scheduled_discovery_timeout_seconds = _get_int_env(
            "GRANTSCOPE_SCHEDULED_DISCOVERY_TIMEOUT_SECONDS", 120 * 60  # 2 hours
        )
        self.enable_scheduler = _truthy(
            os.getenv("GRANTSCOPE_ENABLE_SCHEDULER", "false")
        )
        self._stop_event = asyncio.Event()
        self._current_interval = self.poll_interval_seconds
        self._last_rss_check: Optional[datetime] = None

    def request_stop(self) -> None:
        self._stop_event.set()

    async def run(self) -> None:
        logger.info(
            "Worker starting",
            extra={
                "worker_id": self.worker_id,
                "poll_interval_seconds": self.poll_interval_seconds,
                "max_poll_interval_seconds": self.max_poll_interval_seconds,
                "enable_scheduler": self.enable_scheduler,
            },
        )

        if self.enable_scheduler:
            try:
                start_scheduler()
            except Exception as e:
                logger.error(f"Failed to start scheduler in worker: {e}")

        while not self._stop_event.is_set():
            did_work = False

            try:
                did_work = await self._process_one_research_task() or did_work
                did_work = await self._process_one_brief() or did_work
                did_work = await self._process_one_discovery_run() or did_work
                did_work = await self._process_one_workstream_scan() or did_work
                did_work = await self._check_rss_feeds() or did_work
                did_work = await self._run_scheduled_discovery() or did_work
            except Exception as e:
                logger.exception(f"Worker loop error: {e}")

            if did_work:
                self._current_interval = self.poll_interval_seconds
            else:
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(), timeout=self._current_interval
                    )
                except asyncio.TimeoutError:
                    pass
                # Backoff *after* sleeping so the first idle wait uses the
                # base interval, not 2x.
                self._current_interval = min(
                    self._current_interval * 2,
                    self.max_poll_interval_seconds,
                )

        logger.info("Worker stopping", extra={"worker_id": self.worker_id})

    async def _process_one_research_task(self) -> bool:
        if async_session_factory is None:
            logger.error("Database not configured — cannot process research tasks")
            return False

        async with async_session_factory() as db:
            result = await db.execute(
                select(ResearchTask)
                .where(ResearchTask.status == "queued")
                .order_by(ResearchTask.created_at.asc())
                .limit(1)
            )
            task = result.scalar_one_or_none()
            if not task:
                return False

            task_id = str(task.id)

            now = datetime.now(timezone.utc)
            now_iso = now.isoformat()
            claim_result = await db.execute(
                sa_update(ResearchTask)
                .where(ResearchTask.id == task.id, ResearchTask.status == "queued")
                .values(
                    status="processing",
                    started_at=now,
                    result_summary={
                        "stage": "claimed:research",
                        "heartbeat_at": now_iso,
                        "worker_id": self.worker_id,
                    },
                )
                .returning(ResearchTask.id)
            )
            claimed = claim_result.scalar_one_or_none()
            await db.commit()

            if not claimed:
                return False

            task_data = ResearchTaskCreate(
                card_id=str(task.card_id) if task.card_id else None,
                workstream_id=str(task.workstream_id) if task.workstream_id else None,
                task_type=task.task_type,
            )

            logger.info(
                "Processing research task",
                extra={
                    "worker_id": self.worker_id,
                    "task_id": task_id,
                    "task_type": task.task_type,
                    "card_id": str(task.card_id) if task.card_id else None,
                    "workstream_id": (
                        str(task.workstream_id) if task.workstream_id else None
                    ),
                },
            )

        await execute_research_task_background(task_id, task_data, str(task.user_id))
        return True

    async def _process_one_brief(self) -> bool:
        if async_session_factory is None:
            logger.error("Database not configured — cannot process briefs")
            return False

        async with async_session_factory() as db:
            result = await db.execute(
                select(ExecutiveBrief)
                .where(ExecutiveBrief.status == "pending")
                .order_by(ExecutiveBrief.created_at.asc())
                .limit(1)
            )
            brief = result.scalar_one_or_none()
            if not brief:
                return False

            brief_id = str(brief.id)

            claim_result = await db.execute(
                sa_update(ExecutiveBrief)
                .where(
                    ExecutiveBrief.id == brief.id, ExecutiveBrief.status == "pending"
                )
                .values(status="generating")
                .returning(ExecutiveBrief.id)
            )
            claimed = claim_result.scalar_one_or_none()
            await db.commit()

            if not claimed:
                return False

            since_timestamp: Optional[str] = None
            sources_since_previous = brief.sources_since_previous or {}
            if isinstance(sources_since_previous, dict):
                since_timestamp = sources_since_previous.get(
                    "since_date"
                ) or sources_since_previous.get("since_timestamp")

            workstream_card_id = str(brief.workstream_card_id)
            card_id = str(brief.card_id)

            logger.info(
                "Processing executive brief",
                extra={
                    "worker_id": self.worker_id,
                    "brief_id": brief_id,
                    "workstream_card_id": workstream_card_id,
                    "card_id": card_id,
                },
            )

        # Create a new session for the service to use during generation
        async with async_session_factory() as db:
            service = ExecutiveBriefService(db, openai_client)
            try:
                await asyncio.wait_for(
                    service.generate_executive_brief(
                        brief_id=brief_id,
                        workstream_card_id=workstream_card_id,
                        card_id=card_id,
                        since_timestamp=since_timestamp,
                    ),
                    timeout=self.brief_timeout_seconds,
                )
                await db.commit()
            except asyncio.TimeoutError:
                await service.update_brief_status(
                    brief_id,
                    "failed",
                    error_message=f"Brief generation timed out after {self.brief_timeout_seconds} seconds",
                )
                await db.commit()
            except BaseException as e:
                # Includes CancelledError which is not an Exception.
                await service.update_brief_status(
                    brief_id, "failed", error_message=str(e)
                )
                await db.commit()
                raise
        return True

    async def _process_one_discovery_run(self) -> bool:
        if async_session_factory is None:
            logger.error("Database not configured — cannot process discovery runs")
            return False

        async with async_session_factory() as db:
            result = await db.execute(
                select(DiscoveryRun)
                .where(
                    DiscoveryRun.status == "running",
                    DiscoveryRun.summary_report["stage"].astext == "queued",
                )
                .order_by(DiscoveryRun.started_at.asc())
                .limit(1)
            )
            run = result.scalar_one_or_none()
            if not run:
                return False

            run_id = str(run.id)
            triggered_by_user = (
                str(run.triggered_by_user) if run.triggered_by_user else None
            )

            summary_report: Dict[str, Any] = run.summary_report or {}
            if not isinstance(summary_report, dict):
                summary_report = {}

            summary_report["stage"] = "running"
            summary_report["worker_id"] = self.worker_id
            summary_report["heartbeat_at"] = datetime.now(timezone.utc).isoformat()

            # Claim the run with optimistic lock
            claim_result = await db.execute(
                sa_update(DiscoveryRun)
                .where(
                    DiscoveryRun.id == run.id,
                    DiscoveryRun.status == "running",
                    DiscoveryRun.summary_report["stage"].astext == "queued",
                )
                .values(summary_report=summary_report)
                .returning(DiscoveryRun.id)
            )
            claimed = claim_result.scalar_one_or_none()
            await db.commit()

            if not claimed:
                return False

            config_data = (
                summary_report.get("config")
                if isinstance(summary_report, dict)
                else None
            )
            if not isinstance(config_data, dict):
                config_data = {}

            config = DiscoveryConfigRequest(**config_data)

            if not triggered_by_user:
                # Defensive fallback: pick any system user.
                user_result = await db.execute(select(User.id).limit(1))
                system_user = user_result.scalar_one_or_none()
                triggered_by_user = str(system_user) if system_user else None

            if not triggered_by_user:
                raise RuntimeError(
                    "Discovery run has no triggered_by_user and no users exist to run as."
                )

        # Detect grant-oriented discovery runs
        source_categories = config_data.get("source_categories") or []
        grant_categories = {"grants_gov", "sam_gov"}
        if grant_categories & set(source_categories):
            logger.info(
                "Processing grant opportunity discovery run",
                extra={
                    "worker_id": self.worker_id,
                    "run_id": run_id,
                    "grant_sources": sorted(grant_categories & set(source_categories)),
                },
            )
        else:
            logger.info(
                "Processing discovery run",
                extra={
                    "worker_id": self.worker_id,
                    "run_id": run_id,
                    "triggered_by_user": triggered_by_user,
                },
            )

        try:
            await asyncio.wait_for(
                execute_discovery_run_background(run_id, config, triggered_by_user),
                timeout=self.discovery_timeout_seconds,
            )
        except asyncio.TimeoutError:
            async with async_session_factory() as db:
                summary_report["stage"] = "failed"
                summary_report["timed_out"] = True
                summary_report["timed_out_at"] = datetime.now(timezone.utc).isoformat()
                await db.execute(
                    sa_update(DiscoveryRun)
                    .where(DiscoveryRun.id == uuid.UUID(run_id))
                    .values(
                        status="failed",
                        completed_at=datetime.now(timezone.utc),
                        error_message=f"Discovery run timed out after {self.discovery_timeout_seconds} seconds",
                        summary_report=summary_report,
                    )
                )
                await db.commit()
        except BaseException as e:
            async with async_session_factory() as db:
                summary_report["stage"] = "failed"
                summary_report["failed_at"] = datetime.now(timezone.utc).isoformat()
                await db.execute(
                    sa_update(DiscoveryRun)
                    .where(DiscoveryRun.id == uuid.UUID(run_id))
                    .values(
                        status="failed",
                        completed_at=datetime.now(timezone.utc),
                        error_message=str(e),
                        summary_report=summary_report,
                    )
                )
                await db.commit()
            raise
        return True

    async def _process_one_workstream_scan(self) -> bool:
        """Process one queued workstream scan job."""
        if async_session_factory is None:
            logger.error("Database not configured — cannot process workstream scans")
            return False

        try:
            async with async_session_factory() as db:
                result = await db.execute(
                    select(WorkstreamScan)
                    .where(WorkstreamScan.status == "queued")
                    .order_by(WorkstreamScan.created_at.asc())
                    .limit(1)
                )
                scan = result.scalar_one_or_none()
                if scan:
                    logger.info(f"Found queued workstream scan: {scan.id}")
        except Exception as e:
            logger.error(f"Error querying workstream_scans: {e}")
            return False

        if not scan:
            return False

        scan_id = str(scan.id)

        # Claim the scan by setting status to running
        async with async_session_factory() as db:
            now = datetime.now(timezone.utc)
            claim_result = await db.execute(
                sa_update(WorkstreamScan)
                .where(WorkstreamScan.id == scan.id, WorkstreamScan.status == "queued")
                .values(status="running", started_at=now)
                .returning(WorkstreamScan.id)
            )
            claimed = claim_result.scalar_one_or_none()
            await db.commit()

        if not claimed:
            return False

        config = scan.config or {}
        # Parse config if it's a JSON string (Supabase behavior)
        if isinstance(config, str):
            import json

            try:
                config = json.loads(config)
            except json.JSONDecodeError:
                config = {}

        logger.info(
            "Processing workstream scan",
            extra={
                "worker_id": self.worker_id,
                "scan_id": scan_id,
                "workstream_id": str(scan.workstream_id),
                "user_id": str(scan.user_id),
            },
        )

        try:
            await asyncio.wait_for(
                execute_workstream_scan_background(scan_id, config),
                timeout=self.workstream_scan_timeout_seconds,
            )
        except asyncio.TimeoutError:
            async with async_session_factory() as db:
                await db.execute(
                    sa_update(WorkstreamScan)
                    .where(WorkstreamScan.id == uuid.UUID(scan_id))
                    .values(
                        status="failed",
                        completed_at=datetime.now(timezone.utc),
                        error_message=f"Workstream scan timed out after {self.workstream_scan_timeout_seconds} seconds",
                    )
                )
                await db.commit()
        except BaseException as e:
            async with async_session_factory() as db:
                await db.execute(
                    sa_update(WorkstreamScan)
                    .where(WorkstreamScan.id == uuid.UUID(scan_id))
                    .values(
                        status="failed",
                        completed_at=datetime.now(timezone.utc),
                        error_message=str(e),
                    )
                )
                await db.commit()
            raise
        return True

    async def _check_rss_feeds(self) -> bool:
        """Check RSS feeds for new items and process them.

        Runs at most once every ``rss_check_interval_seconds`` (default 30 min).
        Creates an RSSService, calls ``check_feeds()`` to poll due feeds, then
        ``process_new_items()`` to triage and match new articles to cards.

        Returns:
            True if any feeds were checked or items processed.
        """
        if async_session_factory is None:
            logger.error("Database not configured — cannot check RSS feeds")
            return False

        now = datetime.now(timezone.utc)

        # Skip if we checked recently
        if self._last_rss_check is not None:
            elapsed = (now - self._last_rss_check).total_seconds()
            if elapsed < self.rss_check_interval_seconds:
                return False

        self._last_rss_check = now

        try:
            from app.rss_service import RSSService
            from app.ai_service import AIService

            ai_service = AIService(openai_client)

            async with async_session_factory() as db:
                rss_service = RSSService(db, ai_service)

                # Step 1: Poll feeds that are due
                check_stats = await rss_service.check_feeds()
                logger.info(
                    "RSS feed check complete",
                    extra={
                        "worker_id": self.worker_id,
                        "feeds_checked": check_stats.get("feeds_checked", 0),
                        "items_found": check_stats.get("items_found", 0),
                        "items_new": check_stats.get("items_new", 0),
                        "errors": check_stats.get("errors", 0),
                    },
                )

                # Step 2: Process (triage + match) any new items
                process_stats = await rss_service.process_new_items()
                logger.info(
                    "RSS item processing complete",
                    extra={
                        "worker_id": self.worker_id,
                        "items_processed": process_stats.get("items_processed", 0),
                        "items_matched": process_stats.get("items_matched", 0),
                        "items_pending": process_stats.get("items_pending", 0),
                        "items_irrelevant": process_stats.get("items_irrelevant", 0),
                    },
                )

                await db.commit()

            did_work = (
                check_stats.get("feeds_checked", 0) > 0
                or process_stats.get("items_processed", 0) > 0
            )
            return did_work

        except Exception as e:
            logger.error(f"RSS feed check failed: {e}", exc_info=True)
            return False

    async def _run_scheduled_discovery(self) -> bool:
        """Run a scheduled discovery if one is due.

        Queries the ``discovery_schedule`` table for any enabled schedule whose
        ``next_run_at`` is in the past.  When due the method:

        1. Claims the schedule row (optimistic lock via ``next_run_at`` check).
        2. Processes RSS feeds first (free, no API calls).
        3. Creates a ``discovery_run`` record per configured pillar and lets the
           existing worker loop pick them up.
        4. Stores run statistics in ``last_run_summary``.

        Returns ``True`` if a scheduled discovery was triggered.
        """
        if async_session_factory is None:
            logger.error("Database not configured — cannot run scheduled discovery")
            return False

        try:
            now = datetime.now(timezone.utc)
            now_iso = now.isoformat()

            async with async_session_factory() as db:
                # Check for any due schedules
                result = await db.execute(
                    select(DiscoverySchedule)
                    .where(
                        DiscoverySchedule.enabled == True,  # noqa: E712
                        DiscoverySchedule.next_run_at <= now,
                    )
                    .order_by(DiscoverySchedule.next_run_at.asc())
                    .limit(1)
                )
                schedule = result.scalar_one_or_none()

                if not schedule:
                    return False

                schedule_id = str(schedule.id)
                interval_hours = schedule.interval_hours or 24
                pillars = schedule.pillars_to_scan or sorted(VALID_PILLAR_CODES)
                max_queries = schedule.max_search_queries_per_run or 20
                process_rss = (
                    schedule.process_rss_first
                    if schedule.process_rss_first is not None
                    else True
                )
                schedule_name = schedule.name

                # Claim the schedule by advancing next_run_at (optimistic lock)
                next_run = now + timedelta(hours=interval_hours)
                claim_result = await db.execute(
                    sa_update(DiscoverySchedule)
                    .where(
                        DiscoverySchedule.id == schedule.id,
                        DiscoverySchedule.next_run_at <= now,
                    )
                    .values(
                        last_run_at=now,
                        next_run_at=next_run,
                        last_run_status="running",
                        updated_at=now,
                    )
                    .returning(DiscoverySchedule.id)
                )
                claimed = claim_result.scalar_one_or_none()
                await db.commit()

            if not claimed:
                return False

            logger.info(
                "Scheduled discovery triggered",
                extra={
                    "worker_id": self.worker_id,
                    "schedule_id": schedule_id,
                    "schedule_name": schedule_name,
                    "pillars": pillars,
                    "max_queries": max_queries,
                    "interval_hours": interval_hours,
                },
            )

            summary: dict = {
                "schedule_id": schedule_id,
                "started_at": now_iso,
                "rss_stats": None,
                "discovery_run_ids": [],
                "errors": [],
            }

            # Step 1: Process RSS feeds first (free, no API budget)
            if process_rss:
                try:
                    from app.rss_service import RSSService
                    from app.ai_service import AIService

                    ai_service = AIService(openai_client)

                    async with async_session_factory() as db:
                        rss_service = RSSService(db, ai_service)

                        check_stats = await rss_service.check_feeds()
                        process_stats = await rss_service.process_new_items()
                        await db.commit()

                    summary["rss_stats"] = {
                        "feeds_checked": check_stats.get("feeds_checked", 0),
                        "items_found": check_stats.get("items_found", 0),
                        "items_new": check_stats.get("items_new", 0),
                        "items_processed": process_stats.get("items_processed", 0),
                        "items_matched": process_stats.get("items_matched", 0),
                    }
                    logger.info(
                        "Scheduled discovery: RSS processing complete",
                        extra={"worker_id": self.worker_id, **summary["rss_stats"]},
                    )
                except Exception as rss_err:
                    logger.error(
                        f"Scheduled discovery: RSS processing failed: {rss_err}",
                        exc_info=True,
                    )
                    summary["errors"].append(f"RSS processing failed: {rss_err}")

            # Step 2: Get a system user for the discovery run
            async with async_session_factory() as db:
                user_result = await db.execute(select(User.id).limit(1))
                system_user_id = user_result.scalar_one_or_none()
                user_id = str(system_user_id) if system_user_id else None

            if not user_id:
                logger.warning(
                    "Scheduled discovery: No system user found, skipping discovery run"
                )
                summary["errors"].append("No system user found")
            else:
                # Step 3: Create a discovery run with the scheduled pillars
                try:
                    run_id = str(uuid.uuid4())
                    config_data = {
                        "max_queries_per_run": max_queries,
                        "max_sources_total": max_queries * 10,  # ~10 sources per query
                        "auto_approve_threshold": 0.95,
                        "pillars_filter": pillars,
                        "dry_run": False,
                    }

                    new_run = DiscoveryRun(
                        id=uuid.UUID(run_id),
                        status="running",
                        triggered_by="scheduled",
                        triggered_by_user=uuid.UUID(user_id),
                        cards_created=0,
                        cards_enriched=0,
                        cards_deduplicated=0,
                        sources_found=0,
                        started_at=now,
                        summary_report={
                            "stage": "queued",
                            "config": config_data,
                            "scheduled_by": schedule_id,
                        },
                    )

                    async with async_session_factory() as db:
                        db.add(new_run)
                        await db.commit()

                    summary["discovery_run_ids"].append(run_id)

                    logger.info(
                        "Scheduled discovery: queued discovery run",
                        extra={
                            "worker_id": self.worker_id,
                            "run_id": run_id,
                            "pillars": pillars,
                            "max_queries": max_queries,
                        },
                    )

                except Exception as disc_err:
                    logger.error(
                        f"Scheduled discovery: failed to create discovery run: {disc_err}",
                        exc_info=True,
                    )
                    summary["errors"].append(
                        f"Discovery run creation failed: {disc_err}"
                    )

            # Step 4: Update the schedule with results
            final_status = (
                "completed" if not summary["errors"] else "completed_with_errors"
            )
            summary["completed_at"] = datetime.now(timezone.utc).isoformat()
            summary["status"] = final_status

            async with async_session_factory() as db:
                await db.execute(
                    sa_update(DiscoverySchedule)
                    .where(DiscoverySchedule.id == uuid.UUID(schedule_id))
                    .values(
                        last_run_status=final_status,
                        last_run_summary=summary,
                        updated_at=datetime.now(timezone.utc),
                    )
                )
                await db.commit()

            logger.info(
                "Scheduled discovery complete",
                extra={
                    "worker_id": self.worker_id,
                    "schedule_id": schedule_id,
                    "status": final_status,
                    "discovery_runs": len(summary["discovery_run_ids"]),
                    "errors": len(summary["errors"]),
                },
            )

            return True

        except Exception as e:
            logger.error(f"Scheduled discovery check failed: {e}", exc_info=True)
            return False


async def _main() -> None:
    # Load environment variables (safe no-op in Railway where env is injected).
    load_dotenv(os.getenv("GRANTSCOPE_DOTENV_PATH", ".env"))

    worker = GrantScopeWorker()

    port_env = os.getenv("PORT")
    enable_health_server_default = "true" if port_env else "false"
    enable_health_server = _truthy(
        os.getenv("GRANTSCOPE_WORKER_HEALTH_SERVER", enable_health_server_default)
    )

    server: Optional[uvicorn.Server] = None

    def _request_stop() -> None:
        worker.request_stop()
        if server is not None:
            server.should_exit = True

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _request_stop)
        except NotImplementedError:
            # Windows / limited environments
            signal.signal(sig, lambda *_: _request_stop())

    if enable_health_server:
        port = int(port_env or "8000")
        app = FastAPI(title="GrantScope2 Worker", version="1.0.0")

        @app.get("/api/v1/health")
        async def health() -> Dict[str, Any]:
            return {"status": "ok", "role": "worker", "worker_id": worker.worker_id}

        @app.get("/api/v1/worker/health")
        async def worker_health() -> Dict[str, Any]:
            return {"status": "ok", "worker_id": worker.worker_id}

        config = uvicorn.Config(
            app, host="0.0.0.0", port=port, log_level="info", loop="asyncio"
        )
        server = uvicorn.Server(config)

        server_task = asyncio.create_task(server.serve())
        worker_task = asyncio.create_task(worker.run())

        done, pending = await asyncio.wait(
            {server_task, worker_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        for task in done:
            task.result()
    else:
        await worker.run()


if __name__ == "__main__":
    asyncio.run(_main())
