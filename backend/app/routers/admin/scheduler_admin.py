"""Scheduler admin endpoints -- manage APScheduler jobs.

Provides visibility into all scheduled jobs, enable/disable toggles,
manual trigger capability, and global scheduler status.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.admin_deps import require_admin
from app.deps import get_db, _safe_error
from app.models.db.system_settings import SystemSetting

logger = logging.getLogger(__name__)
router = APIRouter()

# Track scheduler start time for uptime calculation
_scheduler_start_monotonic: float | None = None

# Track in-flight manually triggered jobs to prevent concurrent duplicates
_triggered_jobs: set[str] = set()

# ---------------------------------------------------------------------------
# Scheduler job registry -- mirrors the definitions in app/scheduler.py
# ---------------------------------------------------------------------------

# Each entry maps the APScheduler job ID to its metadata and callable path.
# The callable is imported lazily in the trigger endpoint to avoid circular
# imports at module load time.

JOB_REGISTRY: Dict[str, Dict[str, Any]] = {
    "enrich_thin_descriptions": {
        "name": "Enrich thin card descriptions",
        "description": "AI-enriches cards with thin or missing descriptions",
        "schedule": "Daily at 3:00 AM UTC",
        "callable": "app.scheduler.run_nightly_description_enrichment",
    },
    "scheduled_workstream_scans": {
        "name": "Workstream auto-scans",
        "description": "Queue scans for workstreams with auto_scan enabled",
        "schedule": "Daily at 4:00 AM UTC",
        "callable": "app.scheduler.run_scheduled_workstream_scans",
    },
    "nightly_reputation_aggregation": {
        "name": "Domain reputation aggregation",
        "description": "Recalculate domain reputation composite scores",
        "schedule": "Daily at 5:30 AM UTC",
        "callable": "app.scheduler.run_nightly_reputation_aggregation",
    },
    "nightly_scan": {
        "name": "Nightly content scan",
        "description": "Queue update tasks for cards not recently updated",
        "schedule": "Daily at 6:00 AM UTC",
        "callable": "app.scheduler.run_nightly_scan",
    },
    "nightly_sqi_recalculation": {
        "name": "SQI recalculation",
        "description": "Recalculate Source Quality Index for all cards",
        "schedule": "Daily at 6:30 AM UTC",
        "callable": "app.scheduler.run_nightly_sqi_recalculation",
    },
    "weekly_discovery": {
        "name": "Weekly discovery run",
        "description": "Full discovery run across all pillars",
        "schedule": "Sundays at 2:00 AM UTC",
        "callable": "app.scheduler.run_weekly_discovery",
    },
    "nightly_pattern_detection": {
        "name": "Cross-signal pattern detection",
        "description": "Detect patterns and emerging themes across signals",
        "schedule": "Daily at 7:00 AM UTC",
        "callable": "app.scheduler.run_nightly_pattern_detection",
    },
    "nightly_velocity_calculation": {
        "name": "Velocity trend calculation",
        "description": "Calculate velocity trends for all active cards",
        "schedule": "Daily at 7:30 AM UTC",
        "callable": "app.scheduler.run_nightly_velocity_calculation",
    },
    "daily_digest_batch": {
        "name": "Email digest batch",
        "description": "Process and send digest emails for all due users",
        "schedule": "Daily at 8:00 AM UTC",
        "callable": "app.scheduler.run_digest_batch",
    },
    "scan_grants": {
        "name": "Grant opportunity scan",
        "description": "Scan Grants.gov and SAM.gov for new opportunities",
        "schedule": "Every 6 hours",
        "callable": "app.scheduler.scan_grants",
    },
}

# system_settings key for persisted enable/disable state
_SETTINGS_KEY = "scheduler_jobs"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _read_job_settings(db: AsyncSession) -> Dict[str, bool]:
    """Read the persisted enabled/disabled state for each job.

    Returns a dict mapping job_id -> enabled (bool).  Jobs not present
    in the settings are considered enabled by default.
    """
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key == _SETTINGS_KEY)
    )
    setting = result.scalar_one_or_none()
    if setting and isinstance(setting.value, dict):
        return setting.value
    return {}


def _get_scheduler():
    """Lazily import the scheduler singleton to avoid circular imports."""
    from app.scheduler import scheduler

    return scheduler


def _is_scheduler_running() -> bool:
    """Check if the APScheduler instance is currently running."""
    try:
        sched = _get_scheduler()
        return getattr(sched, "running", False)
    except Exception:
        return False


def _get_apscheduler_job_info(job_id: str) -> Dict[str, Any]:
    """Extract next_run_time from the APScheduler job instance if available."""
    info: Dict[str, Any] = {
        "next_run": None,
    }
    try:
        sched = _get_scheduler()
        if not getattr(sched, "running", False):
            return info
        job = sched.get_job(job_id)
        if job and job.next_run_time:
            info["next_run"] = job.next_run_time.isoformat()
    except Exception:
        pass
    return info


# ---------------------------------------------------------------------------
# GET /admin/scheduler/status
# ---------------------------------------------------------------------------


@router.get("/admin/scheduler/status")
async def scheduler_status(
    _current_user: dict = Depends(require_admin),
):
    """Global scheduler status: running/stopped, job count, uptime."""
    global _scheduler_start_monotonic
    try:
        running = _is_scheduler_running()
        jobs_count = 0
        if running:
            # Track when we first observe the scheduler running
            if _scheduler_start_monotonic is None:
                _scheduler_start_monotonic = time.monotonic()
            try:
                sched = _get_scheduler()
                jobs_count = len(sched.get_jobs())
            except Exception:
                pass
        else:
            # Scheduler not running, reset start time
            _scheduler_start_monotonic = None

        uptime_seconds = 0.0
        if running and _scheduler_start_monotonic is not None:
            uptime_seconds = time.monotonic() - _scheduler_start_monotonic

        return {
            "running": running,
            "jobs_count": jobs_count,
            "uptime_seconds": round(uptime_seconds, 1),
        }
    except Exception as e:
        logger.error("Failed to get scheduler status: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("scheduler status", e),
        ) from e


# ---------------------------------------------------------------------------
# GET /admin/scheduler/jobs
# ---------------------------------------------------------------------------


@router.get("/admin/scheduler/jobs")
async def list_scheduler_jobs(
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(require_admin),
):
    """List all scheduled jobs with name, schedule, enabled status, and timing info.

    Returns a flat JSON array of SchedulerJob objects.
    """
    try:
        job_settings = await _read_job_settings(db)
        scheduler_running = _is_scheduler_running()

        jobs = []
        for job_id, meta in JOB_REGISTRY.items():
            enabled = job_settings.get(job_id, True)  # enabled by default

            # Get live APScheduler info (next_run)
            ap_info = _get_apscheduler_job_info(job_id) if scheduler_running else {}

            # Derive status from enabled state + scheduler running state
            if not enabled:
                job_status = "disabled"
            elif not scheduler_running:
                job_status = "paused"
            else:
                job_status = "active"

            jobs.append(
                {
                    "id": job_id,
                    "name": meta["name"],
                    "trigger": "cron",
                    "description": meta["description"],
                    "schedule": meta["schedule"],
                    "enabled": enabled,
                    "next_run": ap_info.get("next_run"),
                    "last_run": None,
                    "status": job_status,
                }
            )

        return jobs
    except Exception as e:
        logger.error("Failed to list scheduler jobs: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("scheduler jobs listing", e),
        ) from e


# ---------------------------------------------------------------------------
# POST /admin/scheduler/jobs/{job_id}/toggle
# ---------------------------------------------------------------------------


@router.post("/admin/scheduler/jobs/{job_id}/toggle")
async def toggle_scheduler_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Enable or disable a specific scheduled job.

    Toggles the current state: enabled -> disabled, disabled -> enabled.
    Persists state in ``system_settings`` under the ``scheduler_jobs`` key.
    When the scheduler is running, also pauses/resumes the APScheduler job.
    """
    if job_id not in JOB_REGISTRY:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown scheduler job: {job_id}",
        )

    try:
        # Read current settings
        job_settings = await _read_job_settings(db)
        current_enabled = job_settings.get(job_id, True)
        new_enabled = not current_enabled

        # Update settings
        job_settings[job_id] = new_enabled
        now = datetime.now(timezone.utc)

        stmt = pg_insert(SystemSetting).values(
            key=_SETTINGS_KEY,
            value=job_settings,
            description="Scheduler job enable/disable state",
            updated_by=current_user["id"],
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["key"],
            set_={
                "value": job_settings,
                "updated_by": current_user["id"],
                "updated_at": now,
            },
        )
        await db.execute(stmt)
        await db.commit()

        # If the scheduler is running, also pause/resume the APScheduler job
        if _is_scheduler_running():
            try:
                sched = _get_scheduler()
                if new_enabled:
                    sched.resume_job(job_id)
                else:
                    sched.pause_job(job_id)
            except Exception as exc:
                logger.warning(
                    "Could not %s APScheduler job %s: %s",
                    "resume" if new_enabled else "pause",
                    job_id,
                    exc,
                )

        logger.info(
            "Scheduler job '%s' %s by user %s",
            job_id,
            "enabled" if new_enabled else "disabled",
            current_user["id"],
        )

        return {
            "id": job_id,
            "name": JOB_REGISTRY[job_id]["name"],
            "enabled": new_enabled,
            "message": f"Job '{job_id}' {'enabled' if new_enabled else 'disabled'}",
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("Failed to toggle scheduler job %s: %s", job_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("scheduler job toggle", e),
        ) from e


# ---------------------------------------------------------------------------
# POST /admin/scheduler/jobs/{job_id}/trigger
# ---------------------------------------------------------------------------


@router.post("/admin/scheduler/jobs/{job_id}/trigger")
async def trigger_scheduler_job(
    job_id: str,
    _current_user: dict = Depends(require_admin),
):
    """Manually trigger a scheduled job to run now.

    The job function is executed in the background so the request
    returns immediately.  The response confirms that the job was
    dispatched but does not wait for completion.
    """
    if job_id not in JOB_REGISTRY:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown scheduler job: {job_id}",
        )

    if job_id in _triggered_jobs:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job '{job_id}' is already running from a previous manual trigger.",
        )

    _triggered_jobs.add(job_id)

    def _on_job_done(t: asyncio.Task, _jid: str = job_id) -> None:
        _triggered_jobs.discard(_jid)
        if not t.cancelled() and t.exception():
            logger.error("Triggered job '%s' failed: %s", _jid, t.exception())

    try:
        # Import the actual job function from scheduler.py
        from app import scheduler as sched_module

        callable_path = JOB_REGISTRY[job_id]["callable"]
        func_name = callable_path.split(".")[-1]

        job_func = getattr(sched_module, func_name, None)
        if job_func is None:
            _triggered_jobs.discard(job_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Job function '{func_name}' not found in scheduler module",
            )

        # Run in background so the API returns immediately
        task = asyncio.create_task(job_func())
        task.add_done_callback(_on_job_done)

        logger.info(
            "Scheduler job '%s' manually triggered by user %s",
            job_id,
            _current_user["id"],
        )

        return {
            "id": job_id,
            "name": JOB_REGISTRY[job_id]["name"],
            "status": "triggered",
            "message": f"Job '{job_id}' has been triggered and is running in the background.",
        }

    except HTTPException:
        raise
    except Exception as e:
        _triggered_jobs.discard(job_id)
        logger.error("Failed to trigger scheduler job %s: %s", job_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("scheduler job trigger", e),
        ) from e
