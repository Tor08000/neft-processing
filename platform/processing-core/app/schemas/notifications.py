from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.notifications import (
    NotificationChannel,
    NotificationDeliveryStatus,
    NotificationOutboxStatus,
    NotificationPriority,
    NotificationSubjectType,
    NotificationTemplateContentType,
)


class NotificationPreferenceIn(BaseModel):
    subject_type: NotificationSubjectType
    subject_id: str
    event_type: str
    channel: NotificationChannel
    enabled: bool = True
    address_override: str | None = None
    quiet_hours: dict[str, Any] | None = None


class NotificationPreferenceOut(NotificationPreferenceIn):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationTemplateIn(BaseModel):
    code: str
    event_type: str
    channel: NotificationChannel
    locale: str = "ru"
    subject: str | None = None
    body: str
    content_type: NotificationTemplateContentType = NotificationTemplateContentType.TEXT
    is_active: bool = True
    version: int = 1
    required_vars: list[str] | None = None


class NotificationTemplateOut(NotificationTemplateIn):
    id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationDeliveryOut(BaseModel):
    id: str
    message_id: str
    event_type: str
    channel: NotificationChannel
    provider: str
    recipient: str
    status: NotificationDeliveryStatus
    attempt: int
    last_error: str | None
    provider_message_id: str | None
    response_status: int | None
    response_body: str | None
    sent_at: datetime | None
    delivered_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationMessageIn(BaseModel):
    event_type: str
    subject_type: NotificationSubjectType
    subject_id: str
    channels: list[NotificationChannel] | None = None
    template_code: str
    template_vars: dict[str, Any] | None = None
    priority: NotificationPriority = NotificationPriority.NORMAL
    dedupe_key: str


class NotificationMessageOut(NotificationMessageIn):
    id: str
    status: NotificationOutboxStatus
    attempts: int
    next_attempt_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WebPushSubscriptionIn(BaseModel):
    subject_type: NotificationSubjectType
    subject_id: str
    endpoint: str
    p256dh: str
    auth: str
    user_agent: str | None = None


class WebPushSubscriptionOut(WebPushSubscriptionIn):
    id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WebPushSubscriptionLookup(BaseModel):
    subject_type: NotificationSubjectType
    subject_id: str
    endpoint: str
