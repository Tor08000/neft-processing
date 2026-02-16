from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class ContactIn(BaseModel):
    entity_type: str
    entity_id: str
    first_name: str
    last_name: str
    email: str
    phone: str | None = None
    position: str | None = None
    status: str = "active"
    owner_id: str


class ContactPatch(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    position: str | None = None
    status: str | None = None
    owner_id: str | None = None


class PipelineIn(BaseModel):
    name: str


class StageIn(BaseModel):
    pipeline_id: str
    name: str
    position: int
    probability: int


class DealIn(BaseModel):
    entity_type: str
    entity_id: str
    contact_id: str | None = None
    pipeline_id: str
    stage_id: str
    title: str
    amount: float
    currency: str = "USD"
    owner_id: str
    expected_close_date: date | None = None


class DealPatch(BaseModel):
    title: str | None = None
    amount: float | None = None
    currency: str | None = None
    owner_id: str | None = None
    expected_close_date: date | None = None


class MoveStageIn(BaseModel):
    stage_id: str


class CloseDealIn(BaseModel):
    status: str


class TaskIn(BaseModel):
    related_type: str
    related_id: str
    title: str
    description: str | None = None
    due_date: datetime | None = None
    status: str = "open"
    priority: str | None = None
    assigned_to: str


class TaskPatch(BaseModel):
    title: str | None = None
    description: str | None = None
    due_date: datetime | None = None
    status: str | None = None
    priority: str | None = None
    assigned_to: str | None = None


class CommentIn(BaseModel):
    message: str
