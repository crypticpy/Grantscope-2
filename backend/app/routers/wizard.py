"""Wizard router for the Guided Grant Application Wizard.

Provides endpoints for creating, managing, and progressing through wizard
sessions that walk users through grant applications via AI-powered interviews.
"""

import json
import logging
import uuid as _uuid
from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Optional

import fitz  # PyMuPDF -- for PDF text extraction from uploaded files
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, get_current_user_hardcoded, _safe_error
from app.export_service import ExportService
from app.models.db.card import Card
from app.models.db.chat import ChatConversation, ChatMessage
from app.models.db.proposal import Proposal as ProposalDB
from app.models.db.research import ResearchTask
from app.models.db.source import Source
from app.models.db.wizard_session import WizardSession as WizardSessionDB
from app.models.db.workstream import Workstream as WorkstreamDB
from app.models.wizard import (
    GrantContext,
    ProcessGrantResponse,
    WizardSession,
    WizardSessionCreate,
    WizardSessionUpdate,
)
from app.proposal_service import ProposalService
from app.wizard_service import WizardService

from sqlalchemy import desc as sa_desc

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["wizard"])


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


async def _verify_session_ownership(
    session_id: str, user_id: str, db: AsyncSession
) -> dict:
    """Fetch a wizard session by ID and verify ownership.

    Args:
        session_id: UUID of the wizard session.
        user_id: UUID of the authenticated user.
        db: Async database session.

    Returns:
        The session row as a dict.

    Raises:
        HTTPException 404: Session not found.
        HTTPException 403: Not authorized.
    """
    try:
        result = await db.execute(
            select(WizardSessionDB).where(WizardSessionDB.id == session_id)
        )
        session_obj = result.scalar_one_or_none()
    except Exception as e:
        logger.error("Failed to fetch wizard session %s: %s", session_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("fetching wizard session", e),
        ) from e

    if session_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wizard session not found",
        )

    session = _row_to_dict(session_obj)

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


async def _build_grant_context_from_card(db: AsyncSession, card_id: str) -> dict:
    """Load a card + its sources + latest deep research and return a GrantContext dict.

    This ensures the wizard interview AI has full context about the grant
    when the user enters the application workflow from a card detail page.
    """
    # Load the card
    result = await db.execute(select(Card).where(Card.id == _uuid.UUID(card_id)))
    card = result.scalar_one_or_none()
    if not card:
        return {}

    # Build base context from card fields
    ctx: dict = {
        "card_id": str(card.id),
        "grant_name": card.name,
        "grantor": card.grantor,
        "cfda_number": card.cfda_number,
        "grants_gov_id": card.grants_gov_id,
        "grant_type": card.grant_type,
        "eligibility_text": card.eligibility_text,
        "match_requirement": card.match_requirement,
        "source_url": card.source_url,
        "summary": card.summary,
        "description": (card.description or "")[:3000],
    }

    # Deadline
    if card.deadline:
        ctx["deadline"] = card.deadline.strftime("%B %d, %Y")

    # Funding amounts
    if card.funding_amount_min is not None:
        ctx["funding_amount_min"] = float(card.funding_amount_min)
    if card.funding_amount_max is not None:
        ctx["funding_amount_max"] = float(card.funding_amount_max)

    # Load sources attached to this card (summaries + titles)
    try:
        src_result = await db.execute(
            select(Source)
            .where(Source.card_id == _uuid.UUID(card_id))
            .order_by(Source.created_at.desc())
            .limit(20)
        )
        sources = src_result.scalars().all()
        source_docs = []
        for s in sources:
            parts = []
            if s.title:
                parts.append(f"Title: {s.title}")
            if s.url:
                parts.append(f"URL: {s.url}")
            if getattr(s, "ai_summary", None):
                parts.append(f"Summary: {s.ai_summary}")
            elif getattr(s, "content", None):
                parts.append(f"Content: {s.content[:500]}")
            if parts:
                source_docs.append(" | ".join(parts))
        ctx["source_documents"] = source_docs
    except Exception as e:
        logger.warning("Failed to load sources for card %s: %s", card_id, e)

    # Also fetch user-uploaded card documents
    try:
        from app.models.db.card_document import CardDocument

        doc_result = await db.execute(
            select(
                CardDocument.original_filename,
                CardDocument.extracted_text,
                CardDocument.document_type,
            )
            .where(
                CardDocument.card_id == _uuid.UUID(card_id),
                CardDocument.extraction_status == "completed",
            )
            .order_by(CardDocument.created_at.desc())
            .limit(5)
        )
        doc_rows = doc_result.all()
        for doc in doc_rows:
            if doc.extracted_text:
                # Ensure source_documents list exists (may not if sources query failed)
                if "source_documents" not in ctx:
                    ctx["source_documents"] = []
                ctx["source_documents"].append(
                    f"[{doc.document_type.upper()}] {doc.original_filename}:\n{doc.extracted_text[:10000]}"
                )
    except Exception as e:
        logger.warning("Failed to fetch card documents for wizard: %s", card_id, e)

    # Load latest deep research report
    try:
        rt_result = await db.execute(
            select(ResearchTask)
            .where(
                ResearchTask.card_id == _uuid.UUID(card_id),
                ResearchTask.task_type == "deep_research",
                ResearchTask.status == "completed",
            )
            .order_by(sa_desc(ResearchTask.completed_at))
            .limit(1)
        )
        research = rt_result.scalar_one_or_none()
        if research and research.result_summary:
            report = research.result_summary.get("report_preview", "")
            if report:
                ctx["research_report"] = report[:8000]
    except Exception as e:
        logger.warning("Failed to load research for card %s: %s", card_id, e)

    return ctx


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
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
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
    now = datetime.now(timezone.utc)

    # If card_id is provided, pre-populate grant context from the card
    grant_context: dict = {}
    if body.card_id:
        try:
            grant_context = await _build_grant_context_from_card(db, body.card_id)
            logger.info(
                "Pre-populated grant context from card %s (%d fields)",
                body.card_id,
                len([v for v in grant_context.values() if v]),
            )
        except Exception as e:
            logger.warning(
                "Failed to build grant context from card %s: %s", body.card_id, e
            )

    # 1. Create the wizard session first (without conversation_id)
    session_obj = WizardSessionDB(
        user_id=_uuid.UUID(user_id),
        entry_path=body.entry_path,
        current_step=2 if grant_context else 0,
        status="in_progress",
        grant_context=grant_context,
        interview_data={},
        plan_data={},
        created_at=now,
        updated_at=now,
    )

    try:
        db.add(session_obj)
        await db.flush()
        await db.refresh(session_obj)
    except Exception as e:
        logger.error("Failed to create wizard session: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("wizard session creation", e),
        ) from e

    session_id = session_obj.id

    # 2. Create a linked chat conversation with scope='wizard'
    conversation_obj = ChatConversation(
        user_id=_uuid.UUID(user_id),
        scope="wizard",
        scope_id=session_id,
        title=f"Wizard Session - {body.entry_path}",
        created_at=now,
        updated_at=now,
    )

    try:
        db.add(conversation_obj)
        await db.flush()
        await db.refresh(conversation_obj)
    except Exception as e:
        logger.error("Failed to create chat conversation for wizard: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("wizard conversation creation", e),
        ) from e

    conversation_id = conversation_obj.id

    # 3. Link conversation_id back to the wizard session
    try:
        session_obj.conversation_id = conversation_id
        await db.flush()
        await db.refresh(session_obj)
    except Exception as e:
        logger.error("Failed to link conversation to wizard session: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("wizard session update", e),
        ) from e

    return WizardSession(**_row_to_dict(session_obj))


@router.get("/me/wizard/sessions", response_model=list[WizardSession])
async def list_wizard_sessions(
    status_filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """List the authenticated user's wizard sessions.

    Args:
        status_filter: Optional status to filter by (e.g. 'in_progress', 'completed').
        current_user: Authenticated user (injected).

    Returns:
        List of WizardSession records ordered by updated_at desc.
    """
    query = (
        select(WizardSessionDB)
        .where(WizardSessionDB.user_id == current_user["id"])
        .order_by(WizardSessionDB.updated_at.desc())
        .limit(20)
    )

    if status_filter:
        query = query.where(WizardSessionDB.status == status_filter)

    try:
        result = await db.execute(query)
        rows = list(result.scalars().all())
    except Exception as e:
        logger.error("Failed to list wizard sessions: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("listing wizard sessions", e),
        ) from e

    return [WizardSession(**_row_to_dict(row)) for row in rows]


@router.get("/me/wizard/sessions/{session_id}", response_model=WizardSession)
async def get_wizard_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
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
    session = await _verify_session_ownership(session_id, current_user["id"], db)
    return WizardSession(**session)


@router.patch("/me/wizard/sessions/{session_id}", response_model=WizardSession)
async def update_wizard_session(
    session_id: str,
    body: WizardSessionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
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
    await _verify_session_ownership(session_id, current_user["id"], db)

    # Fetch the ORM object for mutation
    try:
        result = await db.execute(
            select(WizardSessionDB).where(WizardSessionDB.id == session_id)
        )
        session_obj = result.scalar_one()
    except Exception as e:
        logger.error("Failed to fetch wizard session %s for update: %s", session_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("wizard session update", e),
        ) from e

    session_obj.updated_at = datetime.now(timezone.utc)

    if body.current_step is not None:
        session_obj.current_step = body.current_step
    if body.status is not None:
        session_obj.status = body.status
    if body.grant_context is not None:
        session_obj.grant_context = body.grant_context.model_dump(mode="json")
    if body.interview_data is not None:
        session_obj.interview_data = body.interview_data
    if body.plan_data is not None:
        session_obj.plan_data = body.plan_data.model_dump(mode="json")

    try:
        await db.flush()
        await db.refresh(session_obj)
    except Exception as e:
        logger.error("Failed to update wizard session %s: %s", session_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("wizard session update", e),
        ) from e

    return WizardSession(**_row_to_dict(session_obj))


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
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
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
    await _verify_session_ownership(session_id, user_id, db)

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
    try:
        result = await db.execute(
            select(WizardSessionDB).where(WizardSessionDB.id == session_id)
        )
        session_obj = result.scalar_one()
        session_obj.grant_context = grant_context_dict
        session_obj.updated_at = datetime.now(timezone.utc)
        if card_id:
            session_obj.card_id = _uuid.UUID(card_id)
        await db.flush()
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
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
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
    session = await _verify_session_ownership(session_id, user_id, db)

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
        msg_result = await db.execute(
            select(ChatMessage.role, ChatMessage.content)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.created_at.asc())
        )
        messages = [
            {"role": row.role, "content": row.content} for row in msg_result.all()
        ]
    except Exception as e:
        logger.error("Failed to load conversation messages: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("loading conversation messages", e),
        ) from e

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
        result = await db.execute(
            select(WizardSessionDB).where(WizardSessionDB.id == session_id)
        )
        session_obj = result.scalar_one()
        session_obj.plan_data = plan_data_dict
        session_obj.updated_at = datetime.now(timezone.utc)
        await db.flush()
    except Exception as e:
        logger.warning("Failed to save plan data to session %s: %s", session_id, e)

    return plan_data_dict


# ---------------------------------------------------------------------------
# Proposal Generation
# ---------------------------------------------------------------------------


@router.post("/me/wizard/sessions/{session_id}/generate-proposal")
async def generate_proposal(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
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
    session = await _verify_session_ownership(session_id, user_id, db)

    card_id = session.get("card_id")
    if not card_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No card linked to this session. Process a grant document first.",
        )

    # Fetch the card
    try:
        card_result = await db.execute(select(Card).where(Card.id == card_id))
        card_obj = card_result.scalar_one_or_none()
    except Exception as e:
        logger.error("Failed to fetch card %s: %s", card_id, e)
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

    # Find or create a workstream for this wizard session
    try:
        ws_result = await db.execute(
            select(WorkstreamDB).where(WorkstreamDB.user_id == user_id).limit(1)
        )
        workstream_obj = ws_result.scalar_one_or_none()
    except Exception as e:
        logger.error("Failed to query workstreams: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("querying workstreams", e),
        ) from e

    if workstream_obj is not None:
        workstream = _row_to_dict(workstream_obj)
    else:
        # Create a default workstream for the user
        now = datetime.now(timezone.utc)
        workstream_obj = WorkstreamDB(
            user_id=_uuid.UUID(user_id),
            name="Grant Applications",
            description="Default workstream for grant proposals generated via the wizard.",
            created_at=now,
            updated_at=now,
        )
        try:
            db.add(workstream_obj)
            await db.flush()
            await db.refresh(workstream_obj)
        except Exception as e:
            logger.error("Failed to create default workstream: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=_safe_error("default workstream creation", e),
            ) from e
        workstream = _row_to_dict(workstream_obj)

    # Build additional context from interview and plan data
    # NOTE: additional_context is assembled for future use when ProposalService
    # supports it; currently generate_full_proposal does not accept it.
    additional_context_parts: list[str] = []
    if session.get("interview_data"):
        additional_context_parts.append(
            f"Interview Data:\n{json.dumps(session['interview_data'], indent=2, default=str)}"
        )
    if session.get("plan_data"):
        additional_context_parts.append(
            f"Project Plan:\n{json.dumps(session['plan_data'], indent=2, default=str)}"
        )
    _additional_context = (  # noqa: F841
        "\n\n".join(additional_context_parts) if additional_context_parts else None
    )

    # Create the proposal record
    now = datetime.now(timezone.utc)
    proposal_obj = ProposalDB(
        card_id=_uuid.UUID(card_id),
        workstream_id=workstream_obj.id,
        user_id=_uuid.UUID(user_id),
        title=f"Proposal: {card.get('name', 'Untitled Grant')}",
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

    proposal_id = str(proposal_obj.id)

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
    now_iso = now.isoformat()
    model_used = generation_result["model_used"]
    gen_metadata = {
        section_name: {"model": model_used, "generated_at": now_iso}
        for section_name in generation_result["sections"]
    }

    try:
        proposal_obj.sections = generation_result["sections"]
        proposal_obj.ai_model = model_used
        proposal_obj.ai_generation_metadata = gen_metadata
        proposal_obj.updated_at = datetime.now(timezone.utc)
        await db.flush()
        await db.refresh(proposal_obj)
    except Exception as e:
        logger.error("Failed to persist generated proposal %s: %s", proposal_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("saving generated proposal", e),
        ) from e

    # Link proposal_id to wizard session
    try:
        ws_result = await db.execute(
            select(WizardSessionDB).where(WizardSessionDB.id == session_id)
        )
        session_obj = ws_result.scalar_one()
        session_obj.proposal_id = proposal_obj.id
        session_obj.updated_at = datetime.now(timezone.utc)
        await db.flush()
    except Exception as e:
        logger.warning(
            "Failed to link proposal %s to wizard session %s: %s",
            proposal_id,
            session_id,
            e,
        )

    proposal_dict = _row_to_dict(proposal_obj)
    return {
        "proposal_id": proposal_id,
        "proposal": proposal_dict,
    }


# ---------------------------------------------------------------------------
# PDF Export
# ---------------------------------------------------------------------------


@router.get("/me/wizard/sessions/{session_id}/export/pdf")
async def export_session_pdf(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
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
    session = await _verify_session_ownership(session_id, user_id, db)

    proposal_id = session.get("proposal_id")
    if not proposal_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No proposal generated yet. Generate a proposal first.",
        )

    # Fetch the proposal
    try:
        proposal_result = await db.execute(
            select(ProposalDB).where(ProposalDB.id == proposal_id)
        )
        proposal_obj = proposal_result.scalar_one_or_none()
    except Exception as e:
        logger.error("Failed to fetch proposal %s: %s", proposal_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("fetching proposal", e),
        ) from e

    if proposal_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Linked proposal not found",
        )

    proposal = _row_to_dict(proposal_obj)

    # Generate PDF via ExportService
    try:
        export_service = ExportService(db)
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
