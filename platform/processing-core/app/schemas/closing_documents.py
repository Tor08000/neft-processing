from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class ClosingPackageGenerateRequest(BaseModel):
    client_id: str
    date_from: date
    date_to: date
    version_mode: str = "AUTO"
    force_new_version: bool = False
    tenant_id: int = Field(..., description="Tenant identifier")


class ClosingPackageGenerateResponse(BaseModel):
    package_id: str
    version: int
    documents: list[dict[str, Any]]


class ClientDocumentSummary(BaseModel):
    id: str
    document_type: str
    status: str
    period_from: date
    period_to: date
    version: int
    number: str | None = None
    created_at: datetime
    pdf_hash: str | None = None
    risk: "ClientDocumentRiskSummary | None" = None


class ClientDocumentListResponse(BaseModel):
    items: list[ClientDocumentSummary]
    total: int
    limit: int
    offset: int


class ClientDocumentFile(BaseModel):
    file_type: str
    sha256: str
    size_bytes: int
    content_type: str
    created_at: datetime


class ClientDocumentEvent(BaseModel):
    id: str
    ts: datetime
    event_type: str
    action: str | None = None
    actor_type: str | None = None
    actor_id: str | None = None
    hash: str | None = None
    prev_hash: str | None = None


class ClientDocumentRiskSummary(BaseModel):
    state: str
    decided_at: datetime | None = None
    decision_id: str | None = None


class ClientDocumentAckDetails(BaseModel):
    ack_by_user_id: str | None = None
    ack_by_email: str | None = None
    ack_ip: str | None = None
    ack_user_agent: str | None = None
    ack_method: str | None = None
    ack_at: datetime | None = None


class ClientDocumentDetails(BaseModel):
    id: str
    document_type: str
    status: str
    period_from: date
    period_to: date
    version: int
    number: str | None = None
    created_at: datetime
    generated_at: datetime | None = None
    sent_at: datetime | None = None
    ack_at: datetime | None = None
    document_hash: str | None = None
    files: list[ClientDocumentFile]
    events: list[ClientDocumentEvent]
    ack_details: ClientDocumentAckDetails | None = None
    risk: ClientDocumentRiskSummary | None = None
    risk_explain: dict | None = None


class DocumentAcknowledgementResponse(BaseModel):
    acknowledged: bool
    ack_at: datetime | None = None
    document_type: str
    document_object_key: str | None = None
    document_hash: str | None = None


class ClosingPackageAckResponse(BaseModel):
    acknowledged: bool
    ack_at: datetime | None = None
