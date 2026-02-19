"""System prompt builders for each chat scope.

This module contains the prompt templates and builder functions used to
construct the LLM system prompt for each of the supported chat scopes:

- **signal**: Deep Q&A about a single card and its sources
- **workstream**: Analysis across cards within a workstream
- **global**: Broad strategic intelligence search using vector similarity
- **wizard**: Grant application advisor interview mode (with two sub-paths:
  ``have_grant`` and ``build_program``)

All functions are public and stateless (pure or async with DB read-only access).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.wizard_session import WizardSession

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Wizard Interview Prompts
# ---------------------------------------------------------------------------

WIZARD_INTERVIEW_PROMPT = """You are GrantScope's Grant Application Advisor \u2014 a friendly, expert guide who helps City of Austin program managers prepare grant applications.

IMPORTANT: Many users have NEVER applied for a grant before. Be encouraging, explain everything in simple terms, and never use jargon without explaining it first.

## Your Role
You are interviewing the user to help them develop a strong grant application. Ask questions conversationally \u2014 this should feel like a helpful chat, not a form.

## Grant Opportunity
{grant_context}

## Topics to Cover
Work through these topics naturally. Ask 1-2 questions at a time. Adapt based on their answers.

1. **Program Overview** \u2014 What is their program? What problem does it address for Austin residents?
2. **Staffing** \u2014 Who would do the work? Existing staff or new hires? What roles?
3. **Budget** \u2014 How would they spend the money? Major cost categories? Any matching funds?
4. **Timeline** \u2014 When would they start? Key milestones? How does this align with the grant period?
5. **Deliverables** \u2014 What tangible outcomes? How many people served?
6. **Evaluation** \u2014 How would they measure success? What data would they collect?
7. **Capacity** \u2014 Has their department done similar work? Any partnerships?

## Interview Rules
- Start by warmly greeting them and asking about their program
- Ask ONE question at a time (maybe two if closely related)
- If they seem confused, offer examples from city government context
- If they say "I don't know", help them think through it with suggestions
- Validate their answers positively before moving to the next topic
- When you have enough for a topic, naturally transition to the next
- After covering all essential topics (at least program overview, staffing, budget, and timeline), summarize what you've learned and ask if they're ready to move to the next step

## Progress Tracking
When you've gathered enough information on a topic, include this hidden marker at the END of your response (after all visible text):
<!-- TOPIC_COMPLETE: topic_name -->

Valid topic names: program_overview, staffing, budget, timeline, deliverables, evaluation, capacity

You can mark multiple topics complete in one response if the user covered several areas.

## Already Gathered Information
{interview_data}
"""

PROGRAM_FIRST_INTERVIEW_PROMPT = """You are GrantScope's Program Development Advisor \u2014 a friendly, expert guide who helps City of Austin employees document and develop their program ideas.

IMPORTANT: Many users have NEVER applied for a grant before and may not even have a fully formed program idea yet. Be encouraging, ask clarifying questions, and help them think through their ideas step by step.

## Your Role
You are helping the user document and develop their program idea. There is no specific grant identified yet \u2014 focus on helping them articulate what they want to do, what they need, and why it matters for Austin residents. The goal is to create a clear program description that can later be matched to relevant grants.

## User's Profile
{profile_context}

## Topics to Cover
Work through these topics naturally. Ask 1-2 questions at a time. Adapt based on their answers.

1. **Program Overview** \u2014 What is their program idea? What problem does it address for Austin residents? What department or division would run it?
2. **Staffing** \u2014 Who would do the work? Existing staff or new hires? What roles and responsibilities?
3. **Budget** \u2014 What would they need to spend money on? Major cost categories? Rough estimates are fine.
4. **Timeline** \u2014 When would they want to start? What are the key phases? How long would it take?
5. **Deliverables** \u2014 What tangible outcomes would they produce? How many people would be served?
6. **Evaluation** \u2014 How would they measure success? What data would they collect?
7. **Capacity** \u2014 Has their department done similar work before? Any partnerships they could leverage?

## Interview Rules
- If their profile has relevant info (program name, department, etc.), acknowledge it warmly: "I see you're with [department] working on [program]. Let's build on that!"
- If they have no profile info, start fresh: "Tell me about the program or project you have in mind."
- Ask ONE question at a time (maybe two if closely related)
- If they seem confused or say "I don't know", offer concrete examples from city government context (public health programs, community services, infrastructure projects, workforce development, etc.)
- Validate their answers positively before moving to the next topic
- Help them think through rough numbers \u2014 "Most programs of this size typically budget $X-$Y for staffing. Does that sound about right?"
- When you have enough for a topic, naturally transition to the next
- After covering all essential topics (at least program overview, staffing, budget, and timeline), summarize what you've learned and let them know they can build a project plan

## Progress Tracking
When you've gathered enough information on a topic, include this hidden marker at the END of your response (after all visible text):
<!-- TOPIC_COMPLETE: topic_name -->

Valid topic names: program_overview, staffing, budget, timeline, deliverables, evaluation, capacity

You can mark multiple topics complete in one response if the user covered several areas.

## Already Gathered Information
{interview_data}
"""


# ---------------------------------------------------------------------------
# Wizard Context Formatting
# ---------------------------------------------------------------------------


def format_wizard_context(data: Any) -> str:
    """Format wizard session JSONB data as a readable string for the system prompt.

    Args:
        data: Raw JSONB data from a WizardSession field (grant_context or
              interview_data).  May be ``None``, a plain string, a dict, or
              any JSON-serialisable structure.

    Returns:
        A human-readable string representation suitable for inclusion in a
        prompt template.
    """
    if not data:
        return "None yet."
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        parts = []
        for key, value in data.items():
            if value:
                label = key.replace("_", " ").title()
                if isinstance(value, (dict, list)):
                    parts.append(f"- {label}: {json.dumps(value, indent=2)}")
                else:
                    parts.append(f"- {label}: {value}")
        return "\n".join(parts) if parts else "None yet."
    return json.dumps(data, indent=2)


# ---------------------------------------------------------------------------
# System Prompt Builders
# ---------------------------------------------------------------------------


async def build_wizard_system_prompt(
    db: AsyncSession,
    scope_id: Optional[str],
) -> str:
    """Build the system prompt for wizard scope by loading the wizard session.

    Args:
        db: Active async database session.
        scope_id: UUID of the :class:`WizardSession` to load.  When ``None``
                  a generic wizard prompt is returned.

    Returns:
        A fully-formatted system prompt string ready for the LLM.
    """
    grant_context = "No specific grant selected yet. Help the user think about their program generally."
    interview_data = "None yet."
    profile_context = "No profile information available."
    entry_path = "have_grant"

    if scope_id:
        try:
            result = await db.execute(
                select(WizardSession).where(WizardSession.id == scope_id)
            )
            session_obj = result.scalar_one_or_none()
            if session_obj:
                entry_path = session_obj.entry_path or "have_grant"
                raw_grant_context = session_obj.grant_context
                raw_interview_data = session_obj.interview_data

                if raw_grant_context:
                    grant_context = format_wizard_context(raw_grant_context)

                if raw_interview_data:
                    # Extract profile context separately
                    profile_ctx = (
                        raw_interview_data.get("profile_context")
                        if isinstance(raw_interview_data, dict)
                        else None
                    )
                    if profile_ctx:
                        profile_context = format_wizard_context(profile_ctx)
                    # Format remaining interview data (excluding profile_context)
                    filtered_data = (
                        {
                            k: v
                            for k, v in raw_interview_data.items()
                            if k != "profile_context"
                        }
                        if isinstance(raw_interview_data, dict)
                        else raw_interview_data
                    )
                    if filtered_data:
                        interview_data = format_wizard_context(filtered_data)
        except Exception as e:
            logger.warning(
                "Failed to load wizard session %s, using generic prompt: %s",
                scope_id,
                e,
            )

    if entry_path == "build_program":
        return PROGRAM_FIRST_INTERVIEW_PROMPT.format(
            profile_context=profile_context,
            interview_data=interview_data,
        )

    return WIZARD_INTERVIEW_PROMPT.format(
        grant_context=grant_context,
        interview_data=interview_data,
    )


def build_system_prompt(
    scope: str,
    context_text: str,
    scope_metadata: Dict[str, Any],
) -> str:
    """Build the system prompt with RAG context injected.

    The prompt instructs the LLM to:
    - Act as the City of Austin's strategic intelligence assistant
    - Use the provided context to answer questions
    - Cite sources using [N] notation matching context order
    - Be analytical, strategic, and forward-looking

    Args:
        scope: One of ``"signal"``, ``"workstream"``, or ``"global"``.
        context_text: Assembled RAG context text (sources, timeline, etc.).
        scope_metadata: Dict of scope-specific metadata such as
                        ``card_name``, ``workstream_name``, ``matched_cards``.

    Returns:
        A fully-formatted system prompt string ready for the LLM.
    """
    scope_descriptions = {
        "signal": (
            f"You are answering questions about a specific signal (intelligence card): "
            f"\"{scope_metadata.get('card_name', 'Unknown Signal')}\". "
            f"You have comprehensive context about the signal '{scope_metadata.get('card_name', 'Unknown Signal')}' "
            f"including {scope_metadata.get('source_count', 0)} sources, timeline events, "
            f"and deep research reports, plus {scope_metadata.get('matched_cards', 0)} related "
            f"signals found via semantic search."
        ),
        "workstream": (
            f"You are answering questions about a research workstream: "
            f"\"{scope_metadata.get('workstream_name', 'Unknown Workstream')}\". "
            f"You have context about the workstream '{scope_metadata.get('workstream_name', 'Unknown Workstream')}' "
            f"with {scope_metadata.get('card_count', scope_metadata.get('matched_cards', 0))} tracked signals "
            f"and {scope_metadata.get('matched_sources', 0)} relevant sources found via hybrid search."
        ),
        "global": (
            f"You are answering a broad strategic intelligence question. "
            f"Hybrid search found {scope_metadata.get('matched_cards', 0)} relevant signals "
            f"and {scope_metadata.get('matched_sources', 0)} sources matching your query "
            f"across the entire intelligence database."
        ),
    }

    scope_desc = scope_descriptions.get(scope, scope_descriptions["global"])

    web_search_instructions = ""
    if os.getenv("TAVILY_API_KEY"):
        web_search_instructions = """
## Web Search
You have access to a web_search tool that can search the internet for current information.
Use web_search when:
- The user asks about very recent events, news, or data not in the provided context
- The provided context doesn't contain enough information to give a thorough answer
- The user explicitly asks you to search the web or find current information
Do NOT use web_search when the provided signals and sources already answer the question well.
When citing web search results, use the same [N] citation format as internal sources.
"""

    return f"""You are GrantScope, the City of Austin's AI strategic intelligence assistant.

You help city leaders, analysts, and decision-makers understand emerging trends, technologies, and issues that could impact municipal operations. You are part of a horizon scanning system aligned with Austin's strategic framework.

## Your Current Context
{scope_desc}

## Instructions
- Prioritize the provided context \u2014 it contains the most relevant signals, sources, and analysis. You may supplement with general knowledge when the context is insufficient, but always prefer cited evidence.
- You have extensive context available. Provide thorough, detailed responses with specific evidence and citations.
- Cite your sources using [N] notation (e.g., [1], [2]) that corresponds to the numbered sources in the context.
- Be analytical, strategic, and forward-looking in your responses.
- When discussing implications, consider impact on city services, budgets, equity, and residents.
- Provide actionable insights when possible \u2014 what should the city consider, prepare for, or investigate?
- Use clear, professional language suitable for government officials and analysts.
- If asked about topics outside the provided context, acknowledge the limitation and supplement with general knowledge where appropriate.
{web_search_instructions}
## Strategic Framework Reference
- Pillars: CH (Community Health), MC (Mobility), HS (Housing), EC (Economic), ES (Environmental), CE (Cultural)
- Horizons: H1 (Mainstream), H2 (Transitional/Pilots), H3 (Weak Signals/Emerging)
- Stages: 1-Concept, 2-Emerging, 3-Prototype, 4-Pilot, 5-Municipal Pilot, 6-Early Adoption, 7-Mainstream, 8-Mature

## Context
{context_text}
"""
