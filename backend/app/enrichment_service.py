"""Signal enrichment service — finds additional sources for weak signals."""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


async def _search_exa(query: str, num_results: int = 7) -> list[dict]:
    """Search via Exa AI. Returns list of {title, url, content, score}."""
    exa_key = os.getenv("EXA_API_KEY")
    if not exa_key:
        return []

    try:
        from exa_py import Exa

        exa = Exa(api_key=exa_key)
        result = await asyncio.to_thread(
            exa.search_and_contents,
            query,
            type="neural",
            use_autoprompt=True,
            num_results=num_results,
            text={"max_characters": 3000},
            start_published_date="2024-01-01",
        )
        return [
            {
                "title": r.title or "Untitled",
                "url": r.url,
                "content": r.text or "",
                "score": r.score if hasattr(r, "score") else 0.7,
            }
            for r in result.results
        ]
    except Exception as e:
        logger.warning(f"Exa search failed: {e}")
        return []


async def _search_tavily(query: str, num_results: int = 7) -> list[dict]:
    """Search via Tavily. Returns list of {title, url, content, score}."""
    tavily_key = os.getenv("TAVILY_API_KEY")
    if not tavily_key:
        return []

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=tavily_key)
        result = await asyncio.to_thread(
            client.search,
            query,
            max_results=num_results,
            search_depth="basic",
            include_answer=False,
        )
        return result.get("results", [])
    except Exception as e:
        logger.warning(f"Tavily search failed: {e}")
        return []


async def _web_search(query: str, num_results: int = 7) -> list[dict]:
    """Search the web using Exa (primary) with Tavily fallback."""
    results = await _search_exa(query, num_results)
    if results:
        return results
    return await _search_tavily(query, num_results)


async def enrich_weak_signals(
    supabase,
    min_sources: int = 3,
    max_cards: int = 100,
    max_new_sources_per_card: int = 5,
    triggered_by_user_id: Optional[str] = None,
) -> dict:
    """Find cards with fewer than `min_sources` sources and enrich them via web search.

    Uses Exa AI (primary) with Tavily fallback to find supporting articles.
    """
    exa_key = os.getenv("EXA_API_KEY")
    tavily_key = os.getenv("TAVILY_API_KEY")
    if not exa_key and not tavily_key:
        return {
            "error": "No search API keys configured (EXA_API_KEY or TAVILY_API_KEY)"
        }

    # Step 1: Find cards with source counts
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
        f"Enrichment: Found {len(weak_cards)} cards with < {min_sources} sources "
        f"(out of {len(all_cards)} total)"
    )

    if not weak_cards:
        return {
            "enriched": 0,
            "sources_added": 0,
            "message": "All cards have sufficient sources",
        }

    # Step 2: Enrich each weak card
    total_sources_added = 0
    enriched_cards = 0
    errors = 0
    error_samples = []
    search_provider = "exa" if exa_key else "tavily"

    # Use semaphore to limit concurrent API calls
    sem = asyncio.Semaphore(3)

    async def enrich_card(card: dict) -> int:
        """Search for and attach additional sources to a card."""
        nonlocal errors
        async with sem:
            try:
                card_name = card["name"]

                # Build a focused search query
                search_query = card_name
                if len(search_query) > 150:
                    search_query = search_query[:150]

                # Search the web
                web_results = await _web_search(
                    search_query, num_results=max_new_sources_per_card + 2
                )

                if not web_results:
                    return 0

                # Get existing source URLs to avoid duplicates
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

                    if len(content) < 50:
                        continue

                    source_record = {
                        "card_id": card["id"],
                        "url": url,
                        "title": title,
                        "full_text": content[:10000],
                        "ai_summary": content[:500],
                        "relevance_to_card": wr.get("score", 0.7),
                        "api_source": f"{search_provider}_enrichment",
                        "ingested_at": now,
                    }

                    try:
                        src_result = (
                            supabase.table("sources").insert(source_record).execute()
                        )
                        if src_result.data:
                            source_id = src_result.data[0]["id"]
                            try:
                                supabase.table("signal_sources").insert(
                                    {
                                        "card_id": card["id"],
                                        "source_id": source_id,
                                        "relationship_type": "supporting",
                                        "confidence": min(wr.get("score", 0.7), 1.0),
                                        "agent_reasoning": (
                                            f"Web enrichment via {search_provider} "
                                            f"for '{card_name[:60]}'"
                                        ),
                                        "created_by": "enrichment_service",
                                        "created_at": now,
                                    }
                                ).execute()
                            except Exception:
                                pass

                            sources_added += 1
                            existing_urls.add(url)
                    except Exception as e:
                        if "duplicate" not in str(e).lower():
                            logger.warning(
                                f"Enrichment: Failed to store source for "
                                f"'{card_name[:30]}': {e}"
                            )

                if sources_added > 0:
                    supabase.table("cards").update({"updated_at": now}).eq(
                        "id", card["id"]
                    ).execute()

                    try:
                        supabase.table("card_timeline").insert(
                            {
                                "card_id": card["id"],
                                "event_type": "sources_enriched",
                                "title": "Additional sources discovered",
                                "description": (
                                    f"Found {sources_added} additional supporting "
                                    f"sources via {search_provider} web search"
                                ),
                                "metadata": {
                                    "source": f"{search_provider}_enrichment",
                                    "count": sources_added,
                                },
                                "created_at": now,
                            }
                        ).execute()
                    except Exception:
                        pass

                logger.info(
                    f"Enrichment: Added {sources_added} sources to "
                    f"'{card_name[:40]}' (had {card['_source_count']})"
                )
                return sources_added

            except Exception as e:
                errors += 1
                err_msg = f"{type(e).__name__}: {e}"
                logger.error(
                    f"Enrichment: Error enriching card "
                    f"{card.get('id', '?')}: {err_msg}"
                )
                if len(error_samples) < 3:
                    error_samples.append(err_msg[:200])
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
        "search_provider": search_provider,
        "error_samples": error_samples,
    }

    logger.info(f"Enrichment complete: {summary}")
    return summary
