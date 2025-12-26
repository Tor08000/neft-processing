from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.models.documents import DocumentFileType
from app.models.legal_integrations import DocumentEnvelopeStatus, SignatureType


@dataclass(frozen=True)
class SigningPayload:
    document_id: str
    document_hash: str
    document_type: str
    client_id: str
    tenant_id: int


@dataclass(frozen=True)
class EnvelopeRef:
    provider: str
    envelope_id: str
    status: DocumentEnvelopeStatus


@dataclass(frozen=True)
class EnvelopeStatus:
    provider: str
    envelope_id: str
    status: DocumentEnvelopeStatus
    status_at: datetime | None = None
    error_message: str | None = None
    meta: dict | None = None


@dataclass(frozen=True)
class SignedArtifact:
    file_type: DocumentFileType
    signature_type: SignatureType
    payload: bytes
    content_type: str
    signed_at: datetime | None = None
    meta: dict | None = None


class ExternalLegalAdapter(Protocol):
    provider: str

    def send_for_signing(self, document_id: str, payload: SigningPayload) -> EnvelopeRef: ...

    def get_status(self, envelope_id: str) -> EnvelopeStatus: ...

    def fetch_signed_artifacts(self, envelope_id: str) -> list[SignedArtifact]: ...


__all__ = [
    "EnvelopeRef",
    "EnvelopeStatus",
    "ExternalLegalAdapter",
    "SignedArtifact",
    "SigningPayload",
]
