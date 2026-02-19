"""
Signal Quality Score computation for GrantScope cards.

Computes a 0-100 quality score based on data completeness and research depth.
The score reflects how well-sourced, researched, and validated a card is.

Scoring Components (weighted):
  - Source Count (15%): Number of sources linked to the card
  - Source Diversity (10%): Variety of source types and domains
  - Avg Credibility (15%): Average credibility rating from discovered sources
  - Avg Triage Confidence (10%): Average AI triage confidence
  - Deep Research (15%): Whether deep research has been performed
  - Research Tasks (10%): Number of completed research tasks
  - Entity Count (5%): Number of entities extracted
  - Human Review (10%): Whether the card has been reviewed by a human
  - Engagement (10%): Follows and workstream membership
"""

import logging
from typing import Optional

from sqlalchemy import select, update as sa_update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.card import Card
from app.models.db.source import Source, DiscoveredSource
from app.models.db.research import ResearchTask
from app.models.db.card_extras import Entity, CardFollow
from app.models.db.workstream import WorkstreamCard
from app.helpers.settings_reader import get_setting

logger = logging.getLogger(__name__)

# Default SQI component weights
DEFAULT_SQI_WEIGHTS: dict[str, float] = {
    "source_count": 0.15,
    "source_diversity": 0.10,
    "avg_credibility": 0.15,
    "avg_triage_confidence": 0.10,
    "deep_research": 0.15,
    "research_tasks": 0.10,
    "entity_count": 0.05,
    "human_review": 0.10,
    "engagement": 0.10,
}


def _score_source_count(count: int) -> int:
    """Score based on number of sources. 0=0, 1-2=30, 3-5=60, 6-10=80, 10+=100."""
    if count == 0:
        return 0
    elif count <= 2:
        return 30
    elif count <= 5:
        return 60
    elif count <= 10:
        return 80
    else:
        return 100


def _score_source_diversity(unique_types: int, unique_domains: int) -> int:
    """Score based on diversity of source types and domains. Capped at 100."""
    type_score = min((unique_types / 5) * 50, 50)
    domain_score = min((unique_domains / 10) * 50, 50)
    return min(int(type_score + domain_score), 100)


def _score_avg_credibility(avg_credibility: Optional[float]) -> int:
    """Score based on average credibility (1.0-5.0 scale). ((avg-1)/4)*100."""
    if avg_credibility is None:
        return 0
    return int(((avg_credibility - 1.0) / 4.0) * 100)


def _score_avg_triage_confidence(avg_confidence: Optional[float]) -> int:
    """Score based on average triage confidence (0-1 scale). avg*100."""
    return 0 if avg_confidence is None else int(avg_confidence * 100)


def _score_deep_research(has_deep_research: bool) -> int:
    """Score based on whether deep research has been performed. 0 or 100."""
    return 100 if has_deep_research else 0


def _score_research_tasks(completed_count: int) -> int:
    """Score based on completed research tasks. 0=0, 1=40, 2=70, 3+=100."""
    if completed_count == 0:
        return 0
    elif completed_count == 1:
        return 40
    elif completed_count == 2:
        return 70
    else:
        return 100


def _score_entity_count(count: int) -> int:
    """Score based on entity count. 0=0, 1-3=40, 4-8=70, 8+=100."""
    if count == 0:
        return 0
    elif count <= 3:
        return 40
    elif count <= 8:
        return 70
    else:
        return 100


def _score_human_review(has_review: bool) -> int:
    """Score based on whether the card has been reviewed. 0 or 100."""
    return 100 if has_review else 0


def _score_engagement(total_engagement: int) -> int:
    """Score based on follows + workstream memberships. 0=0, 1-2=40, 3-5=70, 5+=100."""
    if total_engagement == 0:
        return 0
    elif total_engagement <= 2:
        return 40
    elif total_engagement <= 5:
        return 70
    else:
        return 100


async def compute_signal_quality_score(db: AsyncSession, card_id: str) -> dict:
    """
    Compute signal quality score and component breakdown for a card.

    Args:
        db: AsyncSession instance
        card_id: UUID of the card to score

    Returns:
        dict with "score" (int 0-100) and "breakdown" (dict of component details)
    """
    # Read admin-configurable SQI weights (cached, 60s TTL)
    admin_weights = await get_setting(db, "signal_quality_weights", None)
    weights: dict[str, float] = dict(DEFAULT_SQI_WEIGHTS)
    if isinstance(admin_weights, dict):
        for key in weights:
            if key in admin_weights:
                try:
                    weights[key] = float(admin_weights[key])
                except (ValueError, TypeError):
                    pass

    breakdown = {}

    # 1. Source Count - from sources table
    try:
        sources_result = await db.execute(
            select(func.count(Source.id)).where(Source.card_id == card_id)
        )
        source_count = sources_result.scalar() or 0
    except Exception as e:
        logger.warning(f"Failed to fetch source count for card {card_id}: {e}")
        source_count = 0

    source_count_score = _score_source_count(source_count)
    breakdown["source_count"] = {
        "score": source_count_score,
        "weight": weights["source_count"],
        "raw_value": source_count,
    }

    # 2. Source Diversity (10%) - from discovered_sources: distinct source_type + distinct domain
    try:
        diversity_result = await db.execute(
            select(DiscoveredSource.source_type, DiscoveredSource.domain).where(
                DiscoveredSource.resulting_card_id == card_id
            )
        )
        diversity_data = diversity_result.all()

        unique_types = len(
            {row.source_type for row in diversity_data if row.source_type}
        )
        unique_domains = len({row.domain for row in diversity_data if row.domain})
    except Exception as e:
        logger.warning(f"Failed to fetch source diversity for card {card_id}: {e}")
        unique_types = 0
        unique_domains = 0

    diversity_score = _score_source_diversity(unique_types, unique_domains)
    breakdown["source_diversity"] = {
        "score": diversity_score,
        "weight": weights["source_diversity"],
        "raw_value": {"unique_types": unique_types, "unique_domains": unique_domains},
    }

    # 3. Avg Credibility (15%) - from discovered_sources.analysis_credibility (1.0-5.0)
    try:
        credibility_result = await db.execute(
            select(DiscoveredSource.analysis_credibility).where(
                DiscoveredSource.resulting_card_id == card_id,
                DiscoveredSource.analysis_credibility.isnot(None),
            )
        )
        credibility_data = credibility_result.scalars().all()
        if credibility_data:
            avg_credibility = sum(credibility_data) / len(credibility_data)
        else:
            avg_credibility = None
    except Exception as e:
        logger.warning(f"Failed to fetch avg credibility for card {card_id}: {e}")
        avg_credibility = None

    credibility_score = _score_avg_credibility(avg_credibility)
    breakdown["avg_credibility"] = {
        "score": credibility_score,
        "weight": weights["avg_credibility"],
        "raw_value": round(avg_credibility, 2) if avg_credibility is not None else None,
    }

    # 4. Avg Triage Confidence (10%) - from discovered_sources.triage_confidence (0-1)
    try:
        triage_result = await db.execute(
            select(DiscoveredSource.triage_confidence).where(
                DiscoveredSource.resulting_card_id == card_id,
                DiscoveredSource.triage_confidence.isnot(None),
            )
        )
        triage_data = triage_result.scalars().all()
        if triage_data:
            avg_triage = sum(triage_data) / len(triage_data)
        else:
            avg_triage = None
    except Exception as e:
        logger.warning(f"Failed to fetch avg triage confidence for card {card_id}: {e}")
        avg_triage = None

    triage_score = _score_avg_triage_confidence(avg_triage)
    breakdown["avg_triage_confidence"] = {
        "score": triage_score,
        "weight": weights["avg_triage_confidence"],
        "raw_value": round(avg_triage, 3) if avg_triage is not None else None,
    }

    # 5. Deep Research (15%) - cards.deep_research_at IS NOT NULL
    try:
        card_result = await db.execute(
            select(Card.deep_research_at, Card.reviewed_at).where(Card.id == card_id)
        )
        card_data = card_result.one_or_none()
        has_deep_research = (
            card_data.deep_research_at is not None if card_data else False
        )
        has_review = card_data.reviewed_at is not None if card_data else False
    except Exception as e:
        logger.warning(f"Failed to fetch card data for card {card_id}: {e}")
        has_deep_research = False
        has_review = False

    deep_research_score = _score_deep_research(has_deep_research)
    breakdown["deep_research"] = {
        "score": deep_research_score,
        "weight": weights["deep_research"],
        "raw_value": has_deep_research,
    }

    # 6. Research Tasks (10%) - count completed research tasks for this card
    try:
        research_result = await db.execute(
            select(func.count(ResearchTask.id)).where(
                ResearchTask.card_id == card_id,
                ResearchTask.status == "completed",
            )
        )
        research_task_count = research_result.scalar() or 0
    except Exception as e:
        logger.warning(f"Failed to fetch research task count for card {card_id}: {e}")
        research_task_count = 0

    research_tasks_score = _score_research_tasks(research_task_count)
    breakdown["research_tasks"] = {
        "score": research_tasks_score,
        "weight": weights["research_tasks"],
        "raw_value": research_task_count,
    }

    # 7. Entity Count (5%) - from entities table
    try:
        entity_result = await db.execute(
            select(func.count(Entity.id)).where(Entity.card_id == card_id)
        )
        entity_count = entity_result.scalar() or 0
    except Exception as e:
        logger.warning(f"Failed to fetch entity count for card {card_id}: {e}")
        entity_count = 0

    entity_count_score = _score_entity_count(entity_count)
    breakdown["entity_count"] = {
        "score": entity_count_score,
        "weight": weights["entity_count"],
        "raw_value": entity_count,
    }

    # 8. Human Review (10%) - cards.reviewed_at IS NOT NULL (fetched above with card data)
    human_review_score = _score_human_review(has_review)
    breakdown["human_review"] = {
        "score": human_review_score,
        "weight": weights["human_review"],
        "raw_value": has_review,
    }

    # 9. Engagement (10%) - card_follows COUNT + workstream_cards COUNT
    try:
        follows_result = await db.execute(
            select(func.count(CardFollow.id)).where(CardFollow.card_id == card_id)
        )
        follows_count = follows_result.scalar() or 0
    except Exception as e:
        logger.warning(f"Failed to fetch follows count for card {card_id}: {e}")
        follows_count = 0

    try:
        workstream_result = await db.execute(
            select(func.count(WorkstreamCard.id)).where(
                WorkstreamCard.card_id == card_id
            )
        )
        workstream_count = workstream_result.scalar() or 0
    except Exception as e:
        logger.warning(
            f"Failed to fetch workstream membership count for card {card_id}: {e}"
        )
        workstream_count = 0

    total_engagement = follows_count + workstream_count
    engagement_score = _score_engagement(total_engagement)
    breakdown["engagement"] = {
        "score": engagement_score,
        "weight": weights["engagement"],
        "raw_value": {
            "follows": follows_count,
            "workstream_memberships": workstream_count,
        },
    }

    # Compute weighted total
    total_score = int(
        round(
            sum(
                component["score"] * component["weight"]
                for component in breakdown.values()
            )
        )
    )

    # Clamp to 0-100
    total_score = max(0, min(100, total_score))

    return {
        "score": total_score,
        "breakdown": breakdown,
    }


async def update_signal_quality_score(db: AsyncSession, card_id: str) -> int:
    """
    Compute and save the signal quality score for a card.

    Args:
        db: AsyncSession instance
        card_id: UUID of the card to update

    Returns:
        The computed score (int 0-100)
    """
    result = await compute_signal_quality_score(db, card_id)
    score = result["score"]

    try:
        await db.execute(
            sa_update(Card).where(Card.id == card_id).values(signal_quality_score=score)
        )
        await db.flush()
        logger.info(f"Updated signal quality score for card {card_id}: {score}")
    except Exception as e:
        logger.error(f"Failed to save signal quality score for card {card_id}: {e}")

    return score


async def recompute_all_quality_scores(db: AsyncSession) -> dict:
    """
    Recompute quality scores for all active cards.

    Args:
        db: AsyncSession instance

    Returns:
        dict with "updated" (int) and "errors" (int) counts
    """
    updated = 0
    errors = 0

    try:
        # Fetch all active card IDs
        result = await db.execute(select(Card.id).where(Card.status == "active"))
        cards = result.scalars().all()
    except Exception as e:
        logger.error(
            f"Failed to fetch active cards for quality score recomputation: {e}"
        )
        return {"updated": 0, "errors": 1}

    for card_id in cards:
        try:
            await update_signal_quality_score(db, str(card_id))
            updated += 1
        except Exception as e:
            logger.error(f"Failed to recompute quality score for card {card_id}: {e}")
            errors += 1

    logger.info(f"Recomputed quality scores: {updated} updated, {errors} errors")
    return {"updated": updated, "errors": errors}
