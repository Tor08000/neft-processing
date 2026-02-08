from __future__ import annotations

from enum import Enum

from sqlalchemy import Column, DateTime, Text, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import JSON

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str

JSON_TYPE = JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


class MarketplaceModerationEntityType(str, Enum):
    PRODUCT = "PRODUCT"
    SERVICE = "SERVICE"
    OFFER = "OFFER"


class MarketplaceModerationAction(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    SUSPEND = "SUSPEND"


class MarketplaceModerationAudit(Base):
    __tablename__ = "marketplace_moderation_audit"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    entity_type = Column(
        ExistingEnum(MarketplaceModerationEntityType, name="marketplace_moderation_entity_type"),
        nullable=False,
    )
    entity_id = Column(GUID(), nullable=False, index=True)
    actor_user_id = Column(GUID(), nullable=True)
    actor_role = Column(Text, nullable=True)
    action = Column(
        ExistingEnum(MarketplaceModerationAction, name="marketplace_moderation_action"),
        nullable=False,
    )
    reason_code = Column(Text, nullable=True)
    comment = Column(Text, nullable=True)
    before_status = Column(Text, nullable=True)
    after_status = Column(Text, nullable=True)
    meta = Column(JSON_TYPE, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


__all__ = [
    "MarketplaceModerationAction",
    "MarketplaceModerationAudit",
    "MarketplaceModerationEntityType",
]
