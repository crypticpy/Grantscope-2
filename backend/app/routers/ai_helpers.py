"""AI helper and card creation router."""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.card_analysis_service import queue_card_analysis
from app.deps import get_db, get_current_user_hardcoded, _safe_error, limiter
from app.taxonomy import PILLAR_NAMES, GRANT_CATEGORIES, DEPARTMENT_LIST
from app.openai_provider import (
    azure_openai_client,
    get_chat_deployment,
    get_chat_mini_deployment,
)
from app.models.card_creation import (
    CreateCardFromTopicRequest,
    CreateCardFromTopicResponse,
    ManualCardCreateRequest,
    KeywordSuggestionResponse,
)
from app.models.ai_helpers import (
    SuggestDescriptionRequest,
    SuggestDescriptionResponse,
    ReadinessAssessmentRequest,
    ReadinessAssessmentResponse,
    ReadinessScoreBreakdown,
)
from app.models.db.card import Card
from app.models.db.source import Source, SignalSource
from app.models.db.workstream import WorkstreamCard

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["ai_helpers"])


@router.post("/cards/create-from-topic")
@limiter.limit("10/minute")
async def create_card_from_topic(
    request: Request,
    body: CreateCardFromTopicRequest,
    user=Depends(get_current_user_hardcoded),
    db: AsyncSession = Depends(get_db),
):
    """Quick card creation from a topic phrase. Creates card and optionally starts background scan."""
    try:
        card_id = str(uuid.uuid4())
        card = Card(
            id=uuid.UUID(card_id),
            name=body.topic[:200],
            slug=body.topic[:200].lower().replace(" ", "-").replace("/", "-"),
            description=f"User-created signal: {body.topic}",
            origin="user_created",
            is_exploratory=not body.pillar_hints,
            created_by=uuid.UUID(user["id"]),
            review_status="approved",
            signal_quality_score=0,
            quality_breakdown={},
        )

        if body.pillar_hints and len(body.pillar_hints) > 0:
            card.pillar_id = body.pillar_hints[0]

        if body.source_preferences:
            card.source_preferences = body.source_preferences.dict(exclude_none=True)

        db.add(card)
        await db.flush()

        # Queue background AI analysis
        try:
            await queue_card_analysis(db, card_id, user["id"])
        except Exception:
            logger.warning("Failed to queue card analysis for %s", card_id)

        # If workstream specified, add to workstream
        if body.workstream_id:
            try:
                ws_card = WorkstreamCard(
                    workstream_id=uuid.UUID(body.workstream_id),
                    card_id=uuid.UUID(card_id),
                    status="inbox",
                )
                db.add(ws_card)
                await db.flush()
            except Exception as ws_err:
                logger.warning(
                    f"Card {card_id} created but failed to add to workstream "
                    f"{body.workstream_id}: {str(ws_err)}"
                )

        return CreateCardFromTopicResponse(
            card_id=card_id,
            card_name=body.topic[:200],
            status="created",
            message="Card created. Sources will be discovered in the next scan cycle.",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create card from topic: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("card creation", e),
        ) from e


@router.post("/cards/create-manual")
@limiter.limit("10/minute")
async def create_manual_card(
    request: Request,
    body: ManualCardCreateRequest,
    user=Depends(get_current_user_hardcoded),
    db: AsyncSession = Depends(get_db),
):
    """Create a card from a full manual form with all fields specified.

    Unlike the quick topic-based creation, this endpoint accepts detailed card
    metadata including pillar assignments, horizon, stage, and optional seed URLs.
    Cards created manually are marked with origin='user_created' and bypass the
    discovery pipeline.

    Args:
        body: ManualCardCreateRequest with name, description, pillars, etc.
        user: Authenticated user from JWT token.

    Returns:
        JSON with card_id, card_name, status, and message.

    Raises:
        400: Invalid request data or failed insert.
        500: Unexpected server error.
    """
    try:
        card_id = str(uuid.uuid4())

        # Determine primary pillar from the list, or None for exploratory
        primary_pillar = None
        if body.pillar_ids and len(body.pillar_ids) > 0:
            primary_pillar = body.pillar_ids[0]

        card = Card(
            id=uuid.UUID(card_id),
            name=body.name,
            slug=body.name.lower().replace(" ", "-").replace("/", "-")[:200],
            description=body.description,
            origin="user_created",
            is_exploratory=body.is_exploratory or (not primary_pillar),
            created_by=uuid.UUID(user["id"]),
            review_status="approved",
            signal_quality_score=0,
            quality_breakdown={},
            horizon=body.horizon or "H1",
            stage_id=body.stage or "1",
            pipeline_status=body.pipeline_status or "discovered",
            pipeline_status_changed_at=datetime.now(timezone.utc),
        )

        if primary_pillar:
            card.pillar_id = primary_pillar

        if body.source_preferences:
            card.source_preferences = body.source_preferences.dict(exclude_none=True)

        db.add(card)
        await db.flush()

        # Queue background AI analysis
        try:
            await queue_card_analysis(db, card_id, user["id"])
        except Exception:
            logger.warning("Failed to queue card analysis for %s", card_id)

        # Store seed URLs as sources if provided
        if body.seed_urls and len(body.seed_urls) > 0:
            for url in body.seed_urls:
                try:
                    source_id = uuid.uuid4()
                    source = Source(
                        id=source_id,
                        url=url,
                        title=url,  # Placeholder title; enrichment happens later
                        source_type="user_submitted",
                    )
                    db.add(source)
                    await db.flush()

                    # Link card to source via signal_sources junction table
                    signal_source = SignalSource(
                        card_id=uuid.UUID(card_id),
                        source_id=source_id,
                    )
                    db.add(signal_source)
                    await db.flush()
                except Exception as url_err:
                    logger.warning(
                        f"Card {card_id}: failed to add seed URL {url}: {url_err}"
                    )

        return {
            "card_id": card_id,
            "card_name": body.name,
            "status": "created",
            "message": "Card created successfully.",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create manual card: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("card creation", e),
        ) from e


@router.post("/ai/suggest-keywords")
@limiter.limit("10/minute")
async def suggest_keywords(
    request: Request, topic: str, user=Depends(get_current_user_hardcoded)
):
    """Suggest municipal-relevant keywords for a topic."""
    try:
        client = azure_openai_client
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=get_chat_deployment(),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a municipal government research assistant for the "
                        "City of Austin. Given a topic, suggest 5-10 search keywords "
                        "that would find relevant sources about this topic in the "
                        "context of city government operations, policy, and services. "
                        "Return ONLY a JSON array of strings."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Suggest municipal-relevant search keywords for: {topic}",
                },
            ],
            temperature=0.7,
            max_tokens=300,
        )

        try:
            keywords = json.loads(response.choices[0].message.content)
        except (json.JSONDecodeError, IndexError):
            keywords = [topic]

        return KeywordSuggestionResponse(topic=topic, suggestions=keywords)
    except Exception as e:
        logger.error(f"Failed to suggest keywords for '{topic}': {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("keyword suggestion", e),
        ) from e


@router.post("/ai/suggest-description", response_model=SuggestDescriptionResponse)
@limiter.limit("10/minute")
async def suggest_description(
    request: Request,
    body: SuggestDescriptionRequest,
    user=Depends(get_current_user_hardcoded),
):
    """Generate a workstream description from a name, pillars, and keywords.

    Uses GPT-4.1-mini for cost efficiency. Returns a 1-2 sentence professional
    description explaining what signals the workstream will track.
    """
    try:
        # Build user prompt with available context
        parts = [f"Workstream name: {body.name}"]
        if body.pillar_ids:
            names = [PILLAR_NAMES.get(p, p) for p in body.pillar_ids]
            parts.append(f"Strategic pillars: {', '.join(names)}")
        if body.keywords:
            parts.append(f"Keywords: {', '.join(body.keywords)}")

        user_prompt = "\n".join(parts)

        client = azure_openai_client
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=get_chat_mini_deployment(),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are helping a City of Austin strategic analyst create a "
                        "workstream description for their horizon scanning system. "
                        "Generate a clear, professional 1-2 sentence description that "
                        "explains what signals this workstream will track. Be specific "
                        "about the domain and purpose."
                    ),
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            temperature=0.7,
            max_tokens=150,
        )

        description = (
            response.choices[0].message.content or ""
        ).strip() or f"Tracks emerging signals related to {body.name}."

        return SuggestDescriptionResponse(description=description)
    except Exception as e:
        logger.error(f"Failed to suggest description for '{body.name}': {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("description suggestion", e),
        ) from e


# ============================================================================
# Grant Readiness Assessment
# ============================================================================

_READINESS_SYSTEM_PROMPT = """\
You are a grant readiness assessment specialist for municipal government.

Evaluate a department's readiness to pursue and manage grant funding based on \
their self-assessment responses. Score each factor on a 0-100 scale where:
- 0-25: Not ready (critical gaps)
- 26-50: Low readiness (significant improvements needed)
- 51-75: Moderate readiness (some gaps to address)
- 76-90: High readiness (minor improvements)
- 91-100: Very high readiness (application-ready)

Respond ONLY with valid JSON matching this schema (no markdown fences):
{
  "overall_score": <int 0-100>,
  "readiness_level": "<low|moderate|high|very_high>",
  "summary": "<2-3 sentence summary>",
  "scores": [
    {
      "factor": "<factor name>",
      "score": <int 0-100>,
      "assessment": "<1-2 sentence assessment>",
      "recommendations": ["<specific action>", ...]
    }
  ],
  "strengths": ["<strength>", ...],
  "gaps": ["<gap>", ...],
  "recommendations": ["<action>", ...],
  "suggested_grant_types": ["<grant type>", ...],
  "estimated_preparation_weeks": <int or null>
}
"""


def _build_readiness_prompt(body: ReadinessAssessmentRequest) -> str:
    """Build the user prompt for the readiness assessment."""
    dept_label = body.department_id or "Not specified"
    if body.department_id and body.department_id in DEPARTMENT_LIST:
        dept_info = DEPARTMENT_LIST[body.department_id]
        dept_label = f"{body.department_id} - {dept_info['name']}"

    # Resolve category names
    cat_names = []
    for code in body.grant_categories:
        if code in GRANT_CATEGORIES:
            cat_names.append(GRANT_CATEGORIES[code]["name"])
        else:
            cat_names.append(code)
    categories_str = ", ".join(cat_names) if cat_names else "Not specified"

    # Budget range
    if body.budget_range_min is not None and body.budget_range_max is not None:
        budget_str = f"${body.budget_range_min:,.0f} - ${body.budget_range_max:,.0f}"
    elif body.budget_range_min is not None:
        budget_str = f"${body.budget_range_min:,.0f}+"
    elif body.budget_range_max is not None:
        budget_str = f"Up to ${body.budget_range_max:,.0f}"
    else:
        budget_str = "Not specified"

    parts = [
        f"Department: {dept_label}",
        f"Program: {body.program_description}",
        f"Grant Categories of Interest: {categories_str}",
        f"Budget Range: {budget_str}",
        "",
        "Self-Assessment Responses:",
        f"- Staff Capacity: {body.staff_capacity or 'Not provided'}",
        f"- Past Grant History: {body.past_grants or 'Not provided'}",
        f"- Matching Fund Availability: {body.matching_funds or 'Not provided'}",
        f"- Financial Systems: {body.financial_systems or 'Not provided'}",
        f"- Reporting Capability: {body.reporting_capability or 'Not provided'}",
        f"- Partnerships: {body.partnerships or 'Not provided'}",
        "",
        "Evaluate each of these six factors:",
        "1. Staff Capacity (0-100): Does the department have dedicated grant staff?",
        "2. Grant History (0-100): Track record of successful applications?",
        "3. Financial Systems (0-100): Can they track grant funds separately? Single audits?",
        "4. Matching Capability (0-100): Can they provide matching funds?",
        "5. Reporting Infrastructure (0-100): Federal/state reporting compliance ready?",
        "6. Partnerships (0-100): Relevant community or agency partnerships?",
        "",
        "Provide per-factor scores, overall weighted score, strengths, gaps, "
        "recommended grant types for their readiness level, and estimated "
        "preparation weeks to be application-ready.",
    ]
    return "\n".join(parts)


def _fallback_readiness_response() -> ReadinessAssessmentResponse:
    """Return a generic low-readiness response when AI call fails."""
    return ReadinessAssessmentResponse(
        overall_score=25,
        readiness_level="low",
        summary=(
            "Unable to complete a detailed AI assessment at this time. "
            "Based on limited information, we recommend completing all "
            "questionnaire fields and trying again for a full evaluation."
        ),
        scores=[
            ReadinessScoreBreakdown(
                factor="Staff Capacity",
                score=25,
                assessment="Insufficient information to assess staff readiness.",
                recommendations=["Provide details about grant management staffing."],
            ),
            ReadinessScoreBreakdown(
                factor="Grant History",
                score=25,
                assessment="Insufficient information to assess grant track record.",
                recommendations=["Describe any past grant applications or awards."],
            ),
            ReadinessScoreBreakdown(
                factor="Financial Systems",
                score=25,
                assessment="Insufficient information to assess financial tracking.",
                recommendations=["Describe financial tracking and audit capabilities."],
            ),
            ReadinessScoreBreakdown(
                factor="Matching Capability",
                score=25,
                assessment="Insufficient information to assess matching fund availability.",
                recommendations=["Identify potential sources of matching funds."],
            ),
            ReadinessScoreBreakdown(
                factor="Reporting Infrastructure",
                score=25,
                assessment="Insufficient information to assess reporting readiness.",
                recommendations=["Describe federal/state reporting capabilities."],
            ),
            ReadinessScoreBreakdown(
                factor="Partnerships",
                score=25,
                assessment="Insufficient information to assess partnership landscape.",
                recommendations=["List relevant community or agency partnerships."],
            ),
        ],
        strengths=[],
        gaps=["Incomplete assessment data"],
        recommendations=[
            "Complete all self-assessment questionnaire fields",
            "Retry the assessment for a detailed AI-powered evaluation",
        ],
        suggested_grant_types=[],
        estimated_preparation_weeks=None,
    )


@router.post("/ai/readiness-assessment", response_model=ReadinessAssessmentResponse)
@limiter.limit("5/minute")
async def assess_grant_readiness(
    request: Request,
    body: ReadinessAssessmentRequest,
    user=Depends(get_current_user_hardcoded),
):
    """AI-powered grant readiness assessment for a department/program.

    Evaluates six readiness factors (staff capacity, grant history, financial
    systems, matching capability, reporting infrastructure, and partnerships)
    and returns scored breakdown with actionable recommendations.
    """
    try:
        user_prompt = _build_readiness_prompt(body)

        client = azure_openai_client
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=get_chat_mini_deployment(),
            messages=[
                {"role": "system", "content": _READINESS_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=1500,
        )

        raw = (response.choices[0].message.content or "").strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            lines = raw.split("\n")
            # Remove first and last lines (``` markers)
            lines = [ln for ln in lines if not ln.strip().startswith("```")]
            raw = "\n".join(lines)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("AI readiness response was not valid JSON, using fallback")
            return _fallback_readiness_response()

        # Parse scores
        parsed_scores = []
        for s in data.get("scores", []):
            parsed_scores.append(
                ReadinessScoreBreakdown(
                    factor=s.get("factor", "Unknown"),
                    score=max(0, min(100, int(s.get("score", 0)))),
                    assessment=s.get("assessment", ""),
                    recommendations=s.get("recommendations", []),
                )
            )

        # Clamp overall score
        overall = max(0, min(100, int(data.get("overall_score", 0))))

        # Determine readiness level (validate or derive from score)
        level = data.get("readiness_level", "")
        valid_levels = {"low", "moderate", "high", "very_high"}
        if level not in valid_levels:
            if overall >= 76:
                level = "very_high" if overall >= 91 else "high"
            elif overall >= 51:
                level = "moderate"
            else:
                level = "low"

        return ReadinessAssessmentResponse(
            overall_score=overall,
            readiness_level=level,
            summary=data.get("summary", "Assessment complete."),
            scores=parsed_scores,
            strengths=data.get("strengths", []),
            gaps=data.get("gaps", []),
            recommendations=data.get("recommendations", []),
            suggested_grant_types=data.get("suggested_grant_types", []),
            estimated_preparation_weeks=data.get("estimated_preparation_weeks"),
        )
    except json.JSONDecodeError:
        # Already handled above; this catches any edge case
        logger.warning("Readiness assessment JSON parse error, returning fallback")
        return _fallback_readiness_response()
    except Exception as e:
        logger.error(f"Readiness assessment failed: {str(e)}")
        # Return fallback instead of raising 500, per spec
        return _fallback_readiness_response()
