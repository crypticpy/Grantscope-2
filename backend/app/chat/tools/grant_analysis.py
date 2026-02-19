"""Analysis tools for evaluating grant fit and extracting grant details from URLs.

Provides tools for AI-driven grant fit assessment against a user's
profile and for crawling a URL to extract structured grant data.
"""

from __future__ import annotations

import json
import logging
import uuid as _uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.tools import ToolDefinition, registry
from app.models.db.user import User

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FIT_ASSESSMENT_SYSTEM_PROMPT = """\
You are a grant eligibility and fit assessment expert for the City of Austin, \
Texas. You evaluate whether a grant opportunity is a good fit for a specific \
city department/program based on their profile and the grant details.

You MUST return a valid JSON object with exactly this structure:

{
  "fit_level": "Strong Fit" | "Moderate Fit" | "Weak Fit" | "Likely Not Eligible",
  "reasons": ["reason 1", "reason 2"],
  "concerns": ["concern 1", "concern 2"],
  "recommended_next_steps": ["step 1", "step 2"]
}

Base your assessment on:
1. Alignment between the grant purpose and the user's program mission
2. Whether the user's department/strategic pillars match the grant focus
3. Funding amount relative to the user's typical funding range
4. Eligibility criteria vs. the user's organization type (City of Austin)
5. Deadline feasibility
6. Grant category overlap with user's stated interests

Be honest and specific. If critical information is missing, note it as a concern.\
"""


# ---------------------------------------------------------------------------
# Tool 6: assess_fit
# ---------------------------------------------------------------------------


async def _handle_assess_fit(db: AsyncSession, user_id: str, **kwargs: Any) -> dict:
    """Assess how well a grant opportunity fits the user's profile.

    Loads the authenticated user's profile from the database, then
    sends both the grant details and the profile to Azure OpenAI
    (gpt-4.1-mini) for a structured fit assessment.

    Args:
        db: Async database session.
        user_id: Authenticated user UUID string.
        **kwargs: Grant details (grant_name, grant_description, etc.).

    Returns:
        Dict with fit_level, reasons, concerns, and recommended_next_steps.
    """
    try:
        grant_name: str = kwargs.get("grant_name", "Unknown Grant")
        grant_description: str = kwargs.get("grant_description", "")
        eligibility_text: Optional[str] = kwargs.get("eligibility_text")
        funding_amount: Optional[str] = kwargs.get("funding_amount")
        deadline: Optional[str] = kwargs.get("deadline")

        if not grant_description:
            return {"error": "A 'grant_description' is required for fit assessment."}

        # Load user profile
        profile_data: Dict[str, Any] = {}
        try:
            user_result = await db.execute(
                select(User).where(User.id == _uuid.UUID(user_id))
            )
            user_obj = user_result.scalar_one_or_none()
            if user_obj:
                for field_name in [
                    "department",
                    "program_name",
                    "program_mission",
                    "grant_categories",
                    "strategic_pillars",
                    "priorities",
                    "funding_range_min",
                    "funding_range_max",
                    "grant_experience",
                    "team_size",
                    "budget_range",
                ]:
                    val = getattr(user_obj, field_name, None)
                    if val is not None:
                        if isinstance(val, list):
                            profile_data[field_name] = list(val)
                        else:
                            profile_data[field_name] = val
        except Exception as e:
            logger.warning("Could not load user profile for fit assessment: %s", e)

        if not profile_data:
            return {
                "error": (
                    "Your profile is not set up yet. Please complete your "
                    "profile in Settings before using fit assessment."
                )
            }

        # Build the assessment prompt
        grant_section = (
            f"## Grant Opportunity\n"
            f"Name: {grant_name}\n"
            f"Description: {grant_description}\n"
        )
        if eligibility_text:
            grant_section += f"Eligibility: {eligibility_text}\n"
        if funding_amount:
            grant_section += f"Funding Amount: {funding_amount}\n"
        if deadline:
            grant_section += f"Deadline: {deadline}\n"

        profile_section = (
            f"## User Profile\n"
            f"```json\n{json.dumps(profile_data, indent=2, default=str)}\n```\n"
        )

        user_prompt = (
            f"{grant_section}\n{profile_section}\n"
            "Assess the fit between this grant and the user's profile."
        )

        # Call Azure OpenAI
        from app.openai_provider import (
            azure_openai_async_client,
            get_chat_mini_deployment,
        )

        response = await azure_openai_async_client.chat.completions.create(
            model=get_chat_mini_deployment(),
            messages=[
                {"role": "system", "content": FIT_ASSESSMENT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=2000,
            response_format={"type": "json_object"},
        )

        raw_content = response.choices[0].message.content or "{}"

        try:
            assessment = json.loads(raw_content)
        except json.JSONDecodeError:
            logger.error("Failed to parse fit assessment JSON: %s", raw_content[:200])
            return {"error": "AI returned an invalid response for fit assessment."}

        # Validate expected keys and provide defaults
        return {
            "fit_level": assessment.get("fit_level", "Unknown"),
            "reasons": assessment.get("reasons", []),
            "concerns": assessment.get("concerns", []),
            "recommended_next_steps": assessment.get("recommended_next_steps", []),
        }

    except Exception as exc:
        logger.exception("assess_fit failed: %s", exc)
        return {"error": "Fit assessment is temporarily unavailable. Please try again."}


registry.register(
    ToolDefinition(
        name="assess_fit",
        description=(
            "Evaluate how well a grant opportunity fits the current user's "
            "profile, department, and strategic priorities. Returns a fit "
            "level (Strong/Moderate/Weak/Not Eligible), reasons, concerns, "
            "and recommended next steps."
        ),
        parameters={
            "type": "object",
            "properties": {
                "grant_name": {
                    "type": "string",
                    "description": "Name of the grant opportunity.",
                },
                "grant_description": {
                    "type": "string",
                    "description": "Full description or summary of the grant.",
                },
                "eligibility_text": {
                    "type": "string",
                    "description": "Eligibility criteria text (if available).",
                },
                "funding_amount": {
                    "type": "string",
                    "description": (
                        "Funding amount or range as text "
                        "(e.g. '$50,000 - $250,000')."
                    ),
                },
                "deadline": {
                    "type": "string",
                    "description": "Application deadline (ISO date or human-readable).",
                },
            },
            "required": ["grant_name", "grant_description"],
        },
        handler=_handle_assess_fit,
        requires_online=False,
    )
)


# ---------------------------------------------------------------------------
# Tool 7: analyze_url
# ---------------------------------------------------------------------------


async def _handle_analyze_url(db: AsyncSession, user_id: str, **kwargs: Any) -> dict:
    """Crawl a URL and extract structured grant information.

    Uses the WizardService to crawl the page, then applies AI
    extraction to pull out grant name, funder, deadline, funding
    amounts, eligibility, requirements, and key dates.

    Args:
        db: Async database session (unused).
        user_id: Authenticated user UUID string (unused).
        **kwargs: ``url`` (str, required).

    Returns:
        Dict with the extracted grant context fields.
    """
    try:
        url: str = kwargs.get("url", "")
        if not url:
            return {"error": "A 'url' parameter is required."}

        # Basic URL validation
        if not url.startswith(("http://", "https://")):
            return {"error": "URL must start with http:// or https://"}

        from app.wizard_service import WizardService

        service = WizardService()
        grant_context = await service.extract_grant_from_url(url)

        # Convert Pydantic model / dataclass to dict safely
        if hasattr(grant_context, "model_dump"):
            result = grant_context.model_dump()
        elif hasattr(grant_context, "__dict__"):
            result = {
                k: v for k, v in grant_context.__dict__.items() if not k.startswith("_")
            }
        else:
            result = dict(grant_context)

        # Ensure all values are JSON-serializable
        serializable: Dict[str, Any] = {}
        for key, value in result.items():
            if hasattr(value, "isoformat"):
                serializable[key] = value.isoformat()
            elif isinstance(value, (str, int, float, bool, type(None))):
                serializable[key] = value
            elif isinstance(value, (list, dict)):
                serializable[key] = value
            else:
                serializable[key] = str(value)

        return serializable

    except ValueError as exc:
        logger.warning("analyze_url user error: %s", exc)
        return {"error": str(exc)}
    except Exception as exc:
        logger.exception("analyze_url failed: %s", exc)
        return {"error": "URL analysis is temporarily unavailable. Please try again."}


registry.register(
    ToolDefinition(
        name="analyze_url",
        description=(
            "Crawl a grant opportunity URL (web page or PDF) and extract "
            "structured information including grant name, funder, deadline, "
            "funding amounts, eligibility criteria, requirements, and key dates."
        ),
        parameters={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": (
                        "Full URL of the grant opportunity page or document "
                        "(must start with http:// or https://)."
                    ),
                },
            },
            "required": ["url"],
        },
        handler=_handle_analyze_url,
        requires_online=True,
    )
)
