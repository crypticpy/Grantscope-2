"""Recovery service for reconstructing cards from discovered_sources data.

When cards are accidentally deleted, this service reconstructs ProcessedSource
objects from the preserved discovered_sources audit trail and feeds them through
the signal agent for intelligent re-grouping.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from app.ai_service import AnalysisResult, TriageResult
from app.openai_provider import (
    azure_openai_async_embedding_client,
    get_embedding_deployment,
)
from app.research_service import ProcessedSource, RawSource

logger = logging.getLogger(__name__)


async def _generate_embedding(text: str) -> List[float]:
    """Generate an embedding vector for the given text."""
    truncated = text[:8000]
    resp = await azure_openai_async_embedding_client.embeddings.create(
        model=get_embedding_deployment(),
        input=truncated,
        timeout=60,
    )
    return resp.data[0].embedding


def _reconstruct_processed_source(ds: dict) -> Optional[ProcessedSource]:
    """Reconstruct a ProcessedSource from a discovered_sources row.

    Returns None if the row lacks sufficient analysis data.
    """
    if not ds.get("analysis_summary") and not ds.get("analysis_suggested_card_name"):
        logger.debug(f"Skipping source {ds['id']}: no analysis data")
        return None

    raw = RawSource(
        url=ds.get("url", ""),
        title=ds.get("title", "") or "",
        content=ds.get("full_content") or ds.get("content_snippet") or "",
        source_name=ds.get("domain") or "",
        published_at=ds.get("published_at"),
        source_type=ds.get("source_type"),
        discovered_source_id=ds["id"],
    )

    triage = TriageResult(
        is_relevant=ds.get("triage_is_relevant", True),
        confidence=ds.get("triage_confidence") or 0.7,
        primary_pillar=ds.get("triage_primary_pillar"),
        reason=ds.get("triage_reason") or "recovered from discovered_sources",
    )

    analysis = AnalysisResult(
        summary=ds.get("analysis_summary") or "",
        key_excerpts=ds.get("analysis_key_excerpts") or [],
        pillars=ds.get("analysis_pillars") or [],
        goals=ds.get("analysis_goals") or [],
        steep_categories=ds.get("analysis_steep_categories") or [],
        anchors=ds.get("analysis_anchors") or [],
        horizon=ds.get("analysis_horizon") or "H2",
        suggested_stage=ds.get("analysis_suggested_stage") or 4,
        triage_score=ds.get("analysis_triage_score") or 3,
        credibility=ds.get("analysis_credibility") or 3.0,
        novelty=ds.get("analysis_novelty") or 3.0,
        likelihood=ds.get("analysis_likelihood") or 5.0,
        impact=ds.get("analysis_impact") or 3.0,
        relevance=ds.get("analysis_relevance") or 3.0,
        velocity=5.0,  # Not stored in discovered_sources
        risk=5.0,  # Not stored in discovered_sources
        time_to_awareness_months=ds.get("analysis_time_to_awareness_months") or 12,
        time_to_prepare_months=ds.get("analysis_time_to_prepare_months") or 24,
        suggested_card_name=ds.get("analysis_suggested_card_name") or "",
        is_new_concept=ds.get("analysis_is_new_concept", True),
        entities=[],
        reasoning=ds.get("analysis_reasoning") or "",
    )

    # Embedding will be regenerated; use empty placeholder
    return ProcessedSource(
        raw=raw,
        triage=triage,
        analysis=analysis,
        embedding=[],  # Populated later
        discovered_source_id=ds["id"],
    )


async def recover_cards_from_discovered_sources(
    supabase,
    date_start: str = "2025-12-01",
    date_end: str = "2026-01-01",
    triggered_by_user_id: Optional[str] = None,
) -> dict:
    """Recover cards from discovered_sources for a date range.

    Finds sources in discovered_sources that either:
    - Had cards created (processing_status='card_created'/'card_enriched')
      but the resulting card no longer exists
    - Were fully analyzed but never got a card

    Reconstructs ProcessedSource objects and runs them through the signal agent.

    Args:
        supabase: Supabase client
        date_start: ISO date string for range start
        date_end: ISO date string for range end
        triggered_by_user_id: User ID for created_by fields

    Returns:
        Dict with recovery statistics
    """
    from app.discovery_service import DiscoveryConfig
    from app.signal_agent_service import SignalAgentService

    logger.info(f"Starting card recovery for {date_start} to {date_end}")

    # Step 1: Find all analyzed sources in the date range
    all_sources = (
        supabase.table("discovered_sources")
        .select("*")
        .gte("created_at", date_start)
        .lt("created_at", date_end)
        .in_(
            "processing_status",
            ["card_created", "card_enriched", "analyzed", "deduplicated"],
        )
        .order("created_at", desc=False)
        .execute()
    )

    if not all_sources.data:
        logger.info("No discovered_sources found in date range")
        return {"status": "no_sources", "sources_found": 0}

    logger.info(f"Found {len(all_sources.data)} discovered_sources in range")

    # Step 2: Filter to orphaned sources (cards no longer exist)
    orphaned = []
    card_existence_cache: dict = {}

    for ds in all_sources.data:
        card_id = ds.get("resulting_card_id")

        if card_id:
            # Check cache first
            if card_id not in card_existence_cache:
                check = supabase.table("cards").select("id").eq("id", card_id).execute()
                card_existence_cache[card_id] = bool(check.data)

            if card_existence_cache[card_id]:
                continue  # Card still exists, skip

        # Source is orphaned (card deleted) or never got a card
        orphaned.append(ds)

    if not orphaned:
        logger.info("All cards still exist — no recovery needed")
        return {"status": "no_orphans", "sources_found": len(all_sources.data)}

    logger.info(f"Found {len(orphaned)} orphaned sources to recover")

    # Step 3: Reconstruct ProcessedSource objects
    processed: List[ProcessedSource] = []
    skipped = 0

    for ds in orphaned:
        ps = _reconstruct_processed_source(ds)
        if ps:
            processed.append(ps)
        else:
            skipped += 1

    logger.info(
        f"Reconstructed {len(processed)} sources ({skipped} skipped due to missing data)"
    )

    if not processed:
        return {
            "status": "no_recoverable",
            "sources_found": len(all_sources.data),
            "orphaned": len(orphaned),
            "skipped": skipped,
        }

    # Step 4: Regenerate embeddings (discovered_sources has them but as DB vectors)
    logger.info("Regenerating embeddings for recovered sources...")
    for ps in processed:
        try:
            embed_text = f"{ps.raw.title} {ps.analysis.summary}"
            ps.embedding = await _generate_embedding(embed_text)
        except Exception as e:
            logger.warning(f"Failed to generate embedding for {ps.raw.url}: {e}")
            ps.embedding = []

    # Step 5: Create a recovery discovery run record
    run_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    supabase.table("discovery_runs").insert(
        {
            "id": run_id,
            "status": "running",
            "triggered_by": "manual",
            "triggered_by_user": triggered_by_user_id,
            "cards_created": 0,
            "cards_enriched": 0,
            "cards_deduplicated": 0,
            "sources_found": len(processed),
            "started_at": now,
            "summary_report": {
                "stage": "running",
                "recovery": True,
                "date_range": f"{date_start} to {date_end}",
                "orphaned_sources": len(orphaned),
            },
        }
    ).execute()

    # Step 6: Run through signal agent
    config = DiscoveryConfig(
        max_new_cards_per_run=50,  # Higher limit for recovery
        use_signal_agent=True,
    )

    signal_agent = SignalAgentService(
        supabase=supabase,
        run_id=run_id,
        triggered_by_user_id=triggered_by_user_id,
    )

    try:
        result = await signal_agent.run_signal_detection(
            processed_sources=processed,
            config=config,
        )

        # Update discovery run as completed
        supabase.table("discovery_runs").update(
            {
                "status": "completed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "cards_created": len(result.signals_created),
                "cards_enriched": len(result.signals_enriched),
                "sources_found": len(processed),
                "summary_report": {
                    "stage": "completed",
                    "recovery": True,
                    "signals_created": len(result.signals_created),
                    "signals_enriched": len(result.signals_enriched),
                    "sources_linked": result.sources_linked,
                    "cost_estimate": result.cost_estimate,
                },
            }
        ).eq("id", run_id).execute()

        logger.info(
            f"Recovery complete: {len(result.signals_created)} signals created, "
            f"{len(result.signals_enriched)} enriched"
        )

        return {
            "status": "completed",
            "run_id": run_id,
            "sources_found": len(all_sources.data),
            "orphaned": len(orphaned),
            "recovered": len(processed),
            "signals_created": len(result.signals_created),
            "signals_enriched": len(result.signals_enriched),
            "sources_linked": result.sources_linked,
            "cost_estimate": result.cost_estimate,
        }

    except Exception as e:
        logger.error(f"Recovery failed: {e}", exc_info=True)
        supabase.table("discovery_runs").update(
            {
                "status": "failed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "summary_report": {
                    "stage": "failed",
                    "recovery": True,
                    "error": str(e),
                },
            }
        ).eq("id", run_id).execute()
        raise
