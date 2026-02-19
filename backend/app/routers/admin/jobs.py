"""Background jobs admin endpoints -- list, inspect, retry, cancel research tasks."""

import logging
import uuid as _uuid
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.admin_deps import require_admin
from app.deps import get_db
from app.models.db.research import ResearchTask
from app.routers.admin._helpers import _row_to_dict

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# GET /admin/jobs/stats  (defined BEFORE the /{task_id} routes to avoid
#                         FastAPI treating "stats" as a task_id path param)
# ---------------------------------------------------------------------------
@router.get("/admin/jobs/stats")
async def job_stats(
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(require_admin),
):
    """Aggregate job statistics: counts by status, by type, recent activity, avg duration."""
    try:
        # -- Counts by status -----------------------------------------------
        status_sql = text(
            """
            SELECT
                count(*) FILTER (WHERE status = 'queued')     AS queued,
                count(*) FILTER (WHERE status = 'processing') AS processing,
                count(*) FILTER (WHERE status = 'completed')  AS completed,
                count(*) FILTER (WHERE status = 'failed')     AS failed
            FROM research_tasks
        """
        )
        srow = (await db.execute(status_sql)).one()
        by_status = {
            "queued": srow.queued,
            "processing": srow.processing,
            "completed": srow.completed,
            "failed": srow.failed,
        }

        # -- Counts by task type --------------------------------------------
        type_sql = text(
            """
            SELECT
                count(*) FILTER (WHERE task_type = 'update')              AS update,
                count(*) FILTER (WHERE task_type = 'deep_research')       AS deep_research,
                count(*) FILTER (WHERE task_type = 'workstream_analysis') AS workstream_analysis,
                count(*) FILTER (WHERE task_type = 'card_analysis')       AS card_analysis
            FROM research_tasks
        """
        )
        trow = (await db.execute(type_sql)).one()
        by_type = {
            "update": trow.update,
            "deep_research": trow.deep_research,
            "workstream_analysis": trow.workstream_analysis,
            "card_analysis": trow.card_analysis,
        }

        # -- Recent activity (24h) ------------------------------------------
        recent_sql = text(
            """
            SELECT
                count(*) FILTER (WHERE status = 'completed'
                                   AND completed_at >= now() - interval '24 hours') AS completed_24h,
                count(*) FILTER (WHERE status = 'failed'
                                   AND completed_at >= now() - interval '24 hours') AS failed_24h
            FROM research_tasks
        """
        )
        rrow = (await db.execute(recent_sql)).one()

        # -- Average duration (completed in last 7 days) --------------------
        avg_sql = text(
            """
            SELECT avg(EXTRACT(EPOCH FROM (completed_at - started_at))) AS avg_secs
            FROM research_tasks
            WHERE status = 'completed'
              AND started_at IS NOT NULL
              AND completed_at IS NOT NULL
              AND completed_at >= now() - interval '7 days'
        """
        )
        avg_secs = (await db.execute(avg_sql)).scalar_one_or_none()

        return {
            "by_status": by_status,
            "by_type": by_type,
            "completed_24h": rrow.completed_24h,
            "failed_24h": rrow.failed_24h,
            "avg_duration_seconds": (
                round(avg_secs, 2) if avg_secs is not None else None
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to compute job stats")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Job stats retrieval failed: {type(e).__name__}",
        ) from e


# ---------------------------------------------------------------------------
# POST /admin/jobs/retry-all-failed
# ---------------------------------------------------------------------------
@router.post("/admin/jobs/retry-all-failed")
async def retry_all_failed(
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(require_admin),
):
    """Bulk retry all failed tasks from the last 24 hours."""
    try:
        result = await db.execute(
            update(ResearchTask)
            .where(
                ResearchTask.status == "failed",
                ResearchTask.completed_at >= func.now() - text("interval '24 hours'"),
            )
            .values(
                status="queued",
                error_message=None,
                completed_at=None,
                started_at=None,
                result_summary=None,
            )
        )
        retried = result.rowcount
        await db.commit()
        return {"retried": retried}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to bulk retry failed tasks")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bulk retry failed: {type(e).__name__}",
        ) from e


# ---------------------------------------------------------------------------
# GET /admin/jobs
# ---------------------------------------------------------------------------
@router.get("/admin/jobs")
async def list_jobs(
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(require_admin),
    status_filter: Optional[str] = Query(None, alias="status"),
    task_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    since: Optional[date] = Query(
        None, description="Filter tasks created on or after this date"
    ),
):
    """List research tasks with filters and pagination, including card name when available."""
    try:
        # -- Build base query with optional card name join ------------------
        base_sql = """
            SELECT
                rt.*,
                c.name AS card_name
            FROM research_tasks rt
            LEFT JOIN cards c ON rt.card_id = c.id
            WHERE 1=1
        """
        count_sql = """
            SELECT count(*) FROM research_tasks rt WHERE 1=1
        """
        params: dict = {}

        if status_filter:
            base_sql += " AND rt.status = :status_filter"
            count_sql += " AND rt.status = :status_filter"
            params["status_filter"] = status_filter

        if task_type:
            base_sql += " AND rt.task_type = :task_type"
            count_sql += " AND rt.task_type = :task_type"
            params["task_type"] = task_type

        if since is not None:
            base_sql += " AND rt.created_at >= :since"
            count_sql += " AND rt.created_at >= :since"
            params["since"] = datetime.combine(
                since, datetime.min.time(), tzinfo=timezone.utc
            )

        # Total count
        total = (await db.execute(text(count_sql), params)).scalar_one()

        # Paginated data
        offset = (page - 1) * page_size
        base_sql += " ORDER BY rt.created_at DESC LIMIT :limit OFFSET :offset"
        params["limit"] = page_size
        params["offset"] = offset

        rows = (await db.execute(text(base_sql), params)).mappings().all()

        jobs = []
        for row in rows:
            job = dict(row)
            # Serialize UUID / datetime / Decimal values
            for key, value in job.items():
                if hasattr(value, "hex") and callable(getattr(value, "hex", None)):
                    # UUID
                    job[key] = str(value)
                elif isinstance(value, datetime):
                    job[key] = value.isoformat()
            jobs.append(job)

        return {
            "jobs": jobs,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to list jobs")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Job listing failed: {type(e).__name__}",
        ) from e


# ---------------------------------------------------------------------------
# GET /admin/jobs/{task_id}
# ---------------------------------------------------------------------------
@router.get("/admin/jobs/{task_id}")
async def get_job(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(require_admin),
):
    """Get full detail for a single research task, including card name if linked."""
    try:
        try:
            _uuid.UUID(task_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid task ID format: {task_id}",
            )

        result = await db.execute(
            select(ResearchTask).where(ResearchTask.id == task_id)
        )
        task = result.scalar_one_or_none()

        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task {task_id} not found",
            )

        job = _row_to_dict(task)

        # Attach card name if card_id is set
        if task.card_id:
            card_name_sql = text("SELECT name FROM cards WHERE id = :card_id")
            card_name = (
                await db.execute(card_name_sql, {"card_id": str(task.card_id)})
            ).scalar_one_or_none()
            job["card_name"] = card_name
        else:
            job["card_name"] = None

        return job

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get job %s", task_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Job retrieval failed: {type(e).__name__}",
        ) from e


# ---------------------------------------------------------------------------
# POST /admin/jobs/{task_id}/retry
# ---------------------------------------------------------------------------
@router.post("/admin/jobs/{task_id}/retry")
async def retry_job(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(require_admin),
):
    """Reset a failed or stale-processing task back to queued.

    A task is retryable if:
    - status is 'failed', OR
    - status is 'processing' and started_at is more than 5 minutes ago (stale)
    """
    try:
        try:
            _uuid.UUID(task_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid task ID format: {task_id}",
            )

        result = await db.execute(
            select(ResearchTask).where(ResearchTask.id == task_id)
        )
        task = result.scalar_one_or_none()

        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task {task_id} not found",
            )

        now = datetime.now(timezone.utc)
        is_failed = task.status == "failed"
        started_at = task.started_at
        if started_at is not None and started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        is_stale = (
            task.status == "processing"
            and started_at is not None
            and (now - started_at).total_seconds() > 300
        )

        if not (is_failed or is_stale):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Task is '{task.status}' and not stale -- cannot retry",
            )

        task.status = "queued"
        task.error_message = None
        task.completed_at = None
        task.started_at = None
        task.result_summary = None

        await db.commit()
        await db.refresh(task)

        return _row_to_dict(task)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to retry job %s", task_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Job retry failed: {type(e).__name__}",
        ) from e


# ---------------------------------------------------------------------------
# POST /admin/jobs/{task_id}/cancel
# ---------------------------------------------------------------------------
@router.post("/admin/jobs/{task_id}/cancel")
async def cancel_job(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(require_admin),
):
    """Cancel a queued or processing task."""
    try:
        try:
            _uuid.UUID(task_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid task ID format: {task_id}",
            )

        result = await db.execute(
            select(ResearchTask).where(ResearchTask.id == task_id)
        )
        task = result.scalar_one_or_none()

        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task {task_id} not found",
            )

        if task.status not in ("queued", "processing"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Task is '{task.status}' -- only queued or processing tasks can be cancelled",
            )

        task.status = "failed"
        task.error_message = "Cancelled by admin"
        task.completed_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(task)

        return _row_to_dict(task)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to cancel job %s", task_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Job cancellation failed: {type(e).__name__}",
        ) from e
