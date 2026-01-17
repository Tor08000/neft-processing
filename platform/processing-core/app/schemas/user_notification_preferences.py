from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict

from app.models.user_notification_preferences import UserNotificationChannel


class UserNotificationEventType(str, Enum):
    EXPORT_READY = "export_ready"
    EXPORT_FAILED = "export_failed"
    SCHEDULED_REPORT_READY = "scheduled_report_ready"
    SUPPORT_TICKET_COMMENTED = "support_ticket_commented"
    SUPPORT_SLA_BREACHED = "support_sla_breached"
    SECURITY_EVENTS = "security_events"


class UserNotificationPreferenceItem(BaseModel):
    event_type: UserNotificationEventType
    channel: UserNotificationChannel
    enabled: bool


class UserNotificationPreferenceOut(UserNotificationPreferenceItem):
    user_id: str
    org_id: str
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class UserNotificationPreferencesResponse(BaseModel):
    items: list[UserNotificationPreferenceOut]


class UserNotificationPreferencesPatch(BaseModel):
    items: list[UserNotificationPreferenceItem]


__all__ = [
    "UserNotificationEventType",
    "UserNotificationPreferenceItem",
    "UserNotificationPreferenceOut",
    "UserNotificationPreferencesPatch",
    "UserNotificationPreferencesResponse",
]
