from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from .common import ORMModel


class CommentCreate(BaseModel):
    entity_type: str
    entity_id: str
    body: str


class CommentOut(ORMModel):
    id: str
    tenant_id: str
    entity_type: str
    entity_id: str
    body: str
    created_by_user_id: str | None
    created_at: datetime


class CommentListOut(BaseModel):
    items: list[CommentOut]
    limit: int
    offset: int
    total: int
