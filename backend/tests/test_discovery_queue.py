"""
Unit Tests for Discovery Queue Scoring Functions

Tests the multi-factor scoring algorithm components:
- calculate_novelty_score: Card age and dismissal-based scoring
- calculate_workstream_relevance: Workstream filter criteria matching
- calculate_pillar_alignment: Binary pillar match scoring
- calculate_followed_context: Similarity to followed cards scoring
- calculate_discovery_score: Combined weighted score

Usage:
    cd backend && pytest tests/test_discovery_queue.py -v
"""

import pytest
import sys
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.discovery_scoring import (
    calculate_novelty_score,
    calculate_workstream_relevance,
    calculate_pillar_alignment,
    calculate_followed_context,
    calculate_discovery_score,
    NOVELTY_WEIGHT,
    RELEVANCE_WEIGHT,
    ALIGNMENT_WEIGHT,
    CONTEXT_WEIGHT,
)


# ============================================================================
# FIXTURES AND TEST DATA FACTORIES
# ============================================================================

def make_card(
    card_id: str = "card-1",
    name: str = "Test Card",
    summary: str = "A test summary",
    pillar_id: str = "CH",
    goal_id: str = "CH.1",
    horizon: str = "H1",
    created_at: datetime = None,
    discovered_at: datetime = None,
) -> Dict[str, Any]:
    """Factory function to create test card data."""
    now = datetime.now(timezone.utc)
    return {
        "id": card_id,
        "name": name,
        "summary": summary,
        "pillar_id": pillar_id,
        "goal_id": goal_id,
        "horizon": horizon,
        "created_at": (created_at or now).isoformat(),
        "discovered_at": (discovered_at or now).isoformat() if discovered_at else None,
    }


def make_workstream(
    ws_id: str = "ws-1",
    name: str = "Test Workstream",
    pillar_ids: List[str] = None,
    goal_ids: List[str] = None,
    keywords: List[str] = None,
    horizon: str = None,
    is_active: bool = True,
) -> Dict[str, Any]:
    """Factory function to create test workstream data."""
    return {
        "id": ws_id,
        "name": name,
        "pillar_ids": pillar_ids or [],
        "goal_ids": goal_ids or [],
        "keywords": keywords or [],
        "horizon": horizon,
        "is_active": is_active,
    }


def make_followed_card(
    card_id: str = "followed-1",
    pillar_id: str = "CH",
    goal_id: str = "CH.1",
) -> Dict[str, Any]:
    """Factory function to create test followed card data."""
    return {
        "id": card_id,
        "pillar_id": pillar_id,
        "goal_id": goal_id,
    }


# ============================================================================
# NOVELTY SCORE TESTS
# ============================================================================

class TestCalculateNoveltyScore:
    """Tests for calculate_novelty_score function."""

    def test_recent_card_scores_high(self):
        """Cards less than 7 days old should score 1.0."""
        now = datetime.now(timezone.utc)
        recent_card = make_card(created_at=now - timedelta(days=3))

        score = calculate_novelty_score(recent_card)

        assert score == 1.0, "Recent cards (< 7 days) should score 1.0"

    def test_mid_age_card_scores_medium(self):
        """Cards 7-30 days old should score 0.5."""
        now = datetime.now(timezone.utc)
        mid_age_card = make_card(created_at=now - timedelta(days=15))

        score = calculate_novelty_score(mid_age_card)

        assert score == 0.5, "Mid-age cards (7-30 days) should score 0.5"

    def test_old_card_scores_low(self):
        """Cards older than 30 days should score 0.2."""
        now = datetime.now(timezone.utc)
        old_card = make_card(created_at=now - timedelta(days=60))

        score = calculate_novelty_score(old_card)

        assert score == 0.2, "Old cards (> 30 days) should score 0.2"

    def test_discovered_at_preferred_over_created_at(self):
        """discovered_at should be used if present, over created_at."""
        now = datetime.now(timezone.utc)
        # Created 60 days ago, but discovered 2 days ago
        card = make_card(
            created_at=now - timedelta(days=60),
            discovered_at=now - timedelta(days=2)
        )

        score = calculate_novelty_score(card)

        assert score == 1.0, "discovered_at should take precedence over created_at"

    def test_undismissed_card_gets_boost(self):
        """Cards not in dismissed set get +0.2 boost."""
        now = datetime.now(timezone.utc)
        card = make_card(card_id="card-123", created_at=now - timedelta(days=15))
        dismissed_ids = {"other-card-1", "other-card-2"}

        score = calculate_novelty_score(card, dismissed_ids)

        # Base score 0.5 + 0.2 boost = 0.7
        assert score == 0.7, "Undismissed card should get +0.2 boost"

    def test_dismissed_card_no_boost(self):
        """Cards in dismissed set should not get boost."""
        now = datetime.now(timezone.utc)
        card = make_card(card_id="card-123", created_at=now - timedelta(days=15))
        dismissed_ids = {"card-123", "other-card"}

        score = calculate_novelty_score(card, dismissed_ids)

        assert score == 0.5, "Dismissed card should not get boost"

    def test_boost_capped_at_one(self):
        """Novelty score should be capped at 1.0."""
        now = datetime.now(timezone.utc)
        recent_card = make_card(created_at=now - timedelta(days=2))
        dismissed_ids = set()  # Empty set, so card gets boost

        score = calculate_novelty_score(recent_card, dismissed_ids)

        # Base 1.0 + 0.2 boost should cap at 1.0
        assert score == 1.0, "Score should be capped at 1.0"

    def test_missing_date_defaults_to_mid_score(self):
        """Cards with no date fields should default to 0.5."""
        card = {"id": "no-date-card", "name": "Test"}

        score = calculate_novelty_score(card)

        assert score == 0.5, "Cards without dates should default to 0.5"

    def test_invalid_date_format_handles_gracefully(self):
        """Invalid date strings should not crash, default to 0.5."""
        card = {
            "id": "invalid-date",
            "name": "Test",
            "created_at": "not-a-valid-date",
        }

        score = calculate_novelty_score(card)

        assert score == 0.5, "Invalid dates should default to 0.5"

    def test_boundary_seven_days(self):
        """Card exactly 7 days old should score 0.5 (not 1.0)."""
        now = datetime.now(timezone.utc)
        boundary_card = make_card(created_at=now - timedelta(days=7))

        score = calculate_novelty_score(boundary_card)

        assert score == 0.5, "Card at 7 days should score 0.5"

    def test_boundary_thirty_days(self):
        """Card exactly 30 days old should score 0.2 (not 0.5)."""
        now = datetime.now(timezone.utc)
        boundary_card = make_card(created_at=now - timedelta(days=30))

        score = calculate_novelty_score(boundary_card)

        assert score == 0.2, "Card at 30 days should score 0.2"


# ============================================================================
# WORKSTREAM RELEVANCE TESTS
# ============================================================================

class TestCalculateWorkstreamRelevance:
    """Tests for calculate_workstream_relevance function."""

    def test_empty_workstreams_returns_zero(self):
        """No workstreams should return 0.0 score."""
        card = make_card()

        score = calculate_workstream_relevance(card, [])

        assert score == 0.0

    def test_pillar_match_scores_0_3(self):
        """Single pillar match should add 0.3 to score."""
        card = make_card(pillar_id="CH")
        workstreams = [make_workstream(pillar_ids=["CH"])]

        score = calculate_workstream_relevance(card, workstreams)

        assert score == 0.3, "Pillar match should score 0.3"

    def test_goal_match_scores_0_4(self):
        """Single goal match should add 0.4 to score."""
        card = make_card(pillar_id="XX", goal_id="CH.1")  # Different pillar
        workstreams = [make_workstream(goal_ids=["CH.1"])]

        score = calculate_workstream_relevance(card, workstreams)

        assert score == 0.4, "Goal match should score 0.4"

    def test_keyword_match_scores_0_5(self):
        """Single keyword match should add 0.5 to score."""
        card = make_card(name="AI technology", summary="Machine learning advances")
        workstreams = [make_workstream(keywords=["machine learning"])]

        score = calculate_workstream_relevance(card, workstreams)

        assert score == 0.5, "Keyword match should score 0.5"

    def test_keyword_match_case_insensitive(self):
        """Keyword matching should be case insensitive."""
        card = make_card(name="MACHINE LEARNING Test")
        workstreams = [make_workstream(keywords=["machine learning"])]

        score = calculate_workstream_relevance(card, workstreams)

        assert score == 0.5, "Keyword match should be case insensitive"

    def test_horizon_match_scores_0_3(self):
        """Horizon match should add 0.3 to score."""
        card = make_card(pillar_id="XX", horizon="H2")  # Only horizon matches
        workstreams = [make_workstream(horizon="H2")]

        score = calculate_workstream_relevance(card, workstreams)

        assert score == 0.3, "Horizon match should score 0.3"

    def test_horizon_all_does_not_match(self):
        """Horizon 'ALL' should not add points."""
        card = make_card(pillar_id="XX", horizon="H2")
        workstreams = [make_workstream(horizon="ALL")]

        score = calculate_workstream_relevance(card, workstreams)

        assert score == 0.0, "Horizon 'ALL' should not count as match"

    def test_combined_matches_accumulate(self):
        """Multiple match types should accumulate."""
        card = make_card(
            pillar_id="CH",
            goal_id="CH.1",
            horizon="H1",
            name="AI technology",
        )
        workstreams = [make_workstream(
            pillar_ids=["CH"],       # +0.3
            goal_ids=["CH.1"],       # +0.4
            keywords=["technology"], # +0.5
            horizon="H1",            # +0.3
        )]

        score = calculate_workstream_relevance(card, workstreams)

        # 0.3 + 0.4 + 0.5 + 0.3 = 1.5, capped at 1.0
        assert score == 1.0, "Combined score should cap at 1.0"

    def test_average_across_multiple_workstreams(self):
        """Score should be averaged across active workstreams."""
        card = make_card(pillar_id="CH")
        workstreams = [
            make_workstream(ws_id="ws-1", pillar_ids=["CH"]),  # 0.3
            make_workstream(ws_id="ws-2", pillar_ids=["MC"]),  # 0.0
        ]

        score = calculate_workstream_relevance(card, workstreams)

        # (0.3 + 0.0) / 2 = 0.15
        assert score == 0.15, "Score should be averaged across workstreams"

    def test_inactive_workstreams_ignored(self):
        """Inactive workstreams should not contribute to score."""
        card = make_card(pillar_id="MC")
        workstreams = [
            make_workstream(ws_id="ws-1", pillar_ids=["CH"], is_active=True),   # 0.0
            make_workstream(ws_id="ws-2", pillar_ids=["MC"], is_active=False),  # Ignored
        ]

        score = calculate_workstream_relevance(card, workstreams)

        assert score == 0.0, "Inactive workstreams should be ignored"

    def test_multiple_keyword_matches(self):
        """Multiple keyword matches should each contribute."""
        card = make_card(name="AI and ML", summary="Deep learning neural networks")
        workstreams = [make_workstream(keywords=["deep learning", "neural"])]

        score = calculate_workstream_relevance(card, workstreams)

        # 2 keywords * 0.5 = 1.0
        assert score == 1.0, "Multiple keywords should accumulate"

    def test_card_without_pillar_no_pillar_score(self):
        """Card without pillar_id should not get pillar score."""
        card = make_card(pillar_id=None)
        workstreams = [make_workstream(pillar_ids=["CH"])]

        score = calculate_workstream_relevance(card, workstreams)

        assert score == 0.0, "No pillar on card means no pillar score"

    def test_workstream_without_filters_returns_zero(self):
        """Workstream with no filter criteria should score 0."""
        card = make_card()
        workstreams = [make_workstream()]  # No filters set

        score = calculate_workstream_relevance(card, workstreams)

        assert score == 0.0


# ============================================================================
# PILLAR ALIGNMENT TESTS
# ============================================================================

class TestCalculatePillarAlignment:
    """Tests for calculate_pillar_alignment function."""

    def test_empty_workstreams_returns_zero(self):
        """No workstreams should return 0.0."""
        card = make_card(pillar_id="CH")

        score = calculate_pillar_alignment(card, [])

        assert score == 0.0

    def test_card_without_pillar_returns_zero(self):
        """Card without pillar_id should return 0.0."""
        card = make_card(pillar_id=None)
        workstreams = [make_workstream(pillar_ids=["CH"])]

        score = calculate_pillar_alignment(card, workstreams)

        assert score == 0.0

    def test_matching_pillar_returns_one(self):
        """Card with pillar matching any workstream should return 1.0."""
        card = make_card(pillar_id="CH")
        workstreams = [make_workstream(pillar_ids=["MC", "CH", "HG"])]

        score = calculate_pillar_alignment(card, workstreams)

        assert score == 1.0

    def test_no_matching_pillar_returns_zero(self):
        """Card with pillar not in any workstream should return 0.0."""
        card = make_card(pillar_id="PS")
        workstreams = [make_workstream(pillar_ids=["CH", "MC"])]

        score = calculate_pillar_alignment(card, workstreams)

        assert score == 0.0

    def test_matches_any_workstream(self):
        """Pillar match in any workstream should return 1.0."""
        card = make_card(pillar_id="MC")
        workstreams = [
            make_workstream(ws_id="ws-1", pillar_ids=["CH"]),
            make_workstream(ws_id="ws-2", pillar_ids=["MC"]),  # Match here
        ]

        score = calculate_pillar_alignment(card, workstreams)

        assert score == 1.0

    def test_inactive_workstreams_ignored(self):
        """Inactive workstreams should not be checked."""
        card = make_card(pillar_id="MC")
        workstreams = [
            make_workstream(ws_id="ws-1", pillar_ids=["CH"], is_active=True),
            make_workstream(ws_id="ws-2", pillar_ids=["MC"], is_active=False),  # Ignored
        ]

        score = calculate_pillar_alignment(card, workstreams)

        assert score == 0.0, "Inactive workstream match should be ignored"


# ============================================================================
# FOLLOWED CONTEXT TESTS
# ============================================================================

class TestCalculateFollowedContext:
    """Tests for calculate_followed_context function."""

    def test_empty_followed_cards_returns_zero(self):
        """No followed cards should return 0.0."""
        card = make_card()

        score = calculate_followed_context(card, [])

        assert score == 0.0

    def test_same_pillar_as_followed_scores_0_5(self):
        """Card in same pillar as followed card should add 0.5."""
        card = make_card(pillar_id="CH", goal_id="XX.1")  # Different goal
        followed = [make_followed_card(pillar_id="CH", goal_id="CH.2")]

        score = calculate_followed_context(card, followed)

        assert score == 0.5

    def test_same_goal_as_followed_scores_0_7(self):
        """Card with same goal as followed card should add 0.7."""
        card = make_card(pillar_id="XX", goal_id="CH.1")  # Different pillar
        followed = [make_followed_card(pillar_id="MC", goal_id="CH.1")]

        score = calculate_followed_context(card, followed)

        assert score == 0.7

    def test_both_pillar_and_goal_match(self):
        """Card matching both pillar and goal should score 1.0 (capped)."""
        card = make_card(pillar_id="CH", goal_id="CH.1")
        followed = [make_followed_card(pillar_id="CH", goal_id="CH.1")]

        score = calculate_followed_context(card, followed)

        # 0.5 + 0.7 = 1.2, capped at 1.0
        assert score == 1.0

    def test_multiple_followed_cards_with_match(self):
        """Match with any followed card should count."""
        card = make_card(pillar_id="MC", goal_id="MC.9")  # No goal match
        followed = [
            make_followed_card(card_id="f1", pillar_id="CH", goal_id="CH.1"),
            make_followed_card(card_id="f2", pillar_id="MC", goal_id="MC.2"),  # Pillar match only
        ]

        score = calculate_followed_context(card, followed)

        assert score == 0.5

    def test_no_matches_returns_zero(self):
        """Card not matching any followed card attributes should return 0.0."""
        card = make_card(pillar_id="PS", goal_id="PS.1")
        followed = [
            make_followed_card(pillar_id="CH", goal_id="CH.1"),
            make_followed_card(pillar_id="MC", goal_id="MC.2"),
        ]

        score = calculate_followed_context(card, followed)

        assert score == 0.0

    def test_card_without_pillar_no_pillar_score(self):
        """Card without pillar shouldn't match followed card pillars."""
        card = make_card(pillar_id=None, goal_id="CH.1")
        followed = [make_followed_card(pillar_id="CH", goal_id=None)]

        score = calculate_followed_context(card, followed)

        assert score == 0.0

    def test_followed_without_pillar_no_match(self):
        """Followed card without pillar shouldn't affect pillar matching."""
        card = make_card(pillar_id="CH")
        followed = [make_followed_card(pillar_id=None, goal_id=None)]

        score = calculate_followed_context(card, followed)

        assert score == 0.0


# ============================================================================
# COMBINED DISCOVERY SCORE TESTS
# ============================================================================

class TestCalculateDiscoveryScore:
    """Tests for calculate_discovery_score function."""

    def test_returns_correct_structure(self):
        """Should return dict with discovery_score and score_breakdown."""
        card = make_card()

        result = calculate_discovery_score(card, [], [], None)

        assert "discovery_score" in result
        assert "score_breakdown" in result
        assert isinstance(result["discovery_score"], float)
        assert isinstance(result["score_breakdown"], dict)

    def test_score_breakdown_contains_all_factors(self):
        """Score breakdown should include all 4 scoring factors."""
        card = make_card()

        result = calculate_discovery_score(card, [], [], None)
        breakdown = result["score_breakdown"]

        assert "novelty" in breakdown
        assert "workstream_relevance" in breakdown
        assert "pillar_alignment" in breakdown
        assert "followed_context" in breakdown
        assert "weights" in breakdown

    def test_weights_are_included(self):
        """Weights should be included in the breakdown."""
        card = make_card()

        result = calculate_discovery_score(card, [], [], None)
        weights = result["score_breakdown"]["weights"]

        assert weights["novelty"] == NOVELTY_WEIGHT
        assert weights["relevance"] == RELEVANCE_WEIGHT
        assert weights["alignment"] == ALIGNMENT_WEIGHT
        assert weights["context"] == CONTEXT_WEIGHT

    def test_weights_sum_to_one(self):
        """Scoring weights should sum to 1.0."""
        total_weight = NOVELTY_WEIGHT + RELEVANCE_WEIGHT + ALIGNMENT_WEIGHT + CONTEXT_WEIGHT

        assert total_weight == 1.0, f"Weights sum to {total_weight}, should be 1.0"

    def test_perfect_score_calculation(self):
        """Perfect scores in all factors should result in 1.0 total."""
        now = datetime.now(timezone.utc)
        card = make_card(
            created_at=now - timedelta(days=1),  # Recent = 1.0 novelty
            pillar_id="CH",
            goal_id="CH.1",
        )
        workstreams = [make_workstream(
            pillar_ids=["CH"],
            goal_ids=["CH.1"],
            keywords=["test"],
        )]
        followed = [make_followed_card(pillar_id="CH", goal_id="CH.1")]
        dismissed = set()

        result = calculate_discovery_score(card, workstreams, followed, dismissed)

        # With all perfect scores, weighted sum should approach 1.0
        # Novelty = 1.0 (capped), Relevance = 1.0 (capped), Alignment = 1.0, Context = 1.0
        assert result["discovery_score"] == 1.0

    def test_zero_score_when_no_context(self):
        """User with no workstreams or follows should still get novelty score."""
        now = datetime.now(timezone.utc)
        card = make_card(created_at=now - timedelta(days=1))

        result = calculate_discovery_score(card, [], [], None)

        # Only novelty contributes: 1.0 * 0.25 = 0.25
        expected = NOVELTY_WEIGHT * 1.0
        assert result["discovery_score"] == round(expected, 4)

    def test_dismissed_cards_affect_novelty_only(self):
        """Dismissed cards affect novelty score, not other factors."""
        now = datetime.now(timezone.utc)
        card = make_card(
            card_id="test-card",
            created_at=now - timedelta(days=15),  # Mid-age = 0.5
            pillar_id="CH",
        )
        workstreams = [make_workstream(pillar_ids=["CH"])]
        dismissed = {"test-card"}  # Card is dismissed

        result = calculate_discovery_score(card, workstreams, [], dismissed)
        breakdown = result["score_breakdown"]

        # Novelty should be 0.5 (no boost because dismissed)
        assert breakdown["novelty"] == 0.5
        # Alignment should still work
        assert breakdown["pillar_alignment"] == 1.0

    def test_scores_are_rounded(self):
        """Scores should be rounded to 4 decimal places."""
        card = make_card()

        result = calculate_discovery_score(card, [], [], None)

        # Check that discovery_score has at most 4 decimal places
        score_str = str(result["discovery_score"])
        if '.' in score_str:
            decimals = len(score_str.split('.')[1])
            assert decimals <= 4

    def test_individual_factor_contributions(self):
        """Test that each factor contributes correctly to final score."""
        now = datetime.now(timezone.utc)

        # Card that matches pillar only
        card = make_card(
            created_at=now - timedelta(days=60),  # Old = 0.2 novelty
            pillar_id="CH",
            goal_id="XX.1",  # No goal match
        )
        workstreams = [make_workstream(pillar_ids=["CH"])]

        result = calculate_discovery_score(card, workstreams, [], None)
        breakdown = result["score_breakdown"]

        # Verify individual scores
        assert breakdown["novelty"] == 0.2
        assert breakdown["pillar_alignment"] == 1.0
        assert breakdown["workstream_relevance"] == 0.3  # Pillar match only
        assert breakdown["followed_context"] == 0.0

        # Verify weighted sum
        expected = (
            NOVELTY_WEIGHT * 0.2 +
            RELEVANCE_WEIGHT * 0.3 +
            ALIGNMENT_WEIGHT * 1.0 +
            CONTEXT_WEIGHT * 0.0
        )
        assert result["discovery_score"] == round(expected, 4)


# ============================================================================
# EDGE CASES AND INTEGRATION TESTS
# ============================================================================

class TestScoringEdgeCases:
    """Edge cases and integration scenarios."""

    def test_null_values_handled_gracefully(self):
        """Functions should handle None/null values without crashing."""
        card = {
            "id": "test",
            "name": None,
            "summary": None,
            "pillar_id": None,
            "goal_id": None,
        }

        # Should not raise exceptions
        novelty = calculate_novelty_score(card)
        relevance = calculate_workstream_relevance(card, [])
        alignment = calculate_pillar_alignment(card, [])
        context = calculate_followed_context(card, [])
        combined = calculate_discovery_score(card, [], [], None)

        assert novelty >= 0
        assert relevance >= 0
        assert alignment >= 0
        assert context >= 0
        assert combined["discovery_score"] >= 0

    def test_empty_strings_not_matched(self):
        """Empty strings should not produce matches."""
        card = make_card(pillar_id="", goal_id="")
        workstreams = [make_workstream(pillar_ids=[""], goal_ids=[""])]

        relevance = calculate_workstream_relevance(card, workstreams)

        # Empty strings shouldn't match
        assert relevance == 0.0

    def test_special_characters_in_keywords(self):
        """Keywords with special characters should work."""
        card = make_card(name="C++ programming guide", summary="Learn C# and F#")
        workstreams = [make_workstream(keywords=["c++", "c#"])]

        score = calculate_workstream_relevance(card, workstreams)

        assert score >= 0.5, "Keywords with special chars should match"

    def test_very_long_keyword_list(self):
        """Many keywords should not cause issues."""
        card = make_card(name="Artificial intelligence", summary="Machine learning")
        keywords = [f"keyword{i}" for i in range(100)]
        keywords.append("artificial")  # One match
        workstreams = [make_workstream(keywords=keywords)]

        score = calculate_workstream_relevance(card, workstreams)

        assert score == 0.5  # One keyword match

    def test_unicode_characters(self):
        """Unicode characters should be handled properly."""
        card = make_card(name="日本語テスト", summary="Тест кириллицы")
        workstreams = [make_workstream(keywords=["日本語", "тест"])]

        score = calculate_workstream_relevance(card, workstreams)

        assert score >= 0.5

    def test_all_workstreams_inactive(self):
        """All inactive workstreams should result in zero scores."""
        card = make_card(pillar_id="CH")
        workstreams = [
            make_workstream(ws_id="ws-1", pillar_ids=["CH"], is_active=False),
            make_workstream(ws_id="ws-2", pillar_ids=["CH"], is_active=False),
        ]

        relevance = calculate_workstream_relevance(card, workstreams)
        alignment = calculate_pillar_alignment(card, workstreams)

        assert relevance == 0.0
        assert alignment == 0.0


class TestScoringRanking:
    """Tests to verify correct ranking behavior."""

    def test_more_matches_scores_higher(self):
        """Cards with more matches should score higher."""
        now = datetime.now(timezone.utc)

        # Card with many matches
        high_card = make_card(
            card_id="high",
            created_at=now,
            pillar_id="CH",
            goal_id="CH.1",
            name="AI technology",
        )

        # Card with few matches
        low_card = make_card(
            card_id="low",
            created_at=now - timedelta(days=60),
            pillar_id="PS",
            goal_id="PS.1",
            name="Random stuff",
        )

        workstreams = [make_workstream(
            pillar_ids=["CH"],
            goal_ids=["CH.1"],
            keywords=["technology"],
        )]
        followed = [make_followed_card(pillar_id="CH", goal_id="CH.1")]

        high_result = calculate_discovery_score(high_card, workstreams, followed, set())
        low_result = calculate_discovery_score(low_card, workstreams, followed, set())

        assert high_result["discovery_score"] > low_result["discovery_score"]

    def test_consistent_ordering(self):
        """Same inputs should produce same scores."""
        card = make_card()
        workstreams = [make_workstream(pillar_ids=["CH"])]

        result1 = calculate_discovery_score(card, workstreams, [], None)
        result2 = calculate_discovery_score(card, workstreams, [], None)

        assert result1["discovery_score"] == result2["discovery_score"]


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
