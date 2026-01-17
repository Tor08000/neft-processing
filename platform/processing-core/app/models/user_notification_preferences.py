from __future__ import annotations

from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, Index, String, UniqueConstraint, func

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


class UserNotificationChannel(str, Enum):
    EMAIL = "EMAIL"
    IN_APP = "IN_APP"


class UserNotificationPreference(Base):
    __tablename__ = "user_notification_preferences"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "org_id",
            "event_type",
            "channel",
            name="uq_user_notification_preferences",
        ),
        Index("ix_user_notification_preferences_org_user", "org_id", "user_id"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    user_id = Column(String(64), nullable=False, index=True)
    org_id = Column(String(64), nullable=False, index=True)
    channel = Column(ExistingEnum(UserNotificationChannel, name="user_notification_channel"), nullable=False)
    event_type = Column(String(64), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, onupdate=func.now())


__all__ = ["UserNotificationChannel", "UserNotificationPreference"]
