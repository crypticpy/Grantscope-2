"""Taxonomy endpoints -- public reference data + admin CRUD for pillars,
goals, anchors, stages, priorities, grant categories, and departments."""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, _safe_error
from app.chat.admin_deps import require_admin
from app.models.db.reference import (
    Pillar,
    Goal,
    Anchor,
    Stage,
    Priority,
    GrantCategory,
    Department,
)
from app.routers.admin._helpers import _row_to_dict

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic request schemas
# ---------------------------------------------------------------------------


# -- Pillars ----------------------------------------------------------------


class PillarCreate(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    color: Optional[str] = None
    code: Optional[str] = None


class PillarUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    code: Optional[str] = None


# -- Goals ------------------------------------------------------------------


class GoalCreate(BaseModel):
    id: str
    pillar_id: str
    name: str
    description: Optional[str] = None
    code: Optional[str] = None
    sort_order: Optional[int] = None


class GoalUpdate(BaseModel):
    pillar_id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    code: Optional[str] = None
    sort_order: Optional[int] = None


# -- Anchors ----------------------------------------------------------------


class AnchorCreate(BaseModel):
    name: str
    description: Optional[str] = None
    color: Optional[str] = None


class AnchorUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None


# -- Stages -----------------------------------------------------------------


class StageCreate(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    sort_order: Optional[int] = None
    horizon: Optional[str] = None


class StageUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None
    horizon: Optional[str] = None


# -- Priorities -------------------------------------------------------------


class PriorityCreate(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None


class PriorityUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None


# -- Grant Categories -------------------------------------------------------


class GrantCategoryCreate(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None


class GrantCategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None


# -- Departments ------------------------------------------------------------


class DepartmentCreate(BaseModel):
    id: str
    name: str
    abbreviation: str
    category_ids: Optional[list[str]] = None
    is_active: Optional[bool] = True


class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    abbreviation: Optional[str] = None
    category_ids: Optional[list[str]] = None
    is_active: Optional[bool] = None


# ---------------------------------------------------------------------------
# Read-all endpoint (existing)
# ---------------------------------------------------------------------------


@router.get("/taxonomy")
async def get_taxonomy(db: AsyncSession = Depends(get_db)):
    """Get all taxonomy data"""
    try:
        pillars_q = await db.execute(select(Pillar).order_by(Pillar.name))
        goals_q = await db.execute(
            select(Goal).order_by(Goal.pillar_id, Goal.sort_order)
        )
        anchors_q = await db.execute(select(Anchor).order_by(Anchor.name))
        stages_q = await db.execute(select(Stage).order_by(Stage.sort_order))
        priorities_q = await db.execute(select(Priority).order_by(Priority.name))
        categories_q = await db.execute(
            select(GrantCategory).order_by(GrantCategory.name)
        )
        departments_q = await db.execute(select(Department).order_by(Department.name))

        return {
            "pillars": [_row_to_dict(p) for p in pillars_q.scalars().all()],
            "goals": [_row_to_dict(g) for g in goals_q.scalars().all()],
            "anchors": [_row_to_dict(a) for a in anchors_q.scalars().all()],
            "stages": [_row_to_dict(s) for s in stages_q.scalars().all()],
            "priorities": [_row_to_dict(p) for p in priorities_q.scalars().all()],
            "categories": [_row_to_dict(c) for c in categories_q.scalars().all()],
            "departments": [_row_to_dict(d) for d in departments_q.scalars().all()],
        }
    except Exception as e:
        logger.error("Failed to fetch taxonomy: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("taxonomy retrieval", e),
        ) from e


# ---------------------------------------------------------------------------
# Pillar CRUD
# ---------------------------------------------------------------------------


@router.post("/admin/taxonomy/pillars", status_code=status.HTTP_201_CREATED)
async def create_pillar(
    body: PillarCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Create a new strategic pillar."""
    try:
        existing = await db.get(Pillar, body.id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Pillar '{body.id}' already exists",
            )
        pillar = Pillar(**body.model_dump())
        db.add(pillar)
        await db.flush()
        await db.refresh(pillar)
        return _row_to_dict(pillar)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create pillar: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("pillar creation", e),
        ) from e


@router.patch("/admin/taxonomy/pillars/{pillar_id}")
async def update_pillar(
    pillar_id: str,
    body: PillarUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Update an existing pillar."""
    try:
        pillar = await db.get(Pillar, pillar_id)
        if not pillar:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pillar '{pillar_id}' not found",
            )
        updates = body.model_dump(exclude_unset=True)
        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update",
            )
        for key, value in updates.items():
            setattr(pillar, key, value)
        await db.flush()
        await db.refresh(pillar)
        return _row_to_dict(pillar)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update pillar %s: %s", pillar_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("pillar update", e),
        ) from e


@router.delete("/admin/taxonomy/pillars/{pillar_id}")
async def delete_pillar(
    pillar_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Delete a pillar."""
    try:
        pillar = await db.get(Pillar, pillar_id)
        if not pillar:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pillar '{pillar_id}' not found",
            )
        await db.delete(pillar)
        await db.flush()
        return {"status": "deleted"}
    except HTTPException:
        raise
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete this pillar: it is referenced by other records. Remove or reassign dependent items first.",
        )
    except Exception as e:
        logger.error("Failed to delete pillar %s: %s", pillar_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("pillar deletion", e),
        ) from e


# ---------------------------------------------------------------------------
# Goal CRUD
# ---------------------------------------------------------------------------


@router.post("/admin/taxonomy/goals", status_code=status.HTTP_201_CREATED)
async def create_goal(
    body: GoalCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Create a new goal."""
    try:
        existing = await db.get(Goal, body.id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Goal '{body.id}' already exists",
            )
        goal = Goal(**body.model_dump())
        db.add(goal)
        await db.flush()
        await db.refresh(goal)
        return _row_to_dict(goal)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create goal: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("goal creation", e),
        ) from e


@router.patch("/admin/taxonomy/goals/{goal_id}")
async def update_goal(
    goal_id: str,
    body: GoalUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Update an existing goal."""
    try:
        goal = await db.get(Goal, goal_id)
        if not goal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Goal '{goal_id}' not found",
            )
        updates = body.model_dump(exclude_unset=True)
        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update",
            )
        for key, value in updates.items():
            setattr(goal, key, value)
        await db.flush()
        await db.refresh(goal)
        return _row_to_dict(goal)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update goal %s: %s", goal_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("goal update", e),
        ) from e


@router.delete("/admin/taxonomy/goals/{goal_id}")
async def delete_goal(
    goal_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Delete a goal."""
    try:
        goal = await db.get(Goal, goal_id)
        if not goal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Goal '{goal_id}' not found",
            )
        await db.delete(goal)
        await db.flush()
        return {"status": "deleted"}
    except HTTPException:
        raise
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete this goal: it is referenced by other records. Remove or reassign dependent items first.",
        )
    except Exception as e:
        logger.error("Failed to delete goal %s: %s", goal_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("goal deletion", e),
        ) from e


# ---------------------------------------------------------------------------
# Anchor CRUD
# ---------------------------------------------------------------------------


@router.post("/admin/taxonomy/anchors", status_code=status.HTTP_201_CREATED)
async def create_anchor(
    body: AnchorCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Create a new anchor (UUID auto-generated)."""
    try:
        anchor = Anchor(**body.model_dump())
        db.add(anchor)
        await db.flush()
        await db.refresh(anchor)
        return _row_to_dict(anchor)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create anchor: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("anchor creation", e),
        ) from e


@router.patch("/admin/taxonomy/anchors/{anchor_id}")
async def update_anchor(
    anchor_id: UUID,
    body: AnchorUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Update an existing anchor."""
    try:
        anchor = await db.get(Anchor, anchor_id)
        if not anchor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Anchor '{anchor_id}' not found",
            )
        updates = body.model_dump(exclude_unset=True)
        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update",
            )
        for key, value in updates.items():
            setattr(anchor, key, value)
        await db.flush()
        await db.refresh(anchor)
        return _row_to_dict(anchor)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update anchor %s: %s", anchor_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("anchor update", e),
        ) from e


@router.delete("/admin/taxonomy/anchors/{anchor_id}")
async def delete_anchor(
    anchor_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Delete an anchor."""
    try:
        anchor = await db.get(Anchor, anchor_id)
        if not anchor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Anchor '{anchor_id}' not found",
            )
        await db.delete(anchor)
        await db.flush()
        return {"status": "deleted"}
    except HTTPException:
        raise
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete this anchor: it is referenced by other records. Remove or reassign dependent items first.",
        )
    except Exception as e:
        logger.error("Failed to delete anchor %s: %s", anchor_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("anchor deletion", e),
        ) from e


# ---------------------------------------------------------------------------
# Stage CRUD
# ---------------------------------------------------------------------------


@router.post("/admin/taxonomy/stages", status_code=status.HTTP_201_CREATED)
async def create_stage(
    body: StageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Create a new maturity stage."""
    try:
        existing = await db.get(Stage, body.id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Stage '{body.id}' already exists",
            )
        stage = Stage(**body.model_dump())
        db.add(stage)
        await db.flush()
        await db.refresh(stage)
        return _row_to_dict(stage)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create stage: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("stage creation", e),
        ) from e


@router.patch("/admin/taxonomy/stages/{stage_id}")
async def update_stage(
    stage_id: int,
    body: StageUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Update an existing stage."""
    try:
        stage = await db.get(Stage, stage_id)
        if not stage:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Stage '{stage_id}' not found",
            )
        updates = body.model_dump(exclude_unset=True)
        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update",
            )
        for key, value in updates.items():
            setattr(stage, key, value)
        await db.flush()
        await db.refresh(stage)
        return _row_to_dict(stage)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update stage %s: %s", stage_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("stage update", e),
        ) from e


@router.delete("/admin/taxonomy/stages/{stage_id}")
async def delete_stage(
    stage_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Delete a stage."""
    try:
        stage = await db.get(Stage, stage_id)
        if not stage:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Stage '{stage_id}' not found",
            )
        await db.delete(stage)
        await db.flush()
        return {"status": "deleted"}
    except HTTPException:
        raise
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete this stage: it is referenced by other records. Remove or reassign dependent items first.",
        )
    except Exception as e:
        logger.error("Failed to delete stage %s: %s", stage_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("stage deletion", e),
        ) from e


# ---------------------------------------------------------------------------
# Priority CRUD
# ---------------------------------------------------------------------------


@router.post("/admin/taxonomy/priorities", status_code=status.HTTP_201_CREATED)
async def create_priority(
    body: PriorityCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Create a new priority."""
    try:
        existing = await db.get(Priority, body.id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Priority '{body.id}' already exists",
            )
        priority = Priority(**body.model_dump())
        db.add(priority)
        await db.flush()
        await db.refresh(priority)
        return _row_to_dict(priority)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create priority: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("priority creation", e),
        ) from e


@router.patch("/admin/taxonomy/priorities/{priority_id}")
async def update_priority(
    priority_id: str,
    body: PriorityUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Update an existing priority."""
    try:
        priority = await db.get(Priority, priority_id)
        if not priority:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Priority '{priority_id}' not found",
            )
        updates = body.model_dump(exclude_unset=True)
        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update",
            )
        for key, value in updates.items():
            setattr(priority, key, value)
        await db.flush()
        await db.refresh(priority)
        return _row_to_dict(priority)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update priority %s: %s", priority_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("priority update", e),
        ) from e


@router.delete("/admin/taxonomy/priorities/{priority_id}")
async def delete_priority(
    priority_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Delete a priority."""
    try:
        priority = await db.get(Priority, priority_id)
        if not priority:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Priority '{priority_id}' not found",
            )
        await db.delete(priority)
        await db.flush()
        return {"status": "deleted"}
    except HTTPException:
        raise
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete this priority: it is referenced by other records. Remove or reassign dependent items first.",
        )
    except Exception as e:
        logger.error("Failed to delete priority %s: %s", priority_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("priority deletion", e),
        ) from e


# ---------------------------------------------------------------------------
# Grant Category CRUD
# ---------------------------------------------------------------------------


@router.post("/admin/taxonomy/categories", status_code=status.HTTP_201_CREATED)
async def create_category(
    body: GrantCategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Create a new grant category."""
    try:
        existing = await db.get(GrantCategory, body.id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Grant category '{body.id}' already exists",
            )
        category = GrantCategory(**body.model_dump())
        db.add(category)
        await db.flush()
        await db.refresh(category)
        return _row_to_dict(category)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create grant category: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("grant category creation", e),
        ) from e


@router.patch("/admin/taxonomy/categories/{category_id}")
async def update_category(
    category_id: str,
    body: GrantCategoryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Update an existing grant category."""
    try:
        category = await db.get(GrantCategory, category_id)
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Grant category '{category_id}' not found",
            )
        updates = body.model_dump(exclude_unset=True)
        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update",
            )
        for key, value in updates.items():
            setattr(category, key, value)
        await db.flush()
        await db.refresh(category)
        return _row_to_dict(category)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update grant category %s: %s", category_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("grant category update", e),
        ) from e


@router.delete("/admin/taxonomy/categories/{category_id}")
async def delete_category(
    category_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Delete a grant category."""
    try:
        category = await db.get(GrantCategory, category_id)
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Grant category '{category_id}' not found",
            )
        await db.delete(category)
        await db.flush()
        return {"status": "deleted"}
    except HTTPException:
        raise
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete this category: it is referenced by other records. Remove or reassign dependent items first.",
        )
    except Exception as e:
        logger.error("Failed to delete grant category %s: %s", category_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("grant category deletion", e),
        ) from e


# ---------------------------------------------------------------------------
# Department CRUD
# ---------------------------------------------------------------------------


@router.post("/admin/taxonomy/departments", status_code=status.HTTP_201_CREATED)
async def create_department(
    body: DepartmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Create a new department."""
    try:
        existing = await db.get(Department, body.id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Department '{body.id}' already exists",
            )
        department = Department(**body.model_dump())
        db.add(department)
        await db.flush()
        await db.refresh(department)
        return _row_to_dict(department)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create department: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("department creation", e),
        ) from e


@router.patch("/admin/taxonomy/departments/{department_id}")
async def update_department(
    department_id: str,
    body: DepartmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Update an existing department."""
    try:
        department = await db.get(Department, department_id)
        if not department:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Department '{department_id}' not found",
            )
        updates = body.model_dump(exclude_unset=True)
        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update",
            )
        for key, value in updates.items():
            setattr(department, key, value)
        await db.flush()
        await db.refresh(department)
        return _row_to_dict(department)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update department %s: %s", department_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("department update", e),
        ) from e


@router.delete("/admin/taxonomy/departments/{department_id}")
async def delete_department(
    department_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Soft-delete a department (set is_active=False)."""
    try:
        department = await db.get(Department, department_id)
        if not department:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Department '{department_id}' not found",
            )
        department.is_active = False
        await db.flush()
        await db.refresh(department)
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete department %s: %s", department_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("department deletion", e),
        ) from e
