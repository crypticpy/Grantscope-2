"""
Foresight Background Worker.

This process runs outside the FastAPI web server and executes long-running jobs
that must survive web restarts / scale-to-zero behaviors:
- `research_tasks` (update, deep_research, workstream_analysis)
- `executive_briefs` (pending -> generating -> completed/failed)
- `discovery_runs` (queued via summary_report.stage)

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
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from dotenv import load_dotenv

from app.brief_service import ExecutiveBriefService
from app.main import (
    DiscoveryConfigRequest,
    ResearchTaskCreate,
    execute_discovery_run_background,
    execute_research_task_background,
    openai_client,
    start_scheduler,
    supabase,
)
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
        self.poll_interval_seconds = _get_float_env("FORESIGHT_WORKER_POLL_INTERVAL_SECONDS", 5.0)
        self.brief_timeout_seconds = _get_int_env("FORESIGHT_BRIEF_TIMEOUT_SECONDS", 30 * 60)
        self.discovery_timeout_seconds = _get_int_env("FORESIGHT_DISCOVERY_TIMEOUT_SECONDS", 90 * 60)
        self.enable_scheduler = _truthy(os.getenv("FORESIGHT_ENABLE_SCHEDULER", "false"))
        self._stop_event = asyncio.Event()

    def request_stop(self) -> None:
        self._stop_event.set()

    async def run(self) -> None:
        logger.info(
            "Worker starting",
            extra={
                "worker_id": self.worker_id,
                "poll_interval_seconds": self.poll_interval_seconds,
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
            except Exception as e:
                logger.exception(f"Worker loop error: {e}")

            if not did_work:
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=self.poll_interval_seconds)
                except asyncio.TimeoutError:
                    pass

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
            since_timestamp = sources_since_previous.get("since_date") or sources_since_previous.get("since_timestamp")

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

        config_data = summary_report.get("config") if isinstance(summary_report, dict) else None
        if not isinstance(config_data, dict):
            config_data = {}

        config = DiscoveryConfigRequest(**config_data)

        if not triggered_by_user:
            # Defensive fallback: pick any system user.
            system_user = supabase.table("users").select("id").limit(1).execute().data or []
            triggered_by_user = system_user[0]["id"] if system_user else None

        if not triggered_by_user:
            raise RuntimeError("Discovery run has no triggered_by_user and no users exist to run as.")

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


async def _main() -> None:
    # Load environment variables (safe no-op in Railway where env is injected).
    load_dotenv(os.getenv("FORESIGHT_DOTENV_PATH", ".env"))

    worker = ForesightWorker()

    port_env = os.getenv("PORT")
    enable_health_server_default = "true" if port_env else "false"
    enable_health_server = _truthy(os.getenv("FORESIGHT_WORKER_HEALTH_SERVER", enable_health_server_default))

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

        config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info", loop="asyncio")
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
