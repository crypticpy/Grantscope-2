"""AI helper and card creation router."""

import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.deps import supabase, get_current_user, _safe_error, limiter
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
from app.models.ai_helpers import SuggestDescriptionRequest, SuggestDescriptionResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["ai_helpers"])


@router.post("/cards/create-from-topic")
@limiter.limit("10/minute")
async def create_card_from_topic(
    request: Request, body: CreateCardFromTopicRequest, user=Depends(get_current_user)
):
    """Quick card creation from a topic phrase. Creates card and optionally starts background scan."""
    try:
        card_id = str(uuid.uuid4())
        card_data = {
            "id": card_id,
            "name": body.topic[:200],
            "description": f"User-created signal: {body.topic}",
            "origin": "user_created",
            "is_exploratory": not body.pillar_hints,
            "created_by": user["id"],
            "review_status": "approved",
            "signal_quality_score": 0,
            "quality_breakdown": {},
        }

        if body.pillar_hints and len(body.pillar_hints) > 0:
            card_data["pillar_id"] = body.pillar_hints[0]

        if body.source_preferences:
            card_data["source_preferences"] = body.source_preferences.dict(
                exclude_none=True
            )

        result = supabase.table("cards").insert(card_data).execute()

        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create card",
            )

        # If workstream specified, add to workstream
        if body.workstream_id:
            try:
                supabase.table("workstream_cards").insert(
                    {
                        "workstream_id": body.workstream_id,
                        "card_id": card_id,
                        "column_name": "inbox",
                    }
                ).execute()
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
        )


@router.post("/cards/create-manual")
@limiter.limit("10/minute")
async def create_manual_card(
    request: Request, body: ManualCardCreateRequest, user=Depends(get_current_user)
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

        card_data = {
            "id": card_id,
            "name": body.name,
            "description": body.description,
            "origin": "user_created",
            "is_exploratory": body.is_exploratory or (not primary_pillar),
            "created_by": user["id"],
            "review_status": "approved",
            "signal_quality_score": 0,
            "quality_breakdown": {},
            "horizon": body.horizon or "H1",
            "stage_id": body.stage or "1",
        }

        if primary_pillar:
            card_data["pillar_id"] = primary_pillar

        if body.source_preferences:
            card_data["source_preferences"] = body.source_preferences.dict(
                exclude_none=True
            )

        result = supabase.table("cards").insert(card_data).execute()

        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create card",
            )

        # Store seed URLs as sources if provided
        if body.seed_urls and len(body.seed_urls) > 0:
            for url in body.seed_urls:
                try:
                    source_data = {
                        "id": str(uuid.uuid4()),
                        "url": url,
                        "title": url,  # Placeholder title; enrichment happens later
                        "source_type": "user_submitted",
                    }
                    src_result = supabase.table("sources").insert(source_data).execute()
                    if src_result.data:
                        supabase.table("card_sources").insert(
                            {
                                "card_id": card_id,
                                "source_id": src_result.data[0]["id"],
                            }
                        ).execute()
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
        )


@router.post("/ai/suggest-keywords")
@limiter.limit("10/minute")
async def suggest_keywords(
    request: Request, topic: str, user=Depends(get_current_user)
):
    """Suggest municipal-relevant keywords for a topic."""
    try:
        client = azure_openai_client
        response = client.chat.completions.create(
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
        )


@router.post("/ai/suggest-description", response_model=SuggestDescriptionResponse)
@limiter.limit("10/minute")
async def suggest_description(
    request: Request,
    body: SuggestDescriptionRequest,
    user=Depends(get_current_user),
):
    """Generate a workstream description from a name, pillars, and keywords.

    Uses GPT-4.1-mini for cost efficiency. Returns a 1-2 sentence professional
    description explaining what signals the workstream will track.
    """
    try:
        # Build user prompt with available context
        parts = [f"Workstream name: {body.name}"]
        if body.pillar_ids:
            pillar_labels = {
                "CH": "Community Health",
                "MC": "Mobility & Connectivity",
                "HS": "Housing & Shelter",
                "EC": "Economic Opportunity",
                "ES": "Environmental Sustainability",
                "CE": "Cultural & Educational Vitality",
                "EW": "Environmental & Water",
                "HG": "Housing & Growth",
                "HH": "Health & Human Services",
                "PS": "Public Safety",
            }
            names = [pillar_labels.get(p, p) for p in body.pillar_ids]
            parts.append(f"Strategic pillars: {', '.join(names)}")
        if body.keywords:
            parts.append(f"Keywords: {', '.join(body.keywords)}")

        user_prompt = "\n".join(parts)

        client = azure_openai_client
        response = client.chat.completions.create(
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

        description = (response.choices[0].message.content or "").strip()
        if not description:
            description = f"Tracks emerging signals related to {body.name}."

        return SuggestDescriptionResponse(description=description)
    except Exception as e:
        logger.error(f"Failed to suggest description for '{body.name}': {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("description suggestion", e),
        )
