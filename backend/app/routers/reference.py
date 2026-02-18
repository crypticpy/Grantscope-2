"""Reference data router — departments, pillars, categories, priorities."""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.models.db.reference import Department, Pillar, GrantCategory, Priority

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/reference", tags=["reference"])


@router.get("/departments")
async def list_departments(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Department).where(Department.is_active == True).order_by(Department.name)
    )
    return [
        {
            "id": d.id,
            "name": d.name,
            "abbreviation": d.abbreviation,
            "category_ids": d.category_ids or [],
        }
        for d in result.scalars()
    ]


@router.get("/pillars")
async def list_pillars(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Pillar).order_by(Pillar.id))
    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "code": p.code,
            "color": p.color,
        }
        for p in result.scalars()
    ]


@router.get("/grant-categories")
async def list_grant_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(GrantCategory).order_by(GrantCategory.name))
    return [
        {
            "id": c.id,
            "name": c.name,
            "description": c.description,
            "color": c.color,
            "icon": c.icon,
        }
        for c in result.scalars()
    ]


@router.get("/priorities")
async def list_priorities(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Priority).order_by(Priority.name))
    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "category": p.category,
        }
        for p in result.scalars()
    ]
