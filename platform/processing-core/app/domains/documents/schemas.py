from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class DocumentCreateIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    doc_type: str | None = None
    description: str | None = Field(default=None, max_length=2000)


class DocumentFileOut(BaseModel):
    id: str
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


class DocumentOut(BaseModel):
    id: str
    client_id: str
    direction: str
    title: str
    doc_type: str | None = None
    description: str | None = None
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


class DocumentDetailsResponse(DocumentOut):
    pass
