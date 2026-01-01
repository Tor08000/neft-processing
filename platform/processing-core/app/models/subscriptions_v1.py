from __future__ import annotations

import uuid
from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import BigInteger, JSON

from app.db import Base


class SubscriptionStatus(str, Enum):
    FREE = "FREE"
    ACTIVE = "ACTIVE"
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


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String(32), nullable=False, unique=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")
    billing_period_months = Column(Integer, nullable=False, server_default="0")
    price_cents = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=False, server_default="0")
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
    auto_renew = Column(Boolean, nullable=False, server_default="true")
    grace_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class RoleEntitlement(Base):
    __tablename__ = "role_entitlements"
    __table_args__ = (UniqueConstraint("plan_id", "role_code", name="uq_role_entitlement"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(String(64), ForeignKey("subscription_plans.id"), nullable=False, index=True)
    role_code = Column(String(64), nullable=False)
    entitlements = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
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
    "BonusRule",
    "ClientBonusState",
    "Achievement",
    "AchievementCondition",
    "Streak",
    "Bonus",
    "ClientProgress",
]
