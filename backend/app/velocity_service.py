"""
Signal Velocity Tracking Service for Foresight Application.

Calculates velocity trends for all active cards based on the rate of new
source additions over rolling time windows. Trends indicate whether a
signal is accelerating, decelerating, stable, emerging, or stale.

Algorithm:
1. For each active card, count sources added in three windows:
   - Current week  (last 7 days)
   - Previous week (8-14 days ago)
   - Two weeks ago (15-28 days, averaged per week)
2. Classify trend:
   - emerging:     < 5 total sources AND card created in last 30 days
   - stale:        no sources in last 30 days AND card older than 30 days
   - accelerating: current_week > prev_week AND current_week > 0
   - decelerating: current_week < prev_week AND prev_week > 0
   - stable:       everything else
3. Compute velocity_score = (current - prev) / max(prev, 1) * 100

Usage:
    from app.velocity_service import calculate_velocity_trends, get_velocity_summary

    result = await calculate_velocity_trends(supabase)
    summary = get_velocity_summary(card_id, supabase)
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from supabase import Client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def calculate_velocity_trends(supabase: Client) -> Dict[str, Any]:
    """
    Calculate and update velocity trends for all active cards.

    Queries source counts in rolling time windows for every active card,
    determines trend classification, and writes the result back to the
    cards table.

    Args:
        supabase: Authenticated Supabase client.

    Returns:
        Summary dict with ``updated`` and ``total`` counts.
    """
    now = datetime.now(timezone.utc)
    week_ago = (now - timedelta(days=7)).isoformat()
    two_weeks_ago = (now - timedelta(days=14)).isoformat()
    thirty_days_ago = (now - timedelta(days=30)).isoformat()

    # Fetch all active cards (only need id and created_at)
    try:
        cards_resp = (
            supabase.table("cards")
            .select("id, created_at")
            .eq("status", "active")
            .execute()
        )
    except Exception as exc:
        logger.error("Failed to fetch active cards for velocity calculation: %s", exc)
        return {"updated": 0, "total": 0, "error": str(exc)}

    cards_data = cards_resp.data or []
    if not cards_data:
        logger.info("No active cards found for velocity calculation")
        return {"updated": 0, "total": 0}

    updated = 0

    for card in cards_data:
        card_id = card["id"]
        card_created = card["created_at"]

        try:
            # Count sources in each window using the ingested_at column
            # (falls back gracefully since ingested_at defaults to NOW())

            # Current week (last 7 days)
            current_resp = (
                supabase.table("sources")
                .select("id", count="exact")
                .eq("card_id", card_id)
                .gte("ingested_at", week_ago)
                .execute()
            )
            current_count = current_resp.count or 0

            # Previous week (8-14 days ago)
            prev_resp = (
                supabase.table("sources")
                .select("id", count="exact")
                .eq("card_id", card_id)
                .gte("ingested_at", two_weeks_ago)
                .lt("ingested_at", week_ago)
                .execute()
            )
            prev_count = prev_resp.count or 0

            # Total sources for the card
            total_resp = (
                supabase.table("sources")
                .select("id", count="exact")
                .eq("card_id", card_id)
                .execute()
            )
            total_count = total_resp.count or 0

            # Any sources in last 30 days
            recent_resp = (
                supabase.table("sources")
                .select("id", count="exact")
                .eq("card_id", card_id)
                .gte("ingested_at", thirty_days_ago)
                .execute()
            )
            recent_count = recent_resp.count or 0

            # Determine card age in days
            card_age_days = _card_age_days(card_created, now)

            # Classify trend
            trend = _classify_trend(
                current_count=current_count,
                prev_count=prev_count,
                total_count=total_count,
                recent_count=recent_count,
                card_age_days=card_age_days,
            )

            # Calculate velocity score
            denominator = max(prev_count, 1)
            score = round((current_count - prev_count) / denominator * 100, 2)

            # Persist to database
            supabase.table("cards").update(
                {
                    "velocity_trend": trend,
                    "velocity_score": float(score),
                    "velocity_updated_at": now.isoformat(),
                }
            ).eq("id", card_id).execute()

            updated += 1

        except Exception as exc:
            logger.warning("Failed to update velocity for card %s: %s", card_id, exc)

    logger.info("Velocity trends updated for %d / %d cards", updated, len(cards_data))
    return {"updated": updated, "total": len(cards_data)}


def get_velocity_summary(card_id: str, supabase: Client) -> Optional[Dict[str, Any]]:
    """
    Return a human-readable velocity summary for a single card.

    Args:
        card_id: UUID of the card.
        supabase: Authenticated Supabase client.

    Returns:
        Dict with ``trend``, ``score``, ``summary`` text, and source counts,
        or ``None`` if the card is not found.
    """
    now = datetime.now(timezone.utc)
    week_ago = (now - timedelta(days=7)).isoformat()
    two_weeks_ago = (now - timedelta(days=14)).isoformat()

    try:
        card_resp = (
            supabase.table("cards")
            .select("id, velocity_trend, velocity_score, velocity_updated_at")
            .eq("id", card_id)
            .single()
            .execute()
        )
    except Exception:
        return None

    card_data = card_resp.data
    if not card_data:
        return None

    # Fetch window counts for the summary text
    try:
        current_resp = (
            supabase.table("sources")
            .select("id", count="exact")
            .eq("card_id", card_id)
            .gte("ingested_at", week_ago)
            .execute()
        )
        current_count = current_resp.count or 0

        prev_resp = (
            supabase.table("sources")
            .select("id", count="exact")
            .eq("card_id", card_id)
            .gte("ingested_at", two_weeks_ago)
            .lt("ingested_at", week_ago)
            .execute()
        )
        prev_count = prev_resp.count or 0
    except Exception:
        current_count = 0
        prev_count = 0

    trend = card_data.get("velocity_trend", "stable")
    score = card_data.get("velocity_score", 0)

    summary = _build_summary_text(trend, current_count, prev_count, score)

    return {
        "trend": trend,
        "score": score,
        "velocity_updated_at": card_data.get("velocity_updated_at"),
        "current_week_sources": current_count,
        "prev_week_sources": prev_count,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _card_age_days(created_at_str: str, now: datetime) -> int:
    """Parse a card's created_at timestamp and return age in days."""
    try:
        created = datetime.fromisoformat(created_at_str.replace("Z", "+00:00")).replace(
            tzinfo=None
        )
        return (now - created).days
    except (ValueError, AttributeError):
        # If parsing fails, assume old card
        return 999


def _classify_trend(
    *,
    current_count: int,
    prev_count: int,
    total_count: int,
    recent_count: int,
    card_age_days: int,
) -> str:
    """Determine the velocity trend label based on source counts."""
    if total_count < 5 and card_age_days < 30:
        return "emerging"
    if recent_count == 0 and card_age_days > 30:
        return "stale"
    if current_count > prev_count and current_count > 0:
        return "accelerating"
    if current_count < prev_count and prev_count > 0:
        return "decelerating"
    return "stable"


def _build_summary_text(
    trend: str, current_count: int, prev_count: int, score: float
) -> str:
    """Build a human-readable summary string for the velocity."""
    if trend == "emerging":
        return "New signal — still gathering initial sources"
    if trend == "stale":
        return "No new sources in the last 30 days"
    if current_count == 0 and prev_count == 0:
        return "No recent source activity"

    src_word_curr = "source" if current_count == 1 else "sources"
    src_word_prev = "source" if prev_count == 1 else "sources"

    base = f"{current_count} new {src_word_curr} this week vs {prev_count} {src_word_prev} last week"

    if trend == "accelerating":
        return f"{base} (+{abs(score):.0f}% velocity)"
    return f"{base} ({score:.0f}% velocity)" if trend == "decelerating" else base
