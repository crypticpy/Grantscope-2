"""
Grant-Program Alignment Scoring Service for GrantScope2.

Scores how well a grant opportunity (card) matches a program (workstream) using
six independent factors.  All scoring is heuristic-based -- no external API calls
are made.  The service is stateless and can be instantiated freely.

Scoring Factors
---------------
    fit          (0.25) - Category, keyword, and pillar overlap
    amount       (0.15) - Funding range vs. program budget
    competition  (0.15) - Heuristic competitiveness estimate
    readiness    (0.15) - Program preparedness indicators
    urgency      (0.15) - Days remaining until deadline
    probability  (0.15) - Composite modifier derived from all factors

Each factor produces a sub-score in the range [0, 100].  The overall score
is a weighted average (also 0-100) that drives the recommended action.

Usage
-----
    from app.alignment_service import score_alignment, AlignmentService

    result = await score_alignment(card_dict, workstream_dict)
    print(result.overall_score, result.recommended_action)

    # Batch scoring
    svc = AlignmentService()
    ranked = await svc.score_grants_for_program(cards, workstream)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Tuple

from app.taxonomy import ALIGNMENT_SCORE_FACTORS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class AlignmentResult:
    """Result of scoring a single grant against a program."""

    fit_score: int = 0
    amount_score: int = 0
    competition_score: int = 0
    readiness_score: int = 0
    urgency_score: int = 0
    probability_score: int = 0
    overall_score: int = 0
    explanation: Dict[str, str] = field(default_factory=dict)
    recommended_action: str = "review"


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class AlignmentService:
    """Heuristic alignment scorer -- no external dependencies."""

    # Weight mapping derived from taxonomy constants.
    # Kept as class-level for clarity; mirrors ALIGNMENT_SCORE_FACTORS.
    _WEIGHTS: Dict[str, float] = {
        "fit": float(ALIGNMENT_SCORE_FACTORS["fit"]["weight"]),
        "amount": float(ALIGNMENT_SCORE_FACTORS["amount"]["weight"]),
        "competition": float(ALIGNMENT_SCORE_FACTORS["competition"]["weight"]),
        "readiness": float(ALIGNMENT_SCORE_FACTORS["readiness"]["weight"]),
        "urgency": float(ALIGNMENT_SCORE_FACTORS["urgency"]["weight"]),
        "probability": float(ALIGNMENT_SCORE_FACTORS["probability"]["weight"]),
    }

    # Base competition scores by grant type (higher = less competitive = better
    # chance of winning).
    _COMPETITION_BASE: Dict[str, int] = {
        "federal": 40,
        "state": 55,
        "foundation": 65,
        "local": 70,
    }

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    async def score_grant_against_program(
        self,
        card: dict,
        workstream: dict,
    ) -> AlignmentResult:
        """Score a single grant card against a program workstream.

        Args:
            card: Database row dict with grant fields (category_id,
                funding_amount_min/max, deadline, grantor, eligibility_text,
                grant_type, etc.).
            workstream: Database row dict with program fields (keywords,
                pillar_ids, category_ids, budget, department_id, etc.).

        Returns:
            Populated ``AlignmentResult``.
        """
        fit, fit_expl = self._score_fit(card, workstream)
        amount, amount_expl = self._score_amount(card, workstream)
        competition, comp_expl = self._score_competition(card)
        readiness, ready_expl = self._score_readiness(workstream)
        urgency, urg_expl = self._score_urgency(card)

        sub_scores = {
            "fit": fit,
            "amount": amount,
            "competition": competition,
            "readiness": readiness,
            "urgency": urgency,
        }

        probability, prob_expl = self._calculate_probability(sub_scores)

        # Weighted overall (includes probability as its own factor)
        overall_raw = (
            self._WEIGHTS["fit"] * fit
            + self._WEIGHTS["amount"] * amount
            + self._WEIGHTS["competition"] * competition
            + self._WEIGHTS["readiness"] * readiness
            + self._WEIGHTS["urgency"] * urgency
            + self._WEIGHTS["probability"] * probability
        )
        overall = max(0, min(100, round(overall_raw)))

        action = self._determine_action(overall)

        return AlignmentResult(
            fit_score=fit,
            amount_score=amount,
            competition_score=competition,
            readiness_score=readiness,
            urgency_score=urgency,
            probability_score=probability,
            overall_score=overall,
            explanation={
                "fit": fit_expl,
                "amount": amount_expl,
                "competition": comp_expl,
                "readiness": ready_expl,
                "urgency": urg_expl,
                "probability": prob_expl,
            },
            recommended_action=action,
        )

    async def score_grants_for_program(
        self,
        cards: list[dict],
        workstream: dict,
    ) -> list[tuple[dict, AlignmentResult]]:
        """Score multiple grants against one program.

        Returns a list of ``(card, result)`` tuples sorted by
        ``overall_score`` descending.
        """
        results: list[tuple[dict, AlignmentResult]] = []
        for card in cards:
            result = await self.score_grant_against_program(card, workstream)
            results.append((card, result))

        results.sort(key=lambda pair: pair[1].overall_score, reverse=True)
        return results

    # ------------------------------------------------------------------
    # Individual scoring factors
    # ------------------------------------------------------------------

    def _score_fit(self, card: dict, workstream: dict) -> Tuple[int, str]:
        """Score category, keyword, and pillar overlap.

        Returns:
            ``(score, explanation)`` where score is 0-100.
        """
        score = 0
        reasons: list[str] = []

        # --- Category overlap ---
        card_category = card.get("category_id") or ""
        ws_categories = workstream.get("category_ids") or []
        if card_category and ws_categories:
            if card_category in ws_categories:
                score += 40
                reasons.append(f"Category '{card_category}' matches program categories")
            else:
                reasons.append(f"Category '{card_category}' not in program categories")
        elif not ws_categories:
            # No categories set on workstream -- neutral
            score += 15
            reasons.append("Program has no category filters set")

        # --- Keyword overlap ---
        ws_keywords = workstream.get("keywords") or []
        if ws_keywords:
            card_text = " ".join(
                filter(
                    None,
                    [
                        (card.get("name") or "").lower(),
                        (card.get("summary") or "").lower(),
                    ],
                )
            )
            if card_text:
                matched = [kw for kw in ws_keywords if kw.lower() in card_text]
                if matched:
                    keyword_score = min(30, len(matched) * 10)
                    score += keyword_score
                    reasons.append(
                        f"Matched {len(matched)} keyword(s): {', '.join(matched[:5])}"
                    )
                else:
                    reasons.append("No keyword matches found in grant title/summary")
            else:
                reasons.append("Grant has no title or summary text")
        else:
            score += 10
            reasons.append("Program has no keywords set")

        # --- Pillar overlap ---
        card_pillar = card.get("pillar_id") or ""
        ws_pillars = workstream.get("pillar_ids") or []
        if card_pillar and ws_pillars:
            if card_pillar in ws_pillars:
                score += 30
                reasons.append(f"Pillar '{card_pillar}' matches program pillars")
            else:
                reasons.append(f"Pillar '{card_pillar}' not in program pillars")
        elif not ws_pillars:
            score += 10
            reasons.append("Program has no pillar filters set")

        score = max(0, min(100, score))
        explanation = "; ".join(reasons) if reasons else "No fit data available"
        return score, explanation

    def _score_amount(self, card: dict, workstream: dict) -> Tuple[int, str]:
        """Compare grant funding range against program budget.

        Returns:
            ``(score, explanation)`` where score is 0-100.
        """
        budget = workstream.get("budget")
        if not budget:
            return 50, "Program budget not set; neutral score"

        try:
            budget = float(budget)
        except (TypeError, ValueError):
            return 50, "Program budget is not a valid number; neutral score"

        if budget <= 0:
            return 50, "Program budget is zero or negative; neutral score"

        funding_min = card.get("funding_amount_min")
        funding_max = card.get("funding_amount_max")

        # Attempt to get a representative funding figure
        if funding_max is not None and funding_min is not None:
            try:
                funding = (float(funding_min) + float(funding_max)) / 2.0
            except (TypeError, ValueError):
                return 50, "Grant funding amounts are not valid numbers; neutral score"
        elif funding_max is not None:
            try:
                funding = float(funding_max)
            except (TypeError, ValueError):
                return 50, "Grant funding amount is not a valid number; neutral score"
        elif funding_min is not None:
            try:
                funding = float(funding_min)
            except (TypeError, ValueError):
                return 50, "Grant funding amount is not a valid number; neutral score"
        else:
            return 50, "Grant funding amount not specified; neutral score"

        if funding <= 0:
            return 30, "Grant funding amount is zero or negative"

        ratio = funding / budget  # e.g. 1.0 means exact match

        # Sweet spot: funding is 50%-200% of budget
        if 0.5 <= ratio <= 2.0:
            # Perfect match at ratio == 1.0 => 100
            # Edges of range (0.5 or 2.0) => ~70
            closeness = 1.0 - abs(ratio - 1.0)  # 0..1 where 1 is exact
            score = round(70 + closeness * 30)
            explanation = (
                f"Funding ~${funding:,.0f} is {ratio:.0%} of budget "
                f"${budget:,.0f} (good match)"
            )
        elif ratio < 0.5:
            score = max(10, round(ratio * 100))
            explanation = (
                f"Funding ~${funding:,.0f} is only {ratio:.0%} of budget "
                f"${budget:,.0f} (too small)"
            )
        else:  # ratio > 2.0
            # Gradually decrease but not too harshly -- larger grants still useful
            score = max(30, round(100 - (ratio - 2.0) * 15))
            score = min(70, score)
            explanation = (
                f"Funding ~${funding:,.0f} is {ratio:.0%} of budget "
                f"${budget:,.0f} (larger than needed)"
            )

        return max(0, min(100, score)), explanation

    def _score_competition(self, card: dict) -> Tuple[int, str]:
        """Heuristic competitiveness score.

        Higher score means *better* chance of winning (lower competition).

        Returns:
            ``(score, explanation)`` where score is 0-100.
        """
        grant_type = (card.get("grant_type") or "").lower()
        base = self._COMPETITION_BASE.get(grant_type, 50)
        reasons: list[str] = []

        if grant_type in self._COMPETITION_BASE:
            reasons.append(f"{grant_type.title()} grant (base score {base})")
        else:
            reasons.append("Unknown grant type; using default base score 50")

        # Adjust for funding amount -- higher amounts attract more applicants
        adjustment = 0
        funding_max = card.get("funding_amount_max")
        if funding_max is not None:
            try:
                amount = float(funding_max)
                if amount > 10_000_000:
                    adjustment = -15
                    reasons.append("Very large grant (>$10M); highly competitive")
                elif amount > 1_000_000:
                    adjustment = -10
                    reasons.append("Large grant (>$1M); increased competition")
                elif amount > 500_000:
                    adjustment = -5
                    reasons.append("Medium grant (>$500K); moderate competition")
                elif amount < 50_000:
                    adjustment = 10
                    reasons.append("Small grant (<$50K); less competition")
            except (TypeError, ValueError):
                pass

        score = max(0, min(100, base + adjustment))
        explanation = "; ".join(reasons)
        return score, explanation

    def _score_readiness(self, workstream: dict) -> Tuple[int, str]:
        """Score program readiness based on profile completeness.

        Returns:
            ``(score, explanation)`` where score is 0-100.
        """
        # Use pre-computed readiness if available
        existing_readiness = workstream.get("readiness_score")
        if existing_readiness is not None:
            try:
                val = int(existing_readiness)
                if 0 <= val <= 100:
                    return val, f"Using program readiness assessment score: {val}"
            except (TypeError, ValueError):
                pass

        score = 0
        reasons: list[str] = []

        # Department assigned: +20 baseline
        if workstream.get("department_id"):
            score += 20
            reasons.append("Department assigned (+20)")
        else:
            reasons.append("No department assigned")

        # Budget set: +15
        budget = workstream.get("budget")
        if budget is not None:
            try:
                if float(budget) > 0:
                    score += 15
                    reasons.append("Budget defined (+15)")
                else:
                    reasons.append("Budget is zero or negative")
            except (TypeError, ValueError):
                reasons.append("Budget is not a valid number")
        else:
            reasons.append("No budget set")

        # Keywords set: +15
        keywords = workstream.get("keywords") or []
        if keywords:
            score += 15
            reasons.append(f"Keywords defined ({len(keywords)} keyword(s)) (+15)")
        else:
            reasons.append("No keywords set")

        # Category IDs set: +10
        if workstream.get("category_ids"):
            score += 10
            reasons.append("Categories defined (+10)")

        # Pillar IDs set: +10
        if workstream.get("pillar_ids"):
            score += 10
            reasons.append("Pillars defined (+10)")

        # If nothing useful is set, default to 50 as neutral
        if score == 0:
            score = 50
            reasons = ["Minimal program info available; neutral score"]

        score = max(0, min(100, score))
        explanation = "; ".join(reasons)
        return score, explanation

    def _score_urgency(self, card: dict) -> Tuple[int, str]:
        """Score based on days remaining until the grant deadline.

        Returns:
            ``(score, explanation)`` where score is 0-100.
        """
        deadline_raw = card.get("deadline")
        if not deadline_raw:
            return 30, "No deadline specified; uncertain urgency"

        try:
            if isinstance(deadline_raw, str):
                deadline = datetime.fromisoformat(deadline_raw.replace("Z", "+00:00"))
            elif isinstance(deadline_raw, datetime):
                deadline = deadline_raw
            else:
                return 30, "Deadline format not recognized; uncertain urgency"
        except (ValueError, TypeError):
            return 30, "Could not parse deadline; uncertain urgency"

        now = datetime.now(timezone.utc)
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)

        days_remaining = (deadline - now).days

        if days_remaining < 0:
            return 0, f"Deadline passed {abs(days_remaining)} day(s) ago"
        elif days_remaining < 7:
            return 95, f"Critical: only {days_remaining} day(s) remaining"
        elif days_remaining < 14:
            return 85, f"Urgent: {days_remaining} days remaining"
        elif days_remaining < 30:
            return 70, f"Approaching: {days_remaining} days remaining"
        elif days_remaining < 45:
            return 55, f"{days_remaining} days remaining"
        elif days_remaining < 90:
            return 40, f"{days_remaining} days remaining; moderate timeline"
        else:
            return 25, f"{days_remaining} days remaining; plenty of time"

    # ------------------------------------------------------------------
    # Composite probability
    # ------------------------------------------------------------------

    def _calculate_probability(self, scores: dict) -> Tuple[int, str]:
        """Derive a composite probability score from the sub-scores.

        The probability factor uses the remaining 0.15 weight as a modifier.
        It computes a weighted blend of the other five scores and then
        applies caps when critical factors are too low.

        Returns:
            ``(score, explanation)`` where score is 0-100.
        """
        # Weighted blend of the five input factors (normalised to sum to 1.0
        # since we exclude the probability factor's own weight).
        weight_sum = (
            self._WEIGHTS["fit"]
            + self._WEIGHTS["amount"]
            + self._WEIGHTS["competition"]
            + self._WEIGHTS["readiness"]
            + self._WEIGHTS["urgency"]
        )
        if weight_sum == 0:
            weight_sum = 1.0  # safety

        raw = (
            self._WEIGHTS["fit"] * scores.get("fit", 0)
            + self._WEIGHTS["amount"] * scores.get("amount", 0)
            + self._WEIGHTS["competition"] * scores.get("competition", 0)
            + self._WEIGHTS["readiness"] * scores.get("readiness", 0)
            + self._WEIGHTS["urgency"] * scores.get("urgency", 0)
        ) / weight_sum

        probability = round(raw)
        reasons: list[str] = []
        reasons.append(f"Weighted blend of sub-scores: {probability}")

        # Apply caps for critically low factors
        fit_score = scores.get("fit", 0)
        readiness_score = scores.get("readiness", 0)

        if fit_score < 20:
            capped = min(probability, 30)
            if capped < probability:
                reasons.append(
                    f"Fit score too low ({fit_score}); capped probability at 30"
                )
                probability = capped

        if readiness_score < 20:
            capped = min(probability, 40)
            if capped < probability:
                reasons.append(
                    f"Readiness score too low ({readiness_score}); capped probability at 40"
                )
                probability = capped

        probability = max(0, min(100, probability))
        explanation = "; ".join(reasons)
        return probability, explanation

    # ------------------------------------------------------------------
    # Action determination
    # ------------------------------------------------------------------

    @staticmethod
    def _determine_action(overall_score: int) -> str:
        """Map overall score to a recommended action label.

        Returns:
            One of ``"strong_match"``, ``"good_match"``, ``"review"``,
            or ``"skip"``.
        """
        if overall_score >= 70:
            return "strong_match"
        elif overall_score >= 50:
            return "good_match"
        elif overall_score >= 30:
            return "review"
        else:
            return "skip"


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------


async def score_alignment(card: dict, workstream: dict) -> AlignmentResult:
    """Convenience wrapper: create a service instance and score one grant.

    Args:
        card: Database row dict with grant fields.
        workstream: Database row dict with program fields.

    Returns:
        Populated ``AlignmentResult``.
    """
    service = AlignmentService()
    return await service.score_grant_against_program(card, workstream)
