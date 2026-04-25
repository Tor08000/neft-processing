from __future__ import annotations

from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import JSON

from app.db import Base
from app.db.types import ExistingEnum, new_uuid_str


class AbacPolicyVersionStatus(str, Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class AbacPolicyEffect(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"


JSON_TYPE = JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


class AbacPolicyVersion(Base):
    __tablename__ = "abac_policy_versions"

    id = Column(String(36), primary_key=True, default=new_uuid_str)
    name = Column(String(128), nullable=False)
    status = Column(ExistingEnum(AbacPolicyVersionStatus, name="abac_policy_version_status"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=True)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(String(64), nullable=True)


class AbacPolicy(Base):
    __tablename__ = "abac_policies"
    __table_args__ = (
        UniqueConstraint("version_id", "code", name="uq_abac_policy_version_code"),
        Index("ix_abac_policy_version", "version_id"),
        Index("ix_abac_policy_resource", "resource_type"),
    )

    id = Column(String(36), primary_key=True, default=new_uuid_str)
    version_id = Column(String(36), ForeignKey("abac_policy_versions.id"), nullable=False)
    code = Column(String(128), nullable=False)
    effect = Column(ExistingEnum(AbacPolicyEffect, name="abac_policy_effect"), nullable=False)
    priority = Column(Integer, nullable=False, server_default="0")
    actions = Column(JSON_TYPE, nullable=False)
    resource_type = Column(String(64), nullable=False)
    condition = Column(JSON_TYPE, nullable=True)
    reason_code = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


__all__ = [
    "AbacPolicy",
    "AbacPolicyEffect",
    "AbacPolicyVersion",
    "AbacPolicyVersionStatus",
]
