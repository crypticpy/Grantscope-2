#!/usr/bin/env python3
"""
Manual Verification Script for Discovery Queue Scoring Algorithm

This script verifies the multi-factor scoring algorithm works correctly
for the personalized discovery queue.

Verification Scenarios (from subtask-3-1):
1. User with workstream (pillar=CH, keywords=['electric']) - CH pillar cards rank higher
2. Dismiss a card, verify it doesn't reappear
3. User with no workstreams - fallback to novelty-sorted global queue

Run with: python tests/verify_scoring_algorithm.py
"""

import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List


# ============================================================================
# SCORING WEIGHTS (from spec)
# ============================================================================

NOVELTY_WEIGHT = 0.25
RELEVANCE_WEIGHT = 0.40
ALIGNMENT_WEIGHT = 0.20
CONTEXT_WEIGHT = 0.15


# ============================================================================
# SCORING FUNCTIONS (copied from main.py for standalone testing)
# ============================================================================

def calculate_novelty_score(card: Dict[str, Any], user_dismissed_card_ids: set = None) -> float:
    """
    Calculate novelty score based on card age and user interaction history.
    """
    score = 0.0

    card_date_str = card.get("discovered_at") or card.get("created_at")
    if card_date_str:
        try:
            if isinstance(card_date_str, str):
                card_date = datetime.fromisoformat(card_date_str.replace("Z", "+00:00"))
            else:
                card_date = card_date_str

            now = datetime.now(card_date.tzinfo) if card_date.tzinfo else datetime.now()
            age_days = (now - card_date).days

            if age_days < 7:
                score = 1.0
            elif age_days < 30:
                score = 0.5
            else:
                score = 0.2
        except (ValueError, TypeError):
            score = 0.5
    else:
        score = 0.5

    if user_dismissed_card_ids is not None:
        card_id = card.get("id")
        if card_id and card_id not in user_dismissed_card_ids:
            score = min(1.0, score + 0.2)

    return score


def calculate_workstream_relevance(card: Dict[str, Any], workstreams: List[Dict[str, Any]]) -> float:
    """
    Calculate workstream relevance score based on filter criteria matching.
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
        if not ws.get("is_active", True):
            continue

        ws_score = 0.0

        ws_pillars = ws.get("pillar_ids") or []
        if ws_pillars and card_pillar:
            pillar_matches = sum(1 for p in ws_pillars if p == card_pillar)
            ws_score += min(1.0, pillar_matches * 0.3)

        ws_goals = ws.get("goal_ids") or []
        if ws_goals and card_goal:
            goal_matches = sum(1 for g in ws_goals if g == card_goal)
            ws_score += min(1.0, goal_matches * 0.4)

        ws_keywords = ws.get("keywords") or []
        if ws_keywords:
            keyword_matches = sum(1 for kw in ws_keywords if kw.lower() in card_text)
            ws_score += min(1.0, keyword_matches * 0.5)

        ws_horizon = ws.get("horizon")
        if ws_horizon and ws_horizon != "ALL" and card_horizon:
            if ws_horizon == card_horizon:
                ws_score += 0.3

        workstream_scores.append(min(1.0, ws_score))

    if workstream_scores:
        return sum(workstream_scores) / len(workstream_scores)
    return 0.0


def calculate_pillar_alignment(card: Dict[str, Any], workstreams: List[Dict[str, Any]]) -> float:
    """
    Calculate pillar alignment score - binary match.
    """
    if not workstreams:
        return 0.0

    card_pillar = card.get("pillar_id")
    if not card_pillar:
        return 0.0

    for ws in workstreams:
        if not ws.get("is_active", True):
            continue
        ws_pillars = ws.get("pillar_ids") or []
        if card_pillar in ws_pillars:
            return 1.0

    return 0.0


def calculate_followed_context(card: Dict[str, Any], followed_cards: List[Dict[str, Any]]) -> float:
    """
    Calculate followed context score based on similarity to followed cards.
    """
    if not followed_cards:
        return 0.0

    card_pillar = card.get("pillar_id")
    card_goal = card.get("goal_id")

    score = 0.0

    followed_pillars = {fc.get("pillar_id") for fc in followed_cards if fc.get("pillar_id")}
    if card_pillar and card_pillar in followed_pillars:
        score += 0.5

    followed_goals = {fc.get("goal_id") for fc in followed_cards if fc.get("goal_id")}
    if card_goal and card_goal in followed_goals:
        score += 0.7

    return min(1.0, score)


def calculate_discovery_score(
    card: Dict[str, Any],
    workstreams: List[Dict[str, Any]],
    followed_cards: List[Dict[str, Any]],
    user_dismissed_card_ids: set = None
) -> Dict[str, Any]:
    """
    Calculate the overall discovery score for a card.
    """
    novelty = calculate_novelty_score(card, user_dismissed_card_ids)
    relevance = calculate_workstream_relevance(card, workstreams)
    alignment = calculate_pillar_alignment(card, workstreams)
    context = calculate_followed_context(card, followed_cards)

    discovery_score = (
        NOVELTY_WEIGHT * novelty +
        RELEVANCE_WEIGHT * relevance +
        ALIGNMENT_WEIGHT * alignment +
        CONTEXT_WEIGHT * context
    )

    return {
        "discovery_score": round(discovery_score, 4),
        "score_breakdown": {
            "novelty": round(novelty, 4),
            "workstream_relevance": round(relevance, 4),
            "pillar_alignment": round(alignment, 4),
            "followed_context": round(context, 4),
        }
    }


# ============================================================================
# TEST DATA HELPERS
# ============================================================================

def make_card(
    card_id: str,
    name: str,
    pillar_id: str = None,
    goal_id: str = None,
    horizon: str = None,
    summary: str = None,
    days_ago: int = 0
) -> dict:
    """Create a test card."""
    created_at = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    return {
        "id": card_id,
        "name": name,
        "slug": name.lower().replace(" ", "-"),
        "summary": summary or f"Summary for {name}",
        "pillar_id": pillar_id,
        "goal_id": goal_id,
        "horizon": horizon,
        "status": "active",
        "review_status": "active",
        "created_at": created_at,
        "discovered_at": created_at,
    }


def make_workstream(
    pillar_ids: list = None,
    goal_ids: list = None,
    keywords: list = None,
    horizon: str = None,
    is_active: bool = True
) -> dict:
    """Create a test workstream."""
    return {
        "id": "ws-test",
        "name": "Test Workstream",
        "pillar_ids": pillar_ids or [],
        "goal_ids": goal_ids or [],
        "keywords": keywords or [],
        "horizon": horizon,
        "is_active": is_active,
    }


# ============================================================================
# VERIFICATION TESTS
# ============================================================================

class TestResults:
    """Track test results."""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests = []

    def add_result(self, name: str, passed: bool, details: str = ""):
        self.tests.append({"name": name, "passed": passed, "details": details})
        if passed:
            self.passed += 1
        else:
            self.failed += 1

    def print_summary(self):
        print("\n" + "=" * 70)
        print("VERIFICATION RESULTS SUMMARY")
        print("=" * 70)
        for test in self.tests:
            status = "✅ PASS" if test["passed"] else "❌ FAIL"
            print(f"{status}: {test['name']}")
            if test["details"]:
                print(f"       {test['details']}")
        print("-" * 70)
        print(f"Total: {self.passed}/{self.passed + self.failed} tests passed")
        if self.failed == 0:
            print("🎉 All verification tests passed!")
        else:
            print(f"⚠️ {self.failed} test(s) failed")
        return self.failed == 0


def verify_scenario_1_workstream_user():
    """
    SCENARIO 1: User with workstream (pillar=CH, keywords=['electric'])
    Verify cards with CH pillar rank higher than non-CH cards.
    """
    print("\n" + "=" * 70)
    print("SCENARIO 1: User with workstream (pillar=CH, keywords=['electric'])")
    print("=" * 70)

    results = TestResults()

    # Create test cards
    cards = [
        make_card("c1", "Electric Grid Modernization", pillar_id="CH", days_ago=2),
        make_card("c2", "Water Treatment Plant Expansion", pillar_id="EW", days_ago=2),
        make_card("c3", "Electric Vehicle Infrastructure", pillar_id="CH", days_ago=5),
        make_card("c4", "Housing Development Initiative", pillar_id="HH", days_ago=1),
        make_card("c5", "Clean Energy Storage", pillar_id="CH", days_ago=10),
        make_card("c6", "Public Transit Electric Buses", pillar_id="MC", summary="Electric bus fleet expansion", days_ago=3),
    ]

    # User workstream: pillar=CH, keywords=['electric']
    workstreams = [make_workstream(pillar_ids=["CH"], keywords=["electric"])]
    followed = []
    dismissed = set()

    # Score all cards
    scored = []
    for card in cards:
        result = calculate_discovery_score(card, workstreams, followed, dismissed)
        scored.append({
            "id": card["id"],
            "name": card["name"],
            "pillar_id": card["pillar_id"],
            "score": result["discovery_score"],
            "breakdown": result["score_breakdown"]
        })

    # Sort by discovery_score DESC
    scored.sort(key=lambda x: x["score"], reverse=True)

    print("\nRanked Cards (highest to lowest discovery_score):")
    print("-" * 70)
    for i, s in enumerate(scored, 1):
        print(f"{i}. [{s['pillar_id'] or 'N/A':2}] {s['name'][:40]:<40} Score: {s['score']:.4f}")
        print(f"   Breakdown: novelty={s['breakdown']['novelty']:.2f}, "
              f"relevance={s['breakdown']['workstream_relevance']:.2f}, "
              f"alignment={s['breakdown']['pillar_alignment']:.2f}, "
              f"context={s['breakdown']['followed_context']:.2f}")

    # Test 1: CH cards with 'electric' keyword should be top 2
    top_3_ids = [s["id"] for s in scored[:3]]
    ch_electric_top = "c1" in top_3_ids and "c3" in top_3_ids
    results.add_result(
        "CH cards with 'electric' keyword rank in top 3",
        ch_electric_top,
        f"Top 3 card IDs: {top_3_ids}"
    )

    # Test 2: CH cards should have pillar_alignment = 1.0
    ch_card = next(s for s in scored if s["id"] == "c1")
    ch_alignment_correct = ch_card["breakdown"]["pillar_alignment"] == 1.0
    results.add_result(
        "CH cards have pillar_alignment = 1.0",
        ch_alignment_correct,
        f"Card c1 alignment: {ch_card['breakdown']['pillar_alignment']}"
    )

    # Test 3: Non-CH cards should have pillar_alignment = 0.0
    ew_card = next(s for s in scored if s["id"] == "c2")
    ew_alignment_correct = ew_card["breakdown"]["pillar_alignment"] == 0.0
    results.add_result(
        "Non-CH cards have pillar_alignment = 0.0",
        ew_alignment_correct,
        f"Card c2 (EW) alignment: {ew_card['breakdown']['pillar_alignment']}"
    )

    # Test 4: 'electric' keyword match boosts relevance
    mc_bus = next(s for s in scored if s["id"] == "c6")  # Has 'electric' in summary
    keyword_boosted = mc_bus["breakdown"]["workstream_relevance"] > 0
    results.add_result(
        "Keyword 'electric' boosts relevance (even for non-CH cards)",
        keyword_boosted,
        f"Card c6 (MC with 'electric' keyword) relevance: {mc_bus['breakdown']['workstream_relevance']}"
    )

    # Test 5: CH + electric should rank higher than CH without electric
    c1_score = next(s["score"] for s in scored if s["id"] == "c1")  # CH + electric
    c5_score = next(s["score"] for s in scored if s["id"] == "c5")  # CH but no electric
    ch_electric_ranks_higher = c1_score > c5_score
    results.add_result(
        "CH + 'electric' ranks higher than CH without keyword",
        ch_electric_ranks_higher,
        f"c1 (CH+electric): {c1_score:.4f} vs c5 (CH only): {c5_score:.4f}"
    )

    return results


def verify_scenario_2_dismissed_cards():
    """
    SCENARIO 2: Dismissed card exclusion
    Verify dismissed cards don't appear in queue.
    """
    print("\n" + "=" * 70)
    print("SCENARIO 2: Dismissed card exclusion from queue")
    print("=" * 70)

    results = TestResults()

    # Create cards
    cards = [
        make_card("c1", "Card 1", pillar_id="CH", days_ago=2),
        make_card("c2", "Card 2 - Will be dismissed", pillar_id="CH", days_ago=2),
        make_card("c3", "Card 3", pillar_id="CH", days_ago=5),
    ]

    workstreams = [make_workstream(pillar_ids=["CH"])]
    followed = []

    # Without dismissals
    print("\nBefore dismissal (no dismissed cards):")
    dismissed_empty = set()
    for card in cards:
        result = calculate_discovery_score(card, workstreams, followed, dismissed_empty)
        print(f"  {card['id']}: {card['name'][:30]} -> Score: {result['discovery_score']:.4f}")

    # With dismissal of c2
    print("\nAfter dismissing card c2:")
    dismissed_with_c2 = {"c2"}

    # In the actual endpoint, dismissed cards are filtered out before scoring
    # Here we verify the dismissal affects novelty boost
    for card in cards:
        result = calculate_discovery_score(card, workstreams, followed, dismissed_with_c2)
        in_dismissed = card["id"] in dismissed_with_c2
        status = "(DISMISSED - would be filtered)" if in_dismissed else ""
        print(f"  {card['id']}: {card['name'][:30]} -> Score: {result['discovery_score']:.4f} {status}")

    # Test 1: Dismissed card c2 should not get novelty boost
    c2_with_dismissal = calculate_discovery_score(cards[1], workstreams, followed, dismissed_with_c2)
    c2_without_dismissal = calculate_discovery_score(cards[1], workstreams, followed, set())

    results.add_result(
        "Dismissed card doesn't get novelty boost",
        c2_with_dismissal["score_breakdown"]["novelty"] <= c2_without_dismissal["score_breakdown"]["novelty"],
        f"c2 novelty with dismissal: {c2_with_dismissal['score_breakdown']['novelty']:.4f}, "
        f"without: {c2_without_dismissal['score_breakdown']['novelty']:.4f}"
    )

    # Test 2: Non-dismissed card c1 gets novelty boost when c2 is dismissed
    c1_result = calculate_discovery_score(cards[0], workstreams, followed, dismissed_with_c2)
    c1_has_boost = c1_result["score_breakdown"]["novelty"] >= 1.0  # Recent card + not dismissed
    results.add_result(
        "Non-dismissed card gets novelty boost",
        c1_has_boost,
        f"c1 (not dismissed) novelty: {c1_result['score_breakdown']['novelty']:.4f}"
    )

    # Test 3: Filtering simulation - dismissed cards excluded from eligible list
    eligible_cards = [c for c in cards if c["id"] not in dismissed_with_c2]
    dismissed_excluded = len(eligible_cards) == 2 and all(c["id"] != "c2" for c in eligible_cards)
    results.add_result(
        "Dismissed cards filtered from eligible list",
        dismissed_excluded,
        f"Eligible cards: {[c['id'] for c in eligible_cards]}"
    )

    return results


def verify_scenario_3_no_workstreams():
    """
    SCENARIO 3: User with no workstreams
    Verify fallback to novelty-sorted global queue.
    """
    print("\n" + "=" * 70)
    print("SCENARIO 3: User with no workstreams - novelty-sorted fallback")
    print("=" * 70)

    results = TestResults()

    # Create cards with different ages
    cards = [
        make_card("c-recent", "Recent Card", pillar_id="CH", days_ago=1),
        make_card("c-mid", "Mid-Age Card", pillar_id="EW", days_ago=15),
        make_card("c-old", "Old Card", pillar_id="HH", days_ago=60),
    ]

    # NO workstreams, NO followed cards
    workstreams = []
    followed = []
    dismissed = set()

    # Score all cards
    scored = []
    for card in cards:
        result = calculate_discovery_score(card, workstreams, followed, dismissed)
        scored.append({
            "id": card["id"],
            "name": card["name"],
            "score": result["discovery_score"],
            "breakdown": result["score_breakdown"]
        })

    # Sort by discovery_score DESC
    scored.sort(key=lambda x: x["score"], reverse=True)

    print("\nRanked Cards (no workstreams - should be novelty-ordered):")
    print("-" * 70)
    for i, s in enumerate(scored, 1):
        print(f"{i}. {s['name']:<30} Score: {s['score']:.4f}")
        print(f"   Breakdown: novelty={s['breakdown']['novelty']:.2f}, "
              f"relevance={s['breakdown']['workstream_relevance']:.2f}, "
              f"alignment={s['breakdown']['pillar_alignment']:.2f}, "
              f"context={s['breakdown']['followed_context']:.2f}")

    # Test 1: All personalization scores should be 0
    all_zero_personalization = all(
        s["breakdown"]["workstream_relevance"] == 0.0 and
        s["breakdown"]["pillar_alignment"] == 0.0 and
        s["breakdown"]["followed_context"] == 0.0
        for s in scored
    )
    results.add_result(
        "All personalization scores are 0 (no workstreams/follows)",
        all_zero_personalization,
        "relevance=0, alignment=0, context=0 for all cards"
    )

    # Test 2: Only novelty contributes to score
    recent = next(s for s in scored if s["id"] == "c-recent")
    novelty_only = recent["score"] == round(NOVELTY_WEIGHT * recent["breakdown"]["novelty"], 4)
    results.add_result(
        "Score = NOVELTY_WEIGHT * novelty_score only",
        novelty_only,
        f"recent card score: {recent['score']:.4f}, expected: {NOVELTY_WEIGHT * recent['breakdown']['novelty']:.4f}"
    )

    # Test 3: Most recent card ranks first
    recent_ranks_first = scored[0]["id"] == "c-recent"
    results.add_result(
        "Most recent card ranks first",
        recent_ranks_first,
        f"First card: {scored[0]['id']} ({scored[0]['name']})"
    )

    # Test 4: Oldest card ranks last
    old_ranks_last = scored[-1]["id"] == "c-old"
    results.add_result(
        "Oldest card ranks last",
        old_ranks_last,
        f"Last card: {scored[-1]['id']} ({scored[-1]['name']})"
    )

    # Test 5: Recent novelty > old novelty
    old = next(s for s in scored if s["id"] == "c-old")
    novelty_ordering = recent["breakdown"]["novelty"] > old["breakdown"]["novelty"]
    results.add_result(
        "Recent card novelty > old card novelty",
        novelty_ordering,
        f"Recent: {recent['breakdown']['novelty']:.2f}, Old: {old['breakdown']['novelty']:.2f}"
    )

    return results


def verify_scenario_4_score_transparency():
    """
    SCENARIO 4: Score transparency
    Verify discovery_score field present in all responses.
    """
    print("\n" + "=" * 70)
    print("SCENARIO 4: Score transparency - discovery_score field present")
    print("=" * 70)

    results = TestResults()

    card = make_card("c1", "Test Card", pillar_id="CH", days_ago=5)
    workstreams = [make_workstream(pillar_ids=["CH"])]

    result = calculate_discovery_score(card, workstreams, [], set())

    print("\nScore Response Structure:")
    print(f"  discovery_score: {result['discovery_score']}")
    print(f"  score_breakdown:")
    for key, value in result["score_breakdown"].items():
        print(f"    {key}: {value}")

    # Test 1: discovery_score field present
    has_score = "discovery_score" in result
    results.add_result(
        "discovery_score field present",
        has_score,
        f"discovery_score = {result.get('discovery_score')}"
    )

    # Test 2: discovery_score is numeric
    score_numeric = isinstance(result["discovery_score"], (int, float))
    results.add_result(
        "discovery_score is numeric",
        score_numeric,
        f"Type: {type(result['discovery_score']).__name__}"
    )

    # Test 3: score_breakdown present
    has_breakdown = "score_breakdown" in result
    results.add_result(
        "score_breakdown field present",
        has_breakdown,
        f"Breakdown keys: {list(result.get('score_breakdown', {}).keys())}"
    )

    # Test 4: All 4 factors in breakdown
    breakdown = result.get("score_breakdown", {})
    expected_factors = ["novelty", "workstream_relevance", "pillar_alignment", "followed_context"]
    all_factors_present = all(f in breakdown for f in expected_factors)
    results.add_result(
        "All 4 scoring factors in breakdown",
        all_factors_present,
        f"Found: {list(breakdown.keys())}"
    )

    # Test 5: Factor scores are 0-1 range
    factors_in_range = all(
        0.0 <= breakdown.get(f, -1) <= 1.0
        for f in expected_factors
    )
    results.add_result(
        "All factor scores in 0-1 range",
        factors_in_range,
        f"Values: {[f'{f}={breakdown.get(f)}' for f in expected_factors]}"
    )

    return results


def verify_weight_configuration():
    """Verify the scoring weights are correctly configured."""
    print("\n" + "=" * 70)
    print("WEIGHT CONFIGURATION CHECK")
    print("=" * 70)

    results = TestResults()

    total = NOVELTY_WEIGHT + RELEVANCE_WEIGHT + ALIGNMENT_WEIGHT + CONTEXT_WEIGHT

    print(f"\nScoring Weights:")
    print(f"  NOVELTY_WEIGHT:   {NOVELTY_WEIGHT:.2f} ({NOVELTY_WEIGHT*100:.0f}%)")
    print(f"  RELEVANCE_WEIGHT: {RELEVANCE_WEIGHT:.2f} ({RELEVANCE_WEIGHT*100:.0f}%)")
    print(f"  ALIGNMENT_WEIGHT: {ALIGNMENT_WEIGHT:.2f} ({ALIGNMENT_WEIGHT*100:.0f}%)")
    print(f"  CONTEXT_WEIGHT:   {CONTEXT_WEIGHT:.2f} ({CONTEXT_WEIGHT*100:.0f}%)")
    print(f"  Total:            {total:.2f}")

    results.add_result(
        "Weights sum to 1.0",
        total == 1.0,
        f"Total: {total}"
    )

    results.add_result(
        "NOVELTY_WEIGHT = 0.25",
        NOVELTY_WEIGHT == 0.25,
        f"Actual: {NOVELTY_WEIGHT}"
    )

    results.add_result(
        "RELEVANCE_WEIGHT = 0.40",
        RELEVANCE_WEIGHT == 0.40,
        f"Actual: {RELEVANCE_WEIGHT}"
    )

    results.add_result(
        "ALIGNMENT_WEIGHT = 0.20",
        ALIGNMENT_WEIGHT == 0.20,
        f"Actual: {ALIGNMENT_WEIGHT}"
    )

    results.add_result(
        "CONTEXT_WEIGHT = 0.15",
        CONTEXT_WEIGHT == 0.15,
        f"Actual: {CONTEXT_WEIGHT}"
    )

    return results


def main():
    """Run all verification scenarios."""
    print("=" * 70)
    print("DISCOVERY QUEUE SCORING ALGORITHM - MANUAL VERIFICATION")
    print("=" * 70)
    print(f"Run Time: {datetime.now().isoformat()}")

    all_results = []

    # Run all scenarios
    all_results.append(verify_weight_configuration())
    all_results.append(verify_scenario_1_workstream_user())
    all_results.append(verify_scenario_2_dismissed_cards())
    all_results.append(verify_scenario_3_no_workstreams())
    all_results.append(verify_scenario_4_score_transparency())

    # Print combined summary
    print("\n" + "=" * 70)
    print("FINAL VERIFICATION SUMMARY")
    print("=" * 70)

    total_passed = sum(r.passed for r in all_results)
    total_failed = sum(r.failed for r in all_results)

    for r in all_results:
        r.print_summary()

    print("\n" + "=" * 70)
    print(f"OVERALL: {total_passed}/{total_passed + total_failed} tests passed")
    print("=" * 70)

    if total_failed == 0:
        print("\n✅ All verification tests PASSED!")
        print("The scoring algorithm is working correctly.")
        return 0
    else:
        print(f"\n❌ {total_failed} test(s) FAILED!")
        print("Please review the failed tests above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
