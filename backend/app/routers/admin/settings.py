"""System settings CRUD endpoints -- admin-only configuration management."""

import logging
import uuid as _uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, get_current_user_hardcoded, _safe_error
from app.chat.admin_deps import require_admin
from app.models.db.system_settings import SystemSetting

logger = logging.getLogger(__name__)
router = APIRouter()

# Setting keys that non-admin users are allowed to read
PUBLIC_SETTING_KEYS = {"online_search_enabled"}


class SettingUpdate(BaseModel):
    """Request body for updating a system setting."""

    value: Any
    description: str | None = None


@router.get("/admin/settings")
async def list_settings(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """List all system settings. Admin only."""
    try:
        result = await db.execute(select(SystemSetting).order_by(SystemSetting.key))
        settings = result.scalars().all()
        return [
            {
                "key": s.key,
                "value": s.value,
                "description": s.description,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            }
            for s in settings
        ]
    except Exception as e:
        logger.error(f"Failed to list system settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("system settings retrieval", e),
        ) from e


@router.get("/admin/settings/{key}")
async def get_setting(
    key: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Get a single setting value.

    Non-admin users may only read keys listed in PUBLIC_SETTING_KEYS.
    """
    user_role = current_user.get("role", "")
    if user_role not in ("admin", "service_role") and key not in PUBLIC_SETTING_KEYS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Setting '{key}' not found",
        )
    try:
        result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
        setting = result.scalar_one_or_none()
        if not setting:
            raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")
        return {
            "key": setting.key,
            "value": setting.value,
            "description": setting.description,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get setting '{key}': {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("system setting retrieval", e),
        ) from e


@router.put("/admin/settings/{key}")
async def update_setting(
    key: str,
    body: SettingUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Update a system setting value. Admin only."""
    result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
    setting = result.scalar_one_or_none()
    if not setting:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")

    setting.value = body.value
    if body.description is not None:
        setting.description = body.description
    setting.updated_by = _uuid.UUID(str(current_user["id"]))
    setting.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(setting)

    return {
        "key": setting.key,
        "value": setting.value,
        "description": setting.description,
    }
