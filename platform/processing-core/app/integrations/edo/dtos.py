from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.models.edo import EdoDocumentStatus


@dataclass(frozen=True)
class EdoSendRequest:
    edo_document_id: str
    account_id: str
    document_registry_id: str
    counterparty_id: str
    doc_type: str
    meta: dict[str, Any] | None = None


@dataclass(frozen=True)
class EdoSendResult:
    provider_doc_id: str
    provider_message_id: str | None
    status: EdoDocumentStatus
    raw: dict[str, Any]


@dataclass(frozen=True)
class EdoStatusRequest:
    provider_doc_id: str
    account_id: str


@dataclass(frozen=True)
class EdoStatusResult:
    status: EdoDocumentStatus
    provider_status: str
    raw: dict[str, Any]
    signed_artifacts: list[dict[str, Any]] | None = None


@dataclass(frozen=True)
class EdoInboundRequest:
    provider_event_id: str
    headers: dict[str, Any]
    payload: dict[str, Any]
    received_at: datetime


@dataclass(frozen=True)
class EdoReceiveResult:
    handled: bool
    updated_documents: list[str]
    raw: dict[str, Any]


@dataclass(frozen=True)
class EdoRevokeRequest:
    provider_doc_id: str
    account_id: str
    reason: str | None


@dataclass(frozen=True)
class EdoRevokeResult:
    status: EdoDocumentStatus
    raw: dict[str, Any]


__all__ = [
    "EdoSendRequest",
    "EdoSendResult",
    "EdoStatusRequest",
    "EdoStatusResult",
    "EdoInboundRequest",
    "EdoReceiveResult",
    "EdoRevokeRequest",
    "EdoRevokeResult",
]
