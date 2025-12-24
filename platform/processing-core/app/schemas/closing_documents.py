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


class ClientDocumentListResponse(BaseModel):
    items: list[ClientDocumentSummary]
    total: int
    limit: int
    offset: int


class DocumentAcknowledgementResponse(BaseModel):
    acknowledged: bool
    ack_at: datetime | None = None
    document_type: str
    document_object_key: str | None = None
    document_hash: str | None = None


class ClosingPackageAckResponse(BaseModel):
    acknowledged: bool
    ack_at: datetime | None = None
