from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.integrations import IntegrationFile


@dataclass(frozen=True)
class StoredIntegrationFile:
    file_id: str
    file_name: str
    content_type: str
    sha256: str
    size_bytes: int


def store_integration_file(
    db: Session,
    *,
    file_name: str,
    content_type: str,
    payload: bytes,
) -> StoredIntegrationFile:
    sha256 = hashlib.sha256(payload).hexdigest()
    record = IntegrationFile(
        file_name=file_name,
        content_type=content_type,
        sha256=sha256,
        size_bytes=len(payload),
        payload=payload,
    )
    db.add(record)
    db.flush()
    return StoredIntegrationFile(
        file_id=str(record.id),
        file_name=file_name,
        content_type=content_type,
        sha256=sha256,
        size_bytes=len(payload),
    )


def load_integration_file(db: Session, file_id: str) -> IntegrationFile | None:
    return db.query(IntegrationFile).filter(IntegrationFile.id == file_id).one_or_none()


__all__ = ["StoredIntegrationFile", "store_integration_file", "load_integration_file"]
