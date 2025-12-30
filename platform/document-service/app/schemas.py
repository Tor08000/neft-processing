from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class RenderRequest(BaseModel):
    template_kind: str = Field(..., examples=["HTML"])
    template_id: str | None = None
    template_html: str
    data: dict[str, Any] = Field(default_factory=dict)
    output_format: str = Field(..., examples=["PDF"])
    tenant_id: int
    client_id: str | None = None
    idempotency_key: str
    meta: dict[str, Any] | None = None
    doc_id: str
    doc_type: str
    version: int = Field(ge=1)
    document_date: date | None = None


class RenderResponse(BaseModel):
    bucket: str
    object_key: str
    sha256: str
    size_bytes: int
    content_type: str
    version: int


class PresignRequest(BaseModel):
    bucket: str
    object_key: str
    ttl_seconds: int = Field(ge=1, le=604800)


class PresignResponse(BaseModel):
    url: str


class StorageObjectRef(BaseModel):
    bucket: str
    object_key: str
    sha256: str | None = None


class SignOutput(BaseModel):
    bucket: str
    prefix: str


class SignRequest(BaseModel):
    document_id: str
    provider: str = Field(..., examples=["provider_x"])
    input: StorageObjectRef
    output: SignOutput
    idempotency_key: str
    meta: dict[str, Any] | None = None


class SignedArtifact(BaseModel):
    bucket: str
    object_key: str
    sha256: str
    size_bytes: int


class CertificateInfo(BaseModel):
    subject: str | None = None
    valid_to: datetime | None = None


class SignResponse(BaseModel):
    status: str
    provider_request_id: str | None = None
    signed: SignedArtifact
    signature: SignedArtifact
    certificate: CertificateInfo | None = None


class VerifyRequest(BaseModel):
    provider: str
    input: StorageObjectRef
    signature: StorageObjectRef
    signed: StorageObjectRef | None = None
    meta: dict[str, Any] | None = None


class VerifyResponse(BaseModel):
    status: str
    verified: bool
    error_code: str | None = None
    certificate: CertificateInfo | None = None
