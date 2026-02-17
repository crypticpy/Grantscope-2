"""Attachments router for application document/file management.

Provides endpoints to upload, list, download, replace, and delete files
associated with grant applications. Files are stored in Azure Blob Storage
with metadata persisted in the application_attachments table.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, get_current_user_hardcoded, _safe_error
from app.models.attachment_models import (
    AttachmentListResponse,
    AttachmentResponse,
    AttachmentUploadResponse,
    DownloadUrlResponse,
)
from app.services.attachment_service import AttachmentService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["attachments"])

# Module-level service instance
_service = AttachmentService()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _attachment_to_response(attachment) -> AttachmentResponse:
    """Convert an ApplicationAttachment ORM instance to an API response model."""
    return AttachmentResponse(
        id=str(attachment.id),
        application_id=str(attachment.application_id),
        checklist_item_id=(
            str(attachment.checklist_item_id) if attachment.checklist_item_id else None
        ),
        filename=attachment.filename,
        original_filename=attachment.original_filename,
        blob_path=attachment.blob_path,
        content_type=attachment.content_type,
        file_size_bytes=attachment.file_size_bytes,
        category=attachment.category,
        description=attachment.description,
        version=attachment.version,
        uploaded_by=str(attachment.uploaded_by),
        ai_extracted_data=attachment.ai_extracted_data,
        created_at=attachment.created_at,
        updated_at=attachment.updated_at,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/applications/{application_id}/attachments",
    response_model=AttachmentListResponse,
)
async def list_attachments(
    application_id: uuid.UUID,
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """List all attachments for an application.

    Args:
        application_id: UUID of the parent grant application.
        category: Optional category filter (e.g. 'budget_form', 'narrative').
        db: Async database session (injected).
        current_user: Authenticated user (injected).

    Returns:
        AttachmentListResponse with attachment list and total count.
    """
    try:
        attachments = await _service.list_for_application(
            db=db,
            application_id=application_id,
            category=category,
        )
        responses = [_attachment_to_response(a) for a in attachments]
        return AttachmentListResponse(attachments=responses, total=len(responses))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("listing attachments", e),
        ) from e


@router.post(
    "/applications/{application_id}/attachments",
    response_model=AttachmentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_attachment(
    application_id: uuid.UUID,
    file: UploadFile = File(...),
    category: str = Form("other"),
    checklist_item_id: str | None = Form(None),
    description: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Upload a file attachment to an application.

    Accepts a multipart form with the file and optional metadata fields.

    Args:
        application_id: UUID of the parent grant application.
        file: The file to upload (multipart).
        category: Document category (default 'other').
        checklist_item_id: Optional UUID of a linked checklist item.
        description: Optional human-readable description.
        db: Async database session (injected).
        current_user: Authenticated user (injected).

    Returns:
        AttachmentUploadResponse with the created attachment and a message.

    Raises:
        HTTPException 400: Invalid file type or MIME type.
        HTTPException 413: File exceeds 25 MB limit.
    """
    try:
        parsed_checklist_id = (
            uuid.UUID(checklist_item_id) if checklist_item_id else None
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid checklist_item_id format. Must be a valid UUID.",
        )

    try:
        attachment = await _service.upload(
            db=db,
            application_id=application_id,
            file=file,
            category=category,
            uploaded_by=current_user["id"],
            checklist_item_id=parsed_checklist_id,
            description=description,
        )
        response = _attachment_to_response(attachment)
        return AttachmentUploadResponse(
            attachment=response,
            message=f"File '{attachment.original_filename}' uploaded successfully.",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("uploading attachment", e),
        ) from e


@router.get(
    "/attachments/{attachment_id}/download",
    response_model=DownloadUrlResponse,
)
async def get_download_url(
    attachment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Get a time-limited SAS download URL for an attachment.

    Args:
        attachment_id: UUID of the attachment.
        db: Async database session (injected).
        current_user: Authenticated user (injected).

    Returns:
        DownloadUrlResponse with the SAS URL and expiry info.

    Raises:
        HTTPException 404: Attachment not found.
    """
    try:
        url = await _service.download_url(db=db, attachment_id=attachment_id)
        return DownloadUrlResponse(url=url, expires_in_hours=1)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("generating download URL", e),
        ) from e


@router.delete(
    "/attachments/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_attachment(
    attachment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Delete an attachment from storage and the database.

    Args:
        attachment_id: UUID of the attachment.
        db: Async database session (injected).
        current_user: Authenticated user (injected).

    Raises:
        HTTPException 404: Attachment not found.
    """
    try:
        await _service.delete(
            db=db,
            attachment_id=attachment_id,
            user_id=current_user["id"],
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("deleting attachment", e),
        ) from e


@router.put(
    "/attachments/{attachment_id}/replace",
    response_model=AttachmentUploadResponse,
)
async def replace_attachment(
    attachment_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Replace an attachment with a new file version.

    Uploads the new file and increments the version number. The old blob
    is retained in storage.

    Args:
        attachment_id: UUID of the attachment to replace.
        file: The replacement file (multipart).
        db: Async database session (injected).
        current_user: Authenticated user (injected).

    Returns:
        AttachmentUploadResponse with the updated attachment.

    Raises:
        HTTPException 400: Invalid file type or MIME type.
        HTTPException 404: Attachment not found.
        HTTPException 413: File exceeds 25 MB limit.
    """
    try:
        attachment = await _service.replace(
            db=db,
            attachment_id=attachment_id,
            file=file,
            user_id=current_user["id"],
        )
        response = _attachment_to_response(attachment)
        return AttachmentUploadResponse(
            attachment=response,
            message=f"File replaced successfully (v{attachment.version}).",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("replacing attachment", e),
        ) from e
