from __future__ import annotations

from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import JSON

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


class ServiceIdentityStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class ServiceTokenStatus(str, Enum):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class ServiceTokenAuditAction(str, Enum):
    ISSUED = "ISSUED"
    ROTATED = "ROTATED"
    REVOKED = "REVOKED"
    USED = "USED"
    DENIED = "DENIED"


class ServiceTokenActorType(str, Enum):
    ADMIN = "ADMIN"
    SYSTEM = "SYSTEM"


JSON_TYPE = JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


class ServiceIdentity(Base):
    __tablename__ = "service_identities"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    service_name = Column(String(128), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    status = Column(ExistingEnum(ServiceIdentityStatus, name="service_identity_status"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ServiceToken(Base):
    __tablename__ = "service_tokens"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    service_identity_id = Column(GUID(), ForeignKey("service_identities.id"), nullable=False, index=True)
    token_hash = Column(String(128), nullable=False, unique=True, index=True)
    prefix = Column(String(32), nullable=False, index=True)
    scopes = Column(JSON_TYPE, nullable=False)
    issued_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    rotated_from_id = Column(GUID(), ForeignKey("service_tokens.id"), nullable=True)
    rotation_grace_until = Column(DateTime(timezone=True), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(ExistingEnum(ServiceTokenStatus, name="service_token_status"), nullable=False)

    __table_args__ = (
        Index("ix_service_tokens_identity_status", "service_identity_id", "status"),
    )


class ServiceTokenAudit(Base):
    __tablename__ = "service_token_audit"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    service_token_id = Column(GUID(), ForeignKey("service_tokens.id"), nullable=True, index=True)
    action = Column(ExistingEnum(ServiceTokenAuditAction, name="service_token_audit_action"), nullable=False)
    actor_type = Column(ExistingEnum(ServiceTokenActorType, name="service_token_actor_type"), nullable=False)
    actor_id = Column(String(64), nullable=True)
    ip = Column(String(64), nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    meta = Column(JSON_TYPE, nullable=True)

    __table_args__ = (Index("ix_service_token_audit_action", "action"),)


__all__ = [
    "ServiceIdentity",
    "ServiceIdentityStatus",
    "ServiceToken",
    "ServiceTokenStatus",
    "ServiceTokenAudit",
    "ServiceTokenAuditAction",
    "ServiceTokenActorType",
]
