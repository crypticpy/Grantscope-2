"""Research tasks router."""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from app.deps import supabase, get_current_user, _safe_error, openai_client, limiter
from app.models.research import ResearchTaskCreate, ResearchTask, VALID_TASK_TYPES
from app.research_service import ResearchService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["research"])


# ============================================================================
# Background task
# ============================================================================


async def execute_research_task_background(
    task_id: str, task_data: ResearchTaskCreate, user_id: str
):
    """
    Background task to execute research.

    Updates task status through lifecycle: queued -> processing -> completed/failed

    Research Pipeline (hybrid approach):
    1. Discovery: GPT Researcher with municipal-focused queries
    2. Triage: Quick relevance check (gpt-4o-mini)
    3. Analysis: Full classification and scoring (gpt-4o)
    4. Matching: Vector similarity to existing cards
    5. Storage: Persist with entities for graph building
    """
    service = ResearchService(supabase, openai_client)

    try:

        def _get_timeout_seconds(task_type: str) -> int:
            defaults = {
                "update": 15 * 60,
                "deep_research": 45 * 60,
                "workstream_analysis": 45 * 60,
            }
            env_keys = {
                "update": "RESEARCH_TASK_TIMEOUT_UPDATE_SECONDS",
                "deep_research": "RESEARCH_TASK_TIMEOUT_DEEP_RESEARCH_SECONDS",
                "workstream_analysis": "RESEARCH_TASK_TIMEOUT_WORKSTREAM_ANALYSIS_SECONDS",
            }
            env_key = env_keys.get(task_type)
            if env_key:
                try:
                    return int(
                        os.getenv(env_key, str(defaults.get(task_type, 45 * 60)))
                    )
                except ValueError:
                    return defaults.get(task_type, 45 * 60)
            return defaults.get(task_type, 45 * 60)

        # Update status to processing
        now = datetime.now(timezone.utc).isoformat()
        supabase.table("research_tasks").update(
            {
                "status": "processing",
                "started_at": now,
                "result_summary": {
                    "stage": f"running:{task_data.task_type}",
                    "heartbeat_at": now,
                },
            }
        ).eq("id", task_id).execute()

        timeout_seconds = _get_timeout_seconds(task_data.task_type)

        # Background heartbeat to prevent the stale-task watchdog from killing
        # long-running research while it's still making progress.
        async def _heartbeat():
            while True:
                await asyncio.sleep(60)
                try:
                    supabase.table("research_tasks").update(
                        {
                            "result_summary": {
                                "stage": f"running:{task_data.task_type}",
                                "heartbeat_at": datetime.now(timezone.utc).isoformat(),
                            }
                        }
                    ).eq("id", task_id).execute()
                except Exception:
                    pass

        heartbeat_task = asyncio.create_task(_heartbeat())

        try:
            # Execute based on task type
            if task_data.task_type == "update":
                result = await asyncio.wait_for(
                    service.execute_update(task_data.card_id, task_id),
                    timeout=timeout_seconds,
                )
            elif task_data.task_type == "deep_research":
                result = await asyncio.wait_for(
                    service.execute_deep_research(task_data.card_id, task_id),
                    timeout=timeout_seconds,
                )
            elif task_data.task_type == "workstream_analysis":
                result = await asyncio.wait_for(
                    service.execute_workstream_analysis(
                        task_data.workstream_id, task_id, user_id
                    ),
                    timeout=timeout_seconds,
                )
            else:
                raise ValueError(f"Unknown task type: {task_data.task_type}")
        finally:
            heartbeat_task.cancel()

        # Convert ResearchResult dataclass to dict for storage
        result_summary = {
            "sources_found": result.sources_found,
            "sources_relevant": result.sources_relevant,
            "sources_added": result.sources_added,
            "cards_matched": result.cards_matched,
            "cards_created": result.cards_created,
            "entities_extracted": result.entities_extracted,
            "cost_estimate": result.cost_estimate,
            "report_preview": result.report_preview,  # Full research report text
        }

        # Update as completed
        supabase.table("research_tasks").update(
            {
                "status": "completed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "result_summary": result_summary,
            }
        ).eq("id", task_id).execute()

        # Update signal quality score after research completion
        if task_data.card_id:
            try:
                from app.signal_quality import update_signal_quality_score

                update_signal_quality_score(supabase, task_data.card_id)
            except Exception as e:
                logger.warning(
                    f"Failed to update signal quality score for {task_data.card_id}: {e}"
                )

    except asyncio.TimeoutError:
        # Update as failed (timeout)
        supabase.table("research_tasks").update(
            {
                "status": "failed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "error_message": f"Research task timed out while {task_data.task_type} was running",
            }
        ).eq("id", task_id).execute()

    except Exception as e:
        # Update as failed
        supabase.table("research_tasks").update(
            {
                "status": "failed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "error_message": str(e),
            }
        ).eq("id", task_id).execute()


# ============================================================================
# Routes
# ============================================================================


@router.post("/research", response_model=ResearchTask)
@limiter.limit("5/minute")
async def create_research_task(
    request: Request,
    task_data: ResearchTaskCreate,
    current_user: dict = Depends(get_current_user),
):
    """
    Create and execute a research task.

    Task types:
    - update: Quick refresh with 5-10 new sources
    - deep_research: Comprehensive research with 15-20 sources (limited to 2/day/card)
    - workstream_analysis: Research based on workstream keywords

    Returns immediately with task ID. Poll GET /research/{task_id} for status.
    """
    # Validate input
    if not task_data.card_id and not task_data.workstream_id:
        raise HTTPException(
            status_code=400, detail="Either card_id or workstream_id required"
        )

    if task_data.task_type not in ["update", "deep_research", "workstream_analysis"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid task_type. Use: update, deep_research, workstream_analysis",
        )

    # Check rate limit for deep research
    if task_data.task_type == "deep_research" and task_data.card_id:
        service = ResearchService(supabase, openai_client)
        if not await service.check_rate_limit(task_data.card_id):
            raise HTTPException(
                status_code=429, detail="Daily deep research limit reached (2 per card)"
            )

    # Create task record
    task_record = {
        "user_id": current_user["id"],
        "task_type": task_data.task_type,
        "status": "queued",
    }

    if task_data.card_id:
        task_record["card_id"] = task_data.card_id
    if task_data.workstream_id:
        task_record["workstream_id"] = task_data.workstream_id

    task_result = supabase.table("research_tasks").insert(task_record).execute()

    if not task_result.data:
        raise HTTPException(status_code=500, detail="Failed to create research task")

    task = task_result.data[0]
    task_id = task["id"]

    # Execute research in background (non-blocking)
    # Task execution is handled by the background worker (see `app.worker`).

    return ResearchTask(**task)


@router.get("/research/{task_id}", response_model=ResearchTask)
async def get_research_task(
    task_id: str, current_user: dict = Depends(get_current_user)
):
    """
    Get research task status.

    Use this endpoint to poll for task completion after creating a research task.
    Status values: queued, processing, completed, failed
    """
    result = (
        supabase.table("research_tasks")
        .select("*")
        .eq("id", task_id)
        .eq("user_id", current_user["id"])
        .single()
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Research task not found")

    task = result.data

    def _parse_dt(value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            dt = value
        else:
            try:
                dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except ValueError:
                return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _get_timeout_seconds(task_type: str, status: str) -> int:
        if status == "queued":
            try:
                return int(os.getenv("RESEARCH_TASK_QUEUED_TIMEOUT_SECONDS", "900"))
            except ValueError:
                return 900
        defaults = {
            "update": 15 * 60,
            "deep_research": 45 * 60,
            "workstream_analysis": 45 * 60,
        }
        env_keys = {
            "update": "RESEARCH_TASK_TIMEOUT_UPDATE_SECONDS",
            "deep_research": "RESEARCH_TASK_TIMEOUT_DEEP_RESEARCH_SECONDS",
            "workstream_analysis": "RESEARCH_TASK_TIMEOUT_WORKSTREAM_ANALYSIS_SECONDS",
        }
        env_key = env_keys.get(task_type)
        if env_key:
            try:
                return int(os.getenv(env_key, str(defaults.get(task_type, 45 * 60))))
            except ValueError:
                return defaults.get(task_type, 45 * 60)
        return defaults.get(task_type, 45 * 60)

    def _maybe_fail_stale_task(task_row: Dict[str, Any]) -> Dict[str, Any]:
        status_val = task_row.get("status")
        if status_val not in ("queued", "processing"):
            return task_row

        summary = task_row.get("result_summary") or {}
        heartbeat_dt = (
            _parse_dt(summary.get("heartbeat_at"))
            if isinstance(summary, dict)
            else None
        )

        base_dt = None
        if status_val == "processing":
            base_dt = (
                heartbeat_dt
                or _parse_dt(task_row.get("started_at"))
                or _parse_dt(task_row.get("created_at"))
            )
        else:
            base_dt = _parse_dt(task_row.get("created_at"))

        if not base_dt:
            return task_row

        timeout_seconds = _get_timeout_seconds(
            task_row.get("task_type", ""), status_val
        )
        age_seconds = (datetime.now(timezone.utc) - base_dt).total_seconds()

        if age_seconds <= timeout_seconds:
            return task_row

        age_minutes = int(age_seconds // 60)
        error_message = (
            f"Research task stalled (no progress for ~{age_minutes} minutes). "
            "This can happen if the server restarts mid-task. Please retry."
        )

        new_summary = dict(summary) if isinstance(summary, dict) else {}
        new_summary.update(
            {
                "timed_out": True,
                "timed_out_at": datetime.now(timezone.utc).isoformat(),
                "timeout_seconds": timeout_seconds,
            }
        )

        updates = {
            "status": "failed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "error_message": error_message,
            "result_summary": new_summary,
        }

        try:
            supabase.table("research_tasks").update(updates).eq("id", task_id).eq(
                "user_id", current_user["id"]
            ).execute()
            task_row.update(updates)
        except Exception:
            # If we can't update, return original task row.
            return task_row

        return task_row

    task = _maybe_fail_stale_task(task)

    return ResearchTask(**task)


@router.get("/me/research-tasks", response_model=List[ResearchTask])
async def list_research_tasks(
    current_user: dict = Depends(get_current_user), limit: int = 10
):
    """
    List user's recent research tasks.

    Returns the most recent tasks, ordered by creation date descending.
    """
    result = (
        supabase.table("research_tasks")
        .select("*")
        .eq("user_id", current_user["id"])
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )

    return [ResearchTask(**t) for t in result.data]
