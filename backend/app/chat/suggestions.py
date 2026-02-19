"""Follow-up and starter suggestion generation for the chat service.

This module consolidates all suggestion generation:

- **generate_suggestions_internal**: Quick follow-up questions after an
  assistant response (used inline during streaming).
- **generate_scope_suggestions**: Starter questions when a user opens a
  new chat scope (signal, workstream, global, wizard).
- **generate_smart_suggestions**: Categorised follow-up suggestions with
  categories (deeper, compare, action, explore).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.card import Card
from app.models.db.workstream import Workstream
from app.openai_provider import azure_openai_async_client, get_chat_mini_deployment

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal follow-up suggestions (streamed after assistant response)
# ---------------------------------------------------------------------------


async def generate_suggestions_internal(
    scope: str,
    scope_metadata: Dict[str, Any],
    last_response: str,
    last_question: str,
) -> List[str]:
    """Generate follow-up question suggestions based on the conversation context.

    Uses the mini model for speed and cost efficiency.

    Args:
        scope: Current chat scope (``signal``, ``workstream``, ``global``,
               ``wizard``, or ``grant_assistant``).
        scope_metadata: Scope-specific metadata dict (card name, workstream
                        name, card count, etc.).
        last_response: The assistant's most recent response text (truncated
                       internally).
        last_question: The user's most recent question text (truncated
                       internally).

    Returns:
        A list of up to 3 short follow-up question strings, or an empty list
        on failure.
    """
    scope_hints = {
        "signal": f"""The user is exploring a signal called \"{scope_metadata.get('card_name', 'Unknown')}\". Suggest questions about its implications for Austin, implementation timeline, risks, comparison with similar trends, or what other cities are doing.""",
        "workstream": f"""The user is exploring a workstream called \"{scope_metadata.get('workstream_name', 'Unknown')}\" with {scope_metadata.get('card_count', 0)} signals. Suggest questions about cross-cutting themes, priority signals, resource allocation, or strategic recommendations.""",
        "global": "The user asked a broad strategic question. Suggest questions about specific pillars, emerging patterns, comparisons between trends, or actionable next steps for the city.",
        "wizard": "The user is working through a grant application interview. Suggest responses they might give or questions they might ask about writing the grant, such as budget details, staffing plans, or timeline clarifications.",
        "grant_assistant": "The user is using the Grant Discovery Assistant to search for grant opportunities. Suggest follow-up questions about refining search criteria, exploring related funding sources, comparing grants, or next steps like tracking or applying.",
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


# ---------------------------------------------------------------------------
# Scope-aware starter suggestions (before conversation begins)
# ---------------------------------------------------------------------------


async def generate_scope_suggestions(
    scope: str,
    scope_id: Optional[str],
    db: AsyncSession,
    user_id: str,
) -> List[str]:
    """Generate context-aware suggested questions for a given scope.

    This is the public-facing function called by the API endpoint when the
    user hasn't started a conversation yet.

    Args:
        scope: Chat scope (``signal``, ``workstream``, ``global``, ``wizard``,
               or ``grant_assistant``).
        scope_id: UUID of the scoped entity (card, workstream, etc.).
        db: Active async database session.
        user_id: UUID of the authenticated user.

    Returns:
        A list of up to 3 starter question strings.
    """
    scope_metadata: Dict[str, Any] = {}

    try:
        if scope == "signal" and scope_id:
            result = await db.execute(
                select(
                    Card.name, Card.summary, Card.pillar_id, Card.horizon, Card.stage_id
                ).where(Card.id == scope_id)
            )
            card_row = result.one_or_none()
            if card_row:
                scope_metadata = {
                    "card_name": card_row.name,
                    "card_summary": card_row.summary or "",
                }
        elif scope == "workstream" and scope_id:
            result = await db.execute(
                select(
                    Workstream.name, Workstream.description, Workstream.keywords
                ).where(Workstream.id == scope_id)
            )
            ws_row = result.one_or_none()
            if ws_row:
                scope_metadata = {
                    "workstream_name": ws_row.name,
                    "workstream_description": ws_row.description or "",
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
        "wizard": (
            "Generate 3 starter prompts to help a city program manager begin "
            "a grant application interview. Focus on describing their program, "
            "the problem it solves, and who it would help."
        ),
        "grant_assistant": (
            "Generate 3 starter questions a city employee might ask "
            "a grant discovery assistant. Focus on finding grants for "
            "specific programs, comparing funding opportunities, checking "
            "deadlines, and understanding eligibility requirements."
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
        "wizard": [
            "Tell me about the program I want to fund",
            "I need help figuring out a budget for my grant",
            "What kind of grants are available for city programs?",
        ],
        "grant_assistant": [
            "Find grants for community health programs",
            "What federal funding opportunities are available this quarter?",
            "Show me grants with deadlines in the next 60 days",
        ],
    }

    return fallbacks.get(scope, fallbacks["global"])


# ---------------------------------------------------------------------------
# Smart categorised suggestions
# ---------------------------------------------------------------------------


async def generate_smart_suggestions(
    scope: str,
    scope_context: str,
    conversation_summary: str,
) -> List[Dict[str, str]]:
    """Generate categorised follow-up suggestions using the mini model.

    Each suggestion belongs to one of four categories:
    ``deeper``, ``compare``, ``action``, ``explore``.

    Args:
        scope: Current chat scope.
        scope_context: Short textual description of the scoped entity
                       (e.g. card name + summary, workstream description).
        conversation_summary: A brief summary of the most recent conversation
                              exchange.  May be empty for new conversations.

    Returns:
        A list of dicts with ``text`` and ``category`` keys, or scope-specific
        fallback suggestions on failure.
    """
    context_block = ""
    if conversation_summary:
        context_block = f"""
Recent conversation:
{conversation_summary}
"""

    prompt = f"""Generate exactly 4 follow-up question suggestions for a city analyst using a strategic intelligence system.

Scope: {scope}
{scope_context}
{context_block}
Each suggestion must belong to one of these categories:
- "deeper": Dig deeper into causes, drivers, or details
- "compare": Compare with other cities, trends, or benchmarks
- "action": Identify specific actions, next steps, or recommendations
- "explore": Discover related signals, patterns, or connections

Return a JSON object with a "suggestions" array of exactly 4 objects, one per category.
Each object has "text" (the question, max 80 chars) and "category" (one of: deeper, compare, action, explore).

Example:
{{"suggestions": [
  {{"text": "What are the underlying drivers of this trend?", "category": "deeper"}},
  {{"text": "How does this compare to Denver and Portland?", "category": "compare"}},
  {{"text": "What specific actions should Austin take next?", "category": "action"}},
  {{"text": "What related signals should we watch?", "category": "explore"}}
]}}"""

    try:
        response = await azure_openai_async_client.chat.completions.create(
            model=get_chat_mini_deployment(),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You generate categorized follow-up questions for a strategic "
                        "intelligence chat system. Respond with valid JSON only."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=400,
            temperature=0.8,
        )

        content = response.choices[0].message.content.strip()
        result = json.loads(content)

        # Parse the result
        suggestions_raw: list = []
        if isinstance(result, dict):
            suggestions_raw = result.get("suggestions") or result.get("questions") or []
        elif isinstance(result, list):
            suggestions_raw = result

        valid_categories = {"deeper", "compare", "action", "explore"}
        suggestions: List[Dict[str, str]] = []
        for item in suggestions_raw[:4]:
            if isinstance(item, dict) and "text" in item and "category" in item:
                category = (
                    item["category"]
                    if item["category"] in valid_categories
                    else "deeper"
                )
                suggestions.append(
                    {
                        "text": str(item["text"])[:100],
                        "category": category,
                    }
                )

        if suggestions:
            return suggestions

    except Exception as e:
        logger.warning(f"Smart suggestion generation failed: {e}")

    # Fallback categorized suggestions
    fallbacks = {
        "signal": [
            {
                "text": "What are the underlying drivers of this signal?",
                "category": "deeper",
            },
            {"text": "How does this compare to other cities?", "category": "compare"},
            {"text": "What should Austin do to prepare?", "category": "action"},
            {"text": "What related signals should we track?", "category": "explore"},
        ],
        "workstream": [
            {"text": "What are the cross-cutting themes here?", "category": "deeper"},
            {
                "text": "How do these signals compare to national trends?",
                "category": "compare",
            },
            {
                "text": "Which signals require the most urgent action?",
                "category": "action",
            },
            {
                "text": "What emerging patterns connect these signals?",
                "category": "explore",
            },
        ],
        "global": [
            {
                "text": "What are the fastest-moving trends right now?",
                "category": "deeper",
            },
            {"text": "How does Austin compare to peer cities?", "category": "compare"},
            {
                "text": "What should Austin prioritize in the next 12 months?",
                "category": "action",
            },
            {
                "text": "Are there any new cross-cutting patterns emerging?",
                "category": "explore",
            },
        ],
        "wizard": [
            {
                "text": "Tell me more about what my program does",
                "category": "deeper",
            },
            {
                "text": "What do similar grant applications usually include?",
                "category": "compare",
            },
            {
                "text": "Help me outline a budget for this grant",
                "category": "action",
            },
            {
                "text": "What other funding sources should I consider?",
                "category": "explore",
            },
        ],
        "grant_assistant": [
            {
                "text": "What are the eligibility requirements for this grant?",
                "category": "deeper",
            },
            {
                "text": "How does this compare to other grants in this area?",
                "category": "compare",
            },
            {
                "text": "Create an opportunity card to track this grant",
                "category": "action",
            },
            {
                "text": "Are there similar grants from other agencies?",
                "category": "explore",
            },
        ],
    }
    return fallbacks.get(scope, fallbacks["global"])
