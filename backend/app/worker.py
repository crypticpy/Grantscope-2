"""
Foresight Background Worker.

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

from app.brief_service import ExecutiveBriefService
from app.deps import openai_client, supabase
from app.models.discovery_models import DiscoveryConfigRequest
from app.models.research import ResearchTaskCreate
from app.routers.discovery import execute_discovery_run_background
from app.routers.research import execute_research_task_background
from app.routers.workstream_scans import execute_workstream_scan_background
from app.scheduler import start_scheduler
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


class ForesightWorker:
    def __init__(self) -> None:
        self.worker_id = os.getenv("FORESIGHT_WORKER_ID") or str(uuid.uuid4())
        self.poll_interval_seconds = _get_float_env(
            "FORESIGHT_WORKER_POLL_INTERVAL_SECONDS", 5.0
        )
        self.max_poll_interval_seconds = _get_float_env(
            "FORESIGHT_WORKER_MAX_POLL_INTERVAL_SECONDS", 30.0
        )
        self.brief_timeout_seconds = _get_int_env(
            "FORESIGHT_BRIEF_TIMEOUT_SECONDS", 30 * 60
        )
        self.discovery_timeout_seconds = _get_int_env(
            "FORESIGHT_DISCOVERY_TIMEOUT_SECONDS", 90 * 60
        )
        self.workstream_scan_timeout_seconds = _get_int_env(
            "FORESIGHT_WORKSTREAM_SCAN_TIMEOUT_SECONDS", 5 * 60
        )
        self.rss_check_interval_seconds = _get_int_env(
            "FORESIGHT_RSS_CHECK_INTERVAL_SECONDS", 30 * 60  # 30 minutes
        )
        self.scheduled_discovery_timeout_seconds = _get_int_env(
            "FORESIGHT_SCHEDULED_DISCOVERY_TIMEOUT_SECONDS", 120 * 60  # 2 hours
        )
        self.enable_scheduler = _truthy(
            os.getenv("FORESIGHT_ENABLE_SCHEDULER", "false")
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
        tasks = (
            supabase.table("research_tasks")
            .select("id,user_id,card_id,workstream_id,task_type")
            .eq("status", "queued")
            .order("created_at", desc=False)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not tasks:
            return False

        task = tasks[0]
        task_id = task["id"]

        now = datetime.now(timezone.utc).isoformat()
        claimed = (
            supabase.table("research_tasks")
            .update(
                {
                    "status": "processing",
                    "started_at": now,
                    "result_summary": {
                        "stage": "claimed:research",
                        "heartbeat_at": now,
                        "worker_id": self.worker_id,
                    },
                }
            )
            .eq("id", task_id)
            .eq("status", "queued")
            .execute()
            .data
        )
        if not claimed:
            return False

        task_data = ResearchTaskCreate(
            card_id=task.get("card_id"),
            workstream_id=task.get("workstream_id"),
            task_type=task.get("task_type"),
        )

        logger.info(
            "Processing research task",
            extra={
                "worker_id": self.worker_id,
                "task_id": task_id,
                "task_type": task.get("task_type"),
                "card_id": task.get("card_id"),
                "workstream_id": task.get("workstream_id"),
            },
        )

        await execute_research_task_background(task_id, task_data, task["user_id"])
        return True

    async def _process_one_brief(self) -> bool:
        briefs = (
            supabase.table("executive_briefs")
            .select("id,workstream_card_id,card_id,sources_since_previous,status")
            .eq("status", "pending")
            .order("created_at", desc=False)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not briefs:
            return False

        brief = briefs[0]
        brief_id = brief["id"]

        claimed = (
            supabase.table("executive_briefs")
            .update({"status": "generating"})
            .eq("id", brief_id)
            .eq("status", "pending")
            .execute()
            .data
        )
        if not claimed:
            return False

        since_timestamp: Optional[str] = None
        sources_since_previous = brief.get("sources_since_previous") or {}
        if isinstance(sources_since_previous, dict):
            since_timestamp = sources_since_previous.get(
                "since_date"
            ) or sources_since_previous.get("since_timestamp")

        logger.info(
            "Processing executive brief",
            extra={
                "worker_id": self.worker_id,
                "brief_id": brief_id,
                "workstream_card_id": brief.get("workstream_card_id"),
                "card_id": brief.get("card_id"),
            },
        )

        service = ExecutiveBriefService(supabase, openai_client)
        try:
            await asyncio.wait_for(
                service.generate_executive_brief(
                    brief_id=brief_id,
                    workstream_card_id=brief["workstream_card_id"],
                    card_id=brief["card_id"],
                    since_timestamp=since_timestamp,
                ),
                timeout=self.brief_timeout_seconds,
            )
        except asyncio.TimeoutError:
            await service.update_brief_status(
                brief_id,
                "failed",
                error_message=f"Brief generation timed out after {self.brief_timeout_seconds} seconds",
            )
        except BaseException as e:
            # Includes CancelledError which is not an Exception.
            await service.update_brief_status(brief_id, "failed", error_message=str(e))
            raise
        return True

    async def _process_one_discovery_run(self) -> bool:
        runs = (
            supabase.table("discovery_runs")
            .select("id,triggered_by_user,summary_report,status")
            .eq("status", "running")
            .contains("summary_report", {"stage": "queued"})
            .order("started_at", desc=False)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not runs:
            return False

        run = runs[0]
        run_id = run["id"]
        triggered_by_user = run.get("triggered_by_user")

        summary_report: Dict[str, Any] = run.get("summary_report") or {}
        if not isinstance(summary_report, dict):
            summary_report = {}

        summary_report["stage"] = "running"
        summary_report["worker_id"] = self.worker_id
        summary_report["heartbeat_at"] = datetime.now(timezone.utc).isoformat()

        claimed = (
            supabase.table("discovery_runs")
            .update({"summary_report": summary_report})
            .eq("id", run_id)
            .eq("status", "running")
            .contains("summary_report", {"stage": "queued"})
            .execute()
            .data
        )
        if not claimed:
            return False

        config_data = (
            summary_report.get("config") if isinstance(summary_report, dict) else None
        )
        if not isinstance(config_data, dict):
            config_data = {}

        config = DiscoveryConfigRequest(**config_data)

        if not triggered_by_user:
            # Defensive fallback: pick any system user.
            system_user = (
                supabase.table("users").select("id").limit(1).execute().data or []
            )
            triggered_by_user = system_user[0]["id"] if system_user else None

        if not triggered_by_user:
            raise RuntimeError(
                "Discovery run has no triggered_by_user and no users exist to run as."
            )

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
            summary_report["stage"] = "failed"
            summary_report["timed_out"] = True
            summary_report["timed_out_at"] = datetime.now(timezone.utc).isoformat()
            supabase.table("discovery_runs").update(
                {
                    "status": "failed",
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "error_message": f"Discovery run timed out after {self.discovery_timeout_seconds} seconds",
                    "summary_report": summary_report,
                }
            ).eq("id", run_id).execute()
        except BaseException as e:
            summary_report["stage"] = "failed"
            summary_report["failed_at"] = datetime.now(timezone.utc).isoformat()
            supabase.table("discovery_runs").update(
                {
                    "status": "failed",
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "error_message": str(e),
                    "summary_report": summary_report,
                }
            ).eq("id", run_id).execute()
            raise
        return True

    async def _process_one_workstream_scan(self) -> bool:
        """Process one queued workstream scan job."""
        try:
            result = (
                supabase.table("workstream_scans")
                .select("id,workstream_id,user_id,config,status")
                .eq("status", "queued")
                .order("created_at", desc=False)
                .limit(1)
                .execute()
            )
            scans = result.data or []
            if scans:
                logger.info(
                    f"Found {len(scans)} queued workstream scan(s): {[s['id'] for s in scans]}"
                )
        except Exception as e:
            logger.error(f"Error querying workstream_scans: {e}")
            return False

        if not scans:
            return False

        scan = scans[0]
        scan_id = scan["id"]

        # Claim the scan by setting status to running
        now = datetime.now(timezone.utc).isoformat()
        claimed = (
            supabase.table("workstream_scans")
            .update({"status": "running", "started_at": now})
            .eq("id", scan_id)
            .eq("status", "queued")
            .execute()
            .data
        )
        if not claimed:
            return False

        config = scan.get("config") or {}
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
                "workstream_id": scan.get("workstream_id"),
                "user_id": scan.get("user_id"),
            },
        )

        try:
            await asyncio.wait_for(
                execute_workstream_scan_background(scan_id, config),
                timeout=self.workstream_scan_timeout_seconds,
            )
        except asyncio.TimeoutError:
            supabase.table("workstream_scans").update(
                {
                    "status": "failed",
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "error_message": f"Workstream scan timed out after {self.workstream_scan_timeout_seconds} seconds",
                }
            ).eq("id", scan_id).execute()
        except BaseException as e:
            supabase.table("workstream_scans").update(
                {
                    "status": "failed",
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "error_message": str(e),
                }
            ).eq("id", scan_id).execute()
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
            rss_service = RSSService(supabase, ai_service)

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
        try:
            now = datetime.now(timezone.utc)
            now_iso = now.isoformat()

            # Check for any due schedules
            schedules = (
                supabase.table("discovery_schedule")
                .select("*")
                .eq("enabled", True)
                .lte("next_run_at", now_iso)
                .order("next_run_at", desc=False)
                .limit(1)
                .execute()
                .data
                or []
            )

            if not schedules:
                return False

            schedule = schedules[0]
            schedule_id = schedule["id"]
            interval_hours = schedule.get("interval_hours") or 24
            pillars = schedule.get("pillars_to_scan") or [
                "CH",
                "MC",
                "HS",
                "EC",
                "ES",
                "CE",
            ]
            max_queries = schedule.get("max_search_queries_per_run") or 20
            process_rss = schedule.get("process_rss_first", True)

            # Claim the schedule by advancing next_run_at (optimistic lock)
            next_run = now + timedelta(hours=interval_hours)
            claimed = (
                supabase.table("discovery_schedule")
                .update(
                    {
                        "last_run_at": now_iso,
                        "next_run_at": next_run.isoformat(),
                        "last_run_status": "running",
                        "updated_at": now_iso,
                    }
                )
                .eq("id", schedule_id)
                .lte("next_run_at", now_iso)
                .execute()
                .data
            )
            if not claimed:
                return False

            logger.info(
                "Scheduled discovery triggered",
                extra={
                    "worker_id": self.worker_id,
                    "schedule_id": schedule_id,
                    "schedule_name": schedule.get("name"),
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
                    rss_service = RSSService(supabase, ai_service)

                    check_stats = await rss_service.check_feeds()
                    process_stats = await rss_service.process_new_items()

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
            system_user = (
                supabase.table("users").select("id").limit(1).execute().data or []
            )
            user_id = system_user[0]["id"] if system_user else None

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

                    run_record = {
                        "id": run_id,
                        "status": "running",
                        "triggered_by": "scheduled",
                        "triggered_by_user": user_id,
                        "cards_created": 0,
                        "cards_enriched": 0,
                        "cards_deduplicated": 0,
                        "sources_found": 0,
                        "started_at": now_iso,
                        "summary_report": {
                            "stage": "queued",
                            "config": config_data,
                            "scheduled_by": schedule_id,
                        },
                    }

                    supabase.table("discovery_runs").insert(run_record).execute()
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

            supabase.table("discovery_schedule").update(
                {
                    "last_run_status": final_status,
                    "last_run_summary": summary,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            ).eq("id", schedule_id).execute()

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
    load_dotenv(os.getenv("FORESIGHT_DOTENV_PATH", ".env"))

    worker = ForesightWorker()

    port_env = os.getenv("PORT")
    enable_health_server_default = "true" if port_env else "false"
    enable_health_server = _truthy(
        os.getenv("FORESIGHT_WORKER_HEALTH_SERVER", enable_health_server_default)
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
        app = FastAPI(title="Foresight Worker", version="1.0.0")

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
