from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class DocumentFileOut(BaseModel):
    id: str
    storage_key: str
    filename: str
    mime: str
    size: int
    sha256: str | None = None
    created_at: datetime


class DocumentListItem(BaseModel):
    id: str
    direction: str
    title: str
    doc_type: str | None = None
    status: str
    counterparty_name: str | None = None
    number: str | None = None
    date: date | None = None
    amount: Decimal | None = None
    currency: str | None = None
    created_at: datetime
    files_count: int


class DocumentsListResponse(BaseModel):
    items: list[DocumentListItem]
    total: int
    limit: int
    offset: int


class DocumentDetailsResponse(BaseModel):
    id: str
    client_id: str
    direction: str
    title: str
    doc_type: str | None = None
    status: str
    counterparty_name: str | None = None
    counterparty_inn: str | None = None
    number: str | None = None
    date: date | None = None
    amount: Decimal | None = None
    currency: str | None = None
    created_at: datetime
    updated_at: datetime
    files: list[DocumentFileOut]
