"""Pydantic request/response models for the attachment management API."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AttachmentResponse(BaseModel):
    """Full representation of an application attachment."""

    id: str
    application_id: str
    checklist_item_id: Optional[str] = None
    filename: str
    original_filename: str
    blob_path: str
    content_type: str
    file_size_bytes: int
    category: str = "other"
    description: Optional[str] = None
    version: int = 1
    uploaded_by: str
    ai_extracted_data: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AttachmentListResponse(BaseModel):
    """Paginated list of attachments for an application."""

    attachments: List[AttachmentResponse]
    total: int


class AttachmentUploadResponse(BaseModel):
    """Response returned after a successful file upload."""

    attachment: AttachmentResponse
    message: str


class DownloadUrlResponse(BaseModel):
    """Time-limited SAS download URL for an attachment."""

    url: str
    expires_in_hours: int
