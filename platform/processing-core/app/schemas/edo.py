from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EdoAccountIn(BaseModel):
    id: str | None = None
    name: str
    org_inn: str | None = None
    box_id: str
    credentials_ref: str
    webhook_secret_ref: str
    is_active: bool = True


class EdoAccountOut(EdoAccountIn):
    id: str
    provider: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class EdoCounterpartyIn(BaseModel):
    id: str | None = None
    subject_type: str
    subject_id: str
    provider_counterparty_id: str
    provider_box_id: str | None = None
    display_name: str | None = None
    meta: dict[str, Any] | None = None


class EdoCounterpartyOut(EdoCounterpartyIn):
    id: str
    provider: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class EdoDocumentSendIn(BaseModel):
    document_registry_id: str
    subject_type: str
    subject_id: str
    counterparty_id: str
    document_kind: str
    account_id: str
    meta: dict[str, Any] | None = None
    dedupe_key: str = Field(..., description="Idempotency key for send")


class EdoDocumentOut(BaseModel):
    id: str
    provider: str
    account_id: str
    subject_type: str
    subject_id: str
    document_registry_id: str
    document_kind: str
    provider_doc_id: str | None = None
    provider_thread_id: str | None = None
    status: str
    counterparty_id: str
    send_dedupe_key: str
    attempts_send: int
    attempts_status: int
    next_retry_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class EdoTransitionOut(BaseModel):
    id: str
    edo_document_id: str
    from_status: str | None = None
    to_status: str
    reason_code: str | None = None
    payload: dict[str, Any] | None = None
    actor_type: str
    actor_id: str | None = None
    created_at: datetime


class EdoArtifactOut(BaseModel):
    id: str
    edo_document_id: str
    artifact_type: str
    document_registry_id: str
    content_hash: str | None = None
    provider_ref: dict[str, Any] | None = None
    created_at: datetime


class EdoSendResponse(BaseModel):
    document: EdoDocumentOut
    provider_doc_id: str | None
    status: str


__all__ = [
    "EdoAccountIn",
    "EdoAccountOut",
    "EdoCounterpartyIn",
    "EdoCounterpartyOut",
    "EdoDocumentSendIn",
    "EdoDocumentOut",
    "EdoTransitionOut",
    "EdoArtifactOut",
    "EdoSendResponse",
]
