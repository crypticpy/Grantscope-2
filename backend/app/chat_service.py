"""
Chat Service for Foresight Application (Ask Foresight / NLQ).

Provides RAG-powered conversational AI with three scopes:
- signal: Deep Q&A about a single card and its sources
- workstream: Analysis across cards within a workstream
- global: Broad strategic intelligence search using vector similarity

Uses Azure OpenAI for streaming chat completions and embedding generation.
Context is assembled from Supabase and injected into the system prompt.
"""

import json
import re
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from supabase import Client

from app.openai_provider import (
    azure_openai_async_client,
    azure_openai_embedding_client,
    get_chat_deployment,
    get_chat_mini_deployment,
    get_embedding_deployment,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

RATE_LIMIT_PER_MINUTE = 20
MAX_CONVERSATION_MESSAGES = 50  # Max history messages to include
MAX_CONTEXT_CHARS = 24000  # Cap RAG context size sent to the LLM
STREAM_TIMEOUT = 120  # seconds


# ---------------------------------------------------------------------------
# SSE helpers
# ---------------------------------------------------------------------------


def _sse_event(event_type: str, data: Any) -> str:
    """Format a Server-Sent Event."""
    return f"data: {json.dumps({'type': event_type, 'data': data if event_type != 'token' else None, 'content': data if event_type == 'token' else None})}\n\n"


def _sse_token(content: str) -> str:
    """Format a streaming token SSE event."""
    return f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"


def _sse_error(message: str) -> str:
    """Format an error SSE event."""
    return f"data: {json.dumps({'type': 'error', 'content': message})}\n\n"


# ---------------------------------------------------------------------------
# Rate Limiting
# ---------------------------------------------------------------------------


async def _check_rate_limit(supabase: Client, user_id: str) -> bool:
    """
    Check if user has exceeded the chat rate limit.

    Returns True if the request should be allowed, False if rate limited.
    """
    try:
        one_minute_ago = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()

        # Count messages sent by this user in the last minute
        # We join through conversations to filter by user_id
        (
            supabase.table("chat_messages")
            .select("id", count="exact")
            .eq("role", "user")
            .gte("created_at", one_minute_ago)
            .execute()
        )

        # Since we can't easily filter by user_id through a join in postgrest,
        # we count via conversations
        conv_result = (
            supabase.table("chat_conversations")
            .select("id")
            .eq("user_id", user_id)
            .execute()
        )
        if not conv_result.data:
            return True  # No conversations = no messages = not rate limited

        conv_ids = [c["id"] for c in conv_result.data]

        # Count recent user messages across all their conversations
        count = 0
        # Process in batches to avoid query length limits
        for i in range(0, len(conv_ids), 20):
            batch = conv_ids[i : i + 20]
            msg_result = (
                supabase.table("chat_messages")
                .select("id", count="exact")
                .in_("conversation_id", batch)
                .eq("role", "user")
                .gte("created_at", one_minute_ago)
                .execute()
            )
            count += msg_result.count or 0

        return count < RATE_LIMIT_PER_MINUTE

    except Exception as e:
        logger.warning(f"Rate limit check failed (allowing request): {e}")
        return True  # Fail open


# ---------------------------------------------------------------------------
# Context Retrieval — Signal Scope
# ---------------------------------------------------------------------------


async def _retrieve_signal_context(
    supabase: Client, card_id: str
) -> Tuple[str, Dict[str, Any]]:
    """
    Retrieve full context for a single signal (card).

    Returns (context_text, metadata_dict) where context_text is the
    assembled RAG context and metadata_dict contains card info for
    the system prompt builder.
    """
    # Fetch card details
    card_result = (
        supabase.table("cards")
        .select(
            "id, slug, name, summary, description, pillar_id, goal_id, "
            "horizon, stage_id, novelty_score, impact_score, "
            "relevance_score, velocity_score, risk_score, "
            "opportunity_score, signal_quality_score, status"
        )
        .eq("id", card_id)
        .execute()
    )

    if not card_result.data:
        return "", {"error": "Card not found"}

    card = card_result.data[0]
    parts = [f"## Signal: {card.get('name', 'Unknown')}"]

    parts.append(f"Summary: {card.get('summary', 'No summary available')}")
    if card.get("description"):
        parts.append(f"Description: {card['description'][:2000]}")
    parts.append(
        f"Pillar: {card.get('pillar_id', 'N/A')} | "
        f"Goal: {card.get('goal_id', 'N/A')} | "
        f"Horizon: {card.get('horizon', 'N/A')} | "
        f"Stage: {card.get('stage_id', 'N/A')}"
    )

    # Scores
    scores = []
    for score_name in [
        "impact_score",
        "relevance_score",
        "novelty_score",
        "velocity_score",
        "risk_score",
        "opportunity_score",
        "signal_quality_score",
    ]:
        val = card.get(score_name)
        if val is not None:
            label = score_name.replace("_score", "").replace("_", " ").title()
            scores.append(f"{label}: {val}")
    if scores:
        parts.append(f"Scores: {', '.join(scores)}")

    # Fetch all sources for this card
    sources_result = (
        supabase.table("sources")
        .select(
            "id, title, url, ai_summary, key_excerpts, full_text, "
            "source_type, publisher, published_date, relevance_score"
        )
        .eq("card_id", card_id)
        .order("relevance_score", desc=True)
        .execute()
    )

    sources = sources_result.data or []
    source_map = {}  # For citation resolution later

    if sources:
        parts.append(f"\n## Sources ({len(sources)} total)")
        for i, src in enumerate(sources, 1):
            source_map[i] = {
                "source_id": src["id"],
                "card_id": card_id,
                "card_slug": card.get("slug", ""),
                "title": src.get("title", "Untitled"),
                "url": src.get("url", ""),
                "published_date": src.get("published_date", None),
                "excerpt": (
                    (src.get("key_excerpts") or [None])[0]
                    if src.get("key_excerpts")
                    else (
                        (src.get("ai_summary", "") or "")[:200]
                        if src.get("ai_summary")
                        else None
                    )
                ),
            }

            parts.append(f"\n### [{i}] {src.get('title', 'Untitled')}")
            if src.get("url"):
                parts.append(f"URL: {src['url']}")
            if src.get("publisher"):
                parts.append(f"Publisher: {src['publisher']}")
            if src.get("published_date"):
                parts.append(f"Published: {src['published_date']}")
            if src.get("ai_summary"):
                parts.append(f"AI Summary: {src['ai_summary']}")
            if src.get("key_excerpts"):
                excerpts = src["key_excerpts"]
                if isinstance(excerpts, list) and excerpts:
                    parts.append("Key Excerpts:")
                    parts.extend(f"  - {exc}" for exc in excerpts[:3])
            if src.get("full_text"):
                # Truncate full text to avoid exceeding context window
                full = src["full_text"][:3000]
                parts.append(f"Content: {full}")

    # Fetch timeline events with deep research reports
    try:
        timeline_result = (
            supabase.table("card_timeline")
            .select("event_type, title, description, metadata, created_at")
            .eq("card_id", card_id)
            .order("created_at", desc=True)
            .limit(20)
            .execute()
        )
        if timeline_events := timeline_result.data or []:
            parts.append(f"\n## Timeline ({len(timeline_events)} events)")
            for evt in timeline_events[:10]:
                parts.append(
                    f"- [{evt.get('event_type')}] {evt.get('title')} "
                    f"({evt.get('created_at', '')[:10]})"
                )
                if evt.get("description"):
                    parts.append(f"  {evt['description'][:300]}")
                # Check for deep research reports in metadata
                meta = evt.get("metadata") or {}
                if isinstance(meta, dict):
                    if report := meta.get("report_preview") or meta.get(
                        "deep_research_report"
                    ):
                        parts.append(f"  Research Report Excerpt: {str(report)[:1500]}")
    except Exception as e:
        logger.warning(f"Failed to fetch timeline for card {card_id}: {e}")

    # Fetch deep research reports from research_tasks table
    try:
        research_result = (
            supabase.table("research_tasks")
            .select("task_type, result_summary, completed_at")
            .eq("card_id", card_id)
            .eq("status", "completed")
            .order("completed_at", desc=True)
            .limit(3)
            .execute()
        )
        for task in research_result.data or []:
            result_summary = task.get("result_summary") or {}
            if isinstance(result_summary, dict):
                if report := result_summary.get("report_preview") or result_summary.get(
                    "report"
                ):
                    parts.append(
                        f"\n## Deep Research Report ({task.get('completed_at', '')[:10]})"
                    )
                    parts.append(str(report)[:3000])
    except Exception as e:
        logger.warning(f"Failed to fetch research tasks for card {card_id}: {e}")

    context_text = "\n".join(parts)
    # Truncate to max context size
    if len(context_text) > MAX_CONTEXT_CHARS:
        context_text = context_text[:MAX_CONTEXT_CHARS] + "\n\n[Context truncated]"

    metadata = {
        "card_name": card.get("name"),
        "card_id": card_id,
        "source_count": len(sources),
        "source_map": source_map,
    }

    return context_text, metadata


# ---------------------------------------------------------------------------
# Context Retrieval — Workstream Scope
# ---------------------------------------------------------------------------


async def _retrieve_workstream_context(
    supabase: Client, workstream_id: str
) -> Tuple[str, Dict[str, Any]]:
    """
    Retrieve context for a workstream and its cards.

    Returns (context_text, metadata_dict).
    """
    # Fetch workstream details
    ws_result = (
        supabase.table("workstreams")
        .select("id, name, description, keywords, pillar_ids, goal_ids, horizon")
        .eq("id", workstream_id)
        .execute()
    )

    if not ws_result.data:
        return "", {"error": "Workstream not found"}

    ws = ws_result.data[0]
    parts = [f"## Workstream: {ws.get('name', 'Unknown')}"]

    if ws.get("description"):
        parts.append(f"Description: {ws['description']}")
    if ws.get("keywords"):
        keywords = ws["keywords"]
        if isinstance(keywords, list):
            parts.append(f"Keywords: {', '.join(keywords)}")
    if ws.get("pillar_ids"):
        parts.append(f"Pillars: {', '.join(ws['pillar_ids'])}")
    if ws.get("horizon"):
        parts.append(f"Horizon: {ws['horizon']}")

    # Fetch cards in workstream via join table
    wc_result = (
        supabase.table("workstream_cards")
        .select("card_id")
        .eq("workstream_id", workstream_id)
        .limit(20)
        .execute()
    )

    card_ids = [wc["card_id"] for wc in (wc_result.data or [])]
    source_map = {}
    if card_ids:
        # Fetch card details
        cards_result = (
            supabase.table("cards")
            .select(
                "id, slug, name, summary, pillar_id, goal_id, horizon, stage_id, "
                "impact_score, relevance_score, velocity_score"
            )
            .in_("id", card_ids)
            .execute()
        )

        cards = cards_result.data or []
        parts.append(f"\n## Cards in Workstream ({len(cards)} signals)")

        source_idx = 1

        for card in cards:
            card_id = card["id"]
            parts.append(f"\n### {card.get('name', 'Unknown')}")
            parts.append(f"Summary: {card.get('summary', 'N/A')}")
            parts.append(
                f"Pillar: {card.get('pillar_id', 'N/A')} | "
                f"Horizon: {card.get('horizon', 'N/A')} | "
                f"Stage: {card.get('stage_id', 'N/A')}"
            )

            score_parts = []
            for sn in ["impact_score", "relevance_score", "velocity_score"]:
                v = card.get(sn)
                if v is not None:
                    score_parts.append(f"{sn.replace('_score', '').title()}: {v}")
            if score_parts:
                parts.append(f"Scores: {', '.join(score_parts)}")

            # Fetch top 3 sources per card
            try:
                src_result = (
                    supabase.table("sources")
                    .select("id, title, url, ai_summary, key_excerpts, published_date")
                    .eq("card_id", card_id)
                    .order("relevance_score", desc=True)
                    .limit(3)
                    .execute()
                )

                for src in src_result.data or []:
                    source_map[source_idx] = {
                        "source_id": src["id"],
                        "card_id": card_id,
                        "card_slug": card.get("slug", ""),
                        "title": src.get("title", "Untitled"),
                        "url": src.get("url", ""),
                        "published_date": src.get("published_date", None),
                        "excerpt": (
                            (src.get("key_excerpts") or [None])[0]
                            if src.get("key_excerpts")
                            else (
                                (src.get("ai_summary", "") or "")[:200]
                                if src.get("ai_summary")
                                else None
                            )
                        ),
                    }
                    parts.append(f"  [{source_idx}] {src.get('title', 'Untitled')}")
                    if src.get("ai_summary"):
                        parts.append(f"      Summary: {src['ai_summary'][:400]}")
                    if src.get("key_excerpts"):
                        excerpts = src["key_excerpts"]
                        if isinstance(excerpts, list) and excerpts:
                            parts.append(f"      Key insight: {excerpts[0][:200]}")
                    source_idx += 1
            except Exception as e:
                logger.warning(f"Failed to fetch sources for card {card_id}: {e}")

    context_text = "\n".join(parts)
    if len(context_text) > MAX_CONTEXT_CHARS:
        context_text = context_text[:MAX_CONTEXT_CHARS] + "\n\n[Context truncated]"

    metadata = {
        "workstream_name": ws.get("name"),
        "workstream_id": workstream_id,
        "card_count": len(card_ids),
        "source_map": source_map,
    }

    return context_text, metadata


# ---------------------------------------------------------------------------
# Context Retrieval — Global Scope
# ---------------------------------------------------------------------------


async def _retrieve_global_context(
    supabase: Client, query: str
) -> Tuple[str, Dict[str, Any]]:
    """
    Retrieve context for a global (unscoped) question using semantic search.

    Uses embeddings to find the most relevant cards, then fetches their
    top sources. Also includes active pattern insights for cross-signal context.

    Returns (context_text, metadata_dict).
    """
    # Generate embedding for the user's query
    try:
        embedding_response = azure_openai_embedding_client.embeddings.create(
            model=get_embedding_deployment(),
            input=query[:8000],
        )
        query_embedding = embedding_response.data[0].embedding
    except Exception as e:
        logger.error(f"Failed to generate query embedding: {e}")
        return "", {"error": "Failed to process query for search"}

    # Vector similarity search
    try:
        search_result = supabase.rpc(
            "match_cards_by_embedding",
            {
                "query_embedding": query_embedding,
                "match_threshold": 0.70,
                "match_count": 15,
            },
        ).execute()

        matched_cards = search_result.data or []
    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        matched_cards = []

    parts = []
    source_map = {}
    if matched_cards:
        parts.append(f"## Relevant Signals ({len(matched_cards)} found)")

        # Fetch full card details for matched cards
        matched_ids = [c["id"] for c in matched_cards]
        similarity_map = {c["id"]: c.get("similarity", 0) for c in matched_cards}

        cards_result = (
            supabase.table("cards")
            .select(
                "id, slug, name, summary, description, pillar_id, goal_id, "
                "horizon, stage_id, impact_score, relevance_score, "
                "velocity_score, risk_score"
            )
            .in_("id", matched_ids)
            .execute()
        )

        source_idx = 1

        for card in cards_result.data or []:
            card_id = card["id"]
            sim = similarity_map.get(card_id, 0)
            parts.extend(
                (
                    f"\n### {card.get('name', 'Unknown')} (relevance: {sim:.2f})",
                    f"Summary: {card.get('summary', 'N/A')}",
                )
            )
            if card.get("description"):
                parts.append(f"Description: {card['description'][:500]}")
            parts.append(
                f"Pillar: {card.get('pillar_id', 'N/A')} | "
                f"Horizon: {card.get('horizon', 'N/A')} | "
                f"Stage: {card.get('stage_id', 'N/A')}"
            )

            # Fetch top 2 sources per card
            try:
                src_result = (
                    supabase.table("sources")
                    .select("id, title, url, ai_summary, key_excerpts, published_date")
                    .eq("card_id", card_id)
                    .order("relevance_score", desc=True)
                    .limit(2)
                    .execute()
                )

                for src in src_result.data or []:
                    source_map[source_idx] = {
                        "source_id": src["id"],
                        "card_id": card_id,
                        "card_slug": card.get("slug", ""),
                        "title": src.get("title", "Untitled"),
                        "url": src.get("url", ""),
                        "published_date": src.get("published_date", None),
                        "excerpt": (
                            (src.get("key_excerpts") or [None])[0]
                            if src.get("key_excerpts")
                            else (
                                (src.get("ai_summary", "") or "")[:200]
                                if src.get("ai_summary")
                                else None
                            )
                        ),
                    }
                    parts.append(f"  [{source_idx}] {src.get('title', 'Untitled')}")
                    if src.get("ai_summary"):
                        parts.append(f"      {src['ai_summary'][:300]}")
                    source_idx += 1
            except Exception as e:
                logger.warning(f"Failed to fetch sources for card {card_id}: {e}")

    # Fetch active pattern insights for cross-signal context
    try:
        patterns_result = (
            supabase.table("pattern_insights")
            .select(
                "pattern_title, pattern_summary, opportunity, "
                "affected_pillars, urgency, confidence"
            )
            .eq("status", "active")
            .order("created_at", desc=True)
            .limit(5)
            .execute()
        )

        if patterns := patterns_result.data or []:
            parts.append(f"\n## Active Cross-Signal Patterns ({len(patterns)})")
            for pat in patterns:
                pillars = pat.get("affected_pillars", [])
                if isinstance(pillars, list):
                    pillars = ", ".join(pillars)
                parts.extend(
                    (
                        f"\n**{pat.get('pattern_title', 'Unknown')}** (Urgency: {pat.get('urgency', 'N/A')}, Confidence: {pat.get('confidence', 'N/A')})",
                        f"Pillars: {pillars}",
                    )
                )
                if pat.get("pattern_summary"):
                    parts.append(f"Summary: {pat['pattern_summary']}")
                if pat.get("opportunity"):
                    parts.append(f"Opportunity: {pat['opportunity']}")
    except Exception as e:
        logger.warning(f"Failed to fetch pattern insights: {e}")

    context_text = "\n".join(parts)
    if len(context_text) > MAX_CONTEXT_CHARS:
        context_text = context_text[:MAX_CONTEXT_CHARS] + "\n\n[Context truncated]"

    metadata = {
        "matched_cards": len(matched_cards),
        "source_map": source_map,
    }

    return context_text, metadata


# ---------------------------------------------------------------------------
# Context Retrieval — @Mention Resolution
# ---------------------------------------------------------------------------

MAX_MENTION_CONTEXT_CHARS = 8000  # Cap for mention context to stay within budget


async def _resolve_mention_context(
    supabase_client: Client,
    message: str,
    mentions: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """
    Resolve @mention references and return formatted context for the LLM.

    Supports two resolution paths:
    1. Structured mentions from the frontend (preferred) — list of dicts with
       id, type, and title.
    2. Regex fallback — parses @[Title] patterns from the message text and
       searches cards/workstreams by name.

    Returns a formatted context string capped at MAX_MENTION_CONTEXT_CHARS,
    or an empty string if no mentions are found or resolved.
    """
    # Collect mention descriptors: list of {"id": ..., "type": ..., "title": ...}
    mention_refs: List[Dict[str, Any]] = []

    if mentions:
        # Path 1: structured mentions from the frontend
        for m in mentions:
            mention_refs.append(
                {
                    "id": m.get("id"),
                    "type": m.get("type", "signal"),
                    "title": m.get("title", ""),
                }
            )
    else:
        # Path 2: regex fallback — parse @[Title] from message text
        pattern = r"@\[([^\]]+)\]"
        matches = re.findall(pattern, message)
        for title in matches:
            mention_refs.append({"id": None, "type": None, "title": title})

    if not mention_refs:
        return ""

    parts: List[str] = ["## Referenced Entities"]

    for ref in mention_refs:
        try:
            resolved = False

            # --- Attempt signal resolution ---
            if ref["type"] in ("signal", None):
                card = await _resolve_signal_mention(
                    supabase_client, ref.get("id"), ref["title"]
                )
                if card:
                    parts.append(_format_signal_mention(card))
                    resolved = True

            # --- Attempt workstream resolution ---
            if ref["type"] in ("workstream", None) and not resolved:
                ws = await _resolve_workstream_mention(
                    supabase_client, ref.get("id"), ref["title"]
                )
                if ws:
                    parts.append(_format_workstream_mention(ws))

        except Exception as e:
            logger.warning(f"Failed to resolve mention '{ref.get('title')}': {e}")
            continue

    # If only the header was added, nothing was resolved
    if len(parts) <= 1:
        return ""

    context = "\n\n".join(parts)
    if len(context) > MAX_MENTION_CONTEXT_CHARS:
        context = (
            context[:MAX_MENTION_CONTEXT_CHARS] + "\n\n[Mention context truncated]"
        )

    return context


async def _resolve_signal_mention(
    supabase_client: Client,
    card_id: Optional[str],
    title: str,
) -> Optional[Dict[str, Any]]:
    """
    Resolve a signal mention by ID or by title (ILIKE).

    Returns a dict with card details and top 5 sources, or None if not found.
    """
    card_data = None

    if card_id:
        result = (
            supabase_client.table("cards")
            .select(
                "id, slug, name, summary, description, pillar_id, "
                "horizon, stage_id, impact_score, relevance_score"
            )
            .eq("id", card_id)
            .execute()
        )
        if result.data:
            card_data = result.data[0]

    if not card_data and title:
        result = (
            supabase_client.table("cards")
            .select(
                "id, slug, name, summary, description, pillar_id, "
                "horizon, stage_id, impact_score, relevance_score"
            )
            .ilike("name", f"%{title}%")
            .limit(1)
            .execute()
        )
        if result.data:
            card_data = result.data[0]

    if not card_data:
        return None

    # Fetch top 5 sources for the card
    try:
        src_result = (
            supabase_client.table("sources")
            .select("title, url, ai_summary, key_excerpts")
            .eq("card_id", card_data["id"])
            .order("relevance_score", desc=True)
            .limit(5)
            .execute()
        )
        card_data["_sources"] = src_result.data or []
    except Exception as e:
        logger.warning(
            f"Failed to fetch sources for mentioned card {card_data['id']}: {e}"
        )
        card_data["_sources"] = []

    return card_data


async def _resolve_workstream_mention(
    supabase_client: Client,
    workstream_id: Optional[str],
    title: str,
) -> Optional[Dict[str, Any]]:
    """
    Resolve a workstream mention by ID or by title (ILIKE).

    Returns a dict with workstream details and its card names, or None if not found.
    """
    ws_data = None

    if workstream_id:
        result = (
            supabase_client.table("workstreams")
            .select("id, name, description")
            .eq("id", workstream_id)
            .execute()
        )
        if result.data:
            ws_data = result.data[0]

    if not ws_data and title:
        result = (
            supabase_client.table("workstreams")
            .select("id, name, description")
            .ilike("name", f"%{title}%")
            .limit(1)
            .execute()
        )
        if result.data:
            ws_data = result.data[0]

    if not ws_data:
        return None

    # Fetch card names belonging to this workstream
    try:
        wc_result = (
            supabase_client.table("workstream_cards")
            .select("card_id")
            .eq("workstream_id", ws_data["id"])
            .limit(20)
            .execute()
        )
        card_ids = [wc["card_id"] for wc in (wc_result.data or [])]

        if card_ids:
            cards_result = (
                supabase_client.table("cards")
                .select("name")
                .in_("id", card_ids)
                .execute()
            )
            ws_data["_card_names"] = [
                c["name"] for c in (cards_result.data or []) if c.get("name")
            ]
        else:
            ws_data["_card_names"] = []
    except Exception as e:
        logger.warning(
            f"Failed to fetch cards for mentioned workstream {ws_data['id']}: {e}"
        )
        ws_data["_card_names"] = []

    return ws_data


def _format_signal_mention(card: Dict[str, Any]) -> str:
    """Format a resolved signal mention into a context block."""
    lines = [f"### Signal: {card.get('name', 'Unknown')}"]

    if card.get("summary"):
        lines.append(f"Summary: {card['summary']}")
    if card.get("description"):
        lines.append(f"Description: {card['description'][:800]}")
    if card.get("pillar_id") or card.get("horizon"):
        lines.append(
            f"Pillar: {card.get('pillar_id', 'N/A')} | "
            f"Horizon: {card.get('horizon', 'N/A')} | "
            f"Stage: {card.get('stage_id', 'N/A')}"
        )

    scores = []
    for key in ("impact_score", "relevance_score"):
        val = card.get(key)
        if val is not None:
            label = key.replace("_score", "").replace("_", " ").title()
            scores.append(f"{label}: {val}")
    if scores:
        lines.append(f"Scores: {', '.join(scores)}")

    sources = card.get("_sources", [])
    if sources:
        lines.append("Key Sources:")
        for src in sources:
            src_title = src.get("title", "Untitled")
            excerpt = ""
            if src.get("ai_summary"):
                excerpt = (src["ai_summary"] or "")[:200]
            elif src.get("key_excerpts"):
                excerpts = src["key_excerpts"]
                if isinstance(excerpts, list) and excerpts:
                    excerpt = str(excerpts[0])[:200]
            if excerpt:
                lines.append(f"- {src_title}: {excerpt}")
            else:
                lines.append(f"- {src_title}")

    return "\n".join(lines)


def _format_workstream_mention(ws: Dict[str, Any]) -> str:
    """Format a resolved workstream mention into a context block."""
    lines = [f"### Workstream: {ws.get('name', 'Unknown')}"]

    if ws.get("description"):
        lines.append(f"Description: {ws['description'][:600]}")

    card_names = ws.get("_card_names", [])
    if card_names:
        lines.append(f"Cards ({len(card_names)}): {', '.join(card_names)}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# System Prompt Builder
# ---------------------------------------------------------------------------


def _build_system_prompt(
    scope: str,
    context_text: str,
    scope_metadata: Dict[str, Any],
) -> str:
    """
    Build the system prompt with RAG context injected.

    The prompt instructs the LLM to:
    - Act as the City of Austin's strategic intelligence assistant
    - Use the provided context to answer questions
    - Cite sources using [N] notation matching context order
    - Be analytical, strategic, and forward-looking
    """
    scope_descriptions = {
        "signal": (
            f"You are answering questions about a specific signal (intelligence card): "
            f"\"{scope_metadata.get('card_name', 'Unknown Signal')}\". "
            f"This card has {scope_metadata.get('source_count', 0)} sources. "
            f"Use the detailed card information and source content below to provide "
            f"thorough, evidence-based answers about this signal."
        ),
        "workstream": (
            f"You are answering questions about a research workstream: "
            f"\"{scope_metadata.get('workstream_name', 'Unknown Workstream')}\". "
            f"This workstream tracks {scope_metadata.get('card_count', 0)} signals. "
            f"Use the workstream overview and card summaries below to provide "
            f"analytical insights about trends, priorities, and strategic implications "
            f"across all signals in this workstream."
        ),
        "global": (
            f"You are answering a broad strategic intelligence question. "
            f"The system found {scope_metadata.get('matched_cards', 0)} relevant signals "
            f"using semantic search. Use the search results and pattern insights below "
            f"to provide comprehensive, cross-cutting strategic analysis."
        ),
    }

    scope_desc = scope_descriptions.get(scope, scope_descriptions["global"])

    return f"""You are Foresight, the City of Austin's AI strategic intelligence assistant.

You help city leaders, analysts, and decision-makers understand emerging trends, technologies, and issues that could impact municipal operations. You are part of a horizon scanning system aligned with Austin's strategic framework.

## Your Current Context
{scope_desc}

## Instructions
- Answer questions using ONLY the provided context below. If the context doesn't contain enough information, say so clearly.
- Cite your sources using [N] notation (e.g., [1], [2]) that corresponds to the numbered sources in the context.
- Be analytical, strategic, and forward-looking in your responses.
- When discussing implications, consider impact on city services, budgets, equity, and residents.
- Provide actionable insights when possible — what should the city consider, prepare for, or investigate?
- Use clear, professional language suitable for government officials and analysts.
- If asked about topics outside the provided context, acknowledge the limitation and suggest what might be relevant.

## Strategic Framework Reference
- Pillars: CH (Community Health), MC (Mobility), HS (Housing), EC (Economic), ES (Environmental), CE (Cultural)
- Horizons: H1 (Mainstream), H2 (Transitional/Pilots), H3 (Weak Signals/Emerging)
- Stages: 1-Concept, 2-Emerging, 3-Prototype, 4-Pilot, 5-Municipal Pilot, 6-Early Adoption, 7-Mainstream, 8-Mature

## Context
{context_text}
"""


# ---------------------------------------------------------------------------
# Citation Parsing
# ---------------------------------------------------------------------------


def _parse_citations(
    response_text: str,
    source_map: Dict[int, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Parse [N] citation references from the response text and resolve
    them to actual source data from the source_map.

    Returns a list of citation objects with card_id, source_id, title, url, excerpt.
    """
    # Find all [N] references in the text
    citation_refs = re.findall(r"\[(\d+)\]", response_text)
    seen = set()
    citations = []

    for ref_str in citation_refs:
        ref_num = int(ref_str)
        if ref_num in seen:
            continue
        seen.add(ref_num)

        if source_info := source_map.get(ref_num):
            citations.append(
                {
                    "index": ref_num,
                    "card_id": source_info.get("card_id"),
                    "card_slug": source_info.get("card_slug", ""),
                    "source_id": source_info.get("source_id"),
                    "title": source_info.get("title", ""),
                    "url": source_info.get("url", ""),
                    "published_date": source_info.get("published_date"),
                    "excerpt": source_info.get("excerpt"),
                }
            )

    return citations


# ---------------------------------------------------------------------------
# Conversation Management
# ---------------------------------------------------------------------------


async def _get_or_create_conversation(
    supabase: Client,
    user_id: str,
    scope: str,
    scope_id: Optional[str],
    conversation_id: Optional[str],
    first_message: str,
) -> Tuple[str, bool]:
    """
    Get existing or create new conversation.

    Returns (conversation_id, is_new).
    """
    if conversation_id:
        # Verify the conversation exists and belongs to the user
        result = (
            supabase.table("chat_conversations")
            .select("id")
            .eq("id", conversation_id)
            .eq("user_id", user_id)
            .execute()
        )
        if result.data:
            return conversation_id, False
        else:
            logger.warning(
                f"Conversation {conversation_id} not found for user {user_id}"
            )
            # Fall through to create new one

    # Generate title from first message using mini model
    title = first_message[:100]
    try:
        title_response = await azure_openai_async_client.chat.completions.create(
            model=get_chat_mini_deployment(),
            messages=[
                {
                    "role": "system",
                    "content": "Generate a concise title (max 60 chars) for a conversation "
                    "that starts with this message. Return ONLY the title text, "
                    "no quotes or extra formatting.",
                },
                {"role": "user", "content": first_message[:500]},
            ],
            max_tokens=30,
            temperature=0.5,
        )
        if generated_title := title_response.choices[0].message.content.strip():
            title = generated_title[:100]
    except Exception as e:
        logger.warning(f"Failed to generate conversation title: {e}")

    # Create new conversation
    now = datetime.now(timezone.utc).isoformat()
    insert_data = {
        "user_id": user_id,
        "scope": scope,
        "scope_id": scope_id,
        "title": title,
        "created_at": now,
        "updated_at": now,
    }

    result = supabase.table("chat_conversations").insert(insert_data).execute()

    if result.data:
        return result.data[0]["id"], True
    else:
        raise ValueError("Failed to create conversation")


async def _get_conversation_history(
    supabase: Client,
    conversation_id: str,
) -> List[Dict[str, str]]:
    """
    Fetch recent conversation history for inclusion in the chat context.

    Returns messages in OpenAI format: [{"role": "...", "content": "..."}]
    """
    result = (
        supabase.table("chat_messages")
        .select("role, content")
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .limit(MAX_CONVERSATION_MESSAGES)
        .execute()
    )

    return [
        {"role": msg["role"], "content": msg["content"]} for msg in (result.data or [])
    ]


async def _store_message(
    supabase: Client,
    conversation_id: str,
    role: str,
    content: str,
    citations: Optional[List[Dict]] = None,
    tokens_used: Optional[int] = None,
    model: Optional[str] = None,
) -> str:
    """Store a message in the database. Returns the message ID."""
    now = datetime.now(timezone.utc).isoformat()
    insert_data = {
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
        "citations": citations or [],
        "tokens_used": tokens_used,
        "model": model,
        "created_at": now,
    }

    result = supabase.table("chat_messages").insert(insert_data).execute()

    if result.data:
        return result.data[0]["id"]

    logger.error(f"Failed to store {role} message for conversation {conversation_id}")
    return ""


async def _update_conversation_timestamp(
    supabase: Client, conversation_id: str
) -> None:
    """Update the conversation's updated_at timestamp."""
    try:
        supabase.table("chat_conversations").update(
            {"updated_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", conversation_id).execute()
    except Exception as e:
        logger.warning(f"Failed to update conversation timestamp: {e}")


# ---------------------------------------------------------------------------
# Main Chat Function
# ---------------------------------------------------------------------------


async def chat(
    scope: str,
    scope_id: Optional[str],
    message: str,
    conversation_id: Optional[str],
    user_id: str,
    supabase_client: Client,
    mentions: Optional[List[Dict[str, Any]]] = None,
) -> AsyncGenerator[str, None]:
    """
    Main chat function that returns an async generator of SSE events.

    Orchestrates:
    1. Rate limiting
    2. Conversation management
    3. Context retrieval (scope-dependent)
    4. Streaming LLM response
    5. Citation parsing and storage

    Yields SSE-formatted strings:
    - {"type": "token", "content": "..."} for streaming tokens
    - {"type": "citation", "data": {...}} for each resolved citation
    - {"type": "suggestions", "data": [...]} for follow-up questions
    - {"type": "done", "data": {"conversation_id": "...", "message_id": "..."}}
    - {"type": "error", "content": "..."} on errors
    """
    try:
        # 1. Rate limiting
        if not await _check_rate_limit(supabase_client, user_id):
            yield _sse_error(
                "Rate limit exceeded. Please wait a moment before sending another message."
            )
            return

        # 2. Conversation management
        try:
            conv_id, is_new = await _get_or_create_conversation(
                supabase_client,
                user_id,
                scope,
                scope_id,
                conversation_id,
                message,
            )
        except Exception as e:
            logger.error(f"Failed to manage conversation: {e}")
            yield _sse_error("Failed to create or find conversation. Please try again.")
            return

        # Store the user message
        await _store_message(supabase_client, conv_id, "user", message)

        # 3. Retrieve context based on scope
        context_text = ""
        scope_metadata: Dict[str, Any] = {}

        try:
            if scope == "signal" and scope_id:
                context_text, scope_metadata = await _retrieve_signal_context(
                    supabase_client, scope_id
                )
            elif scope == "workstream" and scope_id:
                context_text, scope_metadata = await _retrieve_workstream_context(
                    supabase_client, scope_id
                )
            else:
                # Global scope — use semantic search
                context_text, scope_metadata = await _retrieve_global_context(
                    supabase_client, message
                )
        except Exception as e:
            logger.error(f"Context retrieval failed for scope={scope}: {e}")
            yield _sse_error("Failed to retrieve context. Please try again.")
            return

        if scope_metadata.get("error"):
            yield _sse_error(f"Context error: {scope_metadata['error']}")
            return

        source_map = scope_metadata.get("source_map", {})

        # 3b. Resolve @mention context (if any)
        mention_context = ""
        if mentions or re.search(r"@\[[^\]]+\]", message):
            try:
                # Convert MentionRef models to dicts if needed
                mention_dicts = None
                if mentions:
                    mention_dicts = [
                        (
                            m
                            if isinstance(m, dict)
                            else (
                                m.dict()
                                if hasattr(m, "dict")
                                else {"id": m.id, "type": m.type, "title": m.title}
                            )
                        )
                        for m in mentions
                    ]

                yield _sse_event(
                    "progress",
                    {
                        "step": "mentions",
                        "detail": (
                            f"Loading context for {len(mention_dicts or [])} mentioned entities..."
                            if mention_dicts
                            else "Resolving @mentions from message..."
                        ),
                    },
                )

                mention_context = await _resolve_mention_context(
                    supabase_client, message, mention_dicts
                )
                if mention_context:
                    context_text = context_text + "\n\n" + mention_context
                    # Re-enforce the overall context cap
                    if len(context_text) > MAX_CONTEXT_CHARS:
                        context_text = (
                            context_text[:MAX_CONTEXT_CHARS] + "\n\n[Context truncated]"
                        )
            except Exception as e:
                logger.warning(f"Mention context resolution failed: {e}")

        yield _sse_event(
            "progress",
            {
                "step": "searching",
                "detail": f"Found {len(source_map)} sources across {scope_metadata.get('card_count', scope_metadata.get('matched_cards', 1))} signals",
            },
        )

        # 4. Build messages for the LLM
        system_prompt = _build_system_prompt(scope, context_text, scope_metadata)

        # Get conversation history (for multi-turn context)
        history = await _get_conversation_history(supabase_client, conv_id)

        # Build the messages array
        messages = [{"role": "system", "content": system_prompt}]

        # Include recent history (skip the last user message since we'll add it fresh)
        if history:
            # Only include prior messages, not the one we just stored
            prior = history[:-1] if history else []
            # Limit history to keep within token budget
            messages.extend(iter(prior[-10:]))
        messages.append({"role": "user", "content": message})

        yield _sse_event(
            "progress",
            {
                "step": "analyzing",
                "detail": "Analyzing sources and synthesizing response...",
            },
        )

        # 5. Stream the LLM response
        full_response = ""
        total_tokens = 0
        model_used = get_chat_deployment()

        try:
            stream = await azure_openai_async_client.chat.completions.create(
                model=model_used,
                messages=messages,
                stream=True,
                temperature=0.7,
                max_tokens=4096,
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    full_response += token
                    yield _sse_token(token)

                # Track usage if available
                if hasattr(chunk, "usage") and chunk.usage:
                    total_tokens = getattr(chunk.usage, "total_tokens", 0)

        except Exception as e:
            error_type = type(e).__name__
            logger.error(f"Azure OpenAI streaming error ({error_type}): {e}")

            if "rate_limit" in str(e).lower() or "429" in str(e):
                yield _sse_error(
                    "The AI service is currently busy. Please try again in a moment."
                )
            elif "timeout" in str(e).lower():
                yield _sse_error(
                    "The request timed out. Please try a simpler question."
                )
            elif "connection" in str(e).lower():
                yield _sse_error("Connection to AI service lost. Please try again.")
            else:
                yield _sse_error(
                    "An error occurred while generating a response. Please try again."
                )

            # Still store partial response if we got any
            if full_response:
                await _store_message(
                    supabase_client,
                    conv_id,
                    "assistant",
                    full_response,
                    model=model_used,
                )
                await _update_conversation_timestamp(supabase_client, conv_id)
            return

        yield _sse_event(
            "progress", {"step": "citing", "detail": "Resolving citations..."}
        )

        # 6. Post-processing: parse citations
        citations = _parse_citations(full_response, source_map)
        for citation in citations:
            yield f"data: {json.dumps({'type': 'citation', 'data': citation})}\n\n"

        # Collect confidence metadata
        meta = {
            "source_count": len(source_map),
            "citation_count": len(citations),
        }
        # Scope-specific metadata
        if scope == "signal":
            meta["signal_name"] = scope_metadata.get("card_name")
            meta["source_count"] = scope_metadata.get("source_count", len(source_map))
        elif scope == "workstream":
            meta["workstream_name"] = scope_metadata.get("workstream_name")
            meta["card_count"] = scope_metadata.get("card_count", 0)
        elif scope == "global":
            meta["matched_cards"] = scope_metadata.get("matched_cards", 0)

        yield _sse_event("metadata", meta)

        # 7. Store assistant message
        message_id = await _store_message(
            supabase_client,
            conv_id,
            "assistant",
            full_response,
            citations=citations,
            tokens_used=total_tokens or None,
            model=model_used,
        )

        # Update conversation timestamp
        await _update_conversation_timestamp(supabase_client, conv_id)

        # 8. Generate follow-up suggestions (non-blocking, best-effort)
        try:
            suggestions = await _generate_suggestions_internal(
                scope, scope_metadata, full_response, message
            )
            if suggestions:
                yield f"data: {json.dumps({'type': 'suggestions', 'data': suggestions})}\n\n"
        except Exception as e:
            logger.warning(f"Failed to generate suggestions: {e}")

        # 9. Done event
        yield f"data: {json.dumps({'type': 'done', 'data': {'conversation_id': conv_id, 'message_id': message_id}})}\n\n"

    except Exception as e:
        logger.error(f"Unhandled error in chat generator: {e}", exc_info=True)
        yield _sse_error("An unexpected error occurred. Please try again.")


# ---------------------------------------------------------------------------
# Suggestion Generation
# ---------------------------------------------------------------------------


async def _generate_suggestions_internal(
    scope: str,
    scope_metadata: Dict[str, Any],
    last_response: str,
    last_question: str,
) -> List[str]:
    """
    Generate follow-up question suggestions based on the conversation context.

    Uses the mini model for speed and cost efficiency.
    """
    scope_hints = {
        "signal": f"""The user is exploring a signal called \"{scope_metadata.get('card_name', 'Unknown')}\". Suggest questions about its implications for Austin, implementation timeline, risks, comparison with similar trends, or what other cities are doing.""",
        "workstream": f"""The user is exploring a workstream called \"{scope_metadata.get('workstream_name', 'Unknown')}\" with {scope_metadata.get('card_count', 0)} signals. Suggest questions about cross-cutting themes, priority signals, resource allocation, or strategic recommendations.""",
        "global": "The user asked a broad strategic question. Suggest questions about specific pillars, emerging patterns, comparisons between trends, or actionable next steps for the city.",
    }

    prompt = f"""Based on this Q&A exchange, suggest exactly 3 follow-up questions the user might ask.

User's question: {last_question[:300]}
Assistant's response (excerpt): {last_response[:600]}

Context: {scope_hints.get(scope, scope_hints['global'])}

Return a JSON array of exactly 3 short questions (max 80 chars each).
Example: ["What are the implementation costs?", "Which cities have adopted this?", "What are the equity implications?"]
"""

    try:
        response = await azure_openai_async_client.chat.completions.create(
            model=get_chat_mini_deployment(),
            messages=[
                {
                    "role": "system",
                    "content": "You suggest follow-up questions. Respond with a JSON array only.",
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=200,
            temperature=0.8,
        )

        content = response.choices[0].message.content.strip()
        result = json.loads(content)

        # Handle both {"suggestions": [...]} and plain [...] formats
        if isinstance(result, list):
            return [str(q)[:100] for q in result[:3]]
        elif isinstance(result, dict):
            suggestions = result.get("suggestions") or result.get("questions") or []
            return [str(q)[:100] for q in suggestions[:3]]

    except Exception as e:
        logger.warning(f"Suggestion generation failed: {e}")

    return []


async def generate_suggestions(
    scope: str,
    scope_id: Optional[str],
    supabase_client: Client,
    user_id: str,
) -> List[str]:
    """
    Generate context-aware suggested questions for a given scope.

    This is the public-facing function called by the API endpoint
    when the user hasn't started a conversation yet.
    """
    scope_metadata: Dict[str, Any] = {}

    try:
        if scope == "signal" and scope_id:
            # Fetch just the card name/summary for generating suggestions
            card_result = (
                supabase_client.table("cards")
                .select("name, summary, pillar_id, horizon, stage_id")
                .eq("id", scope_id)
                .execute()
            )
            if card_result.data:
                card = card_result.data[0]
                scope_metadata = {
                    "card_name": card.get("name"),
                    "card_summary": card.get("summary", ""),
                }
        elif scope == "workstream" and scope_id:
            ws_result = (
                supabase_client.table("workstreams")
                .select("name, description, keywords")
                .eq("id", scope_id)
                .execute()
            )
            if ws_result.data:
                ws = ws_result.data[0]
                scope_metadata = {
                    "workstream_name": ws.get("name"),
                    "workstream_description": ws.get("description", ""),
                    "card_count": 0,
                }
    except Exception as e:
        logger.warning(f"Failed to fetch scope metadata for suggestions: {e}")

    scope_hints = {
        "signal": (
            f"Generate 3 starter questions a city analyst might ask about "
            f"the signal \"{scope_metadata.get('card_name', 'this signal')}\". "
            f"Summary: {scope_metadata.get('card_summary', 'N/A')[:300]}. "
            f"Focus on implications for Austin, implementation, risks, and opportunities."
        ),
        "workstream": (
            f"Generate 3 starter questions a city analyst might ask about "
            f"the research workstream \"{scope_metadata.get('workstream_name', 'this workstream')}\". "
            f"Description: {scope_metadata.get('workstream_description', 'N/A')[:300]}. "
            f"Focus on trends, priorities, resource needs, and strategic recommendations."
        ),
        "global": (
            "Generate 3 starter questions a city analyst might ask about "
            "emerging trends and strategic intelligence for the City of Austin. "
            "Focus on cross-cutting themes, high-velocity signals, new patterns, "
            "and actionable intelligence."
        ),
    }

    prompt = scope_hints.get(scope, scope_hints["global"])

    try:
        response = await azure_openai_async_client.chat.completions.create(
            model=get_chat_mini_deployment(),
            messages=[
                {
                    "role": "system",
                    "content": "You generate starter questions for a strategic intelligence chat. "
                    'Respond with a JSON object: {"suggestions": ["q1", "q2", "q3"]}',
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=200,
            temperature=0.8,
        )

        content = response.choices[0].message.content.strip()
        result = json.loads(content)

        if isinstance(result, dict):
            suggestions = result.get("suggestions") or result.get("questions") or []
            return [str(q)[:100] for q in suggestions[:3]]
        elif isinstance(result, list):
            return [str(q)[:100] for q in result[:3]]

    except Exception as e:
        logger.error(f"Suggestion generation failed: {e}")

    # Fallback suggestions
    fallbacks = {
        "signal": [
            "What are the key implications of this signal for Austin?",
            "How does this compare to what other cities are doing?",
            "What should the city do to prepare for this trend?",
        ],
        "workstream": [
            "What are the most important trends in this workstream?",
            "Which signals require the most urgent attention?",
            "What are the common themes across these signals?",
        ],
        "global": [
            "What are the fastest-moving trends right now?",
            "Are there any new cross-cutting patterns emerging?",
            "What should Austin prioritize in the next 12 months?",
        ],
    }

    return fallbacks.get(scope, fallbacks["global"])
