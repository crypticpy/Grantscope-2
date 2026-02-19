"""Workstream CRUD and feed router (SQLAlchemy 2.0 async)."""

import logging
import uuid
from datetime import datetime, date, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, get_current_user_hardcoded, _safe_error
from app.models.db.workstream import Workstream as WorkstreamORM
from app.models.db.workstream import WorkstreamCard as WorkstreamCardORM
from app.models.db.workstream import WorkstreamScan as WorkstreamScanORM
from app.models.db.card import Card as CardORM
from app.models.workstream import (
    Workstream,
    WorkstreamCreate,
    WorkstreamUpdate,
    WorkstreamCreateResponse,
    AutoPopulateResponse,
    WorkstreamCardWithDetails,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["workstreams & programs"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_dict(obj, skip_cols=None) -> dict:
    """Convert a SQLAlchemy ORM instance to a plain dict, serialising
    UUID / datetime / Decimal values so they are JSON-friendly and
    compatible with the existing Pydantic response models.
    """
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


def _filter_cards_dicts(workstream_dict: dict, cards: list[dict]) -> list[dict]:
    """Apply pillar / goal / horizon / stage / keyword filters (in-memory).

    Operates on plain dicts so it works identically to the old Supabase path
    and to the shared helper in ``app.helpers.workstream_utils``.
    """
    filtered = cards

    ws_pillar_ids = workstream_dict.get("pillar_ids") or []
    if ws_pillar_ids:
        filtered = [c for c in filtered if c.get("pillar_id") in ws_pillar_ids]

    ws_goal_ids = workstream_dict.get("goal_ids") or []
    if ws_goal_ids:
        filtered = [c for c in filtered if c.get("goal_id") in ws_goal_ids]

    ws_horizon = workstream_dict.get("horizon")
    if ws_horizon and ws_horizon != "ALL":
        filtered = [c for c in filtered if c.get("horizon") == ws_horizon]

    ws_stage_ids = workstream_dict.get("stage_ids") or []
    if ws_stage_ids:

        def _stage_num(card_stage_id: str) -> str:
            return (
                card_stage_id.split("_", 1)[0]
                if "_" in card_stage_id
                else card_stage_id
            )

        filtered = [
            c for c in filtered if _stage_num(c.get("stage_id") or "") in ws_stage_ids
        ]

    # Filter by pipeline_statuses (new pipeline lifecycle filter)
    ws_pipeline_statuses = workstream_dict.get("pipeline_statuses") or []
    if ws_pipeline_statuses:
        filtered = [
            c for c in filtered if c.get("pipeline_status") in ws_pipeline_statuses
        ]

    ws_keywords = [k.lower() for k in (workstream_dict.get("keywords") or [])]
    if ws_keywords:

        def _card_text(card: dict) -> str:
            return " ".join(
                [
                    (card.get("name") or "").lower(),
                    (card.get("summary") or "").lower(),
                    (card.get("description") or "").lower(),
                ]
            )

        filtered = [
            c for c in filtered if any(kw in _card_text(c) for kw in ws_keywords)
        ]

    return filtered


async def _auto_queue_workstream_scan_sa(
    db: AsyncSession,
    workstream_id: str,
    user_id: str,
    config: dict,
) -> bool:
    """Queue a workstream scan via SQLAlchemy (replaces supabase helper)."""
    try:
        scan = WorkstreamScanORM(
            workstream_id=uuid.UUID(workstream_id),
            user_id=uuid.UUID(user_id),
            status="queued",
            config=config,
        )
        db.add(scan)
        await db.flush()
        await db.refresh(scan)
        logger.info(
            "Auto-queued workstream scan %s for workstream %s " "(triggered_by: %s)",
            scan.id,
            workstream_id,
            config.get("triggered_by", "unknown"),
        )
        return True
    except Exception as e:
        logger.error(
            "Failed to auto-queue scan for workstream %s: %s", workstream_id, e
        )
        return False


# ---------------------------------------------------------------------------
# GET /me/workstreams
# ---------------------------------------------------------------------------


@router.get("/me/workstreams")
@router.get("/me/programs")
async def get_user_workstreams(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Get user's workstreams."""
    try:
        result = await db.execute(
            select(WorkstreamORM)
            .where(WorkstreamORM.user_id == uuid.UUID(current_user["id"]))
            .order_by(WorkstreamORM.created_at.desc())
        )
        rows = result.scalars().all()
    except Exception as e:
        logger.error("Failed to list workstreams: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("listing workstreams", e),
        ) from e

    return [Workstream(**_row_to_dict(ws)) for ws in rows]


# ---------------------------------------------------------------------------
# POST /me/workstreams
# ---------------------------------------------------------------------------


@router.post("/me/workstreams", response_model=WorkstreamCreateResponse)
@router.post("/me/programs", response_model=WorkstreamCreateResponse)
async def create_workstream(
    workstream_data: WorkstreamCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Create new workstream with optional auto-populate and auto-scan queueing.

    After successful creation:
    1. Auto-populates the workstream with matching existing cards
    2. If fewer than 3 cards matched AND auto_scan is enabled, queues a scan
    """
    now_ts = datetime.now(timezone.utc)

    ws_obj = WorkstreamORM(
        user_id=uuid.UUID(current_user["id"]),
        name=workstream_data.name,
        description=workstream_data.description,
        pillar_ids=workstream_data.pillar_ids,
        goal_ids=workstream_data.goal_ids,
        stage_ids=workstream_data.stage_ids,
        horizon=workstream_data.horizon,
        keywords=workstream_data.keywords,
        is_active=True,
        auto_add=workstream_data.auto_add,
        auto_scan=workstream_data.auto_scan,
        program_type=workstream_data.program_type,
        department_id=workstream_data.department_id,
        budget=(
            Decimal(str(workstream_data.budget))
            if workstream_data.budget is not None
            else None
        ),
        fiscal_year=workstream_data.fiscal_year,
        category_ids=workstream_data.category_ids,
        created_at=now_ts,
        updated_at=now_ts,
    )

    try:
        db.add(ws_obj)
        await db.flush()
        await db.refresh(ws_obj)
    except Exception as e:
        logger.error("Failed to create workstream: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create workstream",
        ) from e

    workstream = _row_to_dict(ws_obj)
    workstream_id = workstream["id"]
    user_id = current_user["id"]

    # --- Post-creation: auto-populate with matching existing cards ---
    auto_populated_count = 0
    scan_queued = False

    try:
        card_result = await db.execute(
            select(CardORM)
            .where(CardORM.status == "active")
            .order_by(CardORM.created_at.desc())
            .limit(60)
        )
        card_rows = card_result.scalars().all()
        cards = [
            _row_to_dict(c, skip_cols={"embedding", "search_vector"}) for c in card_rows
        ]

        # Apply workstream filters
        cards = _filter_cards_dicts(workstream, cards)

        if candidates := cards[:20]:
            for idx, card in enumerate(candidates):
                wc = WorkstreamCardORM(
                    workstream_id=uuid.UUID(workstream_id),
                    card_id=uuid.UUID(card["id"]),
                    added_by=uuid.UUID(user_id),
                    added_at=now_ts,
                    status="inbox",
                    position=idx,
                    added_from="auto",
                    updated_at=now_ts,
                )
                db.add(wc)

            await db.flush()
            auto_populated_count = len(candidates)

        logger.info(
            "Post-creation auto-populate for workstream %s: %d cards added",
            workstream_id,
            auto_populated_count,
        )

    except Exception as e:
        logger.error(
            "Post-creation auto-populate failed for workstream %s: %s",
            workstream_id,
            e,
        )
        # Non-fatal: workstream was created successfully, continue

    # --- Post-creation: queue scan if auto_scan is on and few matches ---
    try:
        if workstream.get("auto_scan") and auto_populated_count < 3:
            ws_keywords = workstream.get("keywords") or []
            ws_pillar_ids = workstream.get("pillar_ids") or []

            if ws_keywords or ws_pillar_ids:
                scan_config = {
                    "workstream_id": workstream_id,
                    "user_id": workstream.get("user_id"),
                    "keywords": ws_keywords,
                    "pillar_ids": ws_pillar_ids,
                    "horizon": workstream.get("horizon") or "ALL",
                    "triggered_by": "post_creation",
                }
                scan_queued = await _auto_queue_workstream_scan_sa(
                    db, workstream_id, user_id, scan_config
                )
    except Exception as e:
        logger.error(
            "Post-creation scan queue failed for workstream %s: %s",
            workstream_id,
            e,
        )

    return WorkstreamCreateResponse(
        id=workstream_id,
        name=workstream.get("name", ""),
        description=workstream.get("description"),
        pillar_ids=workstream.get("pillar_ids") or [],
        goal_ids=workstream.get("goal_ids") or [],
        stage_ids=workstream.get("stage_ids") or [],
        horizon=workstream.get("horizon") or "ALL",
        keywords=workstream.get("keywords") or [],
        is_active=workstream.get("is_active", True),
        auto_scan=workstream.get("auto_scan", False),
        auto_add=workstream.get("auto_add", False),
        auto_populated_count=auto_populated_count,
        program_type=workstream.get("program_type"),
        department_id=workstream.get("department_id"),
        budget=workstream.get("budget"),
        fiscal_year=workstream.get("fiscal_year"),
        category_ids=workstream.get("category_ids") or [],
        scan_queued=scan_queued,
    )


# ---------------------------------------------------------------------------
# PATCH /me/workstreams/{workstream_id}
# ---------------------------------------------------------------------------


@router.patch("/me/workstreams/{workstream_id}", response_model=Workstream)
@router.patch("/me/programs/{workstream_id}", response_model=Workstream)
async def update_workstream(
    workstream_id: str,
    workstream_data: WorkstreamUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Update an existing workstream.

    - Verifies the workstream belongs to the current user
    - Accepts partial updates (any field can be updated)
    - Returns the updated workstream
    """
    try:
        result = await db.execute(
            select(WorkstreamORM).where(WorkstreamORM.id == uuid.UUID(workstream_id))
        )
        ws_obj = result.scalar_one_or_none()
    except Exception as e:
        logger.error("Failed to fetch workstream %s: %s", workstream_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("fetching workstream", e),
        ) from e

    if ws_obj is None:
        raise HTTPException(status_code=404, detail="Workstream not found")

    # Verify ownership
    if str(ws_obj.user_id) != current_user["id"]:
        raise HTTPException(
            status_code=403, detail="Not authorized to update this workstream"
        )

    # Build update dict with only non-None values
    update_dict = {k: v for k, v in workstream_data.dict().items() if v is not None}

    if not update_dict:
        # No updates provided, return existing workstream
        return Workstream(**_row_to_dict(ws_obj))

    # Apply updates
    for field_name, value in update_dict.items():
        if field_name == "budget" and value is not None:
            setattr(ws_obj, field_name, Decimal(str(value)))
        else:
            setattr(ws_obj, field_name, value)

    ws_obj.updated_at = datetime.now(timezone.utc)

    try:
        await db.flush()
        await db.refresh(ws_obj)
    except Exception as e:
        logger.error("Failed to update workstream %s: %s", workstream_id, e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to update workstream",
        ) from e

    return Workstream(**_row_to_dict(ws_obj))


# ---------------------------------------------------------------------------
# DELETE /me/workstreams/{workstream_id}
# ---------------------------------------------------------------------------


@router.delete("/me/workstreams/{workstream_id}")
@router.delete("/me/programs/{workstream_id}")
async def delete_workstream(
    workstream_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Delete a workstream.

    - Verifies the workstream belongs to the current user
    - Permanently deletes the workstream
    """
    try:
        result = await db.execute(
            select(WorkstreamORM).where(WorkstreamORM.id == uuid.UUID(workstream_id))
        )
        ws_obj = result.scalar_one_or_none()
    except Exception as e:
        logger.error("Failed to fetch workstream %s for deletion: %s", workstream_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("fetching workstream", e),
        ) from e

    if ws_obj is None:
        raise HTTPException(status_code=404, detail="Workstream not found")

    # Verify ownership
    if str(ws_obj.user_id) != current_user["id"]:
        raise HTTPException(
            status_code=403, detail="Not authorized to delete this workstream"
        )

    try:
        await db.delete(ws_obj)
        await db.flush()
    except Exception as e:
        logger.error("Failed to delete workstream %s: %s", workstream_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("deleting workstream", e),
        ) from e

    return {"status": "deleted", "message": "Workstream successfully deleted"}


# ---------------------------------------------------------------------------
# GET /me/workstreams/{workstream_id}/feed
# ---------------------------------------------------------------------------


@router.get("/me/workstreams/{workstream_id}/feed")
@router.get("/me/programs/{workstream_id}/feed")
async def get_workstream_feed(
    workstream_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
    limit: int = 20,
    offset: int = 0,
):
    """Get cards for a workstream with filtering support.

    Filters cards based on workstream configuration:
    - pillar_ids: Filter by pillar IDs
    - goal_ids: Filter by goal IDs
    - stage_ids: Filter by stage IDs
    - horizon: Filter by horizon (H1, H2, H3, ALL)
    - keywords: Search card name/summary/description for keywords
    """
    # Verify workstream belongs to user
    try:
        ws_result = await db.execute(
            select(WorkstreamORM).where(
                WorkstreamORM.id == uuid.UUID(workstream_id),
                WorkstreamORM.user_id == uuid.UUID(current_user["id"]),
            )
        )
        ws_obj = ws_result.scalar_one_or_none()
    except Exception as e:
        logger.error("Failed to fetch workstream %s: %s", workstream_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("fetching workstream", e),
        ) from e

    if ws_obj is None:
        raise HTTPException(status_code=404, detail="Workstream not found")

    workstream = _row_to_dict(ws_obj)

    # Build query based on workstream filters
    stmt = select(CardORM).where(CardORM.status == "active")

    # Filter by pillar_ids
    if workstream.get("pillar_ids"):
        stmt = stmt.where(CardORM.pillar_id.in_(workstream["pillar_ids"]))

    # Filter by goal_ids
    if workstream.get("goal_ids"):
        stmt = stmt.where(CardORM.goal_id.in_(workstream["goal_ids"]))

    # Note: stage_ids filter applied in Python because card stage_id format
    # is "5_implementing" while workstream stores ["4", "5", "6"]

    # Filter by horizon (skip if ALL)
    if workstream.get("horizon") and workstream["horizon"] != "ALL":
        stmt = stmt.where(CardORM.horizon == workstream["horizon"])

    # Filter by pipeline_statuses (new pipeline lifecycle filter)
    if workstream.get("pipeline_statuses"):
        stmt = stmt.where(CardORM.pipeline_status.in_(workstream["pipeline_statuses"]))

    stmt = stmt.order_by(CardORM.created_at.desc()).offset(offset).limit(limit)

    try:
        card_result = await db.execute(stmt)
        card_rows = card_result.scalars().all()
    except Exception as e:
        logger.error("Failed to fetch cards for workstream %s: %s", workstream_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("fetching workstream cards", e),
        ) from e

    cards = [
        _row_to_dict(c, skip_cols={"embedding", "search_vector"}) for c in card_rows
    ]

    if stage_ids := workstream.get("stage_ids", []):
        filtered_by_stage = []
        for card in cards:
            card_stage_id = card.get("stage_id") or ""
            stage_num = (
                card_stage_id.split("_")[0] if "_" in card_stage_id else card_stage_id
            )
            if stage_num in stage_ids:
                filtered_by_stage.append(card)
        cards = filtered_by_stage

    if keywords := workstream.get("keywords", []):
        filtered_cards = []
        for card in cards:
            card_text = " ".join(
                [
                    (card.get("name") or "").lower(),
                    (card.get("summary") or "").lower(),
                    (card.get("description") or "").lower(),
                ]
            )
            # Check if any keyword matches (case-insensitive)
            if any(keyword.lower() in card_text for keyword in keywords):
                filtered_cards.append(card)
        return filtered_cards

    return cards


# ---------------------------------------------------------------------------
# POST /me/workstreams/{workstream_id}/auto-populate
# ---------------------------------------------------------------------------


@router.post(
    "/me/workstreams/{workstream_id}/auto-populate",
    response_model=AutoPopulateResponse,
)
@router.post(
    "/me/programs/{workstream_id}/auto-populate",
    response_model=AutoPopulateResponse,
)
async def auto_populate_workstream(
    workstream_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
    limit: int = Query(default=20, ge=1, le=50, description="Maximum cards to add"),
):
    """Auto-populate workstream with matching cards.

    Finds cards matching the workstream's filter criteria (pillars, goals, stages,
    horizon, keywords) that are not already in the workstream, and adds them
    to the 'inbox' column.
    """
    # Verify workstream belongs to user
    try:
        ws_result = await db.execute(
            select(WorkstreamORM).where(
                WorkstreamORM.id == uuid.UUID(workstream_id),
                WorkstreamORM.user_id == uuid.UUID(current_user["id"]),
            )
        )
        ws_obj = ws_result.scalar_one_or_none()
    except Exception as e:
        logger.error("Failed to fetch workstream %s: %s", workstream_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("fetching workstream", e),
        ) from e

    if ws_obj is None:
        raise HTTPException(status_code=404, detail="Workstream not found")

    workstream = _row_to_dict(ws_obj)

    # Get existing card IDs in workstream
    try:
        existing_result = await db.execute(
            select(WorkstreamCardORM.card_id).where(
                WorkstreamCardORM.workstream_id == uuid.UUID(workstream_id)
            )
        )
        existing_card_ids = {str(row) for row in existing_result.scalars().all()}
    except Exception as e:
        logger.error("Failed to fetch existing workstream cards: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("fetching existing workstream cards", e),
        ) from e

    # Build query based on workstream filters
    stmt = select(CardORM).where(CardORM.status == "active")

    # Apply filters
    if workstream.get("pillar_ids"):
        stmt = stmt.where(CardORM.pillar_id.in_(workstream["pillar_ids"]))

    if workstream.get("goal_ids"):
        stmt = stmt.where(CardORM.goal_id.in_(workstream["goal_ids"]))

    if workstream.get("horizon") and workstream["horizon"] != "ALL":
        stmt = stmt.where(CardORM.horizon == workstream["horizon"])

    # Filter by pipeline_statuses (new pipeline lifecycle filter)
    if workstream.get("pipeline_statuses"):
        stmt = stmt.where(CardORM.pipeline_status.in_(workstream["pipeline_statuses"]))

    # Fetch more cards than limit to account for filtering
    fetch_limit = min(limit * 3, 100)
    stmt = stmt.order_by(CardORM.created_at.desc()).limit(fetch_limit)

    try:
        card_result = await db.execute(stmt)
        card_rows = card_result.scalars().all()
    except Exception as e:
        logger.error("Failed to fetch cards for auto-populate: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("fetching cards for auto-populate", e),
        ) from e

    cards = [
        _row_to_dict(c, skip_cols={"embedding", "search_vector"}) for c in card_rows
    ]

    if stage_ids := workstream.get("stage_ids", []):
        filtered_by_stage = []
        for card in cards:
            card_stage_id = card.get("stage_id") or ""
            stage_num = (
                card_stage_id.split("_")[0] if "_" in card_stage_id else card_stage_id
            )
            if stage_num in stage_ids:
                filtered_by_stage.append(card)
        cards = filtered_by_stage

    if keywords := workstream.get("keywords", []):
        filtered_cards = []
        for card in cards:
            card_text = " ".join(
                [
                    (card.get("name") or "").lower(),
                    (card.get("summary") or "").lower(),
                    (card.get("description") or "").lower(),
                ]
            )
            if any(keyword.lower() in card_text for keyword in keywords):
                filtered_cards.append(card)
        cards = filtered_cards

    # Filter out cards already in workstream
    candidates = [c for c in cards if c["id"] not in existing_card_ids][:limit]

    if not candidates:
        return AutoPopulateResponse(added=0, cards=[])

    # Get current max position in inbox
    try:
        position_result = await db.execute(
            select(func.coalesce(func.max(WorkstreamCardORM.position), -1)).where(
                WorkstreamCardORM.workstream_id == uuid.UUID(workstream_id),
                WorkstreamCardORM.status == "inbox",
            )
        )
        start_position = (position_result.scalar() or 0) + 1
    except Exception:
        start_position = 0

    # Add cards to workstream
    now_ts = datetime.now(timezone.utc)
    new_wc_objs: list[WorkstreamCardORM] = []
    for idx, card in enumerate(candidates):
        wc = WorkstreamCardORM(
            workstream_id=uuid.UUID(workstream_id),
            card_id=uuid.UUID(card["id"]),
            added_by=uuid.UUID(current_user["id"]),
            added_at=now_ts,
            status="inbox",
            position=start_position + idx,
            added_from="auto",
            updated_at=now_ts,
        )
        db.add(wc)
        new_wc_objs.append(wc)

    try:
        await db.flush()
        for wc in new_wc_objs:
            await db.refresh(wc)
    except Exception as e:
        logger.error("Failed to auto-populate workstream %s: %s", workstream_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to auto-populate workstream",
        ) from e

    card_map = {c["id"]: c for c in candidates}
    added_cards = [
        WorkstreamCardWithDetails(
            id=str(wc.id),
            workstream_id=str(wc.workstream_id),
            card_id=str(wc.card_id),
            added_by=str(wc.added_by),
            added_at=wc.added_at,
            status=wc.status or "inbox",
            position=wc.position or 0,
            notes=wc.notes,
            reminder_at=wc.reminder_at,
            added_from=wc.added_from or "auto",
            updated_at=wc.updated_at,
            card=card_map.get(str(wc.card_id)),
        )
        for wc in new_wc_objs
    ]
    logger.info(
        "Auto-populated workstream %s with %d cards",
        workstream_id,
        len(added_cards),
    )

    return AutoPopulateResponse(added=len(added_cards), cards=added_cards)


# ---------------------------------------------------------------------------
# POST /me/workstreams/{workstream_id}/auto-scan
# ---------------------------------------------------------------------------


@router.post("/me/workstreams/{workstream_id}/auto-scan")
@router.post("/me/programs/{workstream_id}/auto-scan")
async def toggle_workstream_auto_scan(
    workstream_id: str,
    enable: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Enable or disable automatic scanning for a workstream.

    When auto_scan is enabled, the workstream will be included in periodic
    background source discovery runs.
    """
    try:
        # Verify workstream exists and belongs to user
        result = await db.execute(
            select(WorkstreamORM).where(WorkstreamORM.id == uuid.UUID(workstream_id))
        )
        ws_obj = result.scalar_one_or_none()

        if ws_obj is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workstream not found",
            )
        if str(ws_obj.user_id) != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to modify this workstream",
            )

        # Update auto_scan setting
        ws_obj.auto_scan = enable
        ws_obj.updated_at = datetime.now(timezone.utc)

        await db.flush()
        await db.refresh(ws_obj)

        return {
            "workstream_id": workstream_id,
            "auto_scan": enable,
            "status": "enabled" if enable else "disabled",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to toggle auto_scan for workstream %s: %s",
            workstream_id,
            str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("auto_scan update", e),
        ) from e
