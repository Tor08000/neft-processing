from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from .common import ORMModel


class DealCreate(BaseModel):
    pipeline_id: str
    stage_id: str
    title: str
    amount: float | None = None
    currency: str = "RUB"
    client_id: str | None = None
    partner_id: str | None = None
    contact_id: str | None = None
    owner_user_id: str | None = None
    priority: int = 0
    expected_close_date: date | None = None
    meta: dict = Field(default_factory=dict)


class DealUpdate(BaseModel):
    title: str | None = None
    amount: float | None = None
    currency: str | None = None
    client_id: str | None = None
    partner_id: str | None = None
    contact_id: str | None = None
    owner_user_id: str | None = None
    priority: int | None = None
    expected_close_date: date | None = None
    close_reason: str | None = None
    meta: dict | None = None


class MoveStageIn(BaseModel):
    stage_id: str


class MarkWonIn(BaseModel):
    amount: float | None = None
    close_reason: str | None = None


class MarkLostIn(BaseModel):
    close_reason: str


class DealOut(ORMModel):
    id: str
    tenant_id: str
    pipeline_id: str
    stage_id: str
    title: str
    amount: float | None
    currency: str
    client_id: str | None
    partner_id: str | None
    contact_id: str | None
    owner_user_id: str | None
    priority: int
    status: str
    close_reason: str | None
    expected_close_date: date | None
    meta: dict
    created_at: datetime
    updated_at: datetime


class DealListOut(BaseModel):
    items: list[DealOut]
    limit: int
    offset: int
    total: int
