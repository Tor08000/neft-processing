from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class LegalSubject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    id: str


class LegalRequiredItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    title: str
    locale: str
    required_version: str
    published_at: datetime | None
    effective_from: datetime
    content_hash: str
    accepted: bool
    accepted_at: datetime | None


class LegalRequiredResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: LegalSubject
    required: list[LegalRequiredItem]
    is_blocked: bool
    enabled: bool = True


class LegalDocumentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    code: str
    version: str
    title: str
    locale: str
    effective_from: datetime
    status: str
    content_type: str
    content: str
    content_hash: str
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class LegalAcceptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    version: str
    locale: str
    accepted: bool
    signature: dict[str, Any] | None = None
    meta: dict[str, Any] | None = None


class LegalDocumentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    version: str
    title: str
    locale: str = "ru"
    effective_from: datetime
    content_type: str
    content: str


class LegalDocumentUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    locale: str
    effective_from: datetime
    content_type: str
    content: str


class LegalDocumentListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[LegalDocumentResponse]


class LegalAcceptanceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    subject_type: str
    subject_id: str
    document_code: str
    document_version: str
    document_locale: str
    accepted_at: datetime
    ip: str | None
    user_agent: str | None
    acceptance_hash: str
    signature: dict[str, Any] | None
    meta: dict[str, Any] | None


class LegalAcceptanceListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[LegalAcceptanceResponse]


__all__ = [
    "LegalAcceptRequest",
    "LegalAcceptanceListResponse",
    "LegalAcceptanceResponse",
    "LegalDocumentCreateRequest",
    "LegalDocumentListResponse",
    "LegalDocumentResponse",
    "LegalDocumentUpdateRequest",
    "LegalRequiredItem",
    "LegalRequiredResponse",
    "LegalSubject",
]
