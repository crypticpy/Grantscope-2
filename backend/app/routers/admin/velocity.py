"""Velocity calculation endpoint -- admin-only trigger for velocity trends."""

import asyncio
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.chat.admin_deps import require_admin

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/admin/velocity/calculate")
async def trigger_velocity_calculation(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Trigger velocity trend calculation for all active cards. Runs in background."""
    from app.velocity_service import calculate_velocity_trends
    from app.database import async_session_factory

    async def _run_velocity():
        try:
            async with async_session_factory() as bg_session:
                try:
                    result = await calculate_velocity_trends(bg_session)
                    await bg_session.commit()
                    logger.info("On-demand velocity calculation completed: %s", result)
                except Exception:
                    await bg_session.rollback()
                    raise
        except Exception as exc:
            logger.exception("On-demand velocity calculation failed: %s", exc)

    asyncio.create_task(_run_velocity())
    return {
        "status": "started",
        "message": "Velocity calculation is running in the background.",
    }
