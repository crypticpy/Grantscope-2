"""Grant Discovery Assistant scope configuration.

Configures the grant_assistant chat scope with:
- Profile-aware system prompt tailored to grant discovery
- Tool selection based on admin settings (online search toggle)
- User profile enrichment for personalized search

This module is the bridge between the tool registry (app.chat.tools),
the prompt system (app.chat.prompts), and the chat orchestrator
(app.chat_service).
"""

from __future__ import annotations

import logging
import uuid as _uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Awaitable, Callable, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.tools import registry
from app.models.db.card import Card
from app.models.db.user import User

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Grant Assistant System Prompt
# ---------------------------------------------------------------------------

GRANT_ASSISTANT_SYSTEM_PROMPT = """\
You are GrantScope's Grant Discovery Assistant — an AI expert that helps City of Austin \
employees find, evaluate, and track grant opportunities that match their programs and \
strategic priorities.

## Your Capabilities
You have access to tools that can:
- Search the internal GrantScope database of {card_count} tracked grant opportunities
- {online_capabilities}
- Assess how well a grant fits the user's profile and priorities
- Create opportunity cards to track interesting grants
- Check and manage the user's programs (workstreams)

## User Profile
{user_profile_section}

## Instructions
1. **Start by understanding the user's needs.** If they're vague ("find me grants"), ask 1-2 \
clarifying questions about their focus area, budget needs, or timeline. Use their profile \
context to make smart suggestions.

2. **Search strategically.** Start with the internal database. If results are limited or the \
user asks for more, use external sources (Grants.gov, SAM.gov, web search) when available.

3. **Present results clearly.** For each grant, include: name, funder/agency, funding range, \
deadline, and a brief fit assessment. Highlight why it matches (or doesn't match) their profile.

4. **Be proactive about next steps.** After finding good matches:
   - Offer to create opportunity cards for tracking
   - Suggest adding cards to relevant programs
   - If they don't have a matching program, offer to help create one
   - Recommend related searches they might not have considered

5. **Cite sources.** When referencing internal grants, include the card name. When referencing \
external results, include the source URL.

6. **Be honest about limitations.** If online search is disabled, explain that you're searching \
the internal database only. If a grant seems like a poor fit, say so with reasons.

## Current Date
{current_date}

## Strategic Framework
- Pillars: CH (Community Health), MC (Mobility), HS (Housing), EC (Economic), ES (Environmental), CE (Cultural)
- Grant Categories: Federal, State, Local, Foundation/Private, Corporate
- Grant Types: Formula, Competitive, Pass-through, Cooperative Agreement
"""


def _build_user_profile_section(profile: Dict[str, Any]) -> str:
    """Format the user's profile data for inclusion in the system prompt.

    Args:
        profile: Dict of user profile fields.

    Returns:
        Formatted string describing the user's profile.
    """
    if not profile:
        return (
            "No profile information available. Ask the user about their "
            "department, program focus, and what types of grants they're "
            "interested in."
        )

    parts: List[str] = []

    if profile.get("department"):
        parts.append(f"- Department: {profile['department']}")
    if profile.get("program_name"):
        parts.append(f"- Program: {profile['program_name']}")
    if profile.get("program_mission"):
        parts.append(f"- Mission: {profile['program_mission']}")
    if profile.get("strategic_pillars"):
        pillars = profile["strategic_pillars"]
        if isinstance(pillars, list):
            parts.append(f"- Strategic Pillars: {', '.join(pillars)}")
    if profile.get("grant_categories"):
        cats = profile["grant_categories"]
        if isinstance(cats, list):
            parts.append(f"- Grant Categories of Interest: {', '.join(cats)}")
    if profile.get("priorities"):
        priorities = profile["priorities"]
        if isinstance(priorities, list):
            parts.append(f"- Priorities: {', '.join(priorities)}")
    if profile.get("custom_priorities"):
        # custom_priorities is a Text field (single string), not an array
        parts.append(f"- Custom Priorities: {profile['custom_priorities']}")
    if (
        profile.get("funding_range_min") is not None
        or profile.get("funding_range_max") is not None
    ):
        fmin = profile.get("funding_range_min", "any")
        fmax = profile.get("funding_range_max", "any")
        if isinstance(fmin, (int, float)) and isinstance(fmax, (int, float)):
            parts.append(f"- Typical Funding Range: ${fmin:,} - ${fmax:,}")
        else:
            parts.append(f"- Funding Range: {fmin} - {fmax}")
    if profile.get("grant_experience"):
        parts.append(f"- Grant Experience: {profile['grant_experience']}")
    if profile.get("team_size"):
        parts.append(f"- Team Size: {profile['team_size']}")
    if profile.get("help_wanted"):
        help_items = profile["help_wanted"]
        if isinstance(help_items, list):
            parts.append(f"- Help Wanted: {', '.join(help_items)}")

    if not parts:
        return (
            "Profile exists but has minimal information. Ask clarifying questions "
            "about their focus area and priorities."
        )

    completion = _calculate_profile_completion(profile)
    parts.insert(0, f"Profile completion: {completion}%")

    return "\n".join(parts)


def _calculate_profile_completion(profile: Dict[str, Any]) -> int:
    """Calculate profile completion percentage.

    Args:
        profile: Dict of user profile fields.

    Returns:
        Integer percentage (0-100).
    """
    key_fields = [
        "department",
        "program_name",
        "program_mission",
        "strategic_pillars",
        "grant_categories",
        "priorities",
        "funding_range_min",
        "funding_range_max",
        "grant_experience",
    ]
    filled = sum(1 for f in key_fields if profile.get(f))
    return int((filled / len(key_fields)) * 100)


@dataclass
class GrantAssistantContext:
    """Context object for the grant assistant scope.

    Assembled by build_grant_assistant_context() and consumed by the
    chat orchestrator to configure the grant_assistant scope.

    Attributes:
        system_prompt: The fully-rendered system prompt string.
        tools: OpenAI function-calling tool definitions (filtered by online_enabled).
        tool_handlers: Mapping of tool name to async handler callable.
        user_profile: Raw user profile dict.
        online_enabled: Whether online search tools are available.
    """

    system_prompt: str
    tools: List[Dict[str, Any]]
    tool_handlers: Dict[str, Callable[..., Awaitable[Dict[str, Any]]]]
    user_profile: Dict[str, Any]
    online_enabled: bool = False


async def build_grant_assistant_context(
    db: AsyncSession,
    user_id: str,
    online_enabled: bool = False,
) -> GrantAssistantContext:
    """Load user profile, count grants, build system prompt and tool set.

    This is the main entry point for configuring the grant_assistant scope.
    Called by the chat orchestrator when scope == "grant_assistant".

    Args:
        db: Async database session.
        user_id: Authenticated user UUID string.
        online_enabled: Whether admin has enabled online search.

    Returns:
        GrantAssistantContext with everything the orchestrator needs.
    """
    # 1. Load user profile
    user_profile: Dict[str, Any] = {}
    try:
        result = await db.execute(select(User).where(User.id == _uuid.UUID(user_id)))
        user_obj = result.scalar_one_or_none()
        if user_obj:
            profile_fields = [
                "department",
                "program_name",
                "program_mission",
                "grant_categories",
                "strategic_pillars",
                "priorities",
                "custom_priorities",
                "funding_range_min",
                "funding_range_max",
                "grant_experience",
                "team_size",
                "budget_range",
                "help_wanted",
            ]
            for field_name in profile_fields:
                val = getattr(user_obj, field_name, None)
                if val is not None:
                    user_profile[field_name] = (
                        list(val) if isinstance(val, list) else val
                    )
    except Exception as e:
        logger.warning("Failed to load user profile for grant assistant: %s", e)

    # 2. Count active grant cards
    card_count = 0
    try:
        count_result = await db.execute(
            select(func.count(Card.id)).where(Card.status == "active")
        )
        card_count = count_result.scalar() or 0
    except Exception as e:
        logger.warning("Failed to count grant cards: %s", e)

    # 3. Build system prompt
    user_profile_section = _build_user_profile_section(user_profile)

    online_capabilities = (
        "Search Grants.gov and SAM.gov federal databases, analyze grant URLs, "
        "and search the web for additional opportunities"
        if online_enabled
        else "Online search is currently disabled by your administrator. "
        "Results are limited to the internal database"
    )

    system_prompt = GRANT_ASSISTANT_SYSTEM_PROMPT.format(
        card_count=card_count,
        online_capabilities=online_capabilities,
        user_profile_section=user_profile_section,
        current_date=date.today().isoformat(),
    )

    # 4. Get tools from registry (filtered by online_enabled)
    tools = registry.get_openai_definitions(online_enabled=online_enabled)

    # 5. Build handler map (all tools, not just online — the registry filters definitions)
    tool_handlers: Dict[str, Callable] = {}
    for tool_def in tools:
        tool_name = tool_def["function"]["name"]
        tool_handlers[tool_name] = registry.get_handler(tool_name)

    return GrantAssistantContext(
        system_prompt=system_prompt,
        tools=tools,
        tool_handlers=tool_handlers,
        user_profile=user_profile,
        online_enabled=online_enabled,
    )
