"""
Discovery Queue Scoring Functions

Multi-factor scoring algorithm for personalized discovery queue ranking.
These functions compute individual scoring factors and combine them into
a weighted discovery score.

Scoring Factors:
- Novelty: Card age and user interaction history
- Workstream Relevance: Match against user's workstream filters
- Pillar Alignment: Binary match if card's pillar in any workstream
- Followed Context: Similarity to cards user follows

All individual scores are in the range [0.0, 1.0].
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from app.taxonomy import get_pipeline_phase


# ============================================================================
# SCORING WEIGHTS (configurable)
# ============================================================================

NOVELTY_WEIGHT = 0.25
RELEVANCE_WEIGHT = 0.40
ALIGNMENT_WEIGHT = 0.20
CONTEXT_WEIGHT = 0.15


# ============================================================================
# INDIVIDUAL SCORING FUNCTIONS
# ============================================================================


def calculate_novelty_score(
    card: Dict[str, Any], user_dismissed_card_ids: Optional[set] = None
) -> float:
    """
    Calculate novelty score based on card age and user interaction history.

    Scoring:
    - Recent cards (< 7 days): 1.0
    - Mid-age cards (7-30 days): 0.5
    - Older cards (> 30 days): 0.2
    - Boost: Card never dismissed by user (+0.2, capped at 1.0)

    Args:
        card: Card dictionary with created_at or discovered_at field
        user_dismissed_card_ids: Set of card IDs the user has dismissed

    Returns:
        Float between 0 and 1
    """
    score = 0.0

    if card_date_str := card.get("discovered_at") or card.get("created_at"):
        try:
            # Parse ISO format datetime
            if isinstance(card_date_str, str):
                card_date = datetime.fromisoformat(card_date_str.replace("Z", "+00:00"))
            else:
                card_date = card_date_str

            # Calculate age in days
            now = (
                datetime.now(card_date.tzinfo)
                if card_date.tzinfo
                else datetime.now(timezone.utc)
            )
            age_days = (now - card_date).days

            # Age-based scoring
            if age_days < 7:
                score = 1.0
            elif age_days < 30:
                score = 0.5
            else:
                score = 0.2
        except (ValueError, TypeError):
            # Default to mid-tier score if date parsing fails
            score = 0.5
    else:
        score = 0.5

    # Boost for cards never dismissed by user (indicates novelty)
    if user_dismissed_card_ids is not None:
        card_id = card.get("id")
        if card_id and card_id not in user_dismissed_card_ids:
            score = min(1.0, score + 0.2)

    return score


def calculate_workstream_relevance(
    card: Dict[str, Any], workstreams: List[Dict[str, Any]]
) -> float:
    """
    Calculate workstream relevance score based on filter criteria matching.

    Scoring per workstream:
    - Pillar match: +0.3 per matching pillar (max 1.0)
    - Goal match: +0.4 per matching goal (max 1.0)
    - Keyword match in name/summary: +0.5 per keyword (max 1.0)
    - Horizon match: +0.3 if exact match

    Returns average score across all active workstreams.

    Args:
        card: Card dictionary with pillar_id, goal_id, name, summary, horizon fields
        workstreams: List of workstream dictionaries with filter criteria

    Returns:
        Float between 0 and 1
    """
    if not workstreams:
        return 0.0

    card_pillar = card.get("pillar_id", "")
    card_goal = card.get("goal_id", "")
    card_horizon = card.get("horizon", "")
    card_name = (card.get("name") or "").lower()
    card_summary = (card.get("summary") or "").lower()
    card_text = f"{card_name} {card_summary}"

    workstream_scores = []

    for ws in workstreams:
        # Skip inactive workstreams
        if not ws.get("is_active", True):
            continue

        ws_score = 0.0

        # Pillar matching: +0.3 per match (max 1.0)
        ws_pillars = ws.get("pillar_ids") or []
        if ws_pillars and card_pillar:
            pillar_matches = sum(bool(p == card_pillar) for p in ws_pillars)
            ws_score += min(1.0, pillar_matches * 0.3)

        # Goal matching: +0.4 per match (max 1.0)
        ws_goals = ws.get("goal_ids") or []
        if ws_goals and card_goal:
            goal_matches = sum(bool(g == card_goal) for g in ws_goals)
            ws_score += min(1.0, goal_matches * 0.4)

        if ws_keywords := ws.get("keywords") or []:
            keyword_matches = sum(bool(kw.lower() in card_text) for kw in ws_keywords)
            ws_score += min(1.0, keyword_matches * 0.5)

        # Horizon matching: +0.3 if exact match
        ws_horizon = ws.get("horizon")
        if (
            ws_horizon
            and ws_horizon != "ALL"
            and card_horizon
            and ws_horizon == card_horizon
        ):
            ws_score += 0.3

        # Pipeline phase matching: +0.3 if card's pipeline_status is in
        # any of the workstream's desired pipeline_statuses
        ws_pipeline_statuses = ws.get("pipeline_statuses") or []
        card_pipeline_status = card.get("pipeline_status", "")
        if ws_pipeline_statuses and card_pipeline_status:
            if card_pipeline_status in ws_pipeline_statuses:
                ws_score += 0.3
            else:
                # Partial credit if same phase
                card_phase = get_pipeline_phase(card_pipeline_status)
                ws_phases = {get_pipeline_phase(s) for s in ws_pipeline_statuses}
                if card_phase in ws_phases:
                    ws_score += 0.15

        # Cap individual workstream score at 1.0
        workstream_scores.append(min(1.0, ws_score))

    # Average across all active workstreams
    if workstream_scores:
        return sum(workstream_scores) / len(workstream_scores)
    return 0.0


def calculate_pillar_alignment(
    card: Dict[str, Any], workstreams: List[Dict[str, Any]]
) -> float:
    """
    Calculate pillar alignment score - binary match if card's pillar
    appears in any user workstream.

    Scoring:
    - Card's pillar appears in ANY user workstream: 1.0
    - Card's pillar not in workstreams: 0.0

    Args:
        card: Card dictionary with pillar_id field
        workstreams: List of workstream dictionaries with pillar_ids

    Returns:
        Float: 1.0 if aligned, 0.0 otherwise
    """
    if not workstreams:
        return 0.0

    card_pillar = card.get("pillar_id")
    if not card_pillar:
        return 0.0

    # Check if card's pillar exists in any workstream
    for ws in workstreams:
        if not ws.get("is_active", True):
            continue
        ws_pillars = ws.get("pillar_ids") or []
        if card_pillar in ws_pillars:
            return 1.0

    return 0.0


def calculate_followed_context(
    card: Dict[str, Any], followed_cards: List[Dict[str, Any]]
) -> float:
    """
    Calculate followed context score based on similarity to followed cards.

    Scoring:
    - Card in same pillar as any followed card: +0.5
    - Card shares goal with any followed card: +0.7
    - No followed cards: 0.0 (neutral)

    Args:
        card: Card dictionary with pillar_id, goal_id fields
        followed_cards: List of card dictionaries that user follows

    Returns:
        Float between 0 and 1
    """
    if not followed_cards:
        return 0.0

    card_pillar = card.get("pillar_id")
    card_goal = card.get("goal_id")

    score = 0.0

    # Check for pillar match with followed cards
    followed_pillars = {
        fc.get("pillar_id") for fc in followed_cards if fc.get("pillar_id")
    }
    if card_pillar and card_pillar in followed_pillars:
        score += 0.5

    # Check for goal match with followed cards
    followed_goals = {fc.get("goal_id") for fc in followed_cards if fc.get("goal_id")}
    if card_goal and card_goal in followed_goals:
        score += 0.7

    return min(1.0, score)


def calculate_discovery_score(
    card: Dict[str, Any],
    workstreams: List[Dict[str, Any]],
    followed_cards: List[Dict[str, Any]],
    user_dismissed_card_ids: Optional[set] = None,
) -> Dict[str, Any]:
    """
    Calculate the overall discovery score for a card using multi-factor scoring.

    Formula:
    discovery_score = (
        NOVELTY_WEIGHT * novelty_score +
        RELEVANCE_WEIGHT * workstream_relevance_score +
        ALIGNMENT_WEIGHT * pillar_alignment_score +
        CONTEXT_WEIGHT * followed_context_score
    )

    Args:
        card: Card dictionary
        workstreams: User's workstreams
        followed_cards: Cards the user follows
        user_dismissed_card_ids: Set of dismissed card IDs

    Returns:
        Dictionary with discovery_score and score_breakdown
    """
    novelty = calculate_novelty_score(card, user_dismissed_card_ids)
    relevance = calculate_workstream_relevance(card, workstreams)
    alignment = calculate_pillar_alignment(card, workstreams)
    context = calculate_followed_context(card, followed_cards)

    # Calculate weighted score
    discovery_score = (
        NOVELTY_WEIGHT * novelty
        + RELEVANCE_WEIGHT * relevance
        + ALIGNMENT_WEIGHT * alignment
        + CONTEXT_WEIGHT * context
    )

    return {
        "discovery_score": round(discovery_score, 4),
        "score_breakdown": {
            "novelty": round(novelty, 4),
            "workstream_relevance": round(relevance, 4),
            "pillar_alignment": round(alignment, 4),
            "followed_context": round(context, 4),
            "weights": {
                "novelty": NOVELTY_WEIGHT,
                "relevance": RELEVANCE_WEIGHT,
                "alignment": ALIGNMENT_WEIGHT,
                "context": CONTEXT_WEIGHT,
            },
        },
    }
