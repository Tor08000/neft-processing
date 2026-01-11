from __future__ import annotations

from enum import Enum

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    JSON,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import relationship

from app.db import Base


class UnifiedRuleScope(str, Enum):
    API = "API"
    FLEET = "FLEET"
    BILLING = "BILLING"
    DOCS = "DOCS"
    MARKETPLACE = "MARKETPLACE"
    AUTH = "AUTH"
    CRM = "CRM"
    GLOBAL = "GLOBAL"


class UnifiedRuleMetric(str, Enum):
    COUNT = "COUNT"
    AMOUNT = "AMOUNT"
    RPS = "RPS"
    DECLINES = "DECLINES"
    EXPORTS = "EXPORTS"
    CARDS_ISSUED = "CARDS_ISSUED"


class UnifiedRulePolicy(str, Enum):
    ALLOW = "ALLOW"
    HARD_DECLINE = "HARD_DECLINE"
    SOFT_DECLINE = "SOFT_DECLINE"
    REVIEW = "REVIEW"
    APPLY_LIMIT = "APPLY_LIMIT"
    APPLY_DISCOUNT = "APPLY_DISCOUNT"
    THROTTLE = "THROTTLE"
    STEP_UP_AUTH = "STEP_UP_AUTH"


class RuleSetStatus(str, Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ACTIVE = "ACTIVE"
    ROLLED_BACK = "ROLLED_BACK"
    ARCHIVED = "ARCHIVED"


class RuleSetVersion(Base):
    __tablename__ = "rule_set_versions"

    id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    name = Column(String(128), nullable=False, unique=True)
    scope = Column(SAEnum(UnifiedRuleScope), nullable=False, index=True)
    status = Column(SAEnum(RuleSetStatus), nullable=False, default=RuleSetStatus.DRAFT)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    published_at = Column(DateTime(timezone=True), nullable=True)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(String(256), nullable=True)
    notes = Column(Text, nullable=True)
    parent_version_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("rule_set_versions.id", ondelete="SET NULL"),
        nullable=True,
    )

    rules = relationship("UnifiedRule", back_populates="version", cascade="all, delete-orphan")


class RuleSetActive(Base):
    __tablename__ = "rule_set_active"

    scope = Column(SAEnum(UnifiedRuleScope), primary_key=True)
    version_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("rule_set_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    activated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    version = relationship("RuleSetVersion")


class RuleSetAudit(Base):
    __tablename__ = "rule_set_audits"

    id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    version_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("rule_set_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action = Column(String(32), nullable=False, index=True)
    performed_by = Column(String(256), nullable=True)
    payload = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    performed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class UnifiedRule(Base):
    __tablename__ = "unified_rules"

    id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    code = Column(String(128), nullable=False, unique=True)
    version_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("rule_set_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scope = Column(SAEnum(UnifiedRuleScope), nullable=False, index=True)
    selector = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    window = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    metric = Column(SAEnum(UnifiedRuleMetric), nullable=True)
    value = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    policy = Column(SAEnum(UnifiedRulePolicy), nullable=False)
    priority = Column(Integer, nullable=False, default=100)
    reason_code = Column(String(128), nullable=True)
    explain_template = Column(Text, nullable=True)
    tags = Column(ARRAY(String()).with_variant(JSON(), "sqlite"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    version = relationship("RuleSetVersion", back_populates="rules")

    __table_args__ = (UniqueConstraint("version_id", "code", name="uq_unified_rule_version_code"),)


__all__ = [
    "RuleSetActive",
    "RuleSetAudit",
    "RuleSetStatus",
    "RuleSetVersion",
    "UnifiedRule",
    "UnifiedRuleMetric",
    "UnifiedRulePolicy",
    "UnifiedRuleScope",
]
