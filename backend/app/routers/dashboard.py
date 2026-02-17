"""Dashboard router -- consolidated endpoint for the main dashboard view.

Returns all dashboard data (stats, quality distribution, recent cards,
followed cards, upcoming deadlines) in a single API call to eliminate
the waterfall of individual requests the frontend previously made.
"""

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, get_current_user_hardcoded, _safe_error
from app.models.db.card import Card
from app.models.db.card_extras import CardFollow
from app.models.db.workstream import Workstream

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/me", tags=["dashboard"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Columns to skip when serializing Card rows -- they contain types that
# are not JSON-serializable and are not useful in the API response.
_SKIP_COLUMNS = {"embedding", "search_vector"}


def _card_to_dict(card: Card) -> dict[str, Any]:
    """Convert a Card ORM instance to a JSON-safe dictionary.

    Handles UUID -> str, datetime -> ISO string, and Decimal -> float
    conversions so the result can be returned directly from a FastAPI
    endpoint.
    """
    result: dict[str, Any] = {}
    for col in Card.__table__.columns:
        if col.name in _SKIP_COLUMNS:
            continue
        value = getattr(card, col.name, None)
        if value is None:
            result[col.name] = None
        elif isinstance(value, uuid.UUID):
            result[col.name] = str(value)
        elif isinstance(value, datetime):
            result[col.name] = value.isoformat()
        elif isinstance(value, date):
            result[col.name] = value.isoformat()
        elif isinstance(value, Decimal):
            result[col.name] = float(value)
        else:
            result[col.name] = value
    return result


# ---------------------------------------------------------------------------
# GET /api/v1/me/dashboard
# ---------------------------------------------------------------------------


@router.get("/dashboard")
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Return consolidated dashboard data for the authenticated user.

    Combines stats, quality distribution, recent cards, followed cards,
    and upcoming deadlines into a single response to minimise round-trips.
    """
    user_id = current_user["id"]
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    today = now.date()
    week_later = today + timedelta(days=7)

    try:
        # ── 1. Aggregate stats ────────────────────────────────────────────

        # total_cards: active cards
        total_cards_q = await db.execute(
            select(func.count(Card.id)).where(Card.status == "active")
        )
        total_cards: int = total_cards_q.scalar() or 0

        # new_this_week: active cards created in the last 7 days
        new_this_week_q = await db.execute(
            select(func.count(Card.id)).where(
                Card.status == "active",
                Card.created_at >= week_ago,
            )
        )
        new_this_week: int = new_this_week_q.scalar() or 0

        # following: card_follows for this user
        following_q = await db.execute(
            select(func.count(CardFollow.id)).where(
                CardFollow.user_id == user_id,
            )
        )
        following: int = following_q.scalar() or 0

        # workstreams: owned by this user
        workstreams_q = await db.execute(
            select(func.count(Workstream.id)).where(
                Workstream.user_id == user_id,
            )
        )
        workstreams_count: int = workstreams_q.scalar() or 0

        # deadlines_this_week: active cards with deadline in [today, today+7]
        deadlines_this_week_q = await db.execute(
            select(func.count(Card.id)).where(
                Card.status == "active",
                Card.deadline >= now,
                Card.deadline
                <= datetime(
                    week_later.year,
                    week_later.month,
                    week_later.day,
                    23,
                    59,
                    59,
                    tzinfo=timezone.utc,
                ),
            )
        )
        deadlines_this_week: int = deadlines_this_week_q.scalar() or 0

        # pipeline_value: SUM of AVG(funding_amount_min, funding_amount_max)
        # for active cards that have funding_amount_min set.
        pipeline_value_q = await db.execute(
            select(
                func.coalesce(
                    func.sum(
                        (
                            func.coalesce(Card.funding_amount_min, 0)
                            + func.coalesce(Card.funding_amount_max, 0)
                        )
                        / 2
                    ),
                    0,
                )
            ).where(
                Card.status == "active",
                Card.funding_amount_min.isnot(None),
            )
        )
        pipeline_value_raw = pipeline_value_q.scalar() or 0
        pipeline_value: float = float(pipeline_value_raw)

        # pending_review: cards discovered/pending_review or draft, excluding rejected
        pending_review_q = await db.execute(
            select(func.count(Card.id)).where(
                or_(
                    Card.review_status.in_(["discovered", "pending_review"]),
                    Card.status == "draft",
                ),
                Card.review_status != "rejected",
            )
        )
        pending_review: int = pending_review_q.scalar() or 0

        stats = {
            "total_cards": total_cards,
            "new_this_week": new_this_week,
            "following": following,
            "workstreams": workstreams_count,
            "deadlines_this_week": deadlines_this_week,
            "pipeline_value": pipeline_value,
            "pending_review": pending_review,
        }

        # ── 2. Quality distribution ───────────────────────────────────────
        quality_q = await db.execute(
            select(
                func.count(
                    case(
                        (Card.signal_quality_score >= 75, Card.id),
                    )
                ).label("high"),
                func.count(
                    case(
                        (
                            and_(
                                Card.signal_quality_score >= 50,
                                Card.signal_quality_score < 75,
                            ),
                            Card.id,
                        ),
                    )
                ).label("moderate"),
                func.count(
                    case(
                        (
                            or_(
                                Card.signal_quality_score < 50,
                                Card.signal_quality_score.is_(None),
                            ),
                            Card.id,
                        ),
                    )
                ).label("low"),
            ).where(Card.status == "active")
        )
        quality_row = quality_q.one()
        quality_distribution = {
            "high": quality_row.high,
            "moderate": quality_row.moderate,
            "low": quality_row.low,
        }

        # ── 3. Recent cards (6 most recent active) ────────────────────────
        recent_q = await db.execute(
            select(Card)
            .where(Card.status == "active")
            .order_by(Card.created_at.desc())
            .limit(6)
        )
        recent_cards = [_card_to_dict(c) for c in recent_q.scalars().all()]

        # ── 4. Following cards with priority ──────────────────────────────
        following_cards_q = await db.execute(
            select(CardFollow, Card)
            .join(Card, CardFollow.card_id == Card.id)
            .where(CardFollow.user_id == user_id)
            .order_by(CardFollow.created_at.desc())
        )
        following_cards = []
        for follow, card in following_cards_q.all():
            card_dict = _card_to_dict(card)
            card_dict["follow_id"] = str(follow.id)
            card_dict["follow_priority"] = follow.priority
            following_cards.append(card_dict)

        # ── 5. Upcoming deadlines (5 nearest) ────────────────────────────
        deadlines_q = await db.execute(
            select(Card)
            .where(
                Card.status == "active",
                Card.deadline >= now,
            )
            .order_by(Card.deadline.asc())
            .limit(5)
        )
        upcoming_deadlines = [_card_to_dict(c) for c in deadlines_q.scalars().all()]

        return {
            "stats": stats,
            "quality_distribution": quality_distribution,
            "recent_cards": recent_cards,
            "following_cards": following_cards,
            "upcoming_deadlines": upcoming_deadlines,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Dashboard query failed for user %s: %s", user_id, e)
        # Return sensible defaults so the frontend can still render
        return {
            "stats": {
                "total_cards": 0,
                "new_this_week": 0,
                "following": 0,
                "workstreams": 0,
                "deadlines_this_week": 0,
                "pipeline_value": 0,
                "pending_review": 0,
            },
            "quality_distribution": {"high": 0, "moderate": 0, "low": 0},
            "recent_cards": [],
            "following_cards": [],
            "upcoming_deadlines": [],
        }
