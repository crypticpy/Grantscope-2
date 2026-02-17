"""Wizard router for the Guided Grant Application Wizard.

Provides endpoints for creating, managing, and progressing through wizard
sessions that walk users through grant applications via AI-powered interviews.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

import fitz  # PyMuPDF — for PDF text extraction from uploaded files
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, JSONResponse

from app.deps import supabase, get_current_user, _safe_error
from app.export_service import ExportService
from app.models.wizard import (
    GrantContext,
    PlanData,
    ProcessGrantResponse,
    WizardSession,
    WizardSessionCreate,
    WizardSessionUpdate,
)
from app.proposal_service import ProposalService
from app.wizard_service import WizardService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["wizard"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _verify_session_ownership(session_id: str, user_id: str) -> dict:
    """Fetch a wizard session by ID and verify ownership.

    Args:
        session_id: UUID of the wizard session.
        user_id: UUID of the authenticated user.

    Returns:
        The session row as a dict.

    Raises:
        HTTPException 404: Session not found.
        HTTPException 403: Not authorized.
    """
    result = (
        supabase.table("wizard_sessions").select("*").eq("id", session_id).execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wizard session not found",
        )

    session = result.data[0]

    if session["user_id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this wizard session",
        )

    return session


def _extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """Extract text content from PDF bytes using PyMuPDF.

    Args:
        pdf_bytes: Raw PDF file bytes.

    Returns:
        Extracted text content.

    Raises:
        ValueError: If no text could be extracted.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        text_parts: list[str] = []
        max_pages = min(len(doc), 50)
        for page_idx in range(max_pages):
            page = doc[page_idx]
            page_text = page.get_text("text")
            if page_text and page_text.strip():
                text_parts.append(page_text.strip())

        if not text_parts:
            raise ValueError("No text could be extracted from the uploaded PDF")

        return "\n\n".join(text_parts)
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Session CRUD Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/me/wizard/sessions",
    response_model=WizardSession,
    status_code=status.HTTP_201_CREATED,
)
async def create_wizard_session(
    body: WizardSessionCreate,
    current_user: dict = Depends(get_current_user),
):
    """Create a new wizard session.

    Creates a wizard_sessions row and a linked chat_conversations row
    with scope='wizard'.

    Args:
        body: WizardSessionCreate with entry_path.
        current_user: Authenticated user (injected).

    Returns:
        The created WizardSession.
    """
    user_id = current_user["id"]
    now = datetime.now(timezone.utc).isoformat()

    # 1. Create the wizard session first (without conversation_id)
    session_data = {
        "user_id": user_id,
        "entry_path": body.entry_path,
        "current_step": 0,
        "status": "in_progress",
        "grant_context": {},
        "interview_data": {},
        "plan_data": {},
        "created_at": now,
        "updated_at": now,
    }

    try:
        session_result = (
            supabase.table("wizard_sessions").insert(session_data).execute()
        )
    except Exception as e:
        logger.error("Failed to create wizard session: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("wizard session creation", e),
        ) from e

    if not session_result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create wizard session record",
        )

    session = session_result.data[0]
    session_id = session["id"]

    # 2. Create a linked chat conversation with scope='wizard'
    conversation_data = {
        "user_id": user_id,
        "scope": "wizard",
        "scope_id": session_id,
        "title": f"Wizard Session - {body.entry_path}",
        "created_at": now,
        "updated_at": now,
    }

    try:
        conv_result = (
            supabase.table("chat_conversations").insert(conversation_data).execute()
        )
    except Exception as e:
        logger.error("Failed to create chat conversation for wizard: %s", e)
        # Clean up the orphaned session
        try:
            supabase.table("wizard_sessions").delete().eq("id", session_id).execute()
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("wizard conversation creation", e),
        ) from e

    if not conv_result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create wizard conversation record",
        )

    conversation_id = conv_result.data[0]["id"]

    # 3. Link conversation_id back to the wizard session
    try:
        update_result = (
            supabase.table("wizard_sessions")
            .update({"conversation_id": conversation_id})
            .eq("id", session_id)
            .execute()
        )
    except Exception as e:
        logger.error("Failed to link conversation to wizard session: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("wizard session update", e),
        ) from e

    if not update_result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to link conversation to wizard session",
        )

    return WizardSession(**update_result.data[0])


@router.get("/me/wizard/sessions", response_model=list[WizardSession])
async def list_wizard_sessions(
    status_filter: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """List the authenticated user's wizard sessions.

    Args:
        status_filter: Optional status to filter by (e.g. 'in_progress', 'completed').
        current_user: Authenticated user (injected).

    Returns:
        List of WizardSession records ordered by updated_at desc.
    """
    query = (
        supabase.table("wizard_sessions")
        .select("*")
        .eq("user_id", current_user["id"])
        .order("updated_at", desc=True)
        .limit(20)
    )

    if status_filter:
        query = query.eq("status", status_filter)

    try:
        result = query.execute()
    except Exception as e:
        logger.error("Failed to list wizard sessions: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("listing wizard sessions", e),
        ) from e

    return [WizardSession(**row) for row in (result.data or [])]


@router.get("/me/wizard/sessions/{session_id}", response_model=WizardSession)
async def get_wizard_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get a specific wizard session by ID.

    Args:
        session_id: UUID of the wizard session.
        current_user: Authenticated user (injected).

    Returns:
        The WizardSession record.

    Raises:
        HTTPException 404: Session not found.
        HTTPException 403: Not authorized.
    """
    session = await _verify_session_ownership(session_id, current_user["id"])
    return WizardSession(**session)


@router.patch("/me/wizard/sessions/{session_id}", response_model=WizardSession)
async def update_wizard_session(
    session_id: str,
    body: WizardSessionUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Update a wizard session.

    Only fields present in the request body will be updated.

    Args:
        session_id: UUID of the wizard session.
        body: WizardSessionUpdate with optional fields.
        current_user: Authenticated user (injected).

    Returns:
        The updated WizardSession record.

    Raises:
        HTTPException 404: Session not found.
        HTTPException 403: Not authorized.
    """
    await _verify_session_ownership(session_id, current_user["id"])

    update_data: dict = {"updated_at": datetime.now(timezone.utc).isoformat()}

    if body.current_step is not None:
        update_data["current_step"] = body.current_step
    if body.status is not None:
        update_data["status"] = body.status
    if body.grant_context is not None:
        update_data["grant_context"] = body.grant_context.model_dump(mode="json")
    if body.interview_data is not None:
        update_data["interview_data"] = body.interview_data
    if body.plan_data is not None:
        update_data["plan_data"] = body.plan_data.model_dump(mode="json")

    try:
        result = (
            supabase.table("wizard_sessions")
            .update(update_data)
            .eq("id", session_id)
            .execute()
        )
    except Exception as e:
        logger.error("Failed to update wizard session %s: %s", session_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("wizard session update", e),
        ) from e

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update wizard session",
        )

    return WizardSession(**result.data[0])


# ---------------------------------------------------------------------------
# Grant Processing
# ---------------------------------------------------------------------------


@router.post(
    "/me/wizard/sessions/{session_id}/process-grant",
    response_model=ProcessGrantResponse,
)
async def process_grant(
    session_id: str,
    url: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    current_user: dict = Depends(get_current_user),
):
    """Process a grant document (URL or file upload) and extract structured context.

    Accepts either a URL to a grant opportunity page/PDF or an uploaded file.
    Extracts structured grant context via AI, saves it to the session, and
    auto-creates a card from the extracted data.

    Args:
        session_id: UUID of the wizard session.
        url: Optional URL to a grant opportunity.
        file: Optional uploaded file (PDF, DOCX, TXT).
        current_user: Authenticated user (injected).

    Returns:
        ProcessGrantResponse with grant_context and card_id.

    Raises:
        HTTPException 400: Neither url nor file provided, or extraction fails.
        HTTPException 404: Session not found.
        HTTPException 403: Not authorized.
    """
    user_id = current_user["id"]
    await _verify_session_ownership(session_id, user_id)

    if not url and not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide either a URL or a file upload",
        )

    service = WizardService()
    grant_context: GrantContext
    source_url: Optional[str] = None

    # -- URL path --
    if url:
        source_url = url
        try:
            grant_context = await service.extract_grant_from_url(url)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e
        except Exception as e:
            logger.error("Grant extraction from URL failed: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=_safe_error("grant extraction from URL", e),
            ) from e

    # -- File upload path --
    else:
        assert file is not None

        # Validate file type before reading content
        upload_filename = (file.filename or "").lower()
        if not upload_filename.endswith((".pdf", ".txt")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF and TXT files are accepted",
            )

        try:
            file_bytes = await file.read()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to read uploaded file: {e}",
            ) from e

        if not file_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty",
            )

        # Enforce server-side file size limit (10 MB)
        MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB
        if len(file_bytes) > MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=413,
                detail="File exceeds 10MB limit",
            )

        # Determine file type and extract text
        filename = (file.filename or "").lower()
        content_type = (file.content_type or "").lower()

        if filename.endswith(".pdf") or "pdf" in content_type:
            try:
                text = _extract_text_from_pdf_bytes(file_bytes)
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e),
                ) from e
            except Exception as e:
                logger.error("PDF text extraction failed: %s", e)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to extract text from PDF file",
                ) from e
        elif filename.endswith(".txt") or "text/plain" in content_type:
            try:
                text = file_bytes.decode("utf-8")
            except UnicodeDecodeError:
                text = file_bytes.decode("latin-1")
        else:
            # Attempt to decode as text for other file types
            try:
                text = file_bytes.decode("utf-8")
            except UnicodeDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=("Unsupported file type. Please upload a PDF or text file."),
                )

        if not text or not text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No text could be extracted from the uploaded file",
            )

        try:
            grant_context = await service.extract_grant_from_text(text)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e
        except Exception as e:
            logger.error("Grant extraction from file failed: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=_safe_error("grant extraction from file", e),
            ) from e

    # -- Save grant_context to the session --
    grant_context_dict = grant_context.model_dump(mode="json")

    # -- Auto-create card --
    card_id: Optional[str] = None
    try:
        card_id = service.create_card_from_grant(grant_context, user_id, source_url)
    except Exception as e:
        logger.warning("Failed to auto-create card from grant context: %s", e)
        # Non-fatal: we still have the grant context even if card creation fails

    # -- Update session with grant_context and card_id --
    update_data: dict = {
        "grant_context": grant_context_dict,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if card_id:
        update_data["card_id"] = card_id

    try:
        supabase.table("wizard_sessions").update(update_data).eq(
            "id", session_id
        ).execute()
    except Exception as e:
        logger.error("Failed to save grant context to session %s: %s", session_id, e)
        # Non-fatal: return the result even if session save fails

    return ProcessGrantResponse(
        grant_context=grant_context,
        card_id=card_id,
    )


# ---------------------------------------------------------------------------
# Plan Synthesis
# ---------------------------------------------------------------------------


@router.post("/me/wizard/sessions/{session_id}/synthesize-plan")
async def synthesize_plan(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Synthesize a structured project plan from the wizard interview.

    Loads conversation messages from the session's linked chat_conversations
    record, combines with grant context, and generates a plan via AI.

    Args:
        session_id: UUID of the wizard session.
        current_user: Authenticated user (injected).

    Returns:
        The synthesized PlanData.

    Raises:
        HTTPException 404: Session not found.
        HTTPException 403: Not authorized.
        HTTPException 400: Missing grant context or conversation.
    """
    user_id = current_user["id"]
    session = await _verify_session_ownership(session_id, user_id)

    # Validate prerequisites
    grant_context = session.get("grant_context")
    if not grant_context:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No grant context found. Process a grant document first.",
        )

    conversation_id = session.get("conversation_id")
    if not conversation_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No conversation linked to this session.",
        )

    # Load conversation messages
    try:
        messages_result = (
            supabase.table("chat_messages")
            .select("role, content")
            .eq("conversation_id", conversation_id)
            .order("created_at", desc=False)
            .execute()
        )
    except Exception as e:
        logger.error("Failed to load conversation messages: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("loading conversation messages", e),
        ) from e

    messages = messages_result.data or []

    if not messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No interview messages found. Complete the interview first.",
        )

    # Synthesize the plan
    service = WizardService()
    try:
        plan_data = await service.synthesize_plan(grant_context, messages)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error("Plan synthesis failed for session %s: %s", session_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("plan synthesis", e),
        ) from e

    # Save plan_data to the session
    plan_data_dict = plan_data.model_dump(mode="json")
    try:
        supabase.table("wizard_sessions").update(
            {
                "plan_data": plan_data_dict,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("id", session_id).execute()
    except Exception as e:
        logger.warning("Failed to save plan data to session %s: %s", session_id, e)

    return plan_data_dict


# ---------------------------------------------------------------------------
# Proposal Generation
# ---------------------------------------------------------------------------


@router.post("/me/wizard/sessions/{session_id}/generate-proposal")
async def generate_proposal(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Generate a full grant proposal from the wizard session data.

    Uses the existing ProposalService to generate all proposal sections,
    leveraging the card, interview data, and plan as additional context.

    Args:
        session_id: UUID of the wizard session.
        current_user: Authenticated user (injected).

    Returns:
        Dict with proposal_id and the created proposal data.

    Raises:
        HTTPException 404: Session not found or card not found.
        HTTPException 403: Not authorized.
        HTTPException 400: Missing required data (card, workstream).
    """
    user_id = current_user["id"]
    session = await _verify_session_ownership(session_id, user_id)

    card_id = session.get("card_id")
    if not card_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No card linked to this session. Process a grant document first.",
        )

    # Fetch the card
    card_result = supabase.table("cards").select("*").eq("id", card_id).execute()
    if not card_result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated card not found",
        )
    card = card_result.data[0]

    # Find or create a workstream for this wizard session
    # First, check if user has any workstreams; use the first one or create a default
    ws_result = (
        supabase.table("workstreams")
        .select("*")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )

    if ws_result.data:
        workstream = ws_result.data[0]
    else:
        # Create a default workstream for the user
        now = datetime.now(timezone.utc).isoformat()
        try:
            ws_create_result = (
                supabase.table("workstreams")
                .insert(
                    {
                        "user_id": user_id,
                        "name": "Grant Applications",
                        "description": "Default workstream for grant proposals generated via the wizard.",
                        "created_at": now,
                        "updated_at": now,
                    }
                )
                .execute()
            )
        except Exception as e:
            logger.error("Failed to create default workstream: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=_safe_error("default workstream creation", e),
            ) from e

        if not ws_create_result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create default workstream",
            )
        workstream = ws_create_result.data[0]

    # Build additional context from interview and plan data
    additional_context_parts: list[str] = []
    if session.get("interview_data"):
        additional_context_parts.append(
            f"Interview Data:\n{json.dumps(session['interview_data'], indent=2, default=str)}"
        )
    if session.get("plan_data"):
        additional_context_parts.append(
            f"Project Plan:\n{json.dumps(session['plan_data'], indent=2, default=str)}"
        )
    additional_context = (
        "\n\n".join(additional_context_parts) if additional_context_parts else None
    )

    # Create the proposal record
    now = datetime.now(timezone.utc).isoformat()
    proposal_data = {
        "card_id": card_id,
        "workstream_id": workstream["id"],
        "user_id": user_id,
        "title": f"Proposal: {card.get('name', 'Untitled Grant')}",
        "version": 1,
        "status": "draft",
        "sections": {},
        "ai_generation_metadata": {},
        "created_at": now,
        "updated_at": now,
    }

    try:
        proposal_result = supabase.table("proposals").insert(proposal_data).execute()
    except Exception as e:
        logger.error("Failed to create proposal: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("proposal creation", e),
        ) from e

    if not proposal_result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create proposal record",
        )

    proposal = proposal_result.data[0]
    proposal_id = proposal["id"]

    # Generate all sections using ProposalService
    proposal_service = ProposalService()
    try:
        generation_result = await proposal_service.generate_full_proposal(
            card=card,
            workstream=workstream,
        )
    except Exception as e:
        logger.error(
            "Proposal generation failed for wizard session %s: %s", session_id, e
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("proposal generation", e),
        ) from e

    # Persist generated sections
    model_used = generation_result["model_used"]
    gen_metadata = {
        section_name: {"model": model_used, "generated_at": now}
        for section_name in generation_result["sections"]
    }

    try:
        update_result = (
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
        logger.error("Failed to persist generated proposal %s: %s", proposal_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("saving generated proposal", e),
        ) from e

    # Link proposal_id to wizard session
    try:
        supabase.table("wizard_sessions").update(
            {
                "proposal_id": proposal_id,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("id", session_id).execute()
    except Exception as e:
        logger.warning(
            "Failed to link proposal %s to wizard session %s: %s",
            proposal_id,
            session_id,
            e,
        )

    return {
        "proposal_id": proposal_id,
        "proposal": update_result.data[0] if update_result.data else proposal,
    }


# ---------------------------------------------------------------------------
# PDF Export
# ---------------------------------------------------------------------------


@router.get("/me/wizard/sessions/{session_id}/export/pdf")
async def export_session_pdf(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Export the wizard session's proposal as a PDF.

    Loads the linked proposal and generates a professional PDF using
    ExportService.generate_proposal_pdf().

    Args:
        session_id: UUID of the wizard session.
        current_user: Authenticated user (injected).

    Returns:
        FileResponse with the generated PDF.

    Raises:
        HTTPException 404: Session or proposal not found.
        HTTPException 403: Not authorized.
        HTTPException 400: No proposal generated yet.
        HTTPException 500: PDF generation failed.
    """
    user_id = current_user["id"]
    session = await _verify_session_ownership(session_id, user_id)

    proposal_id = session.get("proposal_id")
    if not proposal_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No proposal generated yet. Generate a proposal first.",
        )

    # Fetch the proposal
    proposal_result = (
        supabase.table("proposals").select("*").eq("id", proposal_id).execute()
    )
    if not proposal_result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Linked proposal not found",
        )

    proposal = proposal_result.data[0]

    # Generate PDF via ExportService
    try:
        export_service = ExportService(supabase)
        pdf_path = await export_service.generate_proposal_pdf(
            proposal_data=proposal,
            grant_context=session.get("grant_context"),
            plan_data=session.get("plan_data"),
        )
    except Exception as e:
        logger.error(
            "Failed to generate proposal PDF for session %s: %s", session_id, e
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("PDF generation", e),
        ) from e

    # Build a safe filename
    title = proposal.get("title", "proposal")
    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)[:40]
    filename = f"Proposal_{safe_title}_{session_id[:8]}.pdf"

    return FileResponse(
        path=pdf_path,
        filename=filename,
        media_type="application/pdf",
        background=None,
    )
