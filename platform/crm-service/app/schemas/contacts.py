from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from .common import ORMModel


class ContactCreate(BaseModel):
    full_name: str
    phone: str | None = None
    email: str | None = None
    position: str | None = None
    company: str | None = None
    tags: list[str] | None = None
    partner_id: str | None = None
    client_id: str | None = None
    status: str = "active"
    meta: dict = Field(default_factory=dict)


class ContactUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    email: str | None = None
    position: str | None = None
    company: str | None = None
    tags: list[str] | None = None
    partner_id: str | None = None
    client_id: str | None = None
    status: str | None = None
    meta: dict | None = None


class ContactOut(ORMModel):
    id: str
    tenant_id: str
    full_name: str
    phone: str | None
    email: str | None
    position: str | None
    company: str | None
    tags: list[str] | None
    partner_id: str | None
    client_id: str | None
    status: str
    meta: dict
    created_at: datetime
    updated_at: datetime


class ContactListOut(BaseModel):
    items: list[ContactOut]
    limit: int
    offset: int
    total: int
