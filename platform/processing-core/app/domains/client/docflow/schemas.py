from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TimelineEventOut(BaseModel):
    id: str
    client_id: str | None
    application_id: str | None
    doc_id: str | None
    event_type: str
    actor_user_id: str | None
    actor_type: str | None
    created_at: datetime
    meta_json: dict = Field(default_factory=dict)


class TimelineResponse(BaseModel):
    items: list[TimelineEventOut]


class CreatePackageRequest(BaseModel):
    package_kind: str = "ONBOARDING_SIGNED_SET"
    application_id: str | None = None
    doc_ids: list[str] | None = None


class PackageOut(BaseModel):
    id: str
    client_id: str
    application_id: str | None
    package_kind: str
    status: str
    filename: str | None
    created_at: datetime


class PackagesResponse(BaseModel):
    items: list[PackageOut]


class NotificationOut(BaseModel):
    id: str
    channel: str
    title: str
    body: str
    event_type: str
    read_at: datetime | None
    created_at: datetime


class NotificationsResponse(BaseModel):
    unread_count: int
    items: list[NotificationOut]
