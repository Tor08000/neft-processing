from __future__ import annotations

import uuid
from enum import Enum

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from app.db import Base


class PlanBillingPeriod(str, Enum):
    MONTHLY = "monthly"
    ANNUAL = "annual"


class PlanFeatureCode(str, Enum):
    FLEET_CARDS = "fleet_cards"
    GROUPS = "groups"
    LIMITS = "limits"
    ALERTS = "alerts"
    WEBHOOK = "webhook"
    PUSH = "push"
    WHITE_LABEL = "white_label"
    SLA = "sla"


class UsageMetric(str, Enum):
    CARDS_ACTIVE = "cards_active"
    TRANSACTIONS = "transactions"
    ALERTS_SENT = "alerts_sent"
    EXPORTS = "exports"


class CommercialPlan(Base):
    __tablename__ = "plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(32), nullable=False, unique=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    base_price_monthly = Column(Numeric, nullable=False, server_default="0")
    currency = Column(String(3), nullable=False, server_default="RUB")
    billing_period = Column(SAEnum(PlanBillingPeriod, name="plan_billing_period"), nullable=False)
    active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PlanFeature(Base):
    __tablename__ = "plan_features"
    __table_args__ = (UniqueConstraint("plan_id", "feature", name="uq_plan_feature"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("plans.id"), nullable=False, index=True)
    feature = Column(SAEnum(PlanFeatureCode, name="plan_feature_code"), nullable=False, index=True)
    enabled = Column(Boolean, nullable=False, server_default="true")
    limits = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UsageCounter(Base):
    __tablename__ = "usage_counters"
    __table_args__ = (
        UniqueConstraint("client_id", "metric", "period_start", "period_end", name="uq_usage_counter"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    metric = Column(SAEnum(UsageMetric, name="usage_metric"), nullable=False, index=True)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    value = Column(Numeric, nullable=False, server_default="0")


class ClientBranding(Base):
    __tablename__ = "client_branding"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False, unique=True, index=True)
    logo_url = Column(String, nullable=True)
    primary_color = Column(String(32), nullable=True)
    secondary_color = Column(String(32), nullable=True)
    support_email = Column(String(255), nullable=True)
    portal_domain = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ClientOnboardingState(Base):
    __tablename__ = "client_onboarding_state"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False, unique=True, index=True)
    current_step = Column(String(64), nullable=True)
    completed_steps = Column(JSONB, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
