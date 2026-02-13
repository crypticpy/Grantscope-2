"""
Signal Agent Service for Foresight.

Replaces deterministic one-source-per-card clustering with an AI agent
that intelligently groups discovered sources into meaningful "signals"
(cards). A signal is a topic, trend, or emerging issue backed by
multiple corroborating sources — not one card per article.

Architecture:
  Phase 1 (cheap): Group sources by strategic pillar from existing triage.
  Phase 2 (intelligent): Per-pillar batch, run an AI agent with tool-calling
      that decides how to group sources into signals (create new or attach
      to existing cards).

Usage:
    from app.signal_agent_service import SignalAgentService

    agent = SignalAgentService(supabase, run_id, triggered_by_user_id)
    result = await agent.run_signal_detection(processed_sources, config)
"""

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from supabase import Client

from app.openai_provider import (
    azure_openai_async_client,
    azure_openai_async_embedding_client,
    get_chat_deployment,
    get_embedding_deployment,
)
from app.research_service import ProcessedSource

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

PILLAR_NAMES = {
    "CH": "Community Health & Sustainability",
    "EW": "Economic & Workforce Development",
    "HG": "High-Performing Government",
    "HH": "Homelessness & Housing",
    "MC": "Mobility & Critical Infrastructure",
    "PS": "Public Safety",
}

STAGE_ID_MAP = {
    1: "1_concept",
    2: "2_exploring",
    3: "3_pilot",
    4: "4_proof",
    5: "5_implementing",
    6: "6_scaling",
    7: "7_mature",
    8: "8_declining",
}

VALID_PILLAR_IDS = {"CH", "EW", "HG", "HH", "MC", "PS"}
VALID_HORIZONS = {"H1", "H2", "H3"}

MAX_AGENT_ITERATIONS = 25

# Approximate token costs (USD) for gpt-4.1
COST_PER_INPUT_TOKEN = 0.002 / 1000
COST_PER_OUTPUT_TOKEN = 0.008 / 1000

# =============================================================================
# System Prompt
# =============================================================================

SIGNAL_AGENT_SYSTEM_PROMPT = """You are a Strategic Signal Detection Agent for the City of Austin's Foresight system.

Your job is to analyze a batch of recently discovered sources and organize them into meaningful SIGNALS.

## What is a Signal?
A signal is an emerging trend, technology, policy shift, or issue that could impact municipal government. A signal is NOT a single news article — it is a coherent theme supported by one or more sources. Multiple articles about the same underlying trend should be grouped into ONE signal.

## Your Task
You will receive a numbered list of source summaries, plus any existing signals (cards) that are semantically related. For EACH source, you must either:

1. **CREATE a new signal** — when the source(s) represent a genuinely new trend not covered by existing signals. Group multiple sources about the same topic into one create_signal call.
2. **ATTACH to an existing signal** — when the source adds evidence or a new angle to an existing signal (card) in the database.

## Decision Framework
- First, use `search_existing_signals` to check if related signals already exist.
- If a strong match exists (the source covers the same core trend), use `attach_source_to_signal`.
- If no existing signal matches, check if other sources in THIS batch cover the same theme. If so, group them into a single `create_signal` call with multiple source indices.
- Use `get_source_details` if you need the full text of a source to make a better decision.
- Use `list_strategic_context` if you need to understand the pillar framework.

## Rules
- Every source MUST be assigned to at least one signal. Do not leave any source unprocessed.
- A source CAN belong to multiple signals if it genuinely relates to more than one trend.
- Prefer attaching to existing signals over creating new ones — avoid signal proliferation.
- When creating a signal, provide a clear, descriptive name (not the article title).
- Signal names should describe the TREND, not a specific event (e.g., "Municipal AI Adoption for Permitting" not "Austin Deploys AI Chatbot").
- Provide honest confidence scores: 0.9+ means very clear fit, 0.5-0.7 means plausible but uncertain.
- Process ALL sources before finishing. Do not stop early.

## Existing Related Signals
{existing_signals}

## Sources to Process
{source_summaries}

Begin by scanning the source list, then use your tools to search for existing signals and make grouping decisions. Process every source."""


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class SignalAction:
    """A deferred action to be executed after the agent loop completes."""

    action_type: str  # 'create_signal' or 'attach_to_existing'
    signal_card_id: Optional[str]  # For attach_to_existing
    source_indices: List[int]
    signal_name: Optional[str]  # For create_signal
    signal_summary: Optional[str]
    signal_properties: Optional[Dict]  # pillar, horizon, stage, scores
    relationship_type: str
    confidence: float
    reasoning: str


@dataclass
class SignalDetectionResult:
    """Aggregate result of a full signal detection run."""

    signals_created: List[str] = field(default_factory=list)
    signals_enriched: List[str] = field(default_factory=list)
    sources_linked: int = 0
    junction_entries_created: int = 0
    auto_approved_count: int = 0
    agent_calls_made: int = 0
    total_tokens_used: int = 0
    cost_estimate: float = 0.0
    pillar_stats: Dict[str, Dict] = field(default_factory=dict)


# =============================================================================
# Tool Definitions
# =============================================================================


def _define_tools() -> List[Dict[str, Any]]:
    """Return the 5 tool definitions in OpenAI function-calling format."""
    return [
        {
            "type": "function",
            "function": {
                "name": "search_existing_signals",
                "description": (
                    "Search the database for existing signals (cards) that are "
                    "semantically similar to a query. Use this to check whether a "
                    "trend or topic already has a signal before creating a new one."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": (
                                "A concise description of the trend or topic to "
                                "search for. Be specific enough to find relevant "
                                "matches."
                            ),
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "create_signal",
                "description": (
                    "Create a new signal (card) from one or more sources that "
                    "represent an emerging trend not covered by existing signals."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "signal_name": {
                            "type": "string",
                            "description": (
                                "A clear, descriptive name for the signal. Should "
                                "describe the TREND, not a single event. Max 200 chars."
                            ),
                        },
                        "signal_summary": {
                            "type": "string",
                            "description": (
                                "A 2-4 sentence summary of the signal: what the trend "
                                "is, why it matters for municipal government, and what "
                                "to watch for."
                            ),
                        },
                        "source_indices": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": (
                                "Indices of the sources (from the source list) that "
                                "belong to this signal."
                            ),
                        },
                        "pillar_id": {
                            "type": "string",
                            "enum": ["CH", "EW", "HG", "HH", "MC", "PS"],
                            "description": "Primary strategic pillar.",
                        },
                        "horizon": {
                            "type": "string",
                            "enum": ["H1", "H2", "H3"],
                            "description": (
                                "Time horizon. H1=now-2yr, H2=2-5yr, H3=5-10yr."
                            ),
                        },
                        "stage": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 8,
                            "description": (
                                "Maturity stage: 1=Concept, 2=Exploring, 3=Pilot, "
                                "4=PoC, 5=Implementing, 6=Scaling, 7=Mature, 8=Declining."
                            ),
                        },
                        "impact_score": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 100,
                            "description": "Potential impact on city operations (0-100).",
                        },
                        "relevance_score": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 100,
                            "description": "Relevance to Austin's strategic priorities (0-100).",
                        },
                        "novelty_score": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 100,
                            "description": "How new or unexpected this trend is (0-100).",
                        },
                        "velocity_score": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 100,
                            "description": "Speed of trend development (0-100).",
                        },
                        "risk_score": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 100,
                            "description": "Threat or uncertainty level (0-100).",
                        },
                        "relationship_type": {
                            "type": "string",
                            "enum": ["primary", "supporting", "contextual", "contrary"],
                            "description": (
                                "How these sources relate to the signal. Usually 'primary' "
                                "for the defining sources of a new signal."
                            ),
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                            "description": "Your confidence in this grouping decision (0-1).",
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "Brief explanation of why these sources form a signal.",
                        },
                    },
                    "required": [
                        "signal_name",
                        "signal_summary",
                        "source_indices",
                        "pillar_id",
                        "horizon",
                        "stage",
                        "impact_score",
                        "relevance_score",
                        "novelty_score",
                        "confidence",
                        "reasoning",
                    ],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "attach_source_to_signal",
                "description": (
                    "Attach one or more sources to an existing signal (card) in the "
                    "database. Use when sources add evidence to an already-tracked trend."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "signal_id": {
                            "type": "string",
                            "description": "The UUID of the existing signal (card) to attach to.",
                        },
                        "source_indices": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Indices of the sources to attach.",
                        },
                        "relationship_type": {
                            "type": "string",
                            "enum": ["primary", "supporting", "contextual", "contrary"],
                            "description": (
                                "How these sources relate to the existing signal."
                            ),
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                            "description": "Confidence in the attachment decision (0-1).",
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "Why these sources belong to this signal.",
                        },
                    },
                    "required": [
                        "signal_id",
                        "source_indices",
                        "relationship_type",
                        "confidence",
                        "reasoning",
                    ],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_source_details",
                "description": (
                    "Retrieve the full content and metadata of a specific source "
                    "from the current batch. Use when the summary is insufficient "
                    "to make a grouping decision."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "source_index": {
                            "type": "integer",
                            "description": "The index of the source to retrieve.",
                        },
                    },
                    "required": ["source_index"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_strategic_context",
                "description": (
                    "List the strategic pillars, priorities, and stage definitions "
                    "used by the City of Austin's Foresight system. Use if you need "
                    "context to correctly classify a signal."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
        },
    ]


# =============================================================================
# Helper Functions
# =============================================================================


def _generate_slug(name: str) -> str:
    """
    Generate a URL-friendly slug from a signal name.

    Pattern: lowercase -> remove non-alnum except spaces -> split/join
    with hyphens -> truncate to 50 chars.
    """
    slug = name.lower()
    slug = "".join(c if c.isalnum() or c == " " else "" for c in slug)
    slug = "-".join(slug.split())
    return slug[:50]


def _extract_domain(url: str) -> str:
    """Extract domain from a URL for display."""
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path
        # Strip www. prefix
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return url[:40]


def _compute_centroid(embeddings: List[List[float]]) -> List[float]:
    """Compute the centroid (element-wise average) of a list of embedding vectors."""
    if not embeddings:
        return []
    dim = len(embeddings[0])
    centroid = [0.0] * dim
    for emb in embeddings:
        for i in range(dim):
            centroid[i] += emb[i]
    n = len(embeddings)
    return [v / n for v in centroid]


def _clamp_score(value: Any, low: int = 0, high: int = 100) -> int:
    """Clamp a score to the valid integer range."""
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return 50  # Default mid-range


# =============================================================================
# SignalAgentService
# =============================================================================


class SignalAgentService:
    """
    AI agent service that groups discovered sources into meaningful signals.

    Replaces deterministic clustering with an intelligent tool-calling agent
    that can search existing signals, create new ones, and attach sources
    to existing cards.
    """

    def __init__(
        self,
        supabase: Client,
        run_id: str,
        triggered_by_user_id: Optional[str] = None,
    ):
        self.supabase = supabase
        self.run_id = run_id
        self.triggered_by_user_id = triggered_by_user_id
        self.tools = _define_tools()

    # =========================================================================
    # Main Entry Point
    # =========================================================================

    async def run_signal_detection(
        self,
        processed_sources: List[ProcessedSource],
        config: Any,  # DiscoveryConfig from app.discovery_service
    ) -> SignalDetectionResult:
        """
        Main entry point. Runs Phase 1 (batch by pillar), then Phase 2
        (agent loop per batch), then executes all accumulated actions.

        Args:
            processed_sources: Fully processed sources with triage, analysis,
                and embeddings.
            config: DiscoveryConfig instance controlling thresholds and limits.

        Returns:
            SignalDetectionResult with summary statistics.
        """
        result = SignalDetectionResult()

        if not processed_sources:
            logger.info("Signal agent: no sources to process")
            return result

        logger.info(
            f"Signal agent: starting detection for {len(processed_sources)} sources "
            f"(run={self.run_id})"
        )

        try:
            # Phase 1: Group sources by pillar
            pillar_batches = self._phase1_batch_by_pillar(processed_sources)
            logger.info(
                f"Signal agent: Phase 1 grouped into {len(pillar_batches)} pillar batches: "
                f"{', '.join(f'{k}({len(v)})' for k, v in pillar_batches.items())}"
            )

            # Phase 2: Run agent loop per pillar batch
            all_actions: List[SignalAction] = []
            total_tokens = 0
            total_agent_calls = 0

            max_new_cards = getattr(config, "max_new_cards_per_run", 15)
            cards_created_so_far = 0

            for pillar_id, batch_sources in pillar_batches.items():
                if not batch_sources:
                    continue

                pillar_name = PILLAR_NAMES.get(pillar_id, pillar_id)
                logger.info(
                    f"Signal agent: Processing pillar {pillar_id} ({pillar_name}) "
                    f"with {len(batch_sources)} sources"
                )

                try:
                    # Prefetch related signals for context
                    existing_signals = await self._prefetch_related_signals(
                        batch_sources
                    )

                    # Build source summaries for the prompt
                    source_summaries = self._build_source_summaries(batch_sources)

                    # Format existing signals for prompt
                    if existing_signals:
                        existing_text = "\n".join(
                            f"- [{s['id']}] \"{s['name']}\" "
                            f"(pillar: {s.get('pillar_id', '?')}, "
                            f"horizon: {s.get('horizon', '?')}, "
                            f"similarity: {s.get('similarity', 0):.2f})\n"
                            f"  Summary: {s.get('summary', 'N/A')[:200]}"
                            for s in existing_signals
                        )
                    else:
                        existing_text = (
                            "None found. You may need to create new signals."
                        )

                    # Build messages
                    system_message = SIGNAL_AGENT_SYSTEM_PROMPT.format(
                        existing_signals=existing_text,
                        source_summaries=source_summaries,
                    )
                    messages = [
                        {"role": "system", "content": system_message},
                        {
                            "role": "user",
                            "content": (
                                f"Process all {len(batch_sources)} sources in the "
                                f"{pillar_name} pillar batch. Search for existing signals "
                                f"first, then create or attach as appropriate. "
                                f"Remaining new-card budget: {max_new_cards - cards_created_so_far}."
                            ),
                        },
                    ]

                    # Run the agent loop
                    actions, tokens = await self._run_agent_loop(
                        messages, self.tools, batch_sources
                    )

                    # Count how many create actions we got
                    new_creates = sum(
                        1 for a in actions if a.action_type == "create_signal"
                    )
                    cards_created_so_far += new_creates

                    all_actions.extend(actions)
                    total_tokens += tokens
                    total_agent_calls += 1

                    result.pillar_stats[pillar_id] = {
                        "sources": len(batch_sources),
                        "actions": len(actions),
                        "creates": new_creates,
                        "attaches": len(actions) - new_creates,
                        "tokens": tokens,
                    }

                except Exception as e:
                    logger.error(
                        f"Signal agent: Error processing pillar {pillar_id}: {e}",
                        exc_info=True,
                    )
                    result.pillar_stats[pillar_id] = {
                        "sources": len(batch_sources),
                        "error": str(e),
                    }

            # Phase 3: Execute all accumulated actions
            logger.info(
                f"Signal agent: Executing {len(all_actions)} actions "
                f"({total_tokens} tokens used across {total_agent_calls} agent calls)"
            )

            execution_result = await self._execute_actions(
                all_actions, processed_sources, config
            )

            result.signals_created = execution_result.get("signals_created", [])
            result.signals_enriched = execution_result.get("signals_enriched", [])
            result.sources_linked = execution_result.get("sources_linked", 0)
            result.junction_entries_created = execution_result.get(
                "junction_entries_created", 0
            )
            result.auto_approved_count = execution_result.get("auto_approved", 0)
            result.agent_calls_made = total_agent_calls
            result.total_tokens_used = total_tokens
            result.cost_estimate = total_tokens * (
                (COST_PER_INPUT_TOKEN + COST_PER_OUTPUT_TOKEN) / 2
            )

            logger.info(
                f"Signal agent: Complete. "
                f"Created {len(result.signals_created)} signals, "
                f"enriched {len(result.signals_enriched)} existing signals, "
                f"linked {result.sources_linked} sources, "
                f"cost ~${result.cost_estimate:.4f}"
            )

            # Store stats on the discovery run
            try:
                self.supabase.table("discovery_runs").update(
                    {
                        "signal_agent_stats": {
                            "signals_created": len(result.signals_created),
                            "signals_enriched": len(result.signals_enriched),
                            "sources_linked": result.sources_linked,
                            "junction_entries": result.junction_entries_created,
                            "agent_calls": result.agent_calls_made,
                            "tokens_used": result.total_tokens_used,
                            "cost_estimate": round(result.cost_estimate, 4),
                            "pillar_stats": result.pillar_stats,
                        }
                    }
                ).eq("id", self.run_id).execute()
            except Exception as e:
                logger.warning(f"Signal agent: Failed to store stats on run: {e}")

            return result

        except Exception as e:
            logger.error(
                f"Signal agent: Fatal error in run_signal_detection: {e}",
                exc_info=True,
            )
            return result

    # =========================================================================
    # Phase 1: Batch by Pillar
    # =========================================================================

    def _phase1_batch_by_pillar(
        self, sources: List[ProcessedSource]
    ) -> Dict[str, List[ProcessedSource]]:
        """
        Group sources by their primary strategic pillar.

        Uses the first pillar from analysis.pillars, falling back to
        triage.primary_pillar, then to "UNKNOWN".
        """
        batches: Dict[str, List[ProcessedSource]] = defaultdict(list)

        for source in sources:
            pillar = None

            # Try analysis pillars first
            if source.analysis and source.analysis.pillars:
                pillar = source.analysis.pillars[0]

            # Fall back to triage primary pillar
            if not pillar and source.triage and source.triage.primary_pillar:
                pillar = source.triage.primary_pillar

            # Final fallback
            if not pillar:
                pillar = "UNKNOWN"

            batches[pillar].append(source)

        return dict(batches)

    # =========================================================================
    # Prefetch Related Signals
    # =========================================================================

    async def _prefetch_related_signals(
        self, sources: List[ProcessedSource]
    ) -> List[Dict]:
        """
        For a batch of sources, compute a centroid embedding and search
        for existing related signals (cards) in the database.
        """
        embeddings = [s.embedding for s in sources if s.embedding]
        if not embeddings:
            logger.debug("Signal agent: No embeddings available for prefetch")
            return []

        centroid = _compute_centroid(embeddings)

        try:
            match_result = self.supabase.rpc(
                "find_similar_cards",
                {
                    "query_embedding": centroid,
                    "match_threshold": 0.7,
                    "match_count": 10,
                },
            ).execute()

            if match_result.data:
                logger.debug(
                    f"Signal agent: Prefetch found {len(match_result.data)} "
                    f"related signals"
                )
                return match_result.data

        except Exception as e:
            logger.warning(f"Signal agent: Prefetch RPC failed: {e}")

        return []

    # =========================================================================
    # Build Source Summaries
    # =========================================================================

    def _build_source_summaries(self, sources: List[ProcessedSource]) -> str:
        """
        Build a numbered list of source summaries for the agent prompt.

        Format:
            [0] "Article Title" (domain.com)
                Summary: 2-3 sentences...
                Pillar: CH | Horizon: H2 | Stage: 4 (PoC)
                Key terms: AI, transit, optimization
        """
        lines = []
        for i, source in enumerate(sources):
            title = (source.raw.title or "Untitled")[:120]
            domain = _extract_domain(source.raw.url or "")

            summary = ""
            pillar = "?"
            horizon = "?"
            stage = "?"
            key_terms = ""

            if source.analysis:
                summary = (source.analysis.summary or "")[:300]
                if source.analysis.pillars:
                    pillar = source.analysis.pillars[0]
                horizon = source.analysis.horizon or "?"
                stage_num = source.analysis.suggested_stage
                stage_label = STAGE_ID_MAP.get(stage_num, "")
                stage = f"{stage_num} ({stage_label.split('_', 1)[-1] if stage_label else '?'})"

                # Extract key terms from entities
                if source.analysis.entities:
                    terms = [e.name for e in source.analysis.entities[:5]]
                    key_terms = ", ".join(terms)

            if not summary and source.triage:
                summary = source.triage.reason or ""
                if source.triage.primary_pillar:
                    pillar = source.triage.primary_pillar

            entry = (
                f'[{i}] "{title}" ({domain})\n'
                f"    Summary: {summary}\n"
                f"    Pillar: {pillar} | Horizon: {horizon} | Stage: {stage}"
            )
            if key_terms:
                entry += f"\n    Key terms: {key_terms}"

            lines.append(entry)

        return "\n\n".join(lines)

    # =========================================================================
    # Agent Loop
    # =========================================================================

    async def _run_agent_loop(
        self,
        messages: List[Dict],
        tools: List[Dict],
        batch_sources: List[ProcessedSource],
    ) -> Tuple[List[SignalAction], int]:
        """
        Non-streaming tool-calling loop. Runs up to MAX_AGENT_ITERATIONS.

        Returns:
            Tuple of (accumulated actions, total tokens used).
        """
        actions: List[SignalAction] = []
        tokens_used = 0

        for iteration in range(MAX_AGENT_ITERATIONS):
            try:
                response = await azure_openai_async_client.chat.completions.create(
                    model=get_chat_deployment(),
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    temperature=0.2,
                    max_tokens=4096,
                )
            except Exception as e:
                logger.error(
                    f"Signal agent: API call failed on iteration {iteration}: {e}"
                )
                break

            choice = response.choices[0]
            if response.usage:
                tokens_used += response.usage.total_tokens

            # If the model finished (no more tool calls), we are done
            if choice.finish_reason == "stop":
                # Append final assistant message for logging
                if choice.message.content:
                    logger.debug(
                        f"Signal agent: Final message: "
                        f"{choice.message.content[:200]}"
                    )
                break

            # Handle tool calls
            if choice.message.tool_calls:
                # Append the assistant message with tool calls
                messages.append(choice.message.model_dump())

                for tc in choice.message.tool_calls:
                    tool_name = tc.function.name
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        logger.warning(
                            f"Signal agent: Invalid JSON in tool call {tool_name}: "
                            f"{tc.function.arguments[:200]}"
                        )
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "content": json.dumps(
                                    {
                                        "error": "Invalid JSON arguments. Please try again."
                                    }
                                ),
                            }
                        )
                        continue

                    logger.debug(
                        f"Signal agent: Tool call [{iteration}] {tool_name}("
                        f"{json.dumps(args)[:200]})"
                    )

                    tool_result, action = await self._handle_tool_call(
                        tool_name, args, batch_sources
                    )

                    if action:
                        actions.append(action)

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(tool_result),
                        }
                    )
            else:
                # No tool calls and not stop — unusual but break to avoid infinite loop
                logger.warning(
                    f"Signal agent: Unexpected finish_reason "
                    f"'{choice.finish_reason}' on iteration {iteration}"
                )
                break

        logger.info(
            f"Signal agent: Agent loop completed after {min(iteration + 1, MAX_AGENT_ITERATIONS)} "
            f"iterations, {len(actions)} actions, {tokens_used} tokens"
        )

        return actions, tokens_used

    # =========================================================================
    # Tool Call Handler
    # =========================================================================

    async def _handle_tool_call(
        self,
        name: str,
        args: Dict[str, Any],
        batch_sources: List[ProcessedSource],
    ) -> Tuple[Dict, Optional[SignalAction]]:
        """
        Handle a single tool call from the agent.

        Returns:
            Tuple of (tool_result_dict, optional SignalAction).
        """
        if name == "search_existing_signals":
            return await self._tool_search_existing_signals(args)

        elif name == "create_signal":
            return self._tool_create_signal(args, batch_sources)

        elif name == "attach_source_to_signal":
            return await self._tool_attach_source_to_signal(args, batch_sources)

        elif name == "get_source_details":
            return self._tool_get_source_details(args, batch_sources)

        elif name == "list_strategic_context":
            return self._tool_list_strategic_context()

        else:
            return {"error": f"Unknown tool: {name}"}, None

    # -------------------------------------------------------------------------
    # Tool: search_existing_signals
    # -------------------------------------------------------------------------

    async def _tool_search_existing_signals(
        self, args: Dict[str, Any]
    ) -> Tuple[Dict, None]:
        """Generate embedding from query and search for similar cards."""
        query = args.get("query", "")
        if not query:
            return {"error": "query is required"}, None

        try:
            # Generate embedding for the search query
            resp = await azure_openai_async_embedding_client.embeddings.create(
                model=get_embedding_deployment(),
                input=query[:8000],
            )
            embedding = resp.data[0].embedding

            # Search for similar cards
            match_result = self.supabase.rpc(
                "find_similar_cards",
                {
                    "query_embedding": embedding,
                    "match_threshold": 0.7,
                    "match_count": 10,
                },
            ).execute()

            matches = match_result.data or []

            if matches:
                results = []
                for m in matches:
                    results.append(
                        {
                            "id": m.get("id"),
                            "name": m.get("name"),
                            "summary": (m.get("summary") or "")[:300],
                            "pillar_id": m.get("pillar_id"),
                            "horizon": m.get("horizon"),
                            "similarity": round(m.get("similarity", 0), 3),
                        }
                    )
                return {
                    "matches": results,
                    "count": len(results),
                    "message": f"Found {len(results)} existing signals matching '{query[:60]}'",
                }, None
            else:
                return {
                    "matches": [],
                    "count": 0,
                    "message": f"No existing signals found matching '{query[:60]}'",
                }, None

        except Exception as e:
            logger.error(f"Signal agent: search_existing_signals failed: {e}")
            return {
                "error": f"Search failed: {str(e)[:200]}",
                "matches": [],
                "count": 0,
            }, None

    # -------------------------------------------------------------------------
    # Tool: create_signal
    # -------------------------------------------------------------------------

    def _tool_create_signal(
        self, args: Dict[str, Any], batch_sources: List[ProcessedSource]
    ) -> Tuple[Dict, Optional[SignalAction]]:
        """Validate create_signal args, return confirmation, accumulate action."""
        signal_name = args.get("signal_name", "").strip()
        signal_summary = args.get("signal_summary", "").strip()
        source_indices = args.get("source_indices", [])

        if not signal_name:
            return {"error": "signal_name is required"}, None
        if not source_indices:
            return {"error": "source_indices is required (at least one source)"}, None

        # Validate source indices
        valid_indices = []
        for idx in source_indices:
            if 0 <= idx < len(batch_sources):
                valid_indices.append(idx)
            else:
                logger.warning(
                    f"Signal agent: Invalid source index {idx} "
                    f"(batch has {len(batch_sources)} sources)"
                )

        if not valid_indices:
            return {
                "error": f"No valid source indices. Batch has {len(batch_sources)} sources (0-{len(batch_sources) - 1})."
            }, None

        # Validate and normalize properties
        pillar_id = args.get("pillar_id", "HG")
        if pillar_id not in VALID_PILLAR_IDS:
            pillar_id = "HG"  # Default to High-Performing Government

        horizon = args.get("horizon", "H2")
        if horizon not in VALID_HORIZONS:
            horizon = "H2"

        stage = args.get("stage", 4)
        if not isinstance(stage, int) or stage < 1 or stage > 8:
            stage = 4

        relationship_type = args.get("relationship_type", "primary")
        if relationship_type not in ("primary", "supporting", "contextual", "contrary"):
            relationship_type = "primary"

        confidence = args.get("confidence", 0.7)
        try:
            confidence = max(0.0, min(1.0, float(confidence)))
        except (TypeError, ValueError):
            confidence = 0.7

        reasoning = args.get("reasoning", "")

        action = SignalAction(
            action_type="create_signal",
            signal_card_id=None,
            source_indices=valid_indices,
            signal_name=signal_name[:200],
            signal_summary=signal_summary[:2000] if signal_summary else None,
            signal_properties={
                "pillar_id": pillar_id,
                "horizon": horizon,
                "stage_id": STAGE_ID_MAP.get(stage, "4_proof"),
                "impact_score": _clamp_score(args.get("impact_score", 50)),
                "relevance_score": _clamp_score(args.get("relevance_score", 50)),
                "novelty_score": _clamp_score(args.get("novelty_score", 50)),
                "velocity_score": _clamp_score(args.get("velocity_score", 50)),
                "risk_score": _clamp_score(args.get("risk_score", 50)),
                "maturity_score": _clamp_score(stage * 12.5),  # Stage 1-8 -> ~12-100
            },
            relationship_type=relationship_type,
            confidence=confidence,
            reasoning=reasoning[:500],
        )

        source_titles = [
            (batch_sources[i].raw.title or "Untitled")[:80] for i in valid_indices
        ]

        return {
            "status": "accepted",
            "signal_name": signal_name[:200],
            "sources_included": len(valid_indices),
            "source_titles": source_titles,
            "message": (
                f"Signal '{signal_name[:60]}' will be created with "
                f"{len(valid_indices)} source(s). Continue processing remaining sources."
            ),
        }, action

    # -------------------------------------------------------------------------
    # Tool: attach_source_to_signal
    # -------------------------------------------------------------------------

    async def _tool_attach_source_to_signal(
        self, args: Dict[str, Any], batch_sources: List[ProcessedSource]
    ) -> Tuple[Dict, Optional[SignalAction]]:
        """Validate signal_id exists, return confirmation, accumulate action."""
        signal_id = args.get("signal_id", "").strip()
        source_indices = args.get("source_indices", [])

        if not signal_id:
            return {"error": "signal_id is required"}, None
        if not source_indices:
            return {"error": "source_indices is required"}, None

        # Validate source indices
        valid_indices = []
        for idx in source_indices:
            if 0 <= idx < len(batch_sources):
                valid_indices.append(idx)

        if not valid_indices:
            return {
                "error": f"No valid source indices. Batch has {len(batch_sources)} sources (0-{len(batch_sources) - 1})."
            }, None

        # Validate the signal (card) exists in the DB
        try:
            card_check = (
                self.supabase.table("cards")
                .select("id, name")
                .eq("id", signal_id)
                .execute()
            )
            if not card_check.data:
                return {
                    "error": f"Signal ID '{signal_id}' not found in database. "
                    f"Use search_existing_signals to find valid IDs."
                }, None
            card_name = card_check.data[0].get("name", "Unknown")
        except Exception as e:
            return {"error": f"Failed to validate signal ID: {str(e)[:200]}"}, None

        relationship_type = args.get("relationship_type", "supporting")
        if relationship_type not in ("primary", "supporting", "contextual", "contrary"):
            relationship_type = "supporting"

        confidence = args.get("confidence", 0.7)
        try:
            confidence = max(0.0, min(1.0, float(confidence)))
        except (TypeError, ValueError):
            confidence = 0.7

        reasoning = args.get("reasoning", "")

        action = SignalAction(
            action_type="attach_to_existing",
            signal_card_id=signal_id,
            source_indices=valid_indices,
            signal_name=card_name,
            signal_summary=None,
            signal_properties=None,
            relationship_type=relationship_type,
            confidence=confidence,
            reasoning=reasoning[:500],
        )

        return {
            "status": "accepted",
            "signal_id": signal_id,
            "signal_name": card_name,
            "sources_attached": len(valid_indices),
            "message": (
                f"{len(valid_indices)} source(s) will be attached to signal "
                f"'{card_name[:60]}'. Continue processing remaining sources."
            ),
        }, action

    # -------------------------------------------------------------------------
    # Tool: get_source_details
    # -------------------------------------------------------------------------

    def _tool_get_source_details(
        self, args: Dict[str, Any], batch_sources: List[ProcessedSource]
    ) -> Tuple[Dict, None]:
        """Return full content of a specific source."""
        idx = args.get("source_index")
        if idx is None:
            return {"error": "source_index is required"}, None

        try:
            idx = int(idx)
        except (TypeError, ValueError):
            return {"error": "source_index must be an integer"}, None

        if idx < 0 or idx >= len(batch_sources):
            return {
                "error": f"Invalid index {idx}. Valid range: 0-{len(batch_sources) - 1}"
            }, None

        source = batch_sources[idx]

        detail = {
            "index": idx,
            "title": source.raw.title or "Untitled",
            "url": source.raw.url or "",
            "source_name": source.raw.source_name or "",
            "content": (source.raw.content or "")[:5000],
        }

        if source.analysis:
            detail["analysis"] = {
                "summary": source.analysis.summary,
                "suggested_card_name": source.analysis.suggested_card_name,
                "pillars": source.analysis.pillars,
                "goals": source.analysis.goals,
                "horizon": source.analysis.horizon,
                "stage": source.analysis.suggested_stage,
                "key_excerpts": source.analysis.key_excerpts[:3],
                "impact": source.analysis.impact,
                "relevance": source.analysis.relevance,
                "novelty": source.analysis.novelty,
                "velocity": source.analysis.velocity,
                "risk": source.analysis.risk,
                "credibility": source.analysis.credibility,
                "is_new_concept": source.analysis.is_new_concept,
            }
            if source.analysis.entities:
                detail["entities"] = [
                    {"name": e.name, "type": e.entity_type}
                    for e in source.analysis.entities[:10]
                ]

        if source.triage:
            detail["triage"] = {
                "is_relevant": source.triage.is_relevant,
                "confidence": source.triage.confidence,
                "primary_pillar": source.triage.primary_pillar,
                "reason": source.triage.reason,
            }

        return detail, None

    # -------------------------------------------------------------------------
    # Tool: list_strategic_context
    # -------------------------------------------------------------------------

    def _tool_list_strategic_context(self) -> Tuple[Dict, None]:
        """Return static pillar, priority, and stage data."""
        return {
            "pillars": {
                code: {
                    "name": name,
                    "id": code,
                }
                for code, name in PILLAR_NAMES.items()
            },
            "stages": {num: stage_id for num, stage_id in STAGE_ID_MAP.items()},
            "horizons": {
                "H1": "Near-term (0-2 years): Emerging now, requires immediate awareness",
                "H2": "Mid-term (2-5 years): Developing trends, time to prepare",
                "H3": "Long-term (5-10 years): Weak signals, future scenarios",
            },
            "scoring": {
                "impact_score": "Potential effect on city operations (0-100)",
                "relevance_score": "Alignment with Austin strategic priorities (0-100)",
                "novelty_score": "How new/unexpected the trend is (0-100)",
                "velocity_score": "Speed of development/adoption (0-100)",
                "risk_score": "Threat or uncertainty level (0-100)",
            },
        }, None

    # =========================================================================
    # Action Execution
    # =========================================================================

    async def _execute_actions(
        self,
        actions: List[SignalAction],
        all_sources: List[ProcessedSource],
        config: Any,
    ) -> Dict:
        """
        Persist all accumulated actions to the database.

        For create_signal:
          1. Generate unique slug
          2. Insert card into cards table
          3. Store embedding on the card
          4. Insert each source into sources table
          5. Insert into signal_sources junction table
          6. Create timeline event

        For attach_to_existing:
          1. Insert source into sources table
          2. Insert into signal_sources junction table
        """
        signals_created: List[str] = []
        signals_enriched: List[str] = []
        sources_linked = 0
        junction_entries = 0
        auto_approved = 0

        max_new_cards = getattr(config, "max_new_cards_per_run", 15)
        auto_approve_threshold = getattr(config, "auto_approve_threshold", 0.95)
        cards_created = 0

        for action in actions:
            try:
                if action.action_type == "create_signal":
                    # Enforce card creation limit
                    if cards_created >= max_new_cards:
                        logger.warning(
                            f"Signal agent: Card creation limit ({max_new_cards}) "
                            f"reached, skipping signal '{action.signal_name}'"
                        )
                        continue

                    card_id = await self._execute_create_signal(
                        action, all_sources, auto_approve_threshold
                    )
                    if card_id:
                        signals_created.append(card_id)
                        cards_created += 1

                        # Track auto-approvals
                        if action.confidence >= auto_approve_threshold:
                            auto_approved += 1

                        # Count sources and junction entries
                        sources_linked += len(action.source_indices)
                        junction_entries += len(action.source_indices)

                elif action.action_type == "attach_to_existing":
                    attached = await self._execute_attach_to_existing(
                        action, all_sources
                    )
                    if attached:
                        if action.signal_card_id not in signals_enriched:
                            signals_enriched.append(action.signal_card_id)
                        sources_linked += attached["sources_stored"]
                        junction_entries += attached["junction_created"]

            except Exception as e:
                logger.error(
                    f"Signal agent: Failed to execute action "
                    f"({action.action_type} '{action.signal_name}'): {e}",
                    exc_info=True,
                )

        return {
            "signals_created": signals_created,
            "signals_enriched": signals_enriched,
            "sources_linked": sources_linked,
            "junction_entries_created": junction_entries,
            "auto_approved": auto_approved,
        }

    # -------------------------------------------------------------------------
    # Execute: Create Signal
    # -------------------------------------------------------------------------

    async def _execute_create_signal(
        self,
        action: SignalAction,
        all_sources: List[ProcessedSource],
        auto_approve_threshold: float,
    ) -> Optional[str]:
        """
        Create a new signal card, store its sources, and link via junction table.

        Returns:
            The new card ID, or None on failure.
        """
        props = action.signal_properties or {}

        # Generate unique slug
        slug = _generate_slug(action.signal_name)
        try:
            existing = (
                self.supabase.table("cards").select("id").eq("slug", slug).execute()
            )
            if existing.data:
                slug = f"{slug}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        except Exception:
            # If slug check fails, append timestamp as safety
            slug = f"{slug}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

        now = datetime.now(timezone.utc).isoformat()

        ai_confidence = None
        try:
            ai_confidence = round(float(action.confidence), 2)
        except (TypeError, ValueError):
            pass

        # Build discovery_metadata from all source URLs
        source_urls = []
        for idx in action.source_indices:
            if 0 <= idx < len(all_sources):
                source_urls.append(
                    {
                        "url": all_sources[idx].raw.url,
                        "title": all_sources[idx].raw.title,
                    }
                )

        card_data = {
            "name": action.signal_name,
            "slug": slug,
            "summary": action.signal_summary or "",
            "horizon": props.get("horizon", "H2"),
            "stage_id": props.get("stage_id", "4_proof"),
            "pillar_id": props.get("pillar_id", "HG"),
            "impact_score": props.get("impact_score", 50),
            "relevance_score": props.get("relevance_score", 50),
            "novelty_score": props.get("novelty_score", 50),
            "velocity_score": props.get("velocity_score", 50),
            "risk_score": props.get("risk_score", 50),
            "maturity_score": props.get("maturity_score", 50),
            "status": "draft",
            "review_status": "pending_review",
            "discovered_at": now,
            "discovery_run_id": self.run_id,
            "ai_confidence": ai_confidence,
            "discovery_metadata": {
                "source_urls": source_urls,
                "agent_reasoning": action.reasoning,
                "source_count": len(action.source_indices),
            },
            "created_by": self.triggered_by_user_id,
            "created_at": now,
            "updated_at": now,
        }

        try:
            result = self.supabase.table("cards").insert(card_data).execute()
        except Exception as e:
            logger.error(
                f"Signal agent: Failed to insert card '{action.signal_name}': {e}"
            )
            return None

        if not result.data:
            logger.error(
                f"Signal agent: Card insert returned no data for '{action.signal_name}'"
            )
            return None

        card_id = result.data[0]["id"]
        logger.info(
            f"Signal agent: Created signal card '{action.signal_name}' -> {card_id}"
        )

        # Store embedding on the card (use centroid of source embeddings)
        try:
            source_embeddings = [
                all_sources[idx].embedding
                for idx in action.source_indices
                if 0 <= idx < len(all_sources) and all_sources[idx].embedding
            ]
            if source_embeddings:
                centroid = _compute_centroid(source_embeddings)
                self.supabase.table("cards").update({"embedding": centroid}).eq(
                    "id", card_id
                ).execute()
        except Exception as e:
            logger.warning(
                f"Signal agent: Failed to store embedding on card {card_id}: {e}"
            )

        # Store each source and create junction entries
        for idx in action.source_indices:
            if idx < 0 or idx >= len(all_sources):
                continue

            source = all_sources[idx]
            source_id = await self._store_source(source, card_id)

            if source_id:
                await self._create_junction_entry(
                    card_id=card_id,
                    source_id=source_id,
                    relationship_type=action.relationship_type,
                    confidence=action.confidence,
                    reasoning=action.reasoning,
                )

                # Update discovered_sources audit trail
                self._update_discovered_source(source, card_id, "card_created")

        # Create timeline event
        await self._create_timeline_event(
            card_id=card_id,
            event_type="discovered",
            description=(
                f"Signal detected by AI agent with {len(action.source_indices)} "
                f"source(s): {action.reasoning[:200]}"
            ),
        )

        # Auto-approve if confidence exceeds threshold
        if action.confidence >= auto_approve_threshold:
            await self._auto_approve_card(card_id)

        return card_id

    # -------------------------------------------------------------------------
    # Execute: Attach to Existing
    # -------------------------------------------------------------------------

    async def _execute_attach_to_existing(
        self,
        action: SignalAction,
        all_sources: List[ProcessedSource],
    ) -> Optional[Dict]:
        """
        Attach sources to an existing signal card.

        Returns:
            Dict with counts, or None on failure.
        """
        card_id = action.signal_card_id
        if not card_id:
            return None

        sources_stored = 0
        junction_created = 0

        for idx in action.source_indices:
            if idx < 0 or idx >= len(all_sources):
                continue

            source = all_sources[idx]
            source_id = await self._store_source(source, card_id)

            if source_id:
                sources_stored += 1
                created = await self._create_junction_entry(
                    card_id=card_id,
                    source_id=source_id,
                    relationship_type=action.relationship_type,
                    confidence=action.confidence,
                    reasoning=action.reasoning,
                )
                if created:
                    junction_created += 1

                # Update discovered_sources audit trail
                self._update_discovered_source(source, card_id, "card_enriched")

        if sources_stored > 0:
            # Create timeline event for enrichment
            await self._create_timeline_event(
                card_id=card_id,
                event_type="source_added",
                description=(
                    f"Signal agent attached {sources_stored} new source(s): "
                    f"{action.reasoning[:200]}"
                ),
            )

            # Update the card's updated_at timestamp
            try:
                self.supabase.table("cards").update(
                    {"updated_at": datetime.now(timezone.utc).isoformat()}
                ).eq("id", card_id).execute()
            except Exception as e:
                logger.warning(
                    f"Signal agent: Failed to update card timestamp {card_id}: {e}"
                )

        return {
            "sources_stored": sources_stored,
            "junction_created": junction_created,
        }

    # =========================================================================
    # Database Helpers
    # =========================================================================

    async def _store_source(
        self, source: ProcessedSource, card_id: str
    ) -> Optional[str]:
        """
        Store a processed source in the sources table, linked to a card.

        Checks for duplicate URLs. Returns the source ID or None.
        """
        try:
            # Check for duplicate URL on this card
            existing = (
                self.supabase.table("sources")
                .select("id")
                .eq("card_id", card_id)
                .eq("url", source.raw.url)
                .execute()
            )
            if existing.data:
                logger.debug(
                    f"Signal agent: Source URL already exists on card {card_id}: "
                    f"{source.raw.url[:80]}"
                )
                return existing.data[0]["id"]

            source_record = {
                "card_id": card_id,
                "url": source.raw.url,
                "title": (source.raw.title or "Untitled")[:500],
                "publication": (
                    (source.raw.source_name or "")[:200]
                    if source.raw.source_name
                    else None
                ),
                "full_text": (
                    source.raw.content[:10000] if source.raw.content else None
                ),
                "ai_summary": (source.analysis.summary if source.analysis else None),
                "key_excerpts": (
                    source.analysis.key_excerpts[:5]
                    if source.analysis and source.analysis.key_excerpts
                    else []
                ),
                "relevance_to_card": (
                    source.analysis.relevance if source.analysis else 0.5
                ),
                "is_peer_reviewed": (
                    False
                    if getattr(source.raw, "is_preprint", False)
                    else (
                        True
                        if getattr(source.raw, "source_type", None) == "academic"
                        else None
                    )
                ),
                "api_source": "discovery_scan",
                "ingested_at": datetime.now(timezone.utc).isoformat(),
            }

            result = self.supabase.table("sources").insert(source_record).execute()

            if result.data:
                return result.data[0]["id"]

        except Exception as e:
            logger.error(
                f"Signal agent: Failed to store source '{source.raw.url[:80]}' "
                f"on card {card_id}: {e}"
            )

        return None

    async def _create_junction_entry(
        self,
        card_id: str,
        source_id: str,
        relationship_type: str,
        confidence: float,
        reasoning: str,
    ) -> bool:
        """
        Insert a row into the signal_sources junction table.

        Returns True if created, False otherwise.
        """
        try:
            self.supabase.table("signal_sources").insert(
                {
                    "card_id": card_id,
                    "source_id": source_id,
                    "relationship_type": relationship_type,
                    "confidence": round(confidence, 3),
                    "agent_reasoning": reasoning[:500] if reasoning else None,
                    "created_by": "signal_agent",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            ).execute()
            return True

        except Exception as e:
            # Likely a unique constraint violation (card_id, source_id)
            if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                logger.debug(
                    f"Signal agent: Junction entry already exists "
                    f"(card={card_id}, source={source_id})"
                )
            else:
                logger.error(
                    f"Signal agent: Failed to create junction entry "
                    f"(card={card_id}, source={source_id}): {e}"
                )
            return False

    async def _create_timeline_event(
        self,
        card_id: str,
        event_type: str,
        description: str,
        source_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> None:
        """Create a timeline event for a card."""
        try:
            self.supabase.table("card_timeline").insert(
                {
                    "card_id": card_id,
                    "event_type": event_type,
                    "title": event_type.replace("_", " ").title(),
                    "description": description,
                    "triggered_by_source_id": source_id,
                    "metadata": metadata or {},
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            ).execute()
        except Exception as e:
            logger.warning(f"Signal agent: Failed to create timeline event: {e}")

    def _update_discovered_source(
        self,
        source: ProcessedSource,
        card_id: str,
        status: str,
    ) -> None:
        """Update the discovered_sources audit trail after processing a source."""
        ds_id = getattr(source, "discovered_source_id", None)
        if not ds_id:
            return
        try:
            self.supabase.table("discovered_sources").update(
                {
                    "processing_status": status,
                    "resulting_card_id": card_id,
                }
            ).eq("id", ds_id).execute()
        except Exception as e:
            logger.warning(
                f"Signal agent: Failed to update discovered_source {ds_id}: {e}"
            )

    async def _auto_approve_card(self, card_id: str) -> None:
        """Auto-approve a card that exceeds the confidence threshold."""
        try:
            self.supabase.table("cards").update(
                {
                    "status": "active",
                    "review_status": "active",
                    "auto_approved_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            ).eq("id", card_id).execute()

            await self._create_timeline_event(
                card_id=card_id,
                event_type="auto_approved",
                description="Signal auto-approved based on high agent confidence score",
            )

            logger.info(f"Signal agent: Auto-approved card {card_id}")

        except Exception as e:
            logger.warning(f"Signal agent: Failed to auto-approve card {card_id}: {e}")
