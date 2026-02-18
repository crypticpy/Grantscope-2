"""Proposals router for AI-assisted grant proposal generation."""

import logging
import uuid as _uuid
from datetime import datetime, date, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, get_current_user_hardcoded, _safe_error
from app.models.db.card import Card
from app.models.db.proposal import Proposal as ProposalDB
from app.models.db.workstream import Workstream as WorkstreamDB
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


def _row_to_dict(obj, skip_cols=None) -> dict:
    """Convert a SQLAlchemy ORM row into a plain dict for serialisation."""
    skip = skip_cols or set()
    result = {}
    for col in obj.__table__.columns:
        if col.name in skip:
            continue
        value = getattr(obj, col.name, None)
        if isinstance(value, _uuid.UUID):
            result[col.name] = str(value)
        elif isinstance(value, (datetime, date)):
            result[col.name] = value.isoformat()
        elif isinstance(value, Decimal):
            result[col.name] = float(value)
        else:
            result[col.name] = value
    return result


def _verify_proposal_ownership(proposal: dict, user_id: str) -> None:
    """Raise 403 if the proposal does not belong to the user."""
    if proposal["user_id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this proposal",
        )


async def _get_proposal_or_404(
    proposal_id: str, user_id: str, db: AsyncSession
) -> dict:
    """Fetch a proposal by ID and verify ownership. Raises 404/403."""
    try:
        result = await db.execute(
            select(ProposalDB).where(ProposalDB.id == proposal_id)
        )
        proposal_obj = result.scalar_one_or_none()
    except Exception as e:
        logger.error("Failed to fetch proposal %s: %s", proposal_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("fetching proposal", e),
        ) from e

    if proposal_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proposal not found",
        )

    proposal = _row_to_dict(proposal_obj)
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
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
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
    # Build the count query
    count_query = (
        select(func.count())
        .select_from(ProposalDB)
        .where(ProposalDB.user_id == current_user["id"])
    )
    if status_filter:
        count_query = count_query.where(ProposalDB.status == status_filter)

    # Build the data query
    data_query = (
        select(ProposalDB)
        .where(ProposalDB.user_id == current_user["id"])
        .order_by(ProposalDB.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if status_filter:
        data_query = data_query.where(ProposalDB.status == status_filter)

    try:
        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0

        data_result = await db.execute(data_query)
        rows = list(data_result.scalars().all())
    except Exception as e:
        logger.error("Failed to list proposals: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("listing proposals", e),
        ) from e

    return ProposalListResponse(
        proposals=[Proposal(**_row_to_dict(row)) for row in rows],
        total=total,
    )


@router.post(
    "/me/proposals",
    response_model=Proposal,
    status_code=status.HTTP_201_CREATED,
)
async def create_proposal(
    body: ProposalCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
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
    try:
        card_result = await db.execute(
            select(Card.id, Card.name).where(Card.id == body.card_id)
        )
        card_row = card_result.one_or_none()
    except Exception as e:
        logger.error("Failed to verify card %s: %s", body.card_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("verifying card", e),
        ) from e

    if card_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found",
        )

    # Verify workstream exists and belongs to user
    try:
        ws_result = await db.execute(
            select(WorkstreamDB.id, WorkstreamDB.user_id).where(
                WorkstreamDB.id == body.workstream_id
            )
        )
        ws_row = ws_result.one_or_none()
    except Exception as e:
        logger.error("Failed to verify workstream %s: %s", body.workstream_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("verifying workstream", e),
        ) from e

    if ws_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workstream not found",
        )
    if str(ws_row.user_id) != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this workstream",
        )

    # Auto-generate title from card name if not provided
    title = body.title or f"Proposal: {card_row.name or 'Untitled Grant'}"

    now = datetime.now(timezone.utc)
    proposal_obj = ProposalDB(
        card_id=_uuid.UUID(body.card_id),
        workstream_id=_uuid.UUID(body.workstream_id),
        user_id=_uuid.UUID(user_id),
        title=title,
        version=1,
        status="draft",
        sections={},
        ai_generation_metadata={},
        created_at=now,
        updated_at=now,
    )

    try:
        db.add(proposal_obj)
        await db.flush()
        await db.refresh(proposal_obj)
    except Exception as e:
        logger.error("Failed to create proposal: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("proposal creation", e),
        ) from e

    return Proposal(**_row_to_dict(proposal_obj))


@router.get("/me/proposals/{proposal_id}", response_model=Proposal)
async def get_proposal(
    proposal_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
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
    proposal = await _get_proposal_or_404(proposal_id, current_user["id"], db)
    return Proposal(**proposal)


@router.patch("/me/proposals/{proposal_id}", response_model=Proposal)
async def update_proposal(
    proposal_id: str,
    body: ProposalUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
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
    await _get_proposal_or_404(proposal_id, current_user["id"], db)

    # Fetch ORM object for mutation
    try:
        result = await db.execute(
            select(ProposalDB).where(ProposalDB.id == proposal_id)
        )
        proposal_obj = result.scalar_one()
    except Exception as e:
        logger.error("Failed to fetch proposal %s for update: %s", proposal_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("proposal update", e),
        ) from e

    proposal_obj.updated_at = datetime.now(timezone.utc)
    if body.title is not None:
        proposal_obj.title = body.title
    if body.status is not None:
        proposal_obj.status = body.status
    if body.sections is not None:
        proposal_obj.sections = body.sections
    if body.review_notes is not None:
        proposal_obj.review_notes = body.review_notes

    try:
        await db.flush()
        await db.refresh(proposal_obj)
    except Exception as e:
        logger.error("Failed to update proposal %s: %s", proposal_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("proposal update", e),
        ) from e

    return Proposal(**_row_to_dict(proposal_obj))


@router.delete(
    "/me/proposals/{proposal_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_proposal(
    proposal_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Delete a proposal.

    Args:
        proposal_id: UUID of the proposal.
        current_user: Authenticated user (injected).

    Raises:
        HTTPException 404: Proposal not found.
        HTTPException 403: Not authorized.
    """
    await _get_proposal_or_404(proposal_id, current_user["id"], db)

    # Fetch ORM object for deletion
    try:
        result = await db.execute(
            select(ProposalDB).where(ProposalDB.id == proposal_id)
        )
        proposal_obj = result.scalar_one()
        await db.delete(proposal_obj)
        await db.flush()
    except Exception as e:
        logger.error("Failed to delete proposal %s: %s", proposal_id, e)
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
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
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
    proposal = await _get_proposal_or_404(proposal_id, current_user["id"], db)

    # Fetch card context
    try:
        card_result = await db.execute(
            select(Card).where(Card.id == proposal["card_id"])
        )
        card_obj = card_result.scalar_one_or_none()
    except Exception as e:
        logger.error("Failed to fetch card %s: %s", proposal["card_id"], e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("fetching card", e),
        ) from e

    if card_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated card not found",
        )
    card = _row_to_dict(card_obj)

    # Fetch workstream context
    try:
        ws_result = await db.execute(
            select(WorkstreamDB).where(WorkstreamDB.id == proposal["workstream_id"])
        )
        ws_obj = ws_result.scalar_one_or_none()
    except Exception as e:
        logger.error("Failed to fetch workstream %s: %s", proposal["workstream_id"], e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("fetching workstream", e),
        ) from e

    if ws_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated workstream not found",
        )
    workstream = _row_to_dict(ws_obj)

    # Generate the section
    # TODO: migrate ProposalService to SQLAlchemy
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
        logger.error("AI generation failed for proposal %s: %s", proposal_id, e)
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
        result = await db.execute(
            select(ProposalDB).where(ProposalDB.id == proposal_id)
        )
        proposal_obj = result.scalar_one()
        proposal_obj.sections = sections
        proposal_obj.ai_model = model_used
        proposal_obj.ai_generation_metadata = {
            **(proposal.get("ai_generation_metadata") or {}),
            body.section_name: {
                "model": model_used,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        proposal_obj.updated_at = datetime.now(timezone.utc)
        await db.flush()
    except Exception as e:
        logger.error("Failed to persist generated section for %s: %s", proposal_id, e)
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
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
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
    proposal = await _get_proposal_or_404(proposal_id, current_user["id"], db)

    # Fetch card context
    try:
        card_result = await db.execute(
            select(Card).where(Card.id == proposal["card_id"])
        )
        card_obj = card_result.scalar_one_or_none()
    except Exception as e:
        logger.error("Failed to fetch card %s: %s", proposal["card_id"], e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("fetching card", e),
        ) from e

    if card_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated card not found",
        )
    card = _row_to_dict(card_obj)

    # Fetch workstream context
    try:
        ws_result = await db.execute(
            select(WorkstreamDB).where(WorkstreamDB.id == proposal["workstream_id"])
        )
        ws_obj = ws_result.scalar_one_or_none()
    except Exception as e:
        logger.error("Failed to fetch workstream %s: %s", proposal["workstream_id"], e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("fetching workstream", e),
        ) from e

    if ws_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated workstream not found",
        )
    workstream = _row_to_dict(ws_obj)

    # Generate all sections
    # TODO: migrate ProposalService to SQLAlchemy
    service = ProposalService()
    try:
        generation_result = await service.generate_full_proposal(
            card=card,
            workstream=workstream,
        )
    except Exception as e:
        logger.error("Full proposal generation failed for %s: %s", proposal_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("full proposal generation", e),
        ) from e

    # Build per-section generation metadata
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    model_used = generation_result["model_used"]
    gen_metadata = {
        section_name: {"model": model_used, "generated_at": now_iso}
        for section_name in generation_result["sections"]
    }

    # Persist
    try:
        result = await db.execute(
            select(ProposalDB).where(ProposalDB.id == proposal_id)
        )
        proposal_obj = result.scalar_one()
        proposal_obj.sections = generation_result["sections"]
        proposal_obj.ai_model = model_used
        proposal_obj.ai_generation_metadata = gen_metadata
        proposal_obj.updated_at = now
        await db.flush()
        await db.refresh(proposal_obj)
    except Exception as e:
        logger.error("Failed to persist generated proposal %s: %s", proposal_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("saving generated proposal", e),
        ) from e

    return Proposal(**_row_to_dict(proposal_obj))
