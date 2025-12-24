from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date

from neft_shared.settings import get_settings

from app.models.documents import DocumentFileType, DocumentType
from app.services.s3_storage import S3Storage

settings = get_settings()


@dataclass(frozen=True)
class StoredDocumentFile:
    bucket: str
    object_key: str
    sha256: str
    size_bytes: int
    content_type: str


class DocumentsStorage:
    def __init__(self) -> None:
        self.bucket = settings.NEFT_S3_BUCKET_DOCUMENTS
        self.storage = S3Storage(bucket=self.bucket)

    @staticmethod
    def build_object_key(
        *,
        tenant_id: int,
        client_id: str,
        period_from: date,
        period_to: date,
        version: int,
        document_type: DocumentType,
        file_type: DocumentFileType,
    ) -> str:
        ext = "pdf" if file_type == DocumentFileType.PDF else "xlsx"
        return (
            f"documents/{tenant_id}/{client_id}/{period_from:%Y-%m-%d}_{period_to:%Y-%m-%d}/"
            f"v{version}/{document_type.value}.{ext}"
        )

    def store_bytes(
        self,
        *,
        object_key: str,
        payload: bytes,
        content_type: str,
    ) -> StoredDocumentFile:
        self.storage.ensure_bucket()
        self.storage.put_bytes(object_key, payload, content_type=content_type)
        sha256 = hashlib.sha256(payload).hexdigest()
        return StoredDocumentFile(
            bucket=self.bucket,
            object_key=object_key,
            sha256=sha256,
            size_bytes=len(payload),
            content_type=content_type,
        )

    def fetch_bytes(self, object_key: str) -> bytes | None:
        return self.storage.get_bytes(object_key)

    def exists(self, object_key: str) -> bool:
        return self.storage.exists(object_key)
