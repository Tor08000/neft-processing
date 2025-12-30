from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DocumentSignRequest(BaseModel):
    provider: str = Field(default="provider_x")
    idempotency_key: str | None = None
    meta: dict[str, Any] | None = None


class DocumentSignatureOut(BaseModel):
    id: str
    document_id: str
    version: int
    provider: str
    request_id: str | None
    status: str
    input_object_key: str | None
    input_sha256: str | None
    signed_object_key: str | None
    signed_sha256: str | None
    signature_object_key: str | None
    signature_sha256: str | None
    attempt: int
    error_code: str | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    meta: dict[str, Any] | None


class DocumentSignResponse(BaseModel):
    signature: DocumentSignatureOut


class DocumentSignatureListResponse(BaseModel):
    items: list[DocumentSignatureOut]


class DocumentSignatureVerifyResponse(BaseModel):
    signature: DocumentSignatureOut
    verified: bool
    status: str
