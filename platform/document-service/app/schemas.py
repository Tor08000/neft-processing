from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RenderRequest(BaseModel):
    template_code: str | None = None
    variables: dict[str, Any] | None = None
    template_kind: str | None = Field(default=None, examples=["HTML"])
    template_id: str | None = None
    template_html: str | None = None
    data: dict[str, Any] | None = None
    output_format: str = Field(..., examples=["PDF"])
    tenant_id: int
    client_id: str | None = None
    idempotency_key: str
    locale: str | None = None
    meta: dict[str, Any] | None = None
    doc_id: str
    doc_type: str
    version: int = Field(ge=1)
    document_date: date | None = None

    @model_validator(mode="after")
    def _ensure_template_payload(self) -> "RenderRequest":
        if self.template_code:
            return self
        if self.template_html and self.template_kind:
            return self
        raise ValueError("template_code or template_html/template_kind must be provided")


class RenderResponse(BaseModel):
    bucket: str
    object_key: str
    sha256: str
    size_bytes: int
    content_type: str
    version: int
    template_hash: str | None = None
    schema_hash: str | None = None


class TemplateListItem(BaseModel):
    code: str
    title: str
    engine: str
    repo_path: str
    schema_path: str
    template_hash: str
    schema_hash: str
    version: str
    status: str


class TemplateDetail(TemplateListItem):
    model_config = ConfigDict(populate_by_name=True)

    schema_: dict[str, Any] = Field(alias="schema")


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
