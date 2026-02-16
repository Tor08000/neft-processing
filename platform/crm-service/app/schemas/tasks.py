from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from .common import ORMModel


class TaskCreate(BaseModel):
    deal_id: str | None = None
    contact_id: str | None = None
    title: str
    description: str | None = None
    due_at: datetime | None = None
    assignee_user_id: str | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    due_at: datetime | None = None
    status: str | None = None
    assignee_user_id: str | None = None


class TaskOut(ORMModel):
    id: str
    tenant_id: str
    deal_id: str | None
    contact_id: str | None
    title: str
    description: str | None
    due_at: datetime | None
    status: str
    assignee_user_id: str | None
    created_by_user_id: str | None
    created_at: datetime
    updated_at: datetime


class TaskListOut(BaseModel):
    items: list[TaskOut]
    limit: int
    offset: int
    total: int
