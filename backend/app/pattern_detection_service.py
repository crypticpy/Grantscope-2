"""
Cross-Signal Pattern Detection Service for Foresight Application.

This service discovers emergent connections across signals (cards) that span
different strategic pillars. It uses vector embedding similarity to find
semantically related signals from different domains, then asks an LLM to
synthesize actionable insights from each cross-pillar cluster.

Pipeline:
1. Fetch active cards with embeddings (max 200 per run)
2. Compute pairwise cosine similarity across different pillars
3. Build clusters of cross-pillar connections (similarity > 0.7, < 0.95)
4. For each cluster, use GPT to synthesize a pattern insight
5. Deduplicate against existing active insights
6. Store new insights in pattern_insights table

Usage:
    service = PatternDetectionService(supabase, openai_client)
    results = await service.run_detection()
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

import numpy as np
from supabase import Client

from app.openai_provider import get_chat_deployment

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MAX_CARDS_PER_RUN = 200
SIMILARITY_LOWER = 0.70  # Minimum similarity to consider a cross-pillar link
SIMILARITY_UPPER = 0.95  # Maximum similarity (above this = likely duplicate)
MIN_CLUSTER_SIZE = 2  # Minimum cards to form a cluster
MAX_CLUSTER_SIZE = 6  # Cap cluster size sent to LLM to control token cost
MAX_INSIGHTS_PER_RUN = 15  # Don't generate more than this many insights per run
REQUEST_TIMEOUT = 90  # seconds per LLM call
DEDUP_TITLE_SIMILARITY = 0.85  # Cosine similarity threshold for deduplicating insights

STRATEGIC_PILLARS = ["CH", "MC", "HS", "EC", "ES", "CE"]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class CardSignal:
    """A card with its embedding and metadata for pattern detection."""

    id: str
    name: str
    summary: str
    pillar_id: str
    stage_id: Optional[str] = None
    horizon: Optional[str] = None
    embedding: Optional[List[float]] = None


@dataclass
class CrossPillarLink:
    """A pair of cards from different pillars with high semantic similarity."""

    card_a: CardSignal
    card_b: CardSignal
    similarity: float


@dataclass
class SignalCluster:
    """A group of cross-pillar connected cards forming a pattern."""

    cards: List[CardSignal] = field(default_factory=list)
    pillars: set = field(default_factory=set)
    avg_similarity: float = 0.0


@dataclass
class PatternInsight:
    """An AI-generated insight from a cluster of cross-pillar signals."""

    pattern_title: str
    pattern_summary: str
    opportunity: str
    confidence: float
    affected_pillars: List[str]
    urgency: str
    related_card_ids: List[str]


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class PatternDetectionService:
    """Detects emergent cross-pillar patterns across strategic signals."""

    def __init__(self, supabase_client: Client, openai_client: Any) -> None:
        self.supabase = supabase_client
        self.openai = openai_client

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    async def run_detection(self) -> Dict[str, Any]:
        """
        Execute the full pattern detection pipeline.

        Returns:
            Summary dict with counts and timing info.
        """
        start = time.time()
        logger.info("Pattern detection run starting")

        # Step 1: Fetch cards
        cards = self._fetch_cards_with_embeddings()
        if len(cards) < MIN_CLUSTER_SIZE:
            logger.info(
                "Not enough cards with embeddings for pattern detection (%d)",
                len(cards),
            )
            return {
                "status": "skipped",
                "reason": "insufficient_cards",
                "card_count": len(cards),
            }

        logger.info(
            "Fetched %d cards with embeddings across %d pillars",
            len(cards),
            len({c.pillar_id for c in cards}),
        )

        # Step 2: Find cross-pillar links
        links = self._find_cross_pillar_links(cards)
        logger.info("Found %d cross-pillar links", len(links))

        if not links:
            return {
                "status": "completed",
                "insights_generated": 0,
                "reason": "no_cross_pillar_links",
                "duration_seconds": time.time() - start,
            }

        # Step 3: Build clusters from links
        clusters = self._build_clusters(links)
        logger.info("Built %d signal clusters", len(clusters))

        # Step 4: Generate insights via LLM (limit to MAX_INSIGHTS_PER_RUN)
        clusters_to_process = clusters[:MAX_INSIGHTS_PER_RUN]
        insights = await self._generate_insights(clusters_to_process)
        logger.info("Generated %d pattern insights", len(insights))

        # Step 5: Deduplicate against existing insights
        new_insights = self._deduplicate_insights(insights)
        logger.info("After dedup: %d new insights", len(new_insights))

        # Step 6: Store in database
        stored_count = self._store_insights(new_insights)

        duration = time.time() - start
        summary = {
            "status": "completed",
            "cards_analyzed": len(cards),
            "cross_pillar_links": len(links),
            "clusters_found": len(clusters),
            "insights_generated": len(insights),
            "insights_stored": stored_count,
            "duration_seconds": round(duration, 2),
        }
        logger.info("Pattern detection completed: %s", summary)
        return summary

    # -----------------------------------------------------------------------
    # Step 1: Fetch cards
    # -----------------------------------------------------------------------

    def _fetch_cards_with_embeddings(self) -> List[CardSignal]:
        """Fetch active cards that have embeddings, limited to MAX_CARDS_PER_RUN."""
        try:
            result = (
                self.supabase.table("cards")
                .select("id, name, summary, pillar_id, stage_id, horizon, embedding")
                .eq("status", "active")
                .neq("review_status", "rejected")
                .not_.is_("embedding", "null")
                .not_.is_("pillar_id", "null")
                .limit(MAX_CARDS_PER_RUN)
                .execute()
            )
            cards_data = result.data or []
        except Exception as e:
            logger.error("Failed to fetch cards for pattern detection: %s", e)
            return []

        cards: List[CardSignal] = []
        for row in cards_data:
            embedding = row.get("embedding")
            if not embedding:
                continue
            # Embedding may come as a list or a string representation
            if isinstance(embedding, str):
                try:
                    embedding = json.loads(embedding)
                except (json.JSONDecodeError, ValueError):
                    continue

            cards.append(
                CardSignal(
                    id=row["id"],
                    name=row["name"],
                    summary=row.get("summary", ""),
                    pillar_id=row.get("pillar_id", ""),
                    stage_id=row.get("stage_id"),
                    horizon=row.get("horizon"),
                    embedding=embedding,
                )
            )
        return cards

    # -----------------------------------------------------------------------
    # Step 2: Cross-pillar similarity
    # -----------------------------------------------------------------------

    def _find_cross_pillar_links(
        self, cards: List[CardSignal]
    ) -> List[CrossPillarLink]:
        """
        Compute cosine similarity between cards from DIFFERENT pillars.
        Returns pairs with similarity in (SIMILARITY_LOWER, SIMILARITY_UPPER).
        """
        if not cards:
            return []

        # Group cards by pillar
        pillar_groups: Dict[str, List[CardSignal]] = {}
        for card in cards:
            pillar_groups.setdefault(card.pillar_id, []).append(card)

        pillars = list(pillar_groups.keys())
        if len(pillars) < 2:
            logger.info(
                "Cards span only %d pillar(s); need at least 2 for cross-pillar detection",
                len(pillars),
            )
            return []

        links: List[CrossPillarLink] = []

        # Compare each pillar pair
        for i in range(len(pillars)):
            for j in range(i + 1, len(pillars)):
                pillar_a, pillar_b = pillars[i], pillars[j]
                cards_a = pillar_groups[pillar_a]
                cards_b = pillar_groups[pillar_b]

                # Vectorized similarity computation
                emb_a = np.array([c.embedding for c in cards_a])
                emb_b = np.array([c.embedding for c in cards_b])

                # Normalize embeddings
                norms_a = np.linalg.norm(emb_a, axis=1, keepdims=True)
                norms_b = np.linalg.norm(emb_b, axis=1, keepdims=True)
                # Avoid division by zero
                norms_a = np.where(norms_a == 0, 1, norms_a)
                norms_b = np.where(norms_b == 0, 1, norms_b)
                emb_a_norm = emb_a / norms_a
                emb_b_norm = emb_b / norms_b

                # Cosine similarity matrix: (len_a, len_b)
                sim_matrix = emb_a_norm @ emb_b_norm.T

                # Extract qualifying pairs
                for ai in range(len(cards_a)):
                    for bi in range(len(cards_b)):
                        sim = float(sim_matrix[ai, bi])
                        if SIMILARITY_LOWER < sim < SIMILARITY_UPPER:
                            links.append(
                                CrossPillarLink(
                                    card_a=cards_a[ai],
                                    card_b=cards_b[bi],
                                    similarity=sim,
                                )
                            )

        # Sort by similarity descending
        links.sort(key=lambda x: x.similarity, reverse=True)
        return links

    # -----------------------------------------------------------------------
    # Step 3: Cluster building (greedy union-find)
    # -----------------------------------------------------------------------

    def _build_clusters(self, links: List[CrossPillarLink]) -> List[SignalCluster]:
        """
        Build clusters of connected signals using a union-find approach.
        Each cluster spans at least 2 pillars.
        """
        # Union-Find structure
        parent: Dict[str, str] = {}

        def find(x: str) -> str:
            while parent.get(x, x) != x:
                parent[x] = parent.get(parent[x], parent[x])
                x = parent[x]
            return x

        def union(a: str, b: str) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        # Card lookup
        card_map: Dict[str, CardSignal] = {}
        similarity_sum: Dict[str, float] = {}
        similarity_count: Dict[str, int] = {}

        for link in links:
            card_map[link.card_a.id] = link.card_a
            card_map[link.card_b.id] = link.card_b
            parent.setdefault(link.card_a.id, link.card_a.id)
            parent.setdefault(link.card_b.id, link.card_b.id)
            union(link.card_a.id, link.card_b.id)

            root = find(link.card_a.id)
            similarity_sum[root] = similarity_sum.get(root, 0.0) + link.similarity
            similarity_count[root] = similarity_count.get(root, 0) + 1

        # Group by root
        groups: Dict[str, List[str]] = {}
        for card_id in card_map:
            root = find(card_id)
            groups.setdefault(root, []).append(card_id)

        clusters: List[SignalCluster] = []
        for root, card_ids in groups.items():
            cards = [card_map[cid] for cid in card_ids]
            pillars = {c.pillar_id for c in cards}

            # Must span at least 2 pillars
            if len(pillars) < 2:
                continue
            if len(cards) < MIN_CLUSTER_SIZE:
                continue

            # Cap cluster size -- take highest-connected cards
            if len(cards) > MAX_CLUSTER_SIZE:
                # Sort by number of links (approximated by picking diverse pillars)
                cards = self._select_representative_cards(cards, MAX_CLUSTER_SIZE)

            final_root = find(root)
            avg_sim = similarity_sum.get(final_root, 0.0) / max(
                similarity_count.get(final_root, 1), 1
            )

            clusters.append(
                SignalCluster(
                    cards=cards,
                    pillars=pillars,
                    avg_similarity=round(avg_sim, 3),
                )
            )

        # Sort clusters by number of pillars (more diverse = more interesting), then by avg similarity
        clusters.sort(key=lambda c: (len(c.pillars), c.avg_similarity), reverse=True)
        return clusters

    def _select_representative_cards(
        self, cards: List[CardSignal], max_count: int
    ) -> List[CardSignal]:
        """Select a diverse subset of cards ensuring pillar coverage."""
        # First, take one card per pillar
        pillar_seen: Dict[str, CardSignal] = {}
        remaining: List[CardSignal] = []
        for card in cards:
            if card.pillar_id not in pillar_seen:
                pillar_seen[card.pillar_id] = card
            else:
                remaining.append(card)

        selected = list(pillar_seen.values())
        if len(selected) >= max_count:
            return selected[:max_count]

        # Fill remaining slots
        for card in remaining:
            if len(selected) >= max_count:
                break
            selected.append(card)

        return selected

    # -----------------------------------------------------------------------
    # Step 4: LLM insight generation
    # -----------------------------------------------------------------------

    async def _generate_insights(
        self, clusters: List[SignalCluster]
    ) -> List[PatternInsight]:
        """Generate LLM-synthesized insights for each cluster."""
        insights: List[PatternInsight] = []

        for cluster in clusters:
            try:
                insight = await self._synthesize_cluster_insight(cluster)
                if insight:
                    insights.append(insight)
            except Exception as e:
                logger.error(
                    "Failed to synthesize insight for cluster (%d cards): %s",
                    len(cluster.cards),
                    e,
                )
                continue

        return insights

    async def _synthesize_cluster_insight(
        self, cluster: SignalCluster
    ) -> Optional[PatternInsight]:
        """Ask the LLM to identify the cross-domain pattern in a signal cluster."""
        signal_summaries = self._format_signal_summaries(cluster)
        card_ids = [c.id for c in cluster.cards]
        pillar_list = sorted(cluster.pillars)

        prompt = f"""You are a strategic foresight analyst for the City of Austin.

These signals come from different strategic pillars but appear connected:

{signal_summaries}

Identify the cross-domain pattern or opportunity:
1. What connects these signals?
2. What emerging opportunity or risk does this convergence create for Austin?
3. What specific action should the city consider?

Respond as JSON:
{{
  "pattern_title": "Short title (max 100 chars)",
  "pattern_summary": "2-3 sentence explanation of the connection",
  "opportunity": "What Austin should do about this",
  "confidence": 0.0-1.0,
  "affected_pillars": {json.dumps(pillar_list)},
  "urgency": "high|medium|low"
}}"""

        try:
            response = self.openai.chat.completions.create(
                model=get_chat_deployment(),
                messages=[
                    {
                        "role": "system",
                        "content": "You are a strategic foresight analyst. Respond only with valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                max_tokens=500,
                temperature=0.7,
                timeout=REQUEST_TIMEOUT,
            )
        except Exception as e:
            logger.error("OpenAI API error during pattern synthesis: %s", e)
            return None

        try:
            result = json.loads(response.choices[0].message.content)
        except (json.JSONDecodeError, IndexError, AttributeError) as e:
            logger.error("Failed to parse LLM pattern response: %s", e)
            return None

        # Validate and clamp confidence
        confidence = float(result.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))

        urgency = result.get("urgency", "medium")
        if urgency not in ("high", "medium", "low"):
            urgency = "medium"

        title = str(result.get("pattern_title", ""))[:100]
        if not title:
            return None

        return PatternInsight(
            pattern_title=title,
            pattern_summary=str(result.get("pattern_summary", "")),
            opportunity=str(result.get("opportunity", "")),
            confidence=confidence,
            affected_pillars=result.get("affected_pillars", pillar_list),
            urgency=urgency,
            related_card_ids=card_ids,
        )

    def _format_signal_summaries(self, cluster: SignalCluster) -> str:
        """Format cluster cards as a numbered list for the LLM prompt."""
        parts: List[str] = []
        for i, card in enumerate(cluster.cards, 1):
            pillar = card.pillar_id or "Unknown"
            horizon = card.horizon or "N/A"
            summary = (card.summary or "No summary")[:300]
            parts.append(
                f"{i}. [{pillar}] {card.name}\n"
                f"   Horizon: {horizon}\n"
                f"   Summary: {summary}"
            )
        return "\n\n".join(parts)

    # -----------------------------------------------------------------------
    # Step 5: Deduplication
    # -----------------------------------------------------------------------

    def _deduplicate_insights(
        self, insights: List[PatternInsight]
    ) -> List[PatternInsight]:
        """
        Remove insights that are too similar to existing active patterns.
        Uses card overlap as the primary dedup signal.
        """
        if not insights:
            return []

        # Fetch existing active insights
        try:
            existing = (
                self.supabase.table("pattern_insights")
                .select("id, pattern_title, related_card_ids")
                .eq("status", "active")
                .execute()
                .data
                or []
            )
        except Exception as e:
            logger.warning("Could not fetch existing insights for dedup: %s", e)
            existing = []

        existing_card_sets = [set(row.get("related_card_ids", [])) for row in existing]

        new_insights: List[PatternInsight] = []
        for insight in insights:
            insight_cards = set(insight.related_card_ids)
            is_duplicate = False

            for existing_set in existing_card_sets:
                if not existing_set:
                    continue
                # Jaccard similarity on card IDs
                intersection = len(insight_cards & existing_set)
                union_size = len(insight_cards | existing_set)
                if union_size > 0 and (intersection / union_size) > 0.5:
                    is_duplicate = True
                    break

            if not is_duplicate:
                new_insights.append(insight)
                # Also add this to existing sets so we don't generate duplicates
                # within the same run
                existing_card_sets.append(insight_cards)

        return new_insights

    # -----------------------------------------------------------------------
    # Step 6: Storage
    # -----------------------------------------------------------------------

    def _store_insights(self, insights: List[PatternInsight]) -> int:
        """Store pattern insights in the database. Returns count of stored insights."""
        stored = 0
        for insight in insights:
            try:
                row = {
                    "pattern_title": insight.pattern_title,
                    "pattern_summary": insight.pattern_summary,
                    "opportunity": insight.opportunity,
                    "confidence": insight.confidence,
                    "affected_pillars": insight.affected_pillars,
                    "urgency": insight.urgency,
                    "related_card_ids": insight.related_card_ids,
                    "status": "active",
                }
                self.supabase.table("pattern_insights").insert(row).execute()
                stored += 1
            except Exception as e:
                logger.error(
                    "Failed to store pattern insight '%s': %s", insight.pattern_title, e
                )
        return stored
