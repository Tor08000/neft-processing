from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, DateTime, Index, Integer, String, Text, JSON
from sqlalchemy.dialects import postgresql

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


class ActorType(str, Enum):
    USER = "USER"
    SERVICE = "SERVICE"
    SYSTEM = "SYSTEM"


JSONB_TYPE = postgresql.JSONB(none_as_null=True)
JSON_TYPE = JSON().with_variant(JSONB_TYPE, "postgresql")

ROLE_ARRAY = postgresql.ARRAY(String()).with_variant(JSON(), "sqlite")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    ts = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    tenant_id = Column(Integer, nullable=True, index=True)

    actor_type = Column(ExistingEnum(ActorType, name="audit_actor_type"), nullable=False)
    actor_id = Column(Text, nullable=True)
    actor_email = Column(Text, nullable=True)
    actor_roles = Column(ROLE_ARRAY, nullable=True)

    ip = Column(postgresql.INET().with_variant(String(64), "sqlite"), nullable=True)
    user_agent = Column(Text, nullable=True)
    request_id = Column(Text, nullable=True)
    trace_id = Column(Text, nullable=True)

    event_type = Column(Text, nullable=False, index=True)
    entity_type = Column(Text, nullable=False, index=True)
    entity_id = Column(Text, nullable=False, index=True)
    action = Column(Text, nullable=False)

    before = Column(JSON_TYPE, nullable=True)
    after = Column(JSON_TYPE, nullable=True)
    diff = Column(JSON_TYPE, nullable=True)
    external_refs = Column(JSON_TYPE, nullable=True)

    reason = Column(Text, nullable=True)
    attachment_key = Column(Text, nullable=True)

    prev_hash = Column(Text, nullable=False)
    hash = Column(Text, nullable=False, unique=True)

    __table_args__ = (
        Index("ix_audit_log_ts_desc", ts.desc()),
        Index("ix_audit_log_entity", "entity_type", "entity_id"),
        Index("ix_audit_log_event_ts", "event_type", "ts"),
        Index("ix_audit_log_external_refs_gin", "external_refs", postgresql_using="gin"),
    )


__all__ = ["ActorType", "AuditLog"]
