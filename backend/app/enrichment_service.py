"""Signal enrichment service — finds additional sources for weak signals."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


async def _web_search(query: str, num_results: int = 7) -> list[dict]:
    """Search the web using SearXNG via the unified search provider."""
    from .search_provider import is_available as search_available
    from .search_provider import search_web, search_news

    if not search_available():
        logger.warning("No search provider configured — returning empty results")
        return []

    try:
        web_results = await search_web(query, num_results=num_results)
        news_results = await search_news(query, num_results=max(num_results // 2, 3))

        seen_urls: set[str] = set()
        results: list[dict] = []
        for r in web_results + news_results:
            if r.url and r.url not in seen_urls:
                seen_urls.add(r.url)
                results.append(
                    {
                        "title": r.title or "Untitled",
                        "url": r.url,
                        "content": r.snippet or "",
                        "score": 0.7,
                    }
                )
        return results[:num_results]
    except Exception as e:
        logger.warning(f"Search provider failed: {e}")
        return []


async def enrich_weak_signals(
    supabase,
    min_sources: int = 3,
    max_cards: int = 100,
    max_new_sources_per_card: int = 5,
    triggered_by_user_id: Optional[str] = None,
) -> dict:
    """Find cards with fewer than `min_sources` sources and enrich them via web search.

    Uses the unified search provider (SearXNG preferred, Serper/Tavily fallback).
    """
    from .search_provider import is_available as search_available

    if not search_available():
        return {
            "error": "No search provider configured (set SEARXNG_BASE_URL, SERPER_API_KEY, or TAVILY_API_KEY)"
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
    search_provider = "searxng"

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


async def enrich_signal_profiles(
    supabase,
    max_cards: int = 5,
    triggered_by_user_id: Optional[str] = None,
) -> dict:
    """Batch-generate rich profiles for cards with blank/thin descriptions.

    Fetches all active cards, filters to those needing profiles, then processes
    up to max_cards per call. Designed for repeated calls until all are done.
    """
    from app.ai_service import AIService
    from app.openai_provider import azure_openai_client

    try:
        from app.content_enricher import extract_content
    except ImportError:
        extract_content = None
        logger.warning(
            "trafilatura not available — thin-source backfill will be skipped"
        )

    ai_service = AIService(azure_openai_client)

    # Fetch ALL active cards (scan everything, limit processing)
    cards_resp = (
        supabase.table("cards")
        .select("id, name, summary, description, pillar_id, horizon")
        .eq("status", "active")
        .order("created_at", desc=True)
        .limit(500)
        .execute()
    )

    if not cards_resp.data:
        return {"status": "no_cards", "enriched": 0}

    # Filter to cards needing profiles
    cards_needing_profiles = [
        c
        for c in cards_resp.data
        if not c.get("description") or len(c.get("description", "")) < 100
    ]

    if not cards_needing_profiles:
        return {
            "status": "all_cards_have_profiles",
            "total_checked": len(cards_resp.data),
            "enriched": 0,
        }

    # Only process max_cards per call to avoid gateway timeouts
    batch = cards_needing_profiles[:max_cards]
    remaining = len(cards_needing_profiles) - len(batch)

    enriched = 0
    errors = 0
    now = datetime.now(timezone.utc).isoformat()

    for card in batch:
        try:
            card_id = card["id"]

            # Fetch linked sources
            sources_resp = (
                supabase.table("sources")
                .select("title, url, ai_summary, key_excerpts, full_text")
                .eq("card_id", card_id)
                .order("created_at", desc=True)
                .limit(10)
                .execute()
            )

            sources = sources_resp.data or []
            if not sources:
                continue

            # Backfill thin source content (if trafilatura available)
            if extract_content:
                for src in sources:
                    content = src.get("full_text") or src.get("ai_summary") or ""
                    if len(content) < 200 and src.get("url"):
                        try:
                            text, title = await extract_content(src["url"])
                            if text:
                                src["full_text"] = text[:10000]
                                # Update in DB too
                                if src.get("id"):
                                    supabase.table("sources").update(
                                        {"full_text": text[:10000]}
                                    ).eq("id", src["id"]).execute()
                        except Exception:
                            pass

            # Build source analyses for profile generation
            source_analyses = []
            for src in sources:
                source_analyses.append(
                    {
                        "title": src.get("title", "Untitled"),
                        "url": src.get("url", ""),
                        "summary": src.get("ai_summary", ""),
                        "key_excerpts": src.get("key_excerpts") or [],
                        "content": src.get("full_text", "")[:500],
                    }
                )

            # Generate profile
            profile = await ai_service.generate_signal_profile(
                signal_name=card["name"],
                signal_summary=card.get("summary", ""),
                pillar_id=card.get("pillar_id", ""),
                horizon=card.get("horizon", "H2"),
                source_analyses=source_analyses,
            )

            if profile and len(profile) > 100:
                # Update card description
                supabase.table("cards").update(
                    {
                        "description": profile,
                        "updated_at": now,
                    }
                ).eq("id", card_id).execute()

                # Create timeline event
                supabase.table("card_timeline").insert(
                    {
                        "card_id": card_id,
                        "event_type": "profile_generated",
                        "title": "Signal profile auto-generated",
                        "description": f"Rich profile generated from {len(sources)} source(s)",
                        "metadata": {
                            "sources_used": len(source_analyses),
                            "profile_length": len(profile),
                            "triggered_by": triggered_by_user_id,
                        },
                        "created_at": now,
                    }
                ).execute()

                enriched += 1
                logger.info(
                    f"Generated profile for card '{card['name'][:50]}' ({len(profile)} chars)"
                )

        except Exception as e:
            errors += 1
            logger.error(f"Profile enrichment failed for card {card.get('id')}: {e}")

    return {
        "status": "completed",
        "total_checked": len(cards_resp.data),
        "needing_profiles": len(cards_needing_profiles),
        "enriched": enriched,
        "errors": errors,
        "remaining": remaining - enriched,
    }
