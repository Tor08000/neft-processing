from __future__ import annotations

from enum import Enum

from sqlalchemy import (
    BigInteger,
    Boolean,
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.db import Base


class RiskRuleScope(str, Enum):
    """Scope of the risk rule target entity."""

    GLOBAL = "GLOBAL"
    CLIENT = "CLIENT"
    CARD = "CARD"
    TARIFF = "TARIFF"
    SEGMENT = "SEGMENT"


class RiskRuleAction(str, Enum):
    """Action to take when a rule is triggered."""

    HARD_DECLINE = "HARD_DECLINE"
    SOFT_FLAG = "SOFT_FLAG"
    TARIFF_LIMIT = "TARIFF_LIMIT"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    BLOCK = "BLOCK"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class RiskRule(Base):
    """Persisted risk rule with raw DSL payload."""

    __tablename__ = "risk_rules"

    id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
        index=True,
    )
    name = Column(String(128), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    scope = Column(SAEnum(RiskRuleScope), nullable=False, index=True)
    subject_ref = Column(String(128), nullable=True, index=True)
    action = Column(SAEnum(RiskRuleAction), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    priority = Column(Integer, nullable=False, default=100)
    dsl_payload = Column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    versions = relationship(
        "RiskRuleVersion",
        back_populates="rule",
        cascade="all, delete-orphan",
    )


class RiskRuleVersion(Base):
    """Historical version of a rule configuration."""

    __tablename__ = "risk_rule_versions"

    id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    rule_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("risk_rules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version = Column(Integer, nullable=False)
    dsl_payload = Column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
    )
    effective_from = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    rule = relationship("RiskRule", back_populates="versions")

    __table_args__ = (UniqueConstraint("rule_id", "version", name="uq_risk_rule_version"),)
