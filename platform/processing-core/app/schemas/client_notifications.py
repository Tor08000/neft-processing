from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.models.client_notification import ClientNotificationSeverity


class ClientNotificationOut(BaseModel):
    id: str
    type: str
    severity: ClientNotificationSeverity
    title: str
    body: str
    link: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    created_at: datetime
    read_at: datetime | None = None


class ClientNotificationListResponse(BaseModel):
    items: list[ClientNotificationOut]
    next_cursor: str | None = None


class ClientNotificationUnreadCount(BaseModel):
    count: int


__all__ = [
    "ClientNotificationListResponse",
    "ClientNotificationOut",
    "ClientNotificationUnreadCount",
]
