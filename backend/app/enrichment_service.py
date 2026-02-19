"""Signal enrichment service — finds additional sources for weak signals."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update as sa_update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.card import Card
from app.models.db.source import Source, SignalSource
from app.models.db.card_extras import CardTimeline
from app.helpers.settings_reader import get_setting

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
    db: AsyncSession,
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
    result = await db.execute(
        select(Card.id, Card.name, Card.summary, Card.pillar_id)
        .where(Card.status == "active")
        .limit(max_cards)
    )
    all_cards_rows = result.all()

    if not all_cards_rows:
        return {"error": "No active cards found", "enriched": 0, "sources_added": 0}

    all_cards = [
        {
            "id": str(row.id),
            "name": row.name,
            "summary": row.summary,
            "pillar_id": row.pillar_id,
        }
        for row in all_cards_rows
    ]

    # For each card, count its sources
    weak_cards = []
    for card in all_cards:
        count_result = await db.execute(
            select(func.count(Source.id)).where(Source.card_id == card["id"])
        )
        source_count = count_result.scalar() or 0
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
                existing_result = await db.execute(
                    select(Source.url).where(Source.card_id == card["id"])
                )
                existing_urls = {row.url for row in existing_result.all() if row.url}

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

                    new_source = Source(
                        card_id=card["id"],
                        url=url,
                        title=title,
                        full_text=content[:10000],
                        ai_summary=content[:500],
                        relevance_to_card=wr.get("score", 0.7),
                        api_source=f"{search_provider}_enrichment",
                        ingested_at=datetime.now(timezone.utc),
                    )

                    try:
                        db.add(new_source)
                        await db.flush()
                        await db.refresh(new_source)

                        source_id = str(new_source.id)
                        try:
                            signal_source = SignalSource(
                                card_id=card["id"],
                                source_id=source_id,
                                relationship_type="supporting",
                                confidence=min(wr.get("score", 0.7), 1.0),
                                agent_reasoning=(
                                    f"Web enrichment via {search_provider} "
                                    f"for '{card_name[:60]}'"
                                ),
                                created_by="enrichment_service",
                            )
                            db.add(signal_source)
                            await db.flush()
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
                    await db.execute(
                        sa_update(Card)
                        .where(Card.id == card["id"])
                        .values(updated_at=now)
                    )
                    await db.flush()

                    try:
                        timeline_event = CardTimeline(
                            card_id=card["id"],
                            event_type="sources_enriched",
                            title="Additional sources discovered",
                            description=(
                                f"Found {sources_added} additional supporting "
                                f"sources via {search_provider} web search"
                            ),
                            metadata_={
                                "source": f"{search_provider}_enrichment",
                                "count": sources_added,
                            },
                        )
                        db.add(timeline_event)
                        await db.flush()
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
    db: AsyncSession,
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
    result = await db.execute(
        select(
            Card.id,
            Card.name,
            Card.summary,
            Card.description,
            Card.pillar_id,
            Card.horizon,
            Card.pipeline_status,
        )
        .where(Card.status == "active")
        .order_by(Card.created_at.desc())
        .limit(500)
    )
    all_cards_rows = result.all()

    if not all_cards_rows:
        return {"status": "no_cards", "enriched": 0}

    all_cards_data = [
        {
            "id": str(row.id),
            "name": row.name,
            "summary": row.summary,
            "description": row.description,
            "pillar_id": row.pillar_id,
            "horizon": row.horizon,
            "pipeline_status": getattr(row, "pipeline_status", None),
        }
        for row in all_cards_rows
    ]

    # Filter to cards needing profiles
    cards_needing_profiles = [
        c
        for c in all_cards_data
        if not c.get("description") or len(c.get("description", "")) < 100
    ]

    if not cards_needing_profiles:
        return {
            "status": "all_cards_have_profiles",
            "total_checked": len(all_cards_data),
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
            sources_result = await db.execute(
                select(
                    Source.id,
                    Source.title,
                    Source.url,
                    Source.ai_summary,
                    Source.key_excerpts,
                    Source.full_text,
                )
                .where(Source.card_id == card_id)
                .order_by(Source.created_at.desc())
                .limit(10)
            )
            sources_rows = sources_result.all()

            if not sources_rows:
                continue

            sources = [
                {
                    "id": str(row.id),
                    "title": row.title,
                    "url": row.url,
                    "ai_summary": row.ai_summary,
                    "key_excerpts": row.key_excerpts,
                    "full_text": row.full_text,
                }
                for row in sources_rows
            ]

            # Backfill thin source content (if trafilatura available)
            if extract_content:
                for src in sources:
                    content = src.get("full_text") or src.get("ai_summary") or ""
                    if len(content) < 200 and src.get("url"):
                        try:
                            text_content, title = await extract_content(src["url"])
                            if text_content:
                                src["full_text"] = text_content[:10000]
                                # Update in DB too
                                if src.get("id"):
                                    await db.execute(
                                        sa_update(Source)
                                        .where(Source.id == src["id"])
                                        .values(full_text=text_content[:10000])
                                    )
                                    await db.flush()
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
                await db.execute(
                    sa_update(Card)
                    .where(Card.id == card_id)
                    .values(description=profile, updated_at=now)
                )
                await db.flush()

                # Create timeline event
                timeline_event = CardTimeline(
                    card_id=card_id,
                    event_type="profile_generated",
                    title="Signal profile auto-generated",
                    description=f"Rich profile generated from {len(sources)} source(s)",
                    metadata_={
                        "sources_used": len(source_analyses),
                        "profile_length": len(profile),
                        "triggered_by": triggered_by_user_id,
                    },
                )
                db.add(timeline_event)
                await db.flush()

                enriched += 1
                logger.info(
                    f"Generated profile for card '{card['name'][:50]}' ({len(profile)} chars)"
                )

        except Exception as e:
            errors += 1
            logger.error(f"Profile enrichment failed for card {card.get('id')}: {e}")

    return {
        "status": "completed",
        "total_checked": len(all_cards_data),
        "needing_profiles": len(cards_needing_profiles),
        "enriched": enriched,
        "errors": errors,
        "remaining": remaining - enriched,
    }


async def enrich_thin_descriptions(
    db: AsyncSession,
    threshold_chars: int = 1600,
    max_cards: int = 10,
    triggered_by_user_id: str | None = None,
) -> dict:
    """Enrich cards with thin descriptions (< threshold_chars).

    For each qualifying card, queues a ``card_analysis`` background task
    (via :func:`app.card_analysis_service.queue_card_analysis`) which will:

    1. Fetch linked sources
    2. If grants_gov_id exists, try to fetch grant details
    3. If total context < 2000 chars, run web search for more context
    4. Call AI with COMPREHENSIVE_ANALYSIS_PROMPT for rich description
    5. Update card description + scores
    6. Generate and store embedding
    7. Create timeline event

    Returns stats dict with counts.
    """
    from sqlalchemy import text as sa_text
    from app.card_analysis_service import queue_card_analysis

    # Apply admin-configurable overrides (cached, 60s TTL)
    thr_raw = await get_setting(db, "enrichment_threshold_chars", threshold_chars)
    max_raw = await get_setting(db, "enrichment_max_cards_per_run", max_cards)
    try:
        threshold_chars = int(thr_raw)
    except (TypeError, ValueError):
        pass
    try:
        max_cards = int(max_raw)
    except (TypeError, ValueError):
        pass

    # Find thin cards
    result = await db.execute(
        sa_text(
            "SELECT id, name, length(COALESCE(description, '')) AS desc_len "
            "FROM cards "
            "WHERE status = 'active' "
            "AND (description IS NULL OR length(description) < :threshold) "
            "ORDER BY created_at DESC "
            "LIMIT :max_cards"
        ),
        {"threshold": threshold_chars, "max_cards": max_cards},
    )
    thin_cards = result.all()

    # Count total needing enrichment (without limit)
    total_result = await db.execute(
        sa_text(
            "SELECT COUNT(*) FROM cards "
            "WHERE status = 'active' "
            "AND (description IS NULL OR length(description) < :threshold)"
        ),
        {"threshold": threshold_chars},
    )
    total_needing = total_result.scalar() or 0

    queued = 0
    errors = 0
    already_queued = 0

    # Use the provided user ID, or fall back to any admin user
    user_id = triggered_by_user_id
    if not user_id:
        admin_result = await db.execute(
            sa_text("SELECT id FROM users WHERE role = 'admin' LIMIT 1")
        )
        admin_row = admin_result.scalar_one_or_none()
        user_id = str(admin_row) if admin_row else None

    if not user_id:
        logger.warning("enrich_thin_descriptions: no user_id available, skipping")
        return {
            "total_needing_enrichment": total_needing,
            "checked": len(thin_cards),
            "queued": 0,
            "already_queued": 0,
            "errors": 0,
            "remaining": total_needing,
        }

    for row in thin_cards:
        card_id = str(row.id)
        try:
            task_id = await queue_card_analysis(db, card_id, user_id)
            if task_id:
                queued += 1
            else:
                already_queued += 1
        except Exception as e:
            logger.warning("Failed to queue enrichment for card %s: %s", card_id, e)
            errors += 1

    await db.flush()

    stats = {
        "total_needing_enrichment": total_needing,
        "checked": len(thin_cards),
        "queued": queued,
        "already_queued": already_queued,
        "errors": errors,
        "remaining": max(0, total_needing - queued - already_queued),
    }
    logger.info("enrich_thin_descriptions: %s", stats)
    return stats
