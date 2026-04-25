from __future__ import annotations

import datetime as dt
from decimal import Decimal

from pydantic import BaseModel, Field


class DocumentCreateIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    doc_type: str | None = None
    description: str | None = Field(default=None, max_length=2000)


class AdminInboundDocumentCreateIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    category: str | None = None
    description: str | None = Field(default=None, max_length=2000)
    attach_mode: str = Field(default="UPLOAD")


class DocumentFileOut(BaseModel):
    id: str
    filename: str
    mime: str
    kind: str | None = None
    size: int
    sha256: str | None = None
    created_at: dt.datetime


class DocumentListItem(BaseModel):
    id: str
    direction: str
    title: str
    category: str | None = None
    doc_type: str | None = None
    status: str
    sender_type: str | None = None
    sender_name: str | None = None
    counterparty_name: str | None = None
    number: str | None = None
    date: dt.date | None = None
    amount: Decimal | None = None
    currency: str | None = None
    created_at: dt.datetime
    files_count: int
    requires_action: bool = False
    action_code: str | None = None
    ack_at: dt.datetime | None = None
    edo_status: str | None = None
    period_from: dt.date | None = None
    period_to: dt.date | None = None


class DocumentsListResponse(BaseModel):
    items: list[DocumentListItem]
    total: int
    limit: int
    offset: int


class DocumentAckDetailsOut(BaseModel):
    ack_by_user_id: str | None = None
    ack_by_email: str | None = None
    ack_ip: str | None = None
    ack_user_agent: str | None = None
    ack_method: str | None = None
    ack_at: dt.datetime | None = None


class DocumentRiskSummaryOut(BaseModel):
    state: str
    decided_at: dt.datetime | None = None
    decision_id: str | None = None


class DocumentOut(BaseModel):
    id: str
    client_id: str
    direction: str
    title: str
    category: str | None = None
    doc_type: str | None = None
    description: str | None = None
    status: str
    sender_type: str | None = None
    sender_name: str | None = None
    counterparty_name: str | None = None
    counterparty_inn: str | None = None
    number: str | None = None
    date: dt.date | None = None
    amount: Decimal | None = None
    currency: str | None = None
    created_at: dt.datetime
    updated_at: dt.datetime
    signed_by_client_at: dt.datetime | None = None
    signed_by_client_user_id: str | None = None
    requires_action: bool = False
    action_code: str | None = None
    ack_at: dt.datetime | None = None
    ack_details: DocumentAckDetailsOut | None = None
    document_hash_sha256: str | None = None
    risk: DocumentRiskSummaryOut | None = None
    risk_explain: dict | None = None
    files: list[DocumentFileOut]


class DocumentDetailsResponse(DocumentOut):
    pass


class DocumentSignIn(BaseModel):
    consent_text_version: str = Field(min_length=1, max_length=32)
    checkbox_confirmed: bool
    signer_full_name: str | None = Field(default=None, max_length=255)
    signer_position: str | None = Field(default=None, max_length=255)


class DocumentSignatureOut(BaseModel):
    id: str
    document_id: str
    signer_user_id: str
    signer_type: str
    signature_method: str
    consent_text_version: str
    document_hash_sha256: str
    signed_at: dt.datetime
    ip: str | None = None
    user_agent: str | None = None
    payload: dict | None = None
    created_at: dt.datetime


class DocumentSignResult(BaseModel):
    document_id: str
    status: str
    signed_by_client_at: dt.datetime | None = None
    signature_id: str
    document_hash_sha256: str


class EdoStateOut(BaseModel):
    id: str
    document_id: str
    client_id: str
    provider: str | None = None
    provider_mode: str
    edo_status: str
    edo_message_id: str | None = None
    last_error_code: str | None = None
    last_error_message: str | None = None
    attempts_send: int
    attempts_poll: int
    next_poll_at: dt.datetime | None = None
    last_polled_at: dt.datetime | None = None
    last_status_at: dt.datetime | None = None
    created_at: dt.datetime
    updated_at: dt.datetime
