from __future__ import annotations

import uuid
from enum import Enum

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import synonym
from sqlalchemy.types import JSON

from app.db import Base


class SubscriptionStatus(str, Enum):
    FREE = "FREE"
    ACTIVE = "ACTIVE"
    PAST_DUE = "PAST_DUE"
    SUSPENDED = "SUSPENDED"
    PENDING = "PENDING"
    PAUSED = "PAUSED"
    GRACE = "GRACE"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class SubscriptionModuleCode(str, Enum):
    FUEL_CORE = "FUEL_CORE"
    AI_ASSISTANT = "AI_ASSISTANT"
    EXPLAIN = "EXPLAIN"
    PENALTIES = "PENALTIES"
    MARKETPLACE = "MARKETPLACE"
    ANALYTICS = "ANALYTICS"
    SLA = "SLA"
    BONUSES = "BONUSES"
    BILLING = "BILLING"
    DOCS = "DOCS"
    FLEET = "FLEET"
    CRM = "CRM"


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String(32), nullable=False, unique=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")
    billing_period_months = Column(Integer, nullable=False, server_default="0")
    price_cents = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=False, server_default="0")
    discount_percent = Column(Integer, nullable=False, server_default="0")
    bonus_multiplier_override = Column(Float, nullable=True)
    currency = Column(String(3), nullable=False, server_default="RUB")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class SubscriptionPlanModule(Base):
    __tablename__ = "subscription_plan_modules"
    __table_args__ = (UniqueConstraint("plan_id", "module_code", name="uq_subscription_plan_module"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(String(64), ForeignKey("subscription_plans.id"), nullable=False, index=True)
    module_code = Column(SAEnum(SubscriptionModuleCode, name="subscription_module_code"), nullable=False, index=True)
    enabled = Column(Boolean, nullable=False, server_default="true")
    tier = Column(String(32), nullable=True)
    limits = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ClientSubscription(Base):
    __tablename__ = "client_subscriptions"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(Integer, nullable=False, index=True)
    client_id = Column(String(64), nullable=False, index=True)
    plan_id = Column(String(64), ForeignKey("subscription_plans.id"), nullable=False, index=True)
    status = Column(SAEnum(SubscriptionStatus, name="subscription_status"), nullable=False, index=True)
    start_at = Column(DateTime(timezone=True), nullable=False)
    end_at = Column(DateTime(timezone=True), nullable=True)
    billing_anchor_day = Column(Integer, nullable=False, server_default="1")
    current_price_version_id = Column(String(36), ForeignKey("price_versions.id"), nullable=True)
    billing_account_id = Column(String(64), nullable=True)
    audit_event_id = Column(String(64), nullable=True)
    auto_renew = Column(Boolean, nullable=False, server_default="true")
    grace_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    started_at = synonym("start_at")
    ends_at = synonym("end_at")


class RoleEntitlement(Base):
    __tablename__ = "role_entitlements"
    __table_args__ = (UniqueConstraint("plan_id", "role_code", name="uq_role_entitlement"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(String(64), ForeignKey("subscription_plans.id"), nullable=False, index=True)
    role_code = Column(String(64), nullable=False)
    entitlements = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class SubscriptionPlanLimit(Base):
    __tablename__ = "subscription_plan_limits"
    __table_args__ = (UniqueConstraint("plan_id", "limit_code", "period", name="uq_subscription_plan_limit"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(String(64), ForeignKey("subscription_plans.id"), nullable=False, index=True)
    limit_code = Column(String(64), nullable=False, index=True)
    value_int = Column(BigInteger, nullable=True)
    value_decimal = Column(Numeric(18, 6), nullable=True)
    value_text = Column(String(128), nullable=True)
    value_json = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    period = Column(String(16), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class SubscriptionEventType(str, Enum):
    ASSIGNED = "ASSIGNED"
    UPGRADED = "UPGRADED"
    DOWNGRADED = "DOWNGRADED"
    RENEWED = "RENEWED"
    CANCELLED = "CANCELLED"
    PRORATED = "PRORATED"
    PRICE_VERSION_CHANGED = "PRICE_VERSION_CHANGED"
    PRICE_VERSION_CAPTURED = "PRICE_VERSION_CAPTURED"


class SubscriptionEvent(Base):
    __tablename__ = "subscription_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(String(64), nullable=False, index=True)
    event_type = Column(SAEnum(SubscriptionEventType, name="subscription_event_type"), nullable=False)
    payload = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    actor_id = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SubscriptionUsageCounter(Base):
    __tablename__ = "subscription_usage_counters"
    __table_args__ = (UniqueConstraint("client_id", "counter_code", "period_key", name="uq_subscription_usage"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(String(64), nullable=False, index=True)
    counter_code = Column(String(64), nullable=False, index=True)
    period_key = Column(String(16), nullable=False, index=True)
    value = Column(BigInteger, nullable=False, server_default="0")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class BonusRule(Base):
    __tablename__ = "bonus_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(String(64), ForeignKey("subscription_plans.id"), nullable=True, index=True)
    rule_code = Column(String(128), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    condition = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    reward = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    enabled = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ClientBonusState(Base):
    __tablename__ = "client_bonus_state"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    client_id = Column(String(64), nullable=False, index=True)
    active_bonuses = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    streaks = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    achievements = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Achievement(Base):
    __tablename__ = "achievements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(128), nullable=False, unique=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")
    is_hidden = Column(Boolean, nullable=False, server_default="false")
    module_code = Column(String(64), nullable=True)
    plan_codes = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class AchievementCondition(Base):
    __tablename__ = "achievement_conditions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    achievement_id = Column(Integer, ForeignKey("achievements.id"), nullable=False, index=True)
    condition = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Streak(Base):
    __tablename__ = "streaks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(128), nullable=False, unique=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")
    module_code = Column(String(64), nullable=True)
    plan_codes = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    condition = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Bonus(Base):
    __tablename__ = "bonuses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(128), nullable=False, unique=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    reward = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")
    plan_codes = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ClientProgress(Base):
    __tablename__ = "client_progress"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    client_id = Column(String(64), nullable=False, index=True)
    achievements = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    streaks = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    bonuses = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


__all__ = [
    "SubscriptionStatus",
    "SubscriptionModuleCode",
    "SubscriptionPlan",
    "SubscriptionPlanModule",
    "ClientSubscription",
    "RoleEntitlement",
    "SubscriptionPlanLimit",
    "SubscriptionEvent",
    "SubscriptionEventType",
    "SubscriptionUsageCounter",
    "BonusRule",
    "ClientBonusState",
    "Achievement",
    "AchievementCondition",
    "Streak",
    "Bonus",
    "ClientProgress",
]
