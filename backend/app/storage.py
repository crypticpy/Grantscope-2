"""Azure Blob Storage integration for application attachments.

Provides async upload, download, delete, and SAS URL generation for files
stored in the ``application-attachments`` container.

Usage::

    from app.storage import attachment_storage

    url = await attachment_storage.upload(
        application_id="abc-123",
        filename="budget.pdf",
        data=file_bytes,
        content_type="application/pdf",
    )
"""

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Lazy import — azure-storage-blob may not be installed in every environment.
# Functions will raise a clear error at call time if missing.
_blob_available = False
try:
    from azure.storage.blob.aio import BlobServiceClient, ContainerClient
    from azure.storage.blob import (
        generate_blob_sas,
        BlobSasPermissions,
        ContentSettings,
    )

    _blob_available = True
except ImportError:
    logger.warning("azure-storage-blob not installed — attachment features disabled")

CONTAINER_NAME = "application-attachments"
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB


def _require_blob(connection_string: str | None = None) -> None:
    if not _blob_available:
        raise RuntimeError(
            "azure-storage-blob is not installed. "
            "Run: pip install azure-storage-blob>=12.19.0"
        )
    if not connection_string:
        raise RuntimeError(
            "AZURE_STORAGE_CONNECTION_STRING is not set. "
            "File upload/download requires Azure Blob Storage configuration."
        )


class AttachmentStorage:
    """Async wrapper around Azure Blob Storage for application attachments."""

    def __init__(self) -> None:
        self.connection_string: str | None = os.getenv(
            "AZURE_STORAGE_CONNECTION_STRING"
        )
        self.account_name: str | None = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
        self.account_key: str | None = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")
        self.container = CONTAINER_NAME

        if not self.connection_string:
            logger.warning(
                "AZURE_STORAGE_CONNECTION_STRING not set — "
                "attachment upload/download will fail at call time"
            )

    def _blob_path(self, application_id: str, filename: str) -> str:
        """Build a unique blob path: applications/{app_id}/{uuid}_{filename}."""
        unique = uuid.uuid4().hex[:8]
        safe_name = filename.replace("/", "_").replace("\\", "_")
        return f"applications/{application_id}/{unique}_{safe_name}"

    async def upload(
        self,
        application_id: str,
        filename: str,
        data: bytes,
        content_type: str,
    ) -> str:
        """Upload a file to Azure Blob Storage.

        Returns the blob path (not the full URL) for storage in the DB.
        Raises ValueError if file exceeds MAX_FILE_SIZE_BYTES.
        """
        _require_blob(self.connection_string)
        if len(data) > MAX_FILE_SIZE_BYTES:
            raise ValueError(
                f"File size {len(data)} bytes exceeds maximum of "
                f"{MAX_FILE_SIZE_BYTES} bytes ({MAX_FILE_SIZE_BYTES // (1024*1024)} MB)"
            )

        blob_path = self._blob_path(application_id, filename)
        async with BlobServiceClient.from_connection_string(
            self.connection_string
        ) as client:
            blob_client = client.get_blob_client(
                container=self.container, blob=blob_path
            )
            await blob_client.upload_blob(
                data,
                content_settings=ContentSettings(content_type=content_type),
                overwrite=True,
            )
        logger.info("Uploaded %s (%d bytes) to %s", filename, len(data), blob_path)
        return blob_path

    async def download(self, blob_path: str) -> bytes:
        """Download a file by its blob path."""
        _require_blob(self.connection_string)
        async with BlobServiceClient.from_connection_string(
            self.connection_string
        ) as client:
            blob_client = client.get_blob_client(
                container=self.container, blob=blob_path
            )
            stream = await blob_client.download_blob()
            return await stream.readall()

    async def delete(self, blob_path: str) -> None:
        """Delete a file from Azure Blob Storage."""
        _require_blob(self.connection_string)
        async with BlobServiceClient.from_connection_string(
            self.connection_string
        ) as client:
            blob_client = client.get_blob_client(
                container=self.container, blob=blob_path
            )
            await blob_client.delete_blob(delete_snapshots="include")
        logger.info("Deleted blob: %s", blob_path)

    def _card_document_blob_path(self, card_id: str, filename: str) -> str:
        """Build a unique blob path for card documents: cards/{card_id}/{uuid}_{filename}."""
        unique = uuid.uuid4().hex[:8]
        safe_name = filename.replace("/", "_").replace("\\", "_")
        return f"cards/{card_id}/{unique}_{safe_name}"

    async def upload_card_document(
        self,
        card_id: str,
        filename: str,
        data: bytes,
        content_type: str,
    ) -> str:
        """Upload a card document to Azure Blob Storage.

        Uses a ``cards/`` prefix instead of ``applications/`` to keep card
        documents organized separately.

        Returns the blob path (not the full URL) for storage in the DB.
        Raises ValueError if file exceeds MAX_FILE_SIZE_BYTES.
        """
        _require_blob(self.connection_string)
        if len(data) > MAX_FILE_SIZE_BYTES:
            raise ValueError(
                f"File size {len(data)} bytes exceeds maximum of "
                f"{MAX_FILE_SIZE_BYTES} bytes ({MAX_FILE_SIZE_BYTES // (1024*1024)} MB)"
            )

        blob_path = self._card_document_blob_path(card_id, filename)
        async with BlobServiceClient.from_connection_string(
            self.connection_string
        ) as client:
            blob_client = client.get_blob_client(
                container=self.container, blob=blob_path
            )
            await blob_client.upload_blob(
                data,
                content_settings=ContentSettings(content_type=content_type),
                overwrite=True,
            )
        logger.info(
            "Uploaded card document %s (%d bytes) to %s",
            filename,
            len(data),
            blob_path,
        )
        return blob_path

    async def generate_sas_url(self, blob_path: str, expiry_hours: int = 1) -> str:
        """Generate a time-limited SAS URL for secure file download.

        The URL is valid for ``expiry_hours`` (default 1 hour).
        """
        _require_blob(self.connection_string)
        if not self.account_name or not self.account_key:
            # Try to extract from connection string
            if self.connection_string:
                parts = dict(
                    pair.split("=", 1)
                    for pair in self.connection_string.split(";")
                    if "=" in pair
                )
                self.account_name = parts.get("AccountName")
                self.account_key = parts.get("AccountKey")

        if not self.account_name or not self.account_key:
            raise RuntimeError(
                "Cannot generate SAS URL: AZURE_STORAGE_ACCOUNT_NAME and "
                "AZURE_STORAGE_ACCOUNT_KEY are required, or include them in "
                "AZURE_STORAGE_CONNECTION_STRING"
            )

        sas_token = generate_blob_sas(
            account_name=self.account_name,
            container_name=self.container,
            blob_name=blob_path,
            account_key=self.account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.now(timezone.utc) + timedelta(hours=expiry_hours),
        )
        return (
            f"https://{self.account_name}.blob.core.windows.net/"
            f"{self.container}/{blob_path}?{sas_token}"
        )


# Module-level singleton
attachment_storage = AttachmentStorage()
