"""Proposals router for AI-assisted grant proposal generation."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from app.deps import supabase, get_current_user, _safe_error
from app.models.proposal import (
    Proposal,
    ProposalCreate,
    ProposalUpdate,
    GenerateSectionRequest,
    GenerateSectionResponse,
    ProposalListResponse,
)
from app.proposal_service import ProposalService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["proposals"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _verify_proposal_ownership(proposal: dict, user_id: str) -> None:
    """Raise 403 if the proposal does not belong to the user."""
    if proposal["user_id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this proposal",
        )


async def _get_proposal_or_404(proposal_id: str, user_id: str) -> dict:
    """Fetch a proposal by ID and verify ownership. Raises 404/403."""
    result = supabase.table("proposals").select("*").eq("id", proposal_id).execute()
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proposal not found",
        )
    proposal = result.data[0]
    _verify_proposal_ownership(proposal, user_id)
    return proposal


# ---------------------------------------------------------------------------
# CRUD Endpoints
# ---------------------------------------------------------------------------


@router.get("/me/proposals", response_model=ProposalListResponse)
async def list_proposals(
    status_filter: str | None = None,
    limit: int = 20,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
):
    """List the authenticated user's proposals.

    Args:
        status_filter: Optional status to filter by (e.g. 'draft', 'submitted').
        limit: Maximum number of proposals to return (default 20).
        offset: Number of proposals to skip (default 0).
        current_user: Authenticated user (injected).

    Returns:
        ProposalListResponse with proposals and total count.
    """
    query = (
        supabase.table("proposals")
        .select("*", count="exact")
        .eq("user_id", current_user["id"])
        .order("updated_at", desc=True)
    )

    if status_filter:
        query = query.eq("status", status_filter)

    query = query.range(offset, offset + limit - 1)
    result = query.execute()

    return ProposalListResponse(
        proposals=[Proposal(**row) for row in (result.data or [])],
        total=result.count or 0,
    )


@router.post(
    "/me/proposals",
    response_model=Proposal,
    status_code=status.HTTP_201_CREATED,
)
async def create_proposal(
    body: ProposalCreate,
    current_user: dict = Depends(get_current_user),
):
    """Create a new proposal draft.

    Verifies that the card and workstream exist and the workstream belongs to
    the authenticated user. Auto-generates a title from the card name when one
    is not provided.

    Args:
        body: ProposalCreate with card_id, workstream_id, and optional title.
        current_user: Authenticated user (injected).

    Returns:
        The created Proposal record.

    Raises:
        HTTPException 404: Card or workstream not found.
        HTTPException 403: Workstream does not belong to the user.
    """
    user_id = current_user["id"]

    # Verify card exists
    card_result = (
        supabase.table("cards").select("id, name").eq("id", body.card_id).execute()
    )
    if not card_result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found",
        )
    card = card_result.data[0]

    # Verify workstream exists and belongs to user
    ws_result = (
        supabase.table("workstreams")
        .select("id, user_id")
        .eq("id", body.workstream_id)
        .execute()
    )
    if not ws_result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workstream not found",
        )
    if ws_result.data[0]["user_id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this workstream",
        )

    # Auto-generate title from card name if not provided
    title = body.title or f"Proposal: {card.get('name', 'Untitled Grant')}"

    now = datetime.now(timezone.utc).isoformat()
    insert_data = {
        "card_id": body.card_id,
        "workstream_id": body.workstream_id,
        "user_id": user_id,
        "title": title,
        "version": 1,
        "status": "draft",
        "sections": {},
        "ai_generation_metadata": {},
        "created_at": now,
        "updated_at": now,
    }

    try:
        result = supabase.table("proposals").insert(insert_data).execute()
    except Exception as e:
        logger.error(f"Failed to create proposal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("proposal creation", e),
        ) from e

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create proposal record",
        )

    return Proposal(**result.data[0])


@router.get("/me/proposals/{proposal_id}", response_model=Proposal)
async def get_proposal(
    proposal_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get a specific proposal by ID.

    Args:
        proposal_id: UUID of the proposal.
        current_user: Authenticated user (injected).

    Returns:
        The Proposal record.

    Raises:
        HTTPException 404: Proposal not found.
        HTTPException 403: Not authorized.
    """
    proposal = await _get_proposal_or_404(proposal_id, current_user["id"])
    return Proposal(**proposal)


@router.patch("/me/proposals/{proposal_id}", response_model=Proposal)
async def update_proposal(
    proposal_id: str,
    body: ProposalUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Update a proposal.

    Only fields present in the request body will be updated.

    Args:
        proposal_id: UUID of the proposal.
        body: ProposalUpdate with optional fields to change.
        current_user: Authenticated user (injected).

    Returns:
        The updated Proposal record.

    Raises:
        HTTPException 404: Proposal not found.
        HTTPException 403: Not authorized.
    """
    await _get_proposal_or_404(proposal_id, current_user["id"])

    update_data: dict = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if body.title is not None:
        update_data["title"] = body.title
    if body.status is not None:
        update_data["status"] = body.status
    if body.sections is not None:
        update_data["sections"] = body.sections
    if body.review_notes is not None:
        update_data["review_notes"] = body.review_notes

    try:
        result = (
            supabase.table("proposals")
            .update(update_data)
            .eq("id", proposal_id)
            .execute()
        )
    except Exception as e:
        logger.error(f"Failed to update proposal {proposal_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("proposal update", e),
        ) from e

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update proposal",
        )

    return Proposal(**result.data[0])


@router.delete(
    "/me/proposals/{proposal_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_proposal(
    proposal_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a proposal.

    Args:
        proposal_id: UUID of the proposal.
        current_user: Authenticated user (injected).

    Raises:
        HTTPException 404: Proposal not found.
        HTTPException 403: Not authorized.
    """
    await _get_proposal_or_404(proposal_id, current_user["id"])

    try:
        supabase.table("proposals").delete().eq("id", proposal_id).execute()
    except Exception as e:
        logger.error(f"Failed to delete proposal {proposal_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("proposal deletion", e),
        ) from e


# ---------------------------------------------------------------------------
# AI Generation Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/me/proposals/{proposal_id}/generate-section",
    response_model=GenerateSectionResponse,
)
async def generate_section(
    proposal_id: str,
    body: GenerateSectionRequest,
    current_user: dict = Depends(get_current_user),
):
    """AI-generate a single proposal section.

    Fetches the related card and workstream for context, calls the AI service,
    and persists the generated draft into the proposal's sections JSONB field.

    Args:
        proposal_id: UUID of the proposal.
        body: GenerateSectionRequest with section_name and optional context.
        current_user: Authenticated user (injected).

    Returns:
        GenerateSectionResponse with the AI draft and model info.

    Raises:
        HTTPException 404: Proposal, card, or workstream not found.
        HTTPException 403: Not authorized.
        HTTPException 500: AI generation failure.
    """
    proposal = await _get_proposal_or_404(proposal_id, current_user["id"])

    # Fetch card context
    card_result = (
        supabase.table("cards").select("*").eq("id", proposal["card_id"]).execute()
    )
    if not card_result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated card not found",
        )
    card = card_result.data[0]

    # Fetch workstream context
    ws_result = (
        supabase.table("workstreams")
        .select("*")
        .eq("id", proposal["workstream_id"])
        .execute()
    )
    if not ws_result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated workstream not found",
        )
    workstream = ws_result.data[0]

    # Generate the section
    service = ProposalService()
    try:
        ai_draft, model_used = await service.generate_section(
            section_name=body.section_name,
            card=card,
            workstream=workstream,
            existing_sections=proposal.get("sections", {}),
            additional_context=body.additional_context,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"AI generation failed for proposal {proposal_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("AI section generation", e),
        ) from e

    # Persist the generated section into the proposal
    sections = proposal.get("sections", {}) or {}
    sections[body.section_name] = {
        "content": ai_draft,
        "ai_draft": ai_draft,
        "last_edited": datetime.now(timezone.utc).isoformat(),
    }

    try:
        supabase.table("proposals").update(
            {
                "sections": sections,
                "ai_model": model_used,
                "ai_generation_metadata": {
                    **proposal.get("ai_generation_metadata", {}),
                    body.section_name: {
                        "model": model_used,
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                    },
                },
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("id", proposal_id).execute()
    except Exception as e:
        logger.error(f"Failed to persist generated section for {proposal_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("saving generated section", e),
        ) from e

    return GenerateSectionResponse(
        section_name=body.section_name,
        ai_draft=ai_draft,
        model_used=model_used,
    )


@router.post(
    "/me/proposals/{proposal_id}/generate-all",
    response_model=Proposal,
)
async def generate_all_sections(
    proposal_id: str,
    current_user: dict = Depends(get_current_user),
):
    """AI-generate all proposal sections at once.

    Fetches the related card and workstream for context, generates every
    standard section sequentially (so later sections can reference earlier
    ones), and persists the full result.

    Args:
        proposal_id: UUID of the proposal.
        current_user: Authenticated user (injected).

    Returns:
        The updated Proposal with all generated sections.

    Raises:
        HTTPException 404: Proposal, card, or workstream not found.
        HTTPException 403: Not authorized.
        HTTPException 500: AI generation failure.
    """
    proposal = await _get_proposal_or_404(proposal_id, current_user["id"])

    # Fetch card context
    card_result = (
        supabase.table("cards").select("*").eq("id", proposal["card_id"]).execute()
    )
    if not card_result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated card not found",
        )
    card = card_result.data[0]

    # Fetch workstream context
    ws_result = (
        supabase.table("workstreams")
        .select("*")
        .eq("id", proposal["workstream_id"])
        .execute()
    )
    if not ws_result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated workstream not found",
        )
    workstream = ws_result.data[0]

    # Generate all sections
    service = ProposalService()
    try:
        generation_result = await service.generate_full_proposal(
            card=card,
            workstream=workstream,
        )
    except Exception as e:
        logger.error(f"Full proposal generation failed for {proposal_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("full proposal generation", e),
        ) from e

    # Build per-section generation metadata
    now = datetime.now(timezone.utc).isoformat()
    model_used = generation_result["model_used"]
    gen_metadata = {
        section_name: {"model": model_used, "generated_at": now}
        for section_name in generation_result["sections"]
    }

    # Persist
    try:
        result = (
            supabase.table("proposals")
            .update(
                {
                    "sections": generation_result["sections"],
                    "ai_model": model_used,
                    "ai_generation_metadata": gen_metadata,
                    "updated_at": now,
                }
            )
            .eq("id", proposal_id)
            .execute()
        )
    except Exception as e:
        logger.error(f"Failed to persist generated proposal {proposal_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("saving generated proposal", e),
        ) from e

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update proposal with generated content",
        )

    return Proposal(**result.data[0])
