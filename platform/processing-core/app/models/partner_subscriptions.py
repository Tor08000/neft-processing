from __future__ import annotations

from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import JSON

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


JSON_TYPE = JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


class PartnerSubscriptionStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CANCELED = "canceled"


class PartnerBillingCycle(str, Enum):
    MONTHLY = "monthly"
    YEARLY = "yearly"


class PartnerPlan(Base):
    __tablename__ = "partner_plans"

    plan_code = Column(String(64), primary_key=True)
    title = Column(String(255), nullable=False)
    description = Column(String(), nullable=True)
    base_commission = Column(Numeric(5, 2), nullable=False, server_default="0")
    monthly_fee = Column(Numeric(18, 2), nullable=False, server_default="0")
    features = Column(JSON_TYPE, nullable=True)
    limits = Column(JSON_TYPE, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class PartnerSubscription(Base):
    __tablename__ = "partner_subscriptions"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    partner_id = Column(GUID(), nullable=False, index=True)
    plan_code = Column(String(64), ForeignKey("partner_plans.plan_code"), nullable=False, index=True)
    status = Column(
        ExistingEnum(PartnerSubscriptionStatus, name="partner_subscription_status"),
        nullable=False,
        default=PartnerSubscriptionStatus.ACTIVE.value,
    )
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)
    billing_cycle = Column(
        ExistingEnum(PartnerBillingCycle, name="partner_subscription_billing_cycle"),
        nullable=False,
        default=PartnerBillingCycle.MONTHLY.value,
    )
    commission_rate = Column(Numeric(5, 2), nullable=True)
    features = Column(JSON_TYPE, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


__all__ = [
    "PartnerBillingCycle",
    "PartnerPlan",
    "PartnerSubscription",
    "PartnerSubscriptionStatus",
]
