from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from neft_shared.settings import get_settings

from app.services.s3_storage import S3Storage

settings = get_settings()


@dataclass(frozen=True)
class BankStatementUpload:
    bucket: str
    object_key: str
    upload_url: str


class BankStatementImportStorage:
    def __init__(self) -> None:
        self.bucket = settings.NEFT_S3_BUCKET_SUPPORT_ATTACHMENTS
        self.storage = S3Storage(bucket=self.bucket)

    @staticmethod
    def normalize_filename(file_name: str) -> str:
        clean = Path(file_name).name.strip()
        return clean or "bank-statement"

    def build_object_key(self, *, import_id: str, file_name: str) -> str:
        safe_name = self.normalize_filename(file_name)
        return f"bank-statements/{import_id}/{uuid4()}-{safe_name}"

    def presign_upload(self, *, object_key: str, content_type: str, expires: int) -> str | None:
        return self.storage.presign_put(object_key, content_type=content_type, expires=expires)

    def fetch_bytes(self, *, object_key: str) -> bytes | None:
        return self.storage.get_bytes(object_key)
