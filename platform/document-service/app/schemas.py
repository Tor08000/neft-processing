from __future__ import annotations

from datetime import date
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
