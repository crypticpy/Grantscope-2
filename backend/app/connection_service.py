"""
Signal connection discovery service.

Automatically finds and creates connections between related signals
based on embedding similarity and LLM-classified relationship types.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from supabase import Client

from .ai_service import AIService
from .openai_provider import get_chat_mini_deployment

logger = logging.getLogger(__name__)

# ============================================================================
# Relationship Type Mapping
# ============================================================================

# LLM classification categories -> database enum values
_RELATIONSHIP_TYPE_MAP = {
    "thematic": "related",
    "causal": "enables",
    "competing": "blocks",
    "enabling": "enables",
    # Pass-through for DB enum values returned directly by LLM
    "related": "related",
    "similar": "similar",
    "derived": "derived",
    "parent": "parent",
    "child": "child",
    "enables": "enables",
    "blocks": "blocks",
}

_VALID_DB_TYPES = {
    "related",
    "similar",
    "derived",
    "parent",
    "child",
    "enables",
    "blocks",
}

# ============================================================================
# Classification Prompt
# ============================================================================

CONNECTION_CLASSIFY_PROMPT = """Classify the relationship between these two municipal foresight signals.

Signal A: {card_a_name}
Summary A: {card_a_summary}

Signal B: {card_b_name}
Summary B: {card_b_summary}

Classify as exactly ONE of:
- thematic: Signals share a common theme or domain but are not causally linked
- causal: Signal A drives or leads to Signal B (or vice versa)
- competing: Signals represent alternative or conflicting approaches
- enabling: One signal is a prerequisite or enabler for the other

Respond with JSON:
{{
  "relationship_type": "thematic|causal|competing|enabling",
  "description": "1-2 sentence explanation of how these signals connect"
}}"""


# ============================================================================
# Connection Service
# ============================================================================


class ConnectionService:
    """
    Discovers and creates connections between related signals (cards)
    using embedding similarity and LLM-classified relationship types.

    Usage:
        service = ConnectionService(supabase_client, ai_service)
        new_count = await service.discover_connections(card_id)
    """

    # Defaults
    DEFAULT_SIMILARITY_THRESHOLD = 0.75
    DEFAULT_MAX_CONNECTIONS = 10
    DEFAULT_BATCH_SIZE = 20

    def __init__(self, supabase: Client, ai_service: AIService):
        """
        Initialize the connection service.

        Args:
            supabase: Supabase client (sync) for database operations.
            ai_service: AIService instance for LLM calls and embeddings.
        """
        self.supabase = supabase
        self.ai_service = ai_service

    # ====================================================================
    # Public API
    # ====================================================================

    async def discover_connections(
        self,
        card_id: str,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        max_connections: int = DEFAULT_MAX_CONNECTIONS,
    ) -> int:
        """
        Discover and create connections for a single card.

        Finds similar cards via embedding similarity, classifies the
        relationship type using an LLM, and inserts new entries into
        the card_relationships table.

        Args:
            card_id: UUID of the card to find connections for.
            similarity_threshold: Minimum cosine similarity (0-1).
            max_connections: Maximum number of new connections to create.

        Returns:
            Number of new connections created.
        """
        # 1. Get the card's embedding
        try:
            card_result = (
                self.supabase.table("cards")
                .select("id, name, summary, embedding")
                .eq("id", card_id)
                .single()
                .execute()
            )
        except Exception as e:
            logger.error(f"Failed to fetch card {card_id}: {e}")
            return 0

        if not card_result.data:
            logger.warning(f"Card not found: {card_id}")
            return 0

        card = card_result.data
        embedding = card.get("embedding")

        if not embedding:
            logger.warning(
                f"Card {card_id} has no embedding, skipping connection discovery"
            )
            return 0

        # 2. Find similar cards via RPC
        try:
            similar_result = self.supabase.rpc(
                "match_cards_by_embedding",
                {
                    "query_embedding": embedding,
                    "match_threshold": similarity_threshold,
                    "match_count": max_connections
                    + 5,  # fetch extra to account for self-match and existing
                },
            ).execute()
        except Exception as e:
            logger.error(f"match_cards_by_embedding RPC failed for card {card_id}: {e}")
            return 0

        if not similar_result.data:
            logger.debug(
                f"No similar cards found for {card_id} above threshold {similarity_threshold}"
            )
            return 0

        # Filter out self-match
        candidates = [c for c in similar_result.data if c["id"] != card_id]

        if not candidates:
            logger.debug(
                f"No candidate connections for card {card_id} (only self-match)"
            )
            return 0

        # 3. Check which relationships already exist
        existing_pairs = self._get_existing_relationships(card_id)

        # 4. Classify and create new connections
        new_count = 0
        for candidate in candidates:
            if new_count >= max_connections:
                break

            target_id = candidate["id"]

            # Skip if relationship already exists in either direction
            if target_id in existing_pairs:
                continue

            # Classify the connection via LLM
            try:
                classification = await self._classify_connection(
                    card_a_name=card.get("name", ""),
                    card_a_summary=card.get("summary", ""),
                    card_b_name=candidate.get("name", ""),
                    card_b_summary=candidate.get("summary", ""),
                )
            except Exception as e:
                logger.warning(
                    f"Connection classification failed between {card_id} and {target_id}: {e}"
                )
                # Default to 'related' if classification fails
                classification = {
                    "relationship_type": "related",
                    "description": "Related signals identified by embedding similarity",
                }

            # Map relationship type to DB enum
            raw_type = classification.get("relationship_type", "related")
            db_type = _RELATIONSHIP_TYPE_MAP.get(raw_type, "related")
            if db_type not in _VALID_DB_TYPES:
                db_type = "related"

            # Insert the relationship
            try:
                self.supabase.table("card_relationships").insert(
                    {
                        "source_card_id": card_id,
                        "target_card_id": target_id,
                        "relationship_type": db_type,
                        "strength": candidate.get("similarity", similarity_threshold),
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                ).execute()
                new_count += 1
                logger.debug(
                    f"Created connection: {card_id} --[{db_type}]--> {target_id} "
                    f"(sim={candidate.get('similarity', 0):.3f})"
                )
            except Exception as e:
                error_msg = str(e).lower()
                if "duplicate" in error_msg or "unique" in error_msg:
                    logger.debug(
                        f"Duplicate relationship skipped: {card_id} -> {target_id}"
                    )
                else:
                    logger.warning(
                        f"Failed to insert relationship {card_id} -> {target_id}: {e}"
                    )

        if new_count > 0:
            logger.info(
                f"Discovered {new_count} new connections for card {card_id} "
                f"(from {len(candidates)} candidates)"
            )
        else:
            logger.debug(f"No new connections created for card {card_id}")

        return new_count

    async def refresh_all_connections(
        self, batch_size: int = DEFAULT_BATCH_SIZE
    ) -> dict:
        """
        Batch process cards to discover connections for those that
        haven't been processed recently.

        Finds cards with embeddings that lack recent connections and
        runs discover_connections on each.

        Args:
            batch_size: Number of cards to process per batch.

        Returns:
            Summary dict with processing counts:
            {
                "cards_processed": int,
                "connections_created": int,
                "cards_skipped": int,
                "errors": int,
            }
        """
        summary = {
            "cards_processed": 0,
            "connections_created": 0,
            "cards_skipped": 0,
            "errors": 0,
        }

        # Find cards with embeddings that have no connections yet,
        # or whose most recent connection is older than 7 days.
        # Simple approach: get cards with embeddings, ordered by updated_at,
        # and process those without recent relationships.
        try:
            cards_result = (
                self.supabase.table("cards")
                .select("id, name")
                .eq("status", "active")
                .not_.is_("embedding", "null")
                .order("updated_at", desc=True)
                .limit(batch_size)
                .execute()
            )
        except Exception as e:
            logger.error(f"Failed to fetch cards for connection refresh: {e}")
            return summary

        if not cards_result.data:
            logger.info("No cards with embeddings found for connection refresh")
            return summary

        for card in cards_result.data:
            card_id = card["id"]
            try:
                new_connections = await self.discover_connections(card_id)
                summary["cards_processed"] += 1
                summary["connections_created"] += new_connections
            except Exception as e:
                logger.warning(f"Connection discovery failed for card {card_id}: {e}")
                summary["errors"] += 1

        logger.info(
            f"Connection refresh complete: "
            f"{summary['cards_processed']} cards processed, "
            f"{summary['connections_created']} connections created, "
            f"{summary['errors']} errors"
        )

        return summary

    # ====================================================================
    # Internal Methods
    # ====================================================================

    async def _classify_connection(
        self,
        card_a_name: str,
        card_a_summary: str,
        card_b_name: str,
        card_b_summary: str,
    ) -> dict:
        """
        Use GPT-4o-mini to classify the relationship between two cards.

        Args:
            card_a_name: Name of the first card.
            card_a_summary: Summary of the first card.
            card_b_name: Name of the second card.
            card_b_summary: Summary of the second card.

        Returns:
            Dict with:
                relationship_type: One of thematic, causal, competing, enabling
                description: 1-2 sentence explanation
        """
        prompt = CONNECTION_CLASSIFY_PROMPT.format(
            card_a_name=card_a_name,
            card_a_summary=(card_a_summary or "No summary available")[:500],
            card_b_name=card_b_name,
            card_b_summary=(card_b_summary or "No summary available")[:500],
        )

        try:
            response = self.ai_service.client.chat.completions.create(
                model=get_chat_mini_deployment(),
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=150,
                timeout=30,
            )

            result = json.loads(response.choices[0].message.content)
            return {
                "relationship_type": result.get("relationship_type", "thematic"),
                "description": result.get("description", ""),
            }
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse connection classification response: {e}")
            return {
                "relationship_type": "thematic",
                "description": "Classification parse error — defaulted to thematic",
            }
        except Exception as e:
            logger.warning(f"Connection classification LLM call failed: {e}")
            raise

    def _get_existing_relationships(self, card_id: str) -> set:
        """
        Get the set of card IDs that already have a relationship with
        the given card (in either direction).

        Args:
            card_id: UUID of the card.

        Returns:
            Set of card IDs with existing relationships.
        """
        existing = set()
        try:
            # Relationships where this card is the source
            outgoing = (
                self.supabase.table("card_relationships")
                .select("target_card_id")
                .eq("source_card_id", card_id)
                .execute()
            )
            for row in outgoing.data or []:
                existing.add(row["target_card_id"])

            # Relationships where this card is the target
            incoming = (
                self.supabase.table("card_relationships")
                .select("source_card_id")
                .eq("target_card_id", card_id)
                .execute()
            )
            for row in incoming.data or []:
                existing.add(row["source_card_id"])

        except Exception as e:
            logger.warning(f"Failed to fetch existing relationships for {card_id}: {e}")

        return existing
