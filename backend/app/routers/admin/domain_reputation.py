"""Domain reputation endpoints -- manage domain trust/quality scores."""

import logging
import uuid as _uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, get_current_user, _safe_error
from app.chat.admin_deps import require_admin
from app.models.domain_reputation import (
    DomainReputationCreate,
    DomainReputationUpdate,
)
from app.models.db.analytics import DomainReputation
from app.routers.admin._helpers import _row_to_dict
from app import domain_reputation_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/domain-reputation")
async def list_domain_reputations(
    page: int = 1,
    page_size: int = 50,
    tier: Optional[int] = None,
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """List all domains with reputation data, paginated and filterable."""
    try:
        # Build base query
        query = select(DomainReputation)
        count_query = select(func.count()).select_from(DomainReputation)

        if tier:
            query = query.where(DomainReputation.curated_tier == tier)
            count_query = count_query.where(DomainReputation.curated_tier == tier)
        if category:
            query = query.where(DomainReputation.category == category)
            count_query = count_query.where(DomainReputation.category == category)

        query = query.order_by(DomainReputation.composite_score.desc())
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        # Execute both queries
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        items_result = await db.execute(query)
        items = [_row_to_dict(r) for r in items_result.scalars().all()]

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    except Exception as e:
        logger.error(f"Failed to list domain reputations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("domain reputations listing", e),
        ) from e


@router.get("/domain-reputation/{domain_id}")
async def get_domain_reputation(
    domain_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get single domain reputation detail."""
    try:
        dom_uuid = _uuid.UUID(domain_id)
        result = await db.execute(
            select(DomainReputation).where(DomainReputation.id == dom_uuid)
        )
        domain = result.scalar_one_or_none()
        if not domain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Domain reputation not found",
            )
        return _row_to_dict(domain)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get domain reputation {domain_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_safe_error("domain reputation lookup", e),
        ) from e


@router.post("/admin/domain-reputation")
async def create_domain_reputation(
    body: DomainReputationCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_admin),
):
    """Add a new domain to the reputation system. Admin only."""
    try:
        data = body.model_dump()
        # Calculate initial composite score based on tier
        tier_scores = {1: 85, 2: 60, 3: 35}
        tier_score = tier_scores.get(data.get("curated_tier"), 20)
        composite = tier_score * 0.50 + data.get("texas_relevance_bonus", 0)

        domain_rep = DomainReputation(
            domain_pattern=data["domain_pattern"],
            organization_name=data["organization_name"],
            category=data["category"],
            curated_tier=data.get("curated_tier"),
            texas_relevance_bonus=data.get("texas_relevance_bonus", 0),
            notes=data.get("notes"),
            composite_score=composite,
        )
        db.add(domain_rep)
        await db.flush()
        await db.refresh(domain_rep)

        return _row_to_dict(domain_rep)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create domain reputation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("domain reputation creation", e),
        ) from e


@router.patch("/admin/domain-reputation/{domain_id}")
async def update_domain_reputation(
    domain_id: str,
    body: DomainReputationUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_admin),
):
    """Update a domain's tier, category, or other fields. Admin only."""
    try:
        data = body.model_dump(exclude_none=True)
        if not data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields provided for update",
            )

        dom_uuid = _uuid.UUID(domain_id)
        result = await db.execute(
            select(DomainReputation).where(DomainReputation.id == dom_uuid)
        )
        domain_rep = result.scalar_one_or_none()
        if not domain_rep:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Domain reputation not found",
            )

        for key, value in data.items():
            setattr(domain_rep, key, value)

        await db.flush()
        await db.refresh(domain_rep)

        return _row_to_dict(domain_rep)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update domain reputation {domain_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("domain reputation update", e),
        ) from e


@router.delete("/admin/domain-reputation/{domain_id}")
async def delete_domain_reputation(
    domain_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_admin),
):
    """Remove a domain from the reputation system. Admin only."""
    try:
        dom_uuid = _uuid.UUID(domain_id)
        await db.execute(
            delete(DomainReputation).where(DomainReputation.id == dom_uuid)
        )
        await db.flush()
        return {"status": "deleted"}
    except Exception as e:
        logger.error(f"Failed to delete domain reputation {domain_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("domain reputation deletion", e),
        ) from e


@router.post("/admin/domain-reputation/recalculate")
async def recalculate_domain_reputations(
    db: AsyncSession = Depends(get_db),
    user=Depends(require_admin),
):
    """Recalculate all composite scores from user ratings + pipeline stats."""
    try:
        return await domain_reputation_service.recalculate_all(db)
    except Exception as e:
        logger.error(f"Failed to recalculate domain reputations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("domain reputations recalculation", e),
        ) from e
