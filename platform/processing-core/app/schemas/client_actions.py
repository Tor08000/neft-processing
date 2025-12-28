from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ReconciliationRequestCreate(BaseModel):
    date_from: date
    date_to: date
    note: str | None = Field(default=None, max_length=2000)


class ReconciliationRequestOut(BaseModel):
    id: str
    status: str
    date_from: date
    date_to: date
    requested_at: datetime | None = None
    generated_at: datetime | None = None
    sent_at: datetime | None = None
    acknowledged_at: datetime | None = None
    result_object_key: str | None = None
    result_bucket: str | None = None
    result_hash_sha256: str | None = None
    version: int | None = None
    note_client: str | None = None
    note_ops: str | None = None
    meta: dict | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ReconciliationRequestList(BaseModel):
    items: list[ReconciliationRequestOut]
    total: int
    limit: int
    offset: int


class DocumentAcknowledgementResponse(BaseModel):
    acknowledged: bool
    ack_at: datetime
    document_type: str
    document_object_key: str | None = None
    document_hash: str | None = None


class InvoiceMessageCreateRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)


class InvoiceMessageOut(BaseModel):
    id: str
    sender_type: str
    sender_user_id: str | None = None
    sender_email: str | None = None
    message: str
    created_at: datetime


class InvoiceMessageCreateResponse(BaseModel):
    thread_id: str
    message_id: str
    status: str


class InvoiceThreadMessagesResponse(BaseModel):
    thread_id: str | None = None
    status: str | None = None
    created_at: datetime | None = None
    closed_at: datetime | None = None
    last_message_at: datetime | None = None
    items: list[InvoiceMessageOut]
    total: int
    limit: int
    offset: int


class ReconciliationRequestStatusUpdate(BaseModel):
    status: str


class ReconciliationAttachResultRequest(BaseModel):
    object_key: str = Field(..., min_length=1, max_length=512)
    bucket: str | None = Field(default=None, max_length=255)
    result_hash_sha256: str = Field(..., min_length=64, max_length=64)


class InvoiceThreadCloseResponse(BaseModel):
    thread_id: str
    status: str
    closed_at: datetime | None = None


class AdminInvoiceMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
