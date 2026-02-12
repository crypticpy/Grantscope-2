"""
Unified Hybrid RAG Engine for Foresight Chat.

Combines PostgreSQL full-text search with pgvector cosine similarity
via Reciprocal Rank Fusion (RRF).  Supports three chat scopes:

    - **signal**     one card + its sources, timeline, research reports
    - **workstream** all cards in a workstream + top sources per card
    - **global**     semantic search across the entire card/source corpus

The public entry point is :py:meth:`RAGEngine.retrieve`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.openai_provider import (
    azure_openai_async_client,
    azure_openai_async_embedding_client,
    get_chat_mini_deployment,
    get_embedding_deployment,
)

logger = logging.getLogger(__name__)


class RAGEngine:
    """
    Unified hybrid retrieval engine for Foresight chat.

    Combines PostgreSQL full-text search with vector similarity
    via Reciprocal Rank Fusion. Supports all three scopes.
    """

    MAX_CONTEXT_CHARS = 120_000  # ~30K tokens, generous for 1M context window
    MAX_MENTION_CONTEXT_CHARS = 15_000

    def __init__(self, supabase_client: Any) -> None:
        self.supabase = supabase_client
        self._ws_card_ids_cache: Dict[str, List[str]] = {}

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def retrieve(
        self,
        query: str,
        scope: str,
        scope_id: Optional[str] = None,
        mentions: Optional[List[Dict[str, Any]]] = None,
        max_context_chars: Optional[int] = None,
    ) -> Tuple[str, dict]:
        """
        Orchestrate the full hybrid-RAG pipeline.

        Parameters
        ----------
        query : str
            The user's chat message / question.
        scope : str
            One of ``"signal"``, ``"workstream"``, or ``"global"``.
        scope_id : str | None
            Card ID (signal) or workstream ID (workstream). Ignored for global.
        mentions : list[dict] | None
            Structured ``@mention`` references from the frontend.
        max_context_chars : int | None
            Override for :pyattr:`MAX_CONTEXT_CHARS`.

        Returns
        -------
        tuple[str, dict]
            ``(context_text, metadata)`` ready for the system prompt.
        """
        VALID_SCOPES = {"signal", "workstream", "global"}
        if scope not in VALID_SCOPES:
            raise ValueError(f"Invalid scope '{scope}'. Must be one of {VALID_SCOPES}")

        budget = max_context_chars or self.MAX_CONTEXT_CHARS

        # Step 1 + 2: expand query & generate embedding (parallel)
        expanded_queries, embedding = await asyncio.gather(
            self._expand_query(query),
            self._generate_embedding(query),
        )

        # Step 3: hybrid search (cards + sources in parallel inside)
        search_results = await self._hybrid_search(
            query,
            expanded_queries,
            embedding,
            scope,
            scope_id,
        )

        cards = search_results.get("cards", [])
        sources = search_results.get("sources", [])

        # Step 4 + 5: enrich + rerank (can run in parallel)
        enrichment, (reranked_cards, reranked_sources) = await asyncio.gather(
            self._enrich_context(scope, scope_id, search_results),
            self._rerank_results(query, cards, sources),
        )

        # Step 6: resolve @mentions
        mention_data: List[Dict[str, Any]] = []
        if mentions or _extract_mention_titles(query):
            mention_data = await self._resolve_mentions(query, mentions)

        # Step 7: assemble final context
        context_text, metadata = self._assemble_context(
            scope,
            scope_id,
            reranked_cards,
            reranked_sources,
            enrichment,
            mention_data,
            budget,
        )

        return context_text, metadata

    # ------------------------------------------------------------------
    # Query expansion
    # ------------------------------------------------------------------

    async def _expand_query(self, query: str) -> List[str]:
        """Use gpt-4.1-mini to produce 2-3 search-query variants."""
        try:
            response = await azure_openai_async_client.chat.completions.create(
                model=get_chat_mini_deployment(),
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Generate 2-3 search query variants for this question. "
                            "Return only the queries, one per line."
                        ),
                    },
                    {"role": "user", "content": f"Original: {query}"},
                ],
                max_tokens=100,
                temperature=0.3,
                timeout=10,
            )
            raw = (response.choices[0].message.content or "").strip()
            variants = [
                line.strip().lstrip("0123456789.-) ")
                for line in raw.splitlines()
                if line.strip()
            ]
            # Always include the original
            if query not in variants:
                variants.insert(0, query)
            return variants
        except Exception:
            logger.warning(
                "Query expansion failed; using original query", exc_info=True
            )
            return [query]

    # ------------------------------------------------------------------
    # Embedding generation
    # ------------------------------------------------------------------

    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate an embedding vector for *text* using the async embedding client."""
        try:
            truncated = text[:8000]
            response = await azure_openai_async_embedding_client.embeddings.create(
                model=get_embedding_deployment(),
                input=truncated,
            )
            return response.data[0].embedding
        except Exception:
            logger.error("Embedding generation failed", exc_info=True)
            return []

    # ------------------------------------------------------------------
    # Hybrid search (FTS + vector via Supabase RPCs)
    # ------------------------------------------------------------------

    async def _hybrid_search(
        self,
        query: str,
        expanded_queries: List[str],
        embedding: List[float],
        scope: str,
        scope_id: Optional[str],
    ) -> Dict[str, list]:
        """
        Run ``hybrid_search_cards`` and ``hybrid_search_sources`` RPCs
        in parallel and return their combined results.
        """
        if not embedding:
            logger.warning(
                "Embedding generation failed; using zero vector (FTS-only effective)"
            )
            embedding = [0.0] * 1536

        fts_query_text = " OR ".join(_sanitize_fts_query(q) for q in expanded_queries)

        # Determine scope_card_ids for source search and card search
        source_scope_ids: Optional[List[str]] = None
        card_scope_ids: Optional[List[str]] = None

        if scope == "signal" and scope_id:
            # Sources: limit to this card; Cards: no scope (find related)
            source_scope_ids = [scope_id]
            card_scope_ids = None
        elif scope == "workstream" and scope_id:
            ws_card_ids = await self._fetch_workstream_card_ids(scope_id)
            source_scope_ids = ws_card_ids if ws_card_ids else None
            # Cards: search both scoped AND unscoped for workstream
            card_scope_ids = None
        # Global: no filters (both stay None)

        # Build RPC params --------------------------------------------------
        card_params: Dict[str, Any] = {
            "query_text": fts_query_text,
            "query_embedding": embedding,
            "match_count": 25,
        }
        if card_scope_ids is not None:
            card_params["scope_card_ids"] = card_scope_ids

        source_params: Dict[str, Any] = {
            "query_text": fts_query_text,
            "query_embedding": embedding,
            "match_count": 30,
        }
        if source_scope_ids is not None:
            source_params["scope_card_ids"] = source_scope_ids

        # Execute both RPCs in parallel
        card_task = self._rpc_safe("hybrid_search_cards", card_params)
        source_task = self._rpc_safe("hybrid_search_sources", source_params)

        card_results, source_results = await asyncio.gather(card_task, source_task)

        return {"cards": card_results, "sources": source_results}

    # ------------------------------------------------------------------
    # Enrichment (scope-specific additions)
    # ------------------------------------------------------------------

    async def _enrich_context(
        self,
        scope: str,
        scope_id: Optional[str],
        search_results: Dict[str, list],
    ) -> Dict[str, Any]:
        """Fetch scope-specific supplementary data."""
        enrichment: Dict[str, Any] = {}

        if scope == "signal" and scope_id:
            enrichment = await self._enrich_signal(scope_id, search_results)
        elif scope == "workstream" and scope_id:
            enrichment = await self._enrich_workstream(scope_id)
        elif scope == "global":
            enrichment = await self._enrich_global()

        return enrichment

    async def _enrich_signal(
        self, card_id: str, search_results: Dict[str, list]
    ) -> Dict[str, Any]:
        """Fetch full card data, all sources, timeline, and research tasks."""
        enrichment: Dict[str, Any] = {}

        # Is the primary card already in search results?
        existing_ids = {c.get("id") for c in search_results.get("cards", [])}

        tasks: list = []

        # Full card data (always fetch to get ALL columns)
        async def fetch_card() -> None:
            try:
                result = (
                    self.supabase.table("cards").select("*").eq("id", card_id).execute()
                )
                if result.data:
                    enrichment["primary_card"] = result.data[0]
                    # If not already in search results, flag it
                    if card_id not in existing_ids:
                        enrichment["primary_card_missing_from_search"] = True
            except Exception:
                logger.warning(
                    "Failed to fetch primary card %s", card_id, exc_info=True
                )

        # ALL sources for the primary card
        async def fetch_all_sources() -> None:
            try:
                result = (
                    self.supabase.table("sources")
                    .select(
                        "id, title, url, ai_summary, key_excerpts, full_text, "
                        "source_type, publisher, published_date, relevance_score"
                    )
                    .eq("card_id", card_id)
                    .order("relevance_score", desc=True)
                    .execute()
                )
                enrichment["all_sources"] = result.data or []
            except Exception:
                logger.warning(
                    "Failed to fetch sources for card %s", card_id, exc_info=True
                )
                enrichment["all_sources"] = []

        # Timeline events
        async def fetch_timeline() -> None:
            try:
                result = (
                    self.supabase.table("card_timeline")
                    .select("event_type, title, description, metadata, created_at")
                    .eq("card_id", card_id)
                    .order("created_at", desc=True)
                    .limit(15)
                    .execute()
                )
                enrichment["timeline"] = result.data or []
            except Exception:
                logger.warning(
                    "Failed to fetch timeline for card %s", card_id, exc_info=True
                )
                enrichment["timeline"] = []

        # Research tasks
        async def fetch_research() -> None:
            try:
                result = (
                    self.supabase.table("research_tasks")
                    .select("task_type, result_summary, completed_at")
                    .eq("card_id", card_id)
                    .eq("status", "completed")
                    .order("completed_at", desc=True)
                    .limit(3)
                    .execute()
                )
                enrichment["research_tasks"] = result.data or []
            except Exception:
                logger.warning(
                    "Failed to fetch research tasks for card %s",
                    card_id,
                    exc_info=True,
                )
                enrichment["research_tasks"] = []

        tasks = [fetch_card(), fetch_all_sources(), fetch_timeline(), fetch_research()]
        await asyncio.gather(*tasks)
        return enrichment

    async def _enrich_workstream(self, workstream_id: str) -> Dict[str, Any]:
        """Fetch workstream details and all member cards' basic info."""
        enrichment: Dict[str, Any] = {}

        try:
            ws_result = (
                self.supabase.table("workstreams")
                .select(
                    "id, name, description, keywords, pillar_ids, goal_ids, horizon"
                )
                .eq("id", workstream_id)
                .execute()
            )
            if ws_result.data:
                enrichment["workstream"] = ws_result.data[0]
        except Exception:
            logger.warning(
                "Failed to fetch workstream %s", workstream_id, exc_info=True
            )

        try:
            card_ids = await self._fetch_workstream_card_ids(workstream_id)
            if card_ids:
                cards_result = (
                    self.supabase.table("cards")
                    .select(
                        "id, slug, name, summary, pillar_id, horizon, stage_id, "
                        "impact_score, relevance_score, velocity_score"
                    )
                    .in_("id", card_ids)
                    .execute()
                )
                enrichment["workstream_cards"] = cards_result.data or []
            else:
                enrichment["workstream_cards"] = []
        except Exception:
            logger.warning(
                "Failed to fetch workstream cards for %s",
                workstream_id,
                exc_info=True,
            )
            enrichment["workstream_cards"] = []

        return enrichment

    async def _enrich_global(self) -> Dict[str, Any]:
        """Fetch active pattern insights for cross-signal context."""
        enrichment: Dict[str, Any] = {}
        try:
            result = (
                self.supabase.table("pattern_insights")
                .select(
                    "pattern_title, pattern_summary, opportunity, "
                    "affected_pillars, urgency, confidence"
                )
                .eq("status", "active")
                .order("created_at", desc=True)
                .limit(10)
                .execute()
            )
            enrichment["pattern_insights"] = result.data or []
        except Exception:
            logger.warning("Failed to fetch pattern insights", exc_info=True)
            enrichment["pattern_insights"] = []
        return enrichment

    # ------------------------------------------------------------------
    # Mention resolution
    # ------------------------------------------------------------------

    async def _resolve_mentions(
        self,
        message: str,
        mentions: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Resolve ``@[Title]`` patterns or structured mentions and return
        a list of context dicts for each resolved entity.
        """
        mention_refs: List[Dict[str, Any]] = []

        if mentions:
            for m in mentions:
                mention_refs.append(
                    {
                        "id": m.get("id"),
                        "type": m.get("type", "signal"),
                        "title": m.get("title", ""),
                    }
                )
        else:
            titles = _extract_mention_titles(message)
            for title in titles:
                mention_refs.append({"id": None, "type": None, "title": title})

        if not mention_refs:
            return []

        resolved: List[Dict[str, Any]] = []

        for ref in mention_refs:
            try:
                entity = await self._resolve_single_mention(ref)
                if entity:
                    resolved.append(entity)
            except Exception:
                logger.warning(
                    "Failed to resolve mention '%s'", ref.get("title"), exc_info=True
                )

        return resolved

    async def _resolve_single_mention(
        self, ref: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Resolve one mention reference to a card or workstream dict."""
        entity_type = ref.get("type")
        entity_id = ref.get("id")
        title = ref.get("title", "")

        # Try signal resolution
        if entity_type in ("signal", None):
            card = await self._lookup_card(entity_id, title)
            if card:
                # Fetch top 5 sources
                try:
                    src_result = (
                        self.supabase.table("sources")
                        .select("title, url, ai_summary, key_excerpts")
                        .eq("card_id", card["id"])
                        .order("relevance_score", desc=True)
                        .limit(5)
                        .execute()
                    )
                    card["_sources"] = src_result.data or []
                except Exception:
                    card["_sources"] = []
                return {"type": "signal", "data": card}

        # Try workstream resolution
        if entity_type in ("workstream", None):
            ws = await self._lookup_workstream(entity_id, title)
            if ws:
                try:
                    wc_result = (
                        self.supabase.table("workstream_cards")
                        .select("card_id")
                        .eq("workstream_id", ws["id"])
                        .limit(20)
                        .execute()
                    )
                    card_ids = [wc["card_id"] for wc in (wc_result.data or [])]
                    if card_ids:
                        cards_result = (
                            self.supabase.table("cards")
                            .select("name")
                            .in_("id", card_ids)
                            .execute()
                        )
                        ws["_card_names"] = [
                            c["name"]
                            for c in (cards_result.data or [])
                            if c.get("name")
                        ]
                    else:
                        ws["_card_names"] = []
                except Exception:
                    ws["_card_names"] = []
                return {"type": "workstream", "data": ws}

        return None

    # ------------------------------------------------------------------
    # Reranking
    # ------------------------------------------------------------------

    async def _rerank_results(
        self,
        query: str,
        cards: List[Dict[str, Any]],
        sources: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Use gpt-4.1-mini to rerank the top candidates by relevance.

        Falls back to original ordering on any failure.
        """
        if not cards and not sources:
            return cards, sources

        # Build a numbered list of candidates (max 30)
        candidates: List[Dict[str, Any]] = []
        candidate_origin: List[Tuple[str, int]] = []  # ("card"|"source", original_idx)

        for i, card in enumerate(cards[:15]):
            label = f"Signal: {card.get('name', 'Unknown')} - {(card.get('summary') or '')[:120]}"
            candidates.append({"index": len(candidates), "text": label})
            candidate_origin.append(("card", i))

        for i, src in enumerate(sources[:15]):
            label = f"Source: {src.get('title', 'Untitled')} - {(src.get('ai_summary') or '')[:120]}"
            candidates.append({"index": len(candidates), "text": label})
            candidate_origin.append(("source", i))

        if not candidates:
            return cards, sources

        numbered = "\n".join(f"{c['index']}. {c['text']}" for c in candidates)

        try:
            response = await azure_openai_async_client.chat.completions.create(
                model=get_chat_mini_deployment(),
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a relevance judge. Given a query and numbered results, "
                            "rate each result 1-10 for relevance. Return ONLY valid JSON: "
                            '[{"index": N, "score": N}, ...]'
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Query: {query}\n\nResults:\n{numbered}",
                    },
                ],
                max_tokens=300,
                temperature=0,
                timeout=15,
            )

            raw = (response.choices[0].message.content or "").strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?\s*", "", raw)
                raw = re.sub(r"\s*```$", "", raw)
            scores = json.loads(raw)

            # Build a score lookup
            score_map: Dict[int, float] = {}
            for item in scores:
                idx = item.get("index")
                sc = item.get("score", 0)
                if idx is not None:
                    score_map[int(idx)] = float(sc)

            # Separate card and source scores
            card_scores: List[Tuple[int, float]] = []
            source_scores: List[Tuple[int, float]] = []

            for cand_idx, (origin_type, orig_idx) in enumerate(candidate_origin):
                relevance = score_map.get(cand_idx, 5.0)
                if origin_type == "card":
                    card_scores.append((orig_idx, relevance))
                else:
                    source_scores.append((orig_idx, relevance))

            # Reorder
            card_scores.sort(key=lambda x: x[1], reverse=True)
            source_scores.sort(key=lambda x: x[1], reverse=True)

            reranked_cards = [cards[idx] for idx, _ in card_scores if idx < len(cards)]
            # Append any remaining cards that weren't in the rerank window
            seen_card_ids = {c.get("id") for c in reranked_cards}
            for c in cards:
                if c.get("id") not in seen_card_ids:
                    reranked_cards.append(c)

            reranked_sources = [
                sources[idx] for idx, _ in source_scores if idx < len(sources)
            ]
            seen_source_ids = {s.get("id") for s in reranked_sources}
            for s in sources:
                if s.get("id") not in seen_source_ids:
                    reranked_sources.append(s)

            return reranked_cards, reranked_sources

        except Exception:
            logger.warning("Reranking failed; returning original order", exc_info=True)
            return cards, sources

    # ------------------------------------------------------------------
    # Context assembly
    # ------------------------------------------------------------------

    def _assemble_context(
        self,
        scope: str,
        scope_id: Optional[str],
        cards: List[Dict[str, Any]],
        sources: List[Dict[str, Any]],
        enrichment: Dict[str, Any],
        mentions: List[Dict[str, Any]],
        max_chars: int,
    ) -> Tuple[str, dict]:
        """
        Build the final context string and source_map for citation resolution.

        Truncates from the bottom (lowest-ranked results) if the budget is exceeded.
        """
        parts: List[str] = []
        source_map: Dict[int, Dict[str, Any]] = {}
        source_idx = 1

        # ---- Section 1: Relevant Signals from hybrid search ----
        if cards:
            parts.append(
                f"## Relevant Signals ({len(cards)} found via hybrid search)\n"
            )
            for card in cards:
                rrf = card.get("rrf_score", 0)
                parts.append(
                    f"### Signal: {card.get('name', 'Unknown')} "
                    f"(relevance: {rrf:.2f})"
                )
                parts.append(f"Summary: {card.get('summary', 'No summary available')}")
                if card.get("description"):
                    parts.append(f"Description: {card['description']}")
                parts.append(
                    f"Pillar: {card.get('pillar_id', 'N/A')} | "
                    f"Horizon: {card.get('horizon', 'N/A')} | "
                    f"Stage: {card.get('stage_id', 'N/A')}"
                )

                score_parts = []
                for sn in (
                    "impact_score",
                    "relevance_score",
                    "velocity_score",
                    "risk_score",
                    "signal_quality_score",
                ):
                    val = card.get(sn)
                    if val is not None:
                        label = sn.replace("_score", "").replace("_", " ").title()
                        score_parts.append(f"{label}: {val}")
                if score_parts:
                    parts.append(f"Scores: {', '.join(score_parts)}")

                # Inline sources for this card from the sources list
                card_id = card.get("id")
                card_sources = [s for s in sources if s.get("card_id") == card_id]
                if card_sources:
                    parts.append("\nSources for this signal:")
                    for src in card_sources[:5]:
                        source_map[source_idx] = _build_source_map_entry(
                            src, card_id, card.get("slug", "")
                        )
                        parts.append(f"  [{source_idx}] {src.get('title', 'Untitled')}")
                        if src.get("url"):
                            parts.append(f"      URL: {src['url']}")
                        if src.get("ai_summary"):
                            parts.append(f"      Summary: {src['ai_summary']}")
                        if src.get("key_excerpts"):
                            excerpts = src["key_excerpts"]
                            if isinstance(excerpts, list) and excerpts:
                                parts.append("      Key excerpts:")
                                for exc in excerpts[:3]:
                                    parts.append(f"        - {exc}")
                        if src.get("full_text"):
                            parts.append(f"      Content: {src['full_text'][:5000]}")
                        source_idx += 1

                parts.append("")  # blank line between signals

        # ---- Section 2: Direct source matches not linked to a search card ----
        matched_card_ids = {c.get("id") for c in cards}
        unlinked_sources = [
            s for s in sources if s.get("card_id") not in matched_card_ids
        ]
        if unlinked_sources:
            parts.append(
                f"\n## Direct Source Matches ({len(unlinked_sources)} found)\n"
            )
            for src in unlinked_sources:
                source_map[source_idx] = _build_source_map_entry(
                    src, src.get("card_id"), src.get("card_slug", "")
                )
                card_name = src.get("card_name", "Unknown signal")
                parts.append(
                    f"  [{source_idx}] {src.get('title', 'Untitled')} "
                    f"(for signal: {card_name})"
                )
                if src.get("ai_summary"):
                    parts.append(f"      {src['ai_summary']}")
                if src.get("full_text"):
                    parts.append(f"      {src['full_text'][:3000]}")
                source_idx += 1

        # ---- Section 3: Scope-specific enrichment ----
        enrichment_text = self._format_enrichment(
            scope, scope_id, enrichment, source_map, source_idx
        )
        if enrichment_text:
            parts.append(enrichment_text)

        # ---- Section 4: @mention context ----
        if mentions:
            mention_text = self._format_mentions(mentions)
            if mention_text:
                parts.append(mention_text)

        # ---- Truncation from bottom ----
        context_text = "\n".join(parts)
        if len(context_text) > max_chars:
            context_text = context_text[:max_chars] + "\n\n[Context truncated]"

        # ---- Build metadata ----
        card_name = None
        workstream_name = None
        if scope == "signal":
            primary = enrichment.get("primary_card") or {}
            card_name = primary.get("name")
            if not card_name and cards:
                card_name = cards[0].get("name")
        elif scope == "workstream":
            ws = enrichment.get("workstream") or {}
            workstream_name = ws.get("name")

        metadata: Dict[str, Any] = {
            "matched_cards": len(cards),
            "matched_sources": len(sources),
            "source_map": source_map,
            "source_count": len(source_map),
        }
        if card_name:
            metadata["card_name"] = card_name
        if workstream_name:
            metadata["workstream_name"] = workstream_name

        return context_text, metadata

    # ------------------------------------------------------------------
    # Enrichment formatters
    # ------------------------------------------------------------------

    def _format_enrichment(
        self,
        scope: str,
        scope_id: Optional[str],
        enrichment: Dict[str, Any],
        source_map: Dict[int, Dict[str, Any]],
        source_idx_start: int,
    ) -> str:
        """Format scope-specific enrichment data as context text."""
        parts: List[str] = []
        source_idx = source_idx_start

        if scope == "signal":
            # Primary card full data (if not already surfaced by search)
            primary = enrichment.get("primary_card")
            if primary and enrichment.get("primary_card_missing_from_search"):
                parts.append("\n## Primary Signal (full detail)\n")
                parts.append(f"Name: {primary.get('name', 'Unknown')}")
                parts.append(f"Summary: {primary.get('summary', 'N/A')}")
                if primary.get("description"):
                    parts.append(f"Description: {primary['description']}")

            # All sources for primary card (supplement search results)
            all_sources = enrichment.get("all_sources", [])
            # Only show sources not already in source_map
            existing_source_ids = {v.get("source_id") for v in source_map.values()}
            new_sources = [
                s for s in all_sources if s.get("id") not in existing_source_ids
            ]
            if new_sources:
                parts.append(
                    f"\n## Additional Sources for Primary Signal "
                    f"({len(new_sources)} not in search results)\n"
                )
                for src in new_sources:
                    source_map[source_idx] = _build_source_map_entry(
                        src, scope_id, primary.get("slug", "") if primary else ""
                    )
                    parts.append(f"  [{source_idx}] {src.get('title', 'Untitled')}")
                    if src.get("ai_summary"):
                        parts.append(f"      Summary: {src['ai_summary']}")
                    if src.get("full_text"):
                        parts.append(f"      Content: {src['full_text'][:3000]}")
                    source_idx += 1

            # Timeline
            timeline = enrichment.get("timeline", [])
            if timeline:
                parts.append(f"\n## Timeline ({len(timeline)} events)\n")
                for evt in timeline:
                    parts.append(
                        f"- [{evt.get('event_type')}] {evt.get('title')} "
                        f"({(evt.get('created_at') or '')[:10]})"
                    )
                    if evt.get("description"):
                        parts.append(f"  {evt['description'][:300]}")
                    meta = evt.get("metadata") or {}
                    if isinstance(meta, dict):
                        report = meta.get("report_preview") or meta.get(
                            "deep_research_report"
                        )
                        if report:
                            parts.append(
                                f"  Research Report Excerpt: {str(report)[:1500]}"
                            )

            # Research tasks
            research = enrichment.get("research_tasks", [])
            for task in research:
                result_summary = task.get("result_summary") or {}
                if isinstance(result_summary, dict):
                    report = result_summary.get("report_preview") or result_summary.get(
                        "report"
                    )
                    if report:
                        parts.append(
                            f"\n## Deep Research Report "
                            f"({(task.get('completed_at') or '')[:10]})\n"
                        )
                        parts.append(str(report)[:3000])

        elif scope == "workstream":
            ws = enrichment.get("workstream")
            if ws:
                parts.append("\n## Workstream Details\n")
                parts.append(f"Name: {ws.get('name', 'Unknown')}")
                if ws.get("description"):
                    parts.append(f"Description: {ws['description']}")
                if ws.get("keywords"):
                    kw = ws["keywords"]
                    if isinstance(kw, list):
                        parts.append(f"Keywords: {', '.join(kw)}")
                if ws.get("pillar_ids"):
                    parts.append(f"Pillars: {', '.join(ws['pillar_ids'])}")
                if ws.get("horizon"):
                    parts.append(f"Horizon: {ws['horizon']}")

            ws_cards = enrichment.get("workstream_cards", [])
            if ws_cards:
                parts.append(
                    f"\n## All Cards in Workstream ({len(ws_cards)} signals)\n"
                )
                for card in ws_cards:
                    parts.append(f"- {card.get('name', 'Unknown')}")
                    parts.append(f"  Summary: {card.get('summary', 'N/A')}")
                    parts.append(
                        f"  Pillar: {card.get('pillar_id', 'N/A')} | "
                        f"Horizon: {card.get('horizon', 'N/A')} | "
                        f"Stage: {card.get('stage_id', 'N/A')}"
                    )

        elif scope == "global":
            patterns = enrichment.get("pattern_insights", [])
            if patterns:
                parts.append(f"\n## Active Cross-Signal Patterns ({len(patterns)})\n")
                for pat in patterns:
                    pillars = pat.get("affected_pillars", [])
                    if isinstance(pillars, list):
                        pillars = ", ".join(str(p) for p in pillars)
                    parts.append(
                        f"**{pat.get('pattern_title', 'Unknown')}** "
                        f"(Urgency: {pat.get('urgency', 'N/A')}, "
                        f"Confidence: {pat.get('confidence', 'N/A')})"
                    )
                    parts.append(f"Pillars: {pillars}")
                    if pat.get("pattern_summary"):
                        parts.append(f"Summary: {pat['pattern_summary']}")
                    if pat.get("opportunity"):
                        parts.append(f"Opportunity: {pat['opportunity']}")
                    parts.append("")

        return "\n".join(parts) if parts else ""

    def _format_mentions(self, mentions: List[Dict[str, Any]]) -> str:
        """Format resolved mentions into a context block."""
        if not mentions:
            return ""

        parts: List[str] = ["\n## Referenced Entities (from @mentions)\n"]

        for mention in mentions:
            m_type = mention.get("type")
            data = mention.get("data", {})

            if m_type == "signal":
                parts.append(f"### Signal: {data.get('name', 'Unknown')}")
                if data.get("summary"):
                    parts.append(f"Summary: {data['summary']}")
                if data.get("description"):
                    parts.append(f"Description: {data['description'][:800]}")
                if data.get("pillar_id") or data.get("horizon"):
                    parts.append(
                        f"Pillar: {data.get('pillar_id', 'N/A')} | "
                        f"Horizon: {data.get('horizon', 'N/A')} | "
                        f"Stage: {data.get('stage_id', 'N/A')}"
                    )
                scores = []
                for key in ("impact_score", "relevance_score"):
                    val = data.get(key)
                    if val is not None:
                        label = key.replace("_score", "").replace("_", " ").title()
                        scores.append(f"{label}: {val}")
                if scores:
                    parts.append(f"Scores: {', '.join(scores)}")

                for src in data.get("_sources", []):
                    src_title = src.get("title", "Untitled")
                    excerpt = ""
                    if src.get("ai_summary"):
                        excerpt = (src["ai_summary"] or "")[:200]
                    elif src.get("key_excerpts"):
                        excerpts_list = src["key_excerpts"]
                        if isinstance(excerpts_list, list) and excerpts_list:
                            excerpt = str(excerpts_list[0])[:200]
                    if excerpt:
                        parts.append(f"- {src_title}: {excerpt}")
                    else:
                        parts.append(f"- {src_title}")

            elif m_type == "workstream":
                parts.append(f"### Workstream: {data.get('name', 'Unknown')}")
                if data.get("description"):
                    parts.append(f"Description: {data['description'][:600]}")
                card_names = data.get("_card_names", [])
                if card_names:
                    parts.append(f"Cards ({len(card_names)}): {', '.join(card_names)}")

            parts.append("")  # blank line

        context = "\n".join(parts)
        if len(context) > self.MAX_MENTION_CONTEXT_CHARS:
            context = (
                context[: self.MAX_MENTION_CONTEXT_CHARS]
                + "\n\n[Mention context truncated]"
            )
        return context

    # ------------------------------------------------------------------
    # Helper: DB lookups
    # ------------------------------------------------------------------

    async def _fetch_workstream_card_ids(self, workstream_id: str) -> List[str]:
        """Return card IDs belonging to a workstream (cached per instance)."""
        if workstream_id in self._ws_card_ids_cache:
            return self._ws_card_ids_cache[workstream_id]

        try:
            result = (
                self.supabase.table("workstream_cards")
                .select("card_id")
                .eq("workstream_id", workstream_id)
                .limit(50)
                .execute()
            )
            card_ids = [wc["card_id"] for wc in (result.data or [])]
            self._ws_card_ids_cache[workstream_id] = card_ids
            return card_ids
        except Exception:
            logger.warning(
                "Failed to fetch workstream card IDs for %s",
                workstream_id,
                exc_info=True,
            )
            return []

    async def _lookup_card(
        self, card_id: Optional[str], title: str
    ) -> Optional[Dict[str, Any]]:
        """Look up a card by ID or by ILIKE name search."""
        try:
            if card_id:
                result = (
                    self.supabase.table("cards")
                    .select(
                        "id, slug, name, summary, description, pillar_id, "
                        "horizon, stage_id, impact_score, relevance_score"
                    )
                    .eq("id", card_id)
                    .execute()
                )
                if result.data:
                    return result.data[0]

            if title:
                result = (
                    self.supabase.table("cards")
                    .select(
                        "id, slug, name, summary, description, pillar_id, "
                        "horizon, stage_id, impact_score, relevance_score"
                    )
                    .ilike("name", f"%{title}%")
                    .limit(1)
                    .execute()
                )
                if result.data:
                    return result.data[0]
        except Exception:
            logger.warning(
                "Card lookup failed for id=%s title=%s", card_id, title, exc_info=True
            )
        return None

    async def _lookup_workstream(
        self, workstream_id: Optional[str], title: str
    ) -> Optional[Dict[str, Any]]:
        """Look up a workstream by ID or by ILIKE name search."""
        try:
            if workstream_id:
                result = (
                    self.supabase.table("workstreams")
                    .select("id, name, description")
                    .eq("id", workstream_id)
                    .execute()
                )
                if result.data:
                    return result.data[0]

            if title:
                result = (
                    self.supabase.table("workstreams")
                    .select("id, name, description")
                    .ilike("name", f"%{title}%")
                    .limit(1)
                    .execute()
                )
                if result.data:
                    return result.data[0]
        except Exception:
            logger.warning(
                "Workstream lookup failed for id=%s title=%s",
                workstream_id,
                title,
                exc_info=True,
            )
        return None

    async def _rpc_safe(self, fn_name: str, params: Dict[str, Any]) -> list:
        """Call a Supabase RPC function with error handling."""
        try:
            result = self.supabase.rpc(fn_name, params).execute()
            return result.data or []
        except Exception:
            logger.error("RPC %s failed", fn_name, exc_info=True)
            return []


# ======================================================================
# Module-level helpers
# ======================================================================


def _sanitize_fts_query(q: str) -> str:
    """Remove characters that could break websearch_to_tsquery."""
    return re.sub(r"[():<>!|&]", " ", q).strip()


def _extract_mention_titles(text: str) -> List[str]:
    """Extract ``@[Title]`` patterns from a message string."""
    return re.findall(r"@\[([^\]]+)\]", text)


def _build_source_map_entry(
    src: Dict[str, Any],
    card_id: Optional[str],
    card_slug: str,
) -> Dict[str, Any]:
    """Build a single source_map entry from a source row."""
    excerpt = None
    key_excerpts = src.get("key_excerpts")
    if key_excerpts and isinstance(key_excerpts, list) and key_excerpts:
        excerpt = str(key_excerpts[0])[:200]
    elif src.get("ai_summary"):
        excerpt = (src["ai_summary"] or "")[:200]

    return {
        "source_id": src.get("id"),
        "card_id": card_id,
        "card_slug": card_slug,
        "title": src.get("title", "Untitled"),
        "url": src.get("url", ""),
        "published_date": src.get("published_date"),
        "excerpt": excerpt,
    }
