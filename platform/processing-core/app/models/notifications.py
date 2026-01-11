from __future__ import annotations

from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.types import JSON

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


class NotificationSubjectType(str, Enum):
    USER = "USER"
    CLIENT = "CLIENT"
    PARTNER = "PARTNER"


class NotificationChannel(str, Enum):
    EMAIL = "EMAIL"
    SMS = "SMS"
    TELEGRAM = "TELEGRAM"
    PUSH = "PUSH"
    WEBHOOK = "WEBHOOK"


class NotificationPriority(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"


class NotificationOutboxStatus(str, Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    DEAD = "DEAD"


class NotificationTemplateContentType(str, Enum):
    TEXT = "TEXT"
    HTML = "HTML"
    MARKDOWN = "MARKDOWN"


class NotificationDeliveryStatus(str, Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"


class NotificationMessage(Base):
    __tablename__ = "notification_outbox"
    __table_args__ = (Index("ix_notification_outbox_status", "status", "next_attempt_at"),)

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    event_type = Column(String(64), nullable=False)
    subject_type = Column(ExistingEnum(NotificationSubjectType, name="notification_subject_type"), nullable=False)
    subject_id = Column(String(64), nullable=False)
    channels = Column(JSON, nullable=True)
    template_code = Column(String(128), nullable=False)
    template_vars = Column(JSON, nullable=True)
    priority = Column(ExistingEnum(NotificationPriority, name="notification_priority"), nullable=False)
    dedupe_key = Column(String(256), nullable=False, unique=True)
    status = Column(ExistingEnum(NotificationOutboxStatus, name="notification_outbox_status"), nullable=False)
    attempts = Column(Integer, nullable=False, default=0, server_default="0")
    next_attempt_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, onupdate=func.now())


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (
        Index("ix_notification_prefs_subject_event", "subject_type", "subject_id", "event_type"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    subject_type = Column(ExistingEnum(NotificationSubjectType, name="notification_subject_type"), nullable=False)
    subject_id = Column(String(64), nullable=False)
    event_type = Column(String(64), nullable=False)
    channel = Column(ExistingEnum(NotificationChannel, name="notification_channel"), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True, server_default="true")
    address_override = Column(String(512), nullable=True)
    quiet_hours = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, onupdate=func.now())


class NotificationTemplate(Base):
    __tablename__ = "notification_templates"
    __table_args__ = (UniqueConstraint("code", name="uq_notification_templates_code"),)

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    code = Column(String(128), nullable=False, unique=True)
    event_type = Column(String(64), nullable=False)
    channel = Column(ExistingEnum(NotificationChannel, name="notification_channel"), nullable=False)
    locale = Column(String(16), nullable=False, default="ru", server_default="ru")
    subject = Column(String(256), nullable=True)
    body = Column(Text, nullable=False)
    content_type = Column(
        ExistingEnum(NotificationTemplateContentType, name="notification_template_content_type"),
        nullable=False,
    )
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    version = Column(Integer, nullable=False, default=1, server_default="1")
    required_vars = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        Index("ix_notification_deliveries_status", "status"),
        UniqueConstraint("message_id", "channel", "recipient", name="uq_notification_delivery_target"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    message_id = Column(GUID(), nullable=False, index=True)
    event_type = Column(String(64), nullable=False)
    channel = Column(ExistingEnum(NotificationChannel, name="notification_channel"), nullable=False)
    provider = Column(String(64), nullable=False)
    recipient = Column(String(256), nullable=False)
    status = Column(ExistingEnum(NotificationDeliveryStatus, name="notification_delivery_status"), nullable=False)
    attempt = Column(Integer, nullable=False, default=0, server_default="0")
    last_error = Column(Text, nullable=True)
    provider_message_id = Column(String(256), nullable=True)
    response_status = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, onupdate=func.now())


class NotificationWebPushSubscription(Base):
    __tablename__ = "notification_webpush_subscriptions"
    __table_args__ = (
        Index("ix_notification_webpush_subject", "subject_type", "subject_id"),
        UniqueConstraint("subject_type", "subject_id", "endpoint", name="uq_notification_webpush_endpoint"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    subject_type = Column(ExistingEnum(NotificationSubjectType, name="notification_subject_type"), nullable=False)
    subject_id = Column(String(64), nullable=False)
    endpoint = Column(String(1024), nullable=False)
    p256dh = Column(String(256), nullable=False)
    auth = Column(String(256), nullable=False)
    user_agent = Column(String(512), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


__all__ = [
    "NotificationChannel",
    "NotificationDelivery",
    "NotificationDeliveryStatus",
    "NotificationMessage",
    "NotificationOutboxStatus",
    "NotificationPreference",
    "NotificationPriority",
    "NotificationSubjectType",
    "NotificationTemplate",
    "NotificationTemplateContentType",
    "NotificationWebPushSubscription",
]
