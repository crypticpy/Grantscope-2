"""Signal enrichment service — finds additional sources for weak signals."""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)


async def enrich_weak_signals(
    supabase,
    min_sources: int = 3,
    max_cards: int = 100,
    max_new_sources_per_card: int = 5,
    triggered_by_user_id: Optional[str] = None,
) -> dict:
    """Find cards with fewer than `min_sources` sources and enrich them via web search.

    Args:
        supabase: Supabase client
        min_sources: Cards with fewer sources than this get enriched
        max_cards: Max number of cards to process
        max_new_sources_per_card: Max additional sources to find per card
        triggered_by_user_id: User ID for audit trail

    Returns:
        Summary dict with counts of enriched cards and sources added
    """
    tavily_key = os.getenv("TAVILY_API_KEY")
    if not tavily_key:
        return {"error": "TAVILY_API_KEY not configured"}

    from tavily import TavilyClient

    tavily = TavilyClient(api_key=tavily_key)

    # Step 1: Find cards with source counts
    # Get all active cards
    cards_resp = (
        supabase.table("cards")
        .select("id, name, summary, pillar_id")
        .eq("status", "active")
        .limit(max_cards)
        .execute()
    )

    all_cards = cards_resp.data or []
    if not all_cards:
        return {"error": "No active cards found", "enriched": 0, "sources_added": 0}

    # For each card, count its sources
    weak_cards = []
    for card in all_cards:
        src_resp = (
            supabase.table("sources")
            .select("id", count="exact")
            .eq("card_id", card["id"])
            .execute()
        )
        source_count = (
            src_resp.count
            if hasattr(src_resp, "count") and src_resp.count is not None
            else len(src_resp.data or [])
        )
        if source_count < min_sources:
            card["_source_count"] = source_count
            weak_cards.append(card)

    logger.info(
        f"Enrichment: Found {len(weak_cards)} cards with < {min_sources} sources (out of {len(all_cards)} total)"
    )

    if not weak_cards:
        return {
            "enriched": 0,
            "sources_added": 0,
            "message": "All cards have sufficient sources",
        }

    # Step 2: Enrich each weak card using Tavily
    total_sources_added = 0
    enriched_cards = 0
    errors = 0

    # Use semaphore to limit concurrent Tavily calls
    sem = asyncio.Semaphore(3)

    async def enrich_card(card: dict) -> int:
        """Search for and attach additional sources to a card. Returns count of sources added."""
        nonlocal errors
        async with sem:
            try:
                card_name = card["name"]
                card_summary = card.get("summary", "")

                # Build a search query from the card's topic
                search_query = (
                    f"{card_name} {card.get('pillar_id', '')} municipal government"
                )
                if len(search_query) > 200:
                    search_query = card_name[:150]

                # Search Tavily
                result = await asyncio.to_thread(
                    tavily.search,
                    search_query,
                    max_results=max_new_sources_per_card
                    + 2,  # fetch a few extra in case of dupes
                    search_depth="basic",
                    include_answer=False,
                )
                web_results = result.get("results", [])

                if not web_results:
                    logger.debug(f"Enrichment: No web results for '{card_name[:40]}'")
                    return 0

                # Get existing source URLs for this card to avoid duplicates
                existing_resp = (
                    supabase.table("sources")
                    .select("url")
                    .eq("card_id", card["id"])
                    .execute()
                )
                existing_urls = {
                    s["url"] for s in (existing_resp.data or []) if s.get("url")
                }

                sources_added = 0
                now = datetime.now(timezone.utc).isoformat()

                for wr in web_results:
                    if sources_added >= max_new_sources_per_card:
                        break

                    url = wr.get("url", "")
                    if not url or url in existing_urls:
                        continue

                    title = (wr.get("title") or "Untitled")[:500]
                    content = wr.get("content", "")

                    # Skip very short content
                    if len(content) < 50:
                        continue

                    # Insert source
                    source_record = {
                        "card_id": card["id"],
                        "url": url,
                        "title": title,
                        "full_text": content[:10000],
                        "ai_summary": content[
                            :500
                        ],  # Tavily content is already a summary
                        "relevance_to_card": wr.get("score", 0.7),
                        "api_source": "tavily_enrichment",
                        "ingested_at": now,
                    }

                    try:
                        src_result = (
                            supabase.table("sources").insert(source_record).execute()
                        )
                        if src_result.data:
                            source_id = src_result.data[0]["id"]
                            # Also create junction entry
                            try:
                                supabase.table("signal_sources").insert(
                                    {
                                        "card_id": card["id"],
                                        "source_id": source_id,
                                        "relationship_type": "supporting",
                                        "confidence": wr.get("score", 0.7),
                                        "agent_reasoning": f"Web enrichment: found via Tavily search for '{card_name[:60]}'",
                                        "created_by": "enrichment_service",
                                        "created_at": now,
                                    }
                                ).execute()
                            except Exception:
                                pass  # Junction entry is optional (might not exist yet)

                            sources_added += 1
                            existing_urls.add(url)
                    except Exception as e:
                        if "duplicate" not in str(e).lower():
                            logger.warning(
                                f"Enrichment: Failed to store source for '{card_name[:30]}': {e}"
                            )

                if sources_added > 0:
                    # Update card updated_at
                    supabase.table("cards").update({"updated_at": now}).eq(
                        "id", card["id"]
                    ).execute()

                    # Add timeline event
                    try:
                        supabase.table("card_timeline").insert(
                            {
                                "card_id": card["id"],
                                "event_type": "sources_enriched",
                                "title": "Additional sources discovered",
                                "description": f"Found {sources_added} additional supporting sources via web search",
                                "metadata": {
                                    "source": "tavily_enrichment",
                                    "count": sources_added,
                                },
                                "created_at": now,
                            }
                        ).execute()
                    except Exception:
                        pass

                logger.info(
                    f"Enrichment: Added {sources_added} sources to '{card_name[:40]}' (had {card['_source_count']})"
                )
                return sources_added

            except Exception as e:
                errors += 1
                logger.error(
                    f"Enrichment: Error enriching card {card.get('id', '?')}: {e}"
                )
                return 0

    # Run enrichment for all weak cards
    results = await asyncio.gather(*[enrich_card(c) for c in weak_cards])

    for count in results:
        if count > 0:
            enriched_cards += 1
            total_sources_added += count

    summary = {
        "enriched_cards": enriched_cards,
        "sources_added": total_sources_added,
        "weak_cards_found": len(weak_cards),
        "total_cards_checked": len(all_cards),
        "errors": errors,
    }

    logger.info(f"Enrichment complete: {summary}")
    return summary
