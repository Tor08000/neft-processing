from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, DateTime, Index, JSON, String, Text
from sqlalchemy.dialects import postgresql

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


class ClientNotificationSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


ROLE_ARRAY = postgresql.ARRAY(String()).with_variant(JSON(), "sqlite")
JSONB_TYPE = postgresql.JSONB(none_as_null=True)
JSON_TYPE = JSON().with_variant(JSONB_TYPE, "postgresql")


class ClientNotification(Base):
    __tablename__ = "client_notifications"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    org_id = Column(GUID(), nullable=False, index=True)
    target_user_id = Column(String(128), nullable=True, index=True)
    target_roles = Column(ROLE_ARRAY, nullable=True)
    type = Column(String(64), nullable=False, index=True)
    severity = Column(
        ExistingEnum(ClientNotificationSeverity, name="client_notification_severity"),
        nullable=False,
        default=ClientNotificationSeverity.INFO,
        index=True,
    )
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    link = Column(String(255), nullable=True)
    entity_type = Column(String(64), nullable=True)
    entity_id = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    read_at = Column(DateTime(timezone=True), nullable=True)
    delivered_email_at = Column(DateTime(timezone=True), nullable=True)
    meta_json = Column(JSON_TYPE, nullable=True)

    __table_args__ = (
        Index("ix_client_notifications_org_read", "org_id", "read_at"),
        Index("ix_client_notifications_org_created", "org_id", "created_at"),
    )


__all__ = ["ClientNotification", "ClientNotificationSeverity"]
