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
    Text,
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


class CRMSubscriptionSegmentReason(str, Enum):
    START = "START"
    UPGRADE = "UPGRADE"
    DOWNGRADE = "DOWNGRADE"
    PAUSE = "PAUSE"
    RESUME = "RESUME"
    CANCEL = "CANCEL"


class CRMProfileStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class CRMFeatureFlagType(str, Enum):
    FUEL_ENABLED = "FUEL_ENABLED"
    LOGISTICS_ENABLED = "LOGISTICS_ENABLED"
    DOCUMENTS_ENABLED = "DOCUMENTS_ENABLED"
    RISK_BLOCKING_ENABLED = "RISK_BLOCKING_ENABLED"
    ACCOUNTING_EXPORT_ENABLED = "ACCOUNTING_EXPORT_ENABLED"
    SUBSCRIPTION_METER_FUEL_ENABLED = "SUBSCRIPTION_METER_FUEL_ENABLED"
    CASES_ENABLED = "CASES_ENABLED"


class CRMLeadStatus(str, Enum):
    NEW = "NEW"
    QUALIFIED = "QUALIFIED"
    DISQUALIFIED = "DISQUALIFIED"
    CONVERTED = "CONVERTED"


class CRMDealStage(str, Enum):
    DISCOVERY = "DISCOVERY"
    PROPOSAL = "PROPOSAL"
    NEGOTIATION = "NEGOTIATION"
    WON = "WON"
    LOST = "LOST"


class CRMDealEventType(str, Enum):
    STAGE_CHANGED = "STAGE_CHANGED"
    NOTE = "NOTE"
    CALL = "CALL"
    EMAIL = "EMAIL"
    TASK_CREATED = "TASK_CREATED"
    CONTRACT_LINKED = "CONTRACT_LINKED"


class CRMTaskSubjectType(str, Enum):
    LEAD = "LEAD"
    DEAL = "DEAL"
    CLIENT = "CLIENT"
    CONTRACT = "CONTRACT"
    TICKET = "TICKET"


class CRMTaskStatus(str, Enum):
    OPEN = "OPEN"
    DONE = "DONE"
    CANCELLED = "CANCELLED"


class CRMTaskPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class CRMClientProfileStatus(str, Enum):
    PROSPECT = "PROSPECT"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    TERMINATED = "TERMINATED"


class CRMClientRiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ClientOnboardingStateEnum(str, Enum):
    LEAD_CREATED = "LEAD_CREATED"
    QUALIFIED_CLIENT_CREATED = "QUALIFIED_CLIENT_CREATED"
    LEGAL_ACCEPTANCE_PENDING = "LEGAL_ACCEPTANCE_PENDING"
    LEGAL_ACCEPTED = "LEGAL_ACCEPTED"
    CONTRACT_PENDING = "CONTRACT_PENDING"
    CONTRACT_SIGNED = "CONTRACT_SIGNED"
    SUBSCRIPTION_ASSIGNED = "SUBSCRIPTION_ASSIGNED"
    LIMITS_APPLIED = "LIMITS_APPLIED"
    CARDS_ISSUED = "CARDS_ISSUED"
    CLIENT_ACTIVATED = "CLIENT_ACTIVATED"
    FIRST_OPERATION_ALLOWED = "FIRST_OPERATION_ALLOWED"
    FAILED = "FAILED"


class ClientOnboardingEventType(str, Enum):
    STATE_CHANGED = "STATE_CHANGED"
    ACTION_APPLIED = "ACTION_APPLIED"
    BLOCKED = "BLOCKED"




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
    crm_contract_version = Column(Integer, nullable=False, default=1, server_default="1")
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
    __table_args__ = (
        Index("ix_crm_subscription_charges_period", "subscription_id", "billing_period_id"),
        UniqueConstraint("subscription_id", "billing_period_id", "charge_key", name="uq_crm_subscription_charge_key"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    subscription_id = Column(GUID(), ForeignKey("crm_subscriptions.id"), nullable=False)
    billing_period_id = Column(GUID(), ForeignKey("billing_periods.id"), nullable=False)
    segment_id = Column(String(36), ForeignKey("crm_subscription_period_segments.id"), nullable=True)
    charge_type = Column(ExistingEnum(CRMSubscriptionChargeType, name="crm_subscription_charge_type"), nullable=False)
    code = Column(String(64), nullable=False)
    charge_key = Column(String(128), nullable=True)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(BigInteger, nullable=False)
    amount = Column(BigInteger, nullable=False)
    currency = Column(String(3), nullable=False)
    source = Column(JSON, nullable=True)
    explain = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CRMUsageCounter(Base):
    __tablename__ = "crm_usage_counters"
    __table_args__ = (Index("ix_crm_usage_counters_period", "subscription_id", "billing_period_id"),)

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    subscription_id = Column(GUID(), ForeignKey("crm_subscriptions.id"), nullable=False)
    billing_period_id = Column(GUID(), ForeignKey("billing_periods.id"), nullable=False)
    segment_id = Column(String(36), ForeignKey("crm_subscription_period_segments.id"), nullable=True)
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
            "tariff_plan_id",
            "status",
            name="uq_crm_subscription_segment_period",
        ),
    )

    id = Column(String(36), primary_key=True, default=new_uuid_str)
    subscription_id = Column(GUID(), ForeignKey("crm_subscriptions.id"), nullable=False)
    billing_period_id = Column(GUID(), ForeignKey("billing_periods.id"), nullable=False)
    tariff_plan_id = Column(String(64), ForeignKey("crm_tariff_plans.id"), nullable=False)
    segment_start = Column(DateTime(timezone=True), nullable=False)
    segment_end = Column(DateTime(timezone=True), nullable=False)
    status = Column(ExistingEnum(CRMSubscriptionSegmentStatus, name="crm_subscription_segment_status"), nullable=False)
    days_count = Column(Integer, nullable=False)
    reason = Column(ExistingEnum(CRMSubscriptionSegmentReason, name="crm_subscription_segment_reason"), nullable=True)
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


class CRMLead(Base):
    __tablename__ = "crm_leads"

    id = Column(String(36), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False, index=True)
    source = Column(String(64), nullable=True)
    status = Column(ExistingEnum(CRMLeadStatus, name="crm_lead_status"), nullable=False)
    company_name = Column(String(256), nullable=True)
    contact_name = Column(String(256), nullable=True)
    phone = Column(String(64), nullable=True)
    email = Column(String(256), nullable=True)
    comment = Column(Text, nullable=True)
    utm = Column(JSON, nullable=True)
    assigned_to = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CRMDeal(Base):
    __tablename__ = "crm_deals"

    id = Column(String(36), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False, index=True)
    lead_id = Column(String(36), ForeignKey("crm_leads.id"), nullable=True)
    client_id = Column(String(64), ForeignKey("crm_clients.id"), nullable=True)
    stage = Column(ExistingEnum(CRMDealStage, name="crm_deal_stage"), nullable=False)
    value_amount = Column(BigInteger, nullable=True)
    currency = Column(String(3), nullable=True)
    probability = Column(Integer, nullable=True)
    next_step = Column(Text, nullable=True)
    owner_id = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CRMDealEvent(Base):
    __tablename__ = "crm_deal_events"
    __table_args__ = (Index("ix_crm_deal_events_deal_ts", "deal_id", "created_at"),)

    id = Column(String(36), primary_key=True, default=new_uuid_str)
    deal_id = Column(String(36), ForeignKey("crm_deals.id"), nullable=False, index=True)
    event_type = Column(ExistingEnum(CRMDealEventType, name="crm_deal_event_type"), nullable=False)
    payload = Column(JSON, nullable=True)
    actor_id = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CRMTask(Base):
    __tablename__ = "crm_tasks"
    __table_args__ = (Index("ix_crm_tasks_due", "due_at"),)

    id = Column(String(36), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False, index=True)
    subject_type = Column(ExistingEnum(CRMTaskSubjectType, name="crm_task_subject_type"), nullable=False)
    subject_id = Column(String(64), nullable=False)
    title = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(ExistingEnum(CRMTaskStatus, name="crm_task_status"), nullable=False)
    priority = Column(ExistingEnum(CRMTaskPriority, name="crm_task_priority"), nullable=False)
    due_at = Column(DateTime(timezone=True), nullable=True)
    assigned_to = Column(String(64), nullable=True)
    created_by = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CRMTicketLink(Base):
    __tablename__ = "crm_ticket_links"
    __table_args__ = (UniqueConstraint("client_id", "ticket_id", name="uq_crm_ticket_links_scope"),)

    id = Column(String(36), primary_key=True, default=new_uuid_str)
    client_id = Column(String(64), ForeignKey("crm_clients.id"), nullable=False, index=True)
    ticket_id = Column(String(64), nullable=False, index=True)
    linked_by = Column(String(64), nullable=True)
    linked_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CRMClientProfile(Base):
    __tablename__ = "crm_client_profiles"

    client_id = Column(String(64), ForeignKey("crm_clients.id"), primary_key=True)
    legal_name = Column(String(256), nullable=True)
    inn = Column(String(32), nullable=True)
    kpp = Column(String(32), nullable=True)
    ogrn = Column(String(32), nullable=True)
    legal_address = Column(Text, nullable=True)
    actual_address = Column(Text, nullable=True)
    bank_details = Column(JSON, nullable=True)
    contacts = Column(JSON, nullable=True)
    roles = Column(JSON, nullable=True)
    status = Column(
        ExistingEnum(CRMClientProfileStatus, name="crm_client_profile_status"), nullable=False
    )
    risk_level = Column(
        ExistingEnum(CRMClientRiskLevel, name="crm_client_risk_level"), nullable=True
    )
    tags = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ClientOnboardingState(Base):
    __tablename__ = "client_onboarding_state"

    client_id = Column(String(64), ForeignKey("crm_clients.id"), primary_key=True)
    state = Column(
        ExistingEnum(ClientOnboardingStateEnum, name="client_onboarding_state"),
        nullable=False,
    )
    state_entered_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_blocked = Column(Boolean, nullable=False, default=False, server_default="false")
    block_reason = Column(Text, nullable=True)
    meta = Column(JSON, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ClientOnboardingEvent(Base):
    __tablename__ = "client_onboarding_events"
    __table_args__ = (Index("ix_onboarding_events_client_ts", "client_id", "created_at"),)

    id = Column(String(36), primary_key=True, default=new_uuid_str)
    client_id = Column(String(64), ForeignKey("crm_clients.id"), nullable=False, index=True)
    event_type = Column(
        ExistingEnum(ClientOnboardingEventType, name="client_onboarding_event_type"),
        nullable=False,
    )
    from_state = Column(
        ExistingEnum(ClientOnboardingStateEnum, name="client_onboarding_state"),
        nullable=True,
    )
    to_state = Column(
        ExistingEnum(ClientOnboardingStateEnum, name="client_onboarding_state"),
        nullable=True,
    )
    actor_id = Column(String(64), nullable=True)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


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
    "CRMSubscriptionSegmentReason",
    "CRMSubscriptionSegmentStatus",
    "CRMUsageCounter",
    "CRMUsageMetric",
    "CRMTariffPlan",
    "CRMTariffStatus",
    "CRMLead",
    "CRMLeadStatus",
    "CRMDeal",
    "CRMDealStage",
    "CRMDealEvent",
    "CRMDealEventType",
    "CRMTask",
    "CRMTaskPriority",
    "CRMTaskStatus",
    "CRMTaskSubjectType",
    "CRMTicketLink",
    "CRMClientProfile",
    "CRMClientProfileStatus",
    "CRMClientRiskLevel",
    "ClientOnboardingState",
    "ClientOnboardingStateEnum",
    "ClientOnboardingEvent",
    "ClientOnboardingEventType",
]
