from __future__ import annotations

from enum import Enum

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


class CRMClientStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    CLOSED = "CLOSED"


class CRMContractStatus(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    TERMINATED = "TERMINATED"


class CRMBillingMode(str, Enum):
    POSTPAID = "POSTPAID"
    PREPAID = "PREPAID"


class CRMTariffStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class CRMBillingPeriod(str, Enum):
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"


class CRMSubscriptionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    CANCELLED = "CANCELLED"


class CRMBillingCycle(str, Enum):
    MONTHLY = "MONTHLY"


class CRMSubscriptionChargeType(str, Enum):
    BASE_FEE = "BASE_FEE"
    OVERAGE = "OVERAGE"


class CRMUsageMetric(str, Enum):
    CARDS_COUNT = "CARDS_COUNT"
    VEHICLES_COUNT = "VEHICLES_COUNT"
    DRIVERS_COUNT = "DRIVERS_COUNT"
    FUEL_TX_COUNT = "FUEL_TX_COUNT"
    FUEL_VOLUME = "FUEL_VOLUME"
    LOGISTICS_ORDERS = "LOGISTICS_ORDERS"


class CRMSubscriptionSegmentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"


class CRMProfileStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class CRMFeatureFlagType(str, Enum):
    FUEL_ENABLED = "FUEL_ENABLED"
    LOGISTICS_ENABLED = "LOGISTICS_ENABLED"
    DOCUMENTS_ENABLED = "DOCUMENTS_ENABLED"
    RISK_BLOCKING_ENABLED = "RISK_BLOCKING_ENABLED"
    ACCOUNTING_EXPORT_ENABLED = "ACCOUNTING_EXPORT_ENABLED"


class CRMClient(Base):
    __tablename__ = "crm_clients"
    __table_args__ = (UniqueConstraint("tenant_id", "id", name="uq_crm_clients_tenant_id"),)

    id = Column(String(64), primary_key=True)
    tenant_id = Column(Integer, nullable=False)
    legal_name = Column(String(256), nullable=False)
    tax_id = Column(String(32), nullable=True)
    kpp = Column(String(32), nullable=True)
    country = Column(String(2), nullable=False)
    timezone = Column(String(64), nullable=False, default="Europe/Moscow", server_default="Europe/Moscow")
    status = Column(ExistingEnum(CRMClientStatus, name="crm_client_status"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    meta = Column(JSON, nullable=True)


class CRMContract(Base):
    __tablename__ = "crm_contracts"
    __table_args__ = (Index("ix_crm_contracts_client_status", "client_id", "status"),)

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False)
    client_id = Column(String(64), ForeignKey("crm_clients.id"), nullable=False)
    contract_number = Column(String(128), nullable=False)
    status = Column(ExistingEnum(CRMContractStatus, name="crm_contract_status"), nullable=False)
    valid_from = Column(DateTime(timezone=True), nullable=True)
    valid_to = Column(DateTime(timezone=True), nullable=True)
    billing_mode = Column(ExistingEnum(CRMBillingMode, name="crm_billing_mode"), nullable=False)
    currency = Column(String(3), nullable=False)
    risk_profile_id = Column(GUID(), ForeignKey("crm_risk_profiles.id"), nullable=True)
    limit_profile_id = Column(GUID(), ForeignKey("crm_limit_profiles.id"), nullable=True)
    documents_required = Column(Boolean, nullable=False, default=False, server_default="false")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    meta = Column(JSON, nullable=True)


class CRMTariffPlan(Base):
    __tablename__ = "crm_tariff_plans"

    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)
    description = Column(String(512), nullable=True)
    status = Column(ExistingEnum(CRMTariffStatus, name="crm_tariff_status"), nullable=False)
    billing_period = Column(ExistingEnum(CRMBillingPeriod, name="crm_billing_period"), nullable=False)
    base_fee_minor = Column(BigInteger, nullable=False, default=0)
    currency = Column(String(3), nullable=False)
    features = Column(JSON, nullable=True)
    limits_defaults = Column(JSON, nullable=True)
    definition = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CRMSubscription(Base):
    __tablename__ = "crm_subscriptions"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False)
    client_id = Column(String(64), ForeignKey("crm_clients.id"), nullable=False)
    tariff_plan_id = Column(String(64), ForeignKey("crm_tariff_plans.id"), nullable=False)
    status = Column(ExistingEnum(CRMSubscriptionStatus, name="crm_subscription_status"), nullable=False)
    billing_cycle = Column(ExistingEnum(CRMBillingCycle, name="crm_billing_cycle"), nullable=False)
    billing_day = Column(Integer, nullable=False, default=1, server_default="1")
    started_at = Column(DateTime(timezone=True), nullable=False)
    paused_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    meta = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CRMSubscriptionCharge(Base):
    __tablename__ = "crm_subscription_charges"
    __table_args__ = (Index("ix_crm_subscription_charges_period", "subscription_id", "billing_period_id"),)

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    subscription_id = Column(GUID(), ForeignKey("crm_subscriptions.id"), nullable=False)
    billing_period_id = Column(GUID(), ForeignKey("billing_periods.id"), nullable=False)
    charge_type = Column(ExistingEnum(CRMSubscriptionChargeType, name="crm_subscription_charge_type"), nullable=False)
    code = Column(String(64), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(BigInteger, nullable=False)
    amount = Column(BigInteger, nullable=False)
    currency = Column(String(3), nullable=False)
    source = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CRMUsageCounter(Base):
    __tablename__ = "crm_usage_counters"
    __table_args__ = (Index("ix_crm_usage_counters_period", "subscription_id", "billing_period_id"),)

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    subscription_id = Column(GUID(), ForeignKey("crm_subscriptions.id"), nullable=False)
    billing_period_id = Column(GUID(), ForeignKey("billing_periods.id"), nullable=False)
    metric = Column(ExistingEnum(CRMUsageMetric, name="crm_usage_metric"), nullable=False)
    value = Column(BigInteger, nullable=False)
    limit_value = Column(BigInteger, nullable=True)
    overage = Column(BigInteger, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CRMSubscriptionPeriodSegment(Base):
    __tablename__ = "crm_subscription_period_segments"
    __table_args__ = (
        UniqueConstraint(
            "subscription_id",
            "billing_period_id",
            "segment_start",
            "segment_end",
            name="uq_crm_subscription_segment_period",
        ),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    subscription_id = Column(GUID(), ForeignKey("crm_subscriptions.id"), nullable=False)
    billing_period_id = Column(GUID(), ForeignKey("billing_periods.id"), nullable=False)
    tariff_plan_id = Column(String(64), ForeignKey("crm_tariff_plans.id"), nullable=False)
    segment_start = Column(DateTime(timezone=True), nullable=False)
    segment_end = Column(DateTime(timezone=True), nullable=False)
    status = Column(ExistingEnum(CRMSubscriptionSegmentStatus, name="crm_subscription_segment_status"), nullable=False)
    days_count = Column(Integer, nullable=False)
    meta = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CRMLimitProfile(Base):
    __tablename__ = "crm_limit_profiles"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False)
    name = Column(String(128), nullable=False)
    status = Column(ExistingEnum(CRMProfileStatus, name="crm_profile_status"), nullable=False)
    definition = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CRMRiskProfile(Base):
    __tablename__ = "crm_risk_profiles"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False)
    name = Column(String(128), nullable=False)
    status = Column(ExistingEnum(CRMProfileStatus, name="crm_profile_status"), nullable=False)
    risk_policy_id = Column(String(64), nullable=False)
    threshold_set_id = Column(String(64), nullable=True)
    shadow_enabled = Column(Boolean, nullable=False, default=False, server_default="false")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    meta = Column(JSON, nullable=True)


class CRMFeatureFlag(Base):
    __tablename__ = "crm_feature_flags"
    __table_args__ = (UniqueConstraint("tenant_id", "client_id", "feature", name="uq_crm_feature_flag"),)

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False)
    client_id = Column(String(64), ForeignKey("crm_clients.id"), nullable=False)
    feature = Column(ExistingEnum(CRMFeatureFlagType, name="crm_feature_flag"), nullable=False)
    enabled = Column(Boolean, nullable=False, default=False, server_default="false")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    updated_by = Column(String(64), nullable=True)


__all__ = [
    "CRMBillingMode",
    "CRMBillingPeriod",
    "CRMBillingCycle",
    "CRMClient",
    "CRMClientStatus",
    "CRMContract",
    "CRMContractStatus",
    "CRMFeatureFlag",
    "CRMFeatureFlagType",
    "CRMLimitProfile",
    "CRMProfileStatus",
    "CRMRiskProfile",
    "CRMSubscription",
    "CRMSubscriptionStatus",
    "CRMSubscriptionCharge",
    "CRMSubscriptionChargeType",
    "CRMSubscriptionPeriodSegment",
    "CRMSubscriptionSegmentStatus",
    "CRMUsageCounter",
    "CRMUsageMetric",
    "CRMTariffPlan",
    "CRMTariffStatus",
]
