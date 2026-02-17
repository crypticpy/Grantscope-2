"""Business logic for application attachment management.

Handles file validation, upload/download orchestration via Azure Blob Storage,
and CRUD operations against the application_attachments table.
"""

import logging
import uuid
from typing import Optional

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.attachment import ApplicationAttachment
from app.storage import attachment_storage

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB

ALLOWED_EXTENSIONS: set[str] = {
    "pdf",
    "docx",
    "doc",
    "xlsx",
    "xls",
    "png",
    "jpg",
    "jpeg",
    "txt",
}

ALLOWED_MIME_TYPES: set[str] = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "image/png",
    "image/jpeg",
    "text/plain",
}

VALID_CATEGORIES: set[str] = {
    "narrative",
    "budget_form",
    "letter_of_support",
    "org_chart",
    "resume",
    "audit_report",
    "registration_proof",
    "indirect_rate_agreement",
    "data_management_plan",
    "other",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _validate_file(file: UploadFile) -> tuple[str, int, bytes]:
    """Validate file extension, MIME type, and size.

    Args:
        file: The uploaded file.

    Returns:
        Tuple of (original_filename, file_size_bytes, file_data).

    Raises:
        HTTPException 400: Invalid extension or MIME type.
        HTTPException 413: File exceeds size limit.
    """
    original_filename = file.filename or "unnamed_file"

    # Validate extension (case-insensitive)
    ext = (
        original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else ""
    )
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"File type '.{ext}' is not allowed. "
                f"Accepted types: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            ),
        )

    # Validate MIME type
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"MIME type '{content_type}' is not allowed. "
                f"Accepted types: {', '.join(sorted(ALLOWED_MIME_TYPES))}"
            ),
        )

    # Read content and check size
    data = await file.read()
    file_size_bytes = len(data)

    if file_size_bytes == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    if file_size_bytes > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                f"File size ({file_size_bytes:,} bytes) exceeds the "
                f"{MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB limit."
            ),
        )

    return original_filename, file_size_bytes, data


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class AttachmentService:
    """Manages attachment lifecycle: upload, download, replace, delete, list."""

    async def upload(
        self,
        db: AsyncSession,
        application_id: uuid.UUID,
        file: UploadFile,
        category: str,
        uploaded_by: str,
        checklist_item_id: Optional[uuid.UUID] = None,
        description: Optional[str] = None,
    ) -> ApplicationAttachment:
        """Upload a file and persist the attachment record.

        Args:
            db: Async database session.
            application_id: UUID of the parent application.
            file: The uploaded file.
            category: Document category (e.g. 'budget_form', 'narrative').
            uploaded_by: UUID of the uploading user.
            checklist_item_id: Optional linked checklist item.
            description: Optional human-readable description.

        Returns:
            The created ApplicationAttachment ORM instance.
        """
        original_filename, file_size_bytes, data = await _validate_file(file)

        # Generate a unique stored filename
        unique_prefix = uuid.uuid4().hex[:8]
        stored_filename = f"{unique_prefix}_{original_filename}"

        content_type = (file.content_type or "application/octet-stream").lower()

        # Upload to blob storage
        blob_path = await attachment_storage.upload(
            application_id=str(application_id),
            filename=stored_filename,
            data=data,
            content_type=content_type,
        )

        # Create DB record
        attachment = ApplicationAttachment(
            application_id=application_id,
            checklist_item_id=checklist_item_id,
            filename=stored_filename,
            original_filename=original_filename,
            blob_path=blob_path,
            content_type=content_type,
            file_size_bytes=file_size_bytes,
            category=category if category in VALID_CATEGORIES else "other",
            description=description,
            version=1,
            uploaded_by=uuid.UUID(uploaded_by),
        )
        db.add(attachment)
        await db.flush()
        await db.refresh(attachment)

        logger.info(
            "Uploaded attachment %s (%s, %d bytes) for application %s",
            attachment.id,
            original_filename,
            file_size_bytes,
            application_id,
        )
        return attachment

    async def download_url(
        self,
        db: AsyncSession,
        attachment_id: uuid.UUID,
    ) -> str:
        """Generate a time-limited SAS download URL for an attachment.

        Args:
            db: Async database session.
            attachment_id: UUID of the attachment.

        Returns:
            A SAS URL string valid for 1 hour.

        Raises:
            HTTPException 404: Attachment not found.
        """
        attachment = await db.get(ApplicationAttachment, attachment_id)
        if not attachment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Attachment not found",
            )

        url = await attachment_storage.generate_sas_url(attachment.blob_path)
        return url

    async def delete(
        self,
        db: AsyncSession,
        attachment_id: uuid.UUID,
        user_id: str,
    ) -> None:
        """Delete an attachment from blob storage and the database.

        Args:
            db: Async database session.
            attachment_id: UUID of the attachment.
            user_id: UUID of the requesting user (for audit logging).

        Raises:
            HTTPException 404: Attachment not found.
        """
        attachment = await db.get(ApplicationAttachment, attachment_id)
        if not attachment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Attachment not found",
            )

        # Delete from blob storage
        await attachment_storage.delete(attachment.blob_path)

        # Delete DB record
        await db.delete(attachment)
        await db.flush()

        logger.info(
            "Deleted attachment %s (blob: %s) by user %s",
            attachment_id,
            attachment.blob_path,
            user_id,
        )

    async def replace(
        self,
        db: AsyncSession,
        attachment_id: uuid.UUID,
        file: UploadFile,
        user_id: str,
    ) -> ApplicationAttachment:
        """Replace an attachment with a new file version.

        Uploads the new file, increments the version number, and updates
        the DB record. The old blob is left in storage for now.

        Args:
            db: Async database session.
            attachment_id: UUID of the attachment to replace.
            file: The new uploaded file.
            user_id: UUID of the requesting user (for audit logging).

        Returns:
            The updated ApplicationAttachment ORM instance.

        Raises:
            HTTPException 404: Attachment not found.
        """
        attachment = await db.get(ApplicationAttachment, attachment_id)
        if not attachment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Attachment not found",
            )

        original_filename, file_size_bytes, data = await _validate_file(file)

        # Generate new stored filename
        unique_prefix = uuid.uuid4().hex[:8]
        stored_filename = f"{unique_prefix}_{original_filename}"
        content_type = (file.content_type or "application/octet-stream").lower()

        # Upload new file to blob storage
        new_blob_path = await attachment_storage.upload(
            application_id=str(attachment.application_id),
            filename=stored_filename,
            data=data,
            content_type=content_type,
        )

        # Update DB record (keep old blob, just update metadata)
        attachment.filename = stored_filename
        attachment.original_filename = original_filename
        attachment.blob_path = new_blob_path
        attachment.content_type = content_type
        attachment.file_size_bytes = file_size_bytes
        attachment.version = attachment.version + 1

        await db.flush()
        await db.refresh(attachment)

        logger.info(
            "Replaced attachment %s with v%d (%s, %d bytes) by user %s",
            attachment_id,
            attachment.version,
            original_filename,
            file_size_bytes,
            user_id,
        )
        return attachment

    async def list_for_application(
        self,
        db: AsyncSession,
        application_id: uuid.UUID,
        category: Optional[str] = None,
    ) -> list[ApplicationAttachment]:
        """List all attachments for an application, optionally filtered by category.

        Args:
            db: Async database session.
            application_id: UUID of the parent application.
            category: Optional category filter.

        Returns:
            List of ApplicationAttachment records ordered by category then
            created_at descending.
        """
        stmt = (
            select(ApplicationAttachment)
            .where(ApplicationAttachment.application_id == application_id)
            .order_by(
                ApplicationAttachment.category,
                ApplicationAttachment.created_at.desc(),
            )
        )

        if category:
            stmt = stmt.where(ApplicationAttachment.category == category)

        result = await db.execute(stmt)
        return list(result.scalars().all())
