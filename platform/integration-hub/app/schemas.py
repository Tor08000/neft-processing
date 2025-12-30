from __future__ import annotations

from pydantic import BaseModel, Field


class ArtifactRef(BaseModel):
    bucket: str
    object_key: str
    sha256: str | None = None


class CounterpartyRef(BaseModel):
    inn: str
    kpp: str
    edo_id: str | None = None


class DispatchRequest(BaseModel):
    document_id: str
    signature_id: str | None = None
    provider: str
    artifact: ArtifactRef
    counterparty: CounterpartyRef
    idempotency_key: str
    meta: dict = Field(default_factory=dict)


class DispatchResponse(BaseModel):
    status: str
    edo_document_id: str


class EdoDocumentResponse(BaseModel):
    edo_document_id: str
    document_id: str
    signature_id: str | None = None
    provider: str
    status: str
    provider_message_id: str | None = None
    provider_document_id: str | None = None
    attempt: int
    last_error: str | None = None


__all__ = [
    "ArtifactRef",
    "CounterpartyRef",
    "DispatchRequest",
    "DispatchResponse",
    "EdoDocumentResponse",
]
