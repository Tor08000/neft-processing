from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.crm import (
    CRMBillingCycle,
    CRMBillingMode,
    CRMBillingPeriod,
    CRMClientStatus,
    CRMContractStatus,
    CRMFeatureFlagType,
    CRMProfileStatus,
    CRMSubscriptionStatus,
    CRMTariffStatus,
)


class CRMClientCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    tenant_id: int
    legal_name: str
    tax_id: Optional[str] = None
    kpp: Optional[str] = None
    country: str
    timezone: str = "Europe/Moscow"
    status: CRMClientStatus = CRMClientStatus.ACTIVE
    meta: Optional[dict[str, Any]] = None


class CRMClientUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    legal_name: Optional[str] = None
    tax_id: Optional[str] = None
    kpp: Optional[str] = None
    country: Optional[str] = None
    timezone: Optional[str] = None
    status: Optional[CRMClientStatus] = None
    meta: Optional[dict[str, Any]] = None


class CRMClientOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    tenant_id: int
    legal_name: str
    tax_id: Optional[str] = None
    kpp: Optional[str] = None
    country: str
    timezone: str
    status: CRMClientStatus
    created_at: datetime
    updated_at: datetime
    meta: Optional[dict[str, Any]] = None


class CRMContractCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: int
    contract_number: str
    status: CRMContractStatus = CRMContractStatus.DRAFT
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    billing_mode: CRMBillingMode = CRMBillingMode.POSTPAID
    currency: str = "RUB"
    risk_profile_id: Optional[str] = None
    limit_profile_id: Optional[str] = None
    documents_required: bool = False
    meta: Optional[dict[str, Any]] = None


class CRMContractOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    tenant_id: int
    client_id: str
    contract_number: str
    status: CRMContractStatus
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    billing_mode: CRMBillingMode
    currency: str
    risk_profile_id: Optional[str] = None
    limit_profile_id: Optional[str] = None
    documents_required: bool
    crm_contract_version: int
    created_at: datetime
    meta: Optional[dict[str, Any]] = None


class CRMTariffCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    description: Optional[str] = None
    status: CRMTariffStatus = CRMTariffStatus.ACTIVE
    billing_period: CRMBillingPeriod
    base_fee_minor: int = Field(..., ge=0)
    currency: str = "RUB"
    features: Optional[dict[str, Any]] = None
    limits_defaults: Optional[dict[str, Any]] = None
    definition: Optional[dict[str, Any]] = None


class CRMTariffUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[CRMTariffStatus] = None
    billing_period: Optional[CRMBillingPeriod] = None
    base_fee_minor: Optional[int] = Field(None, ge=0)
    currency: Optional[str] = None
    features: Optional[dict[str, Any]] = None
    limits_defaults: Optional[dict[str, Any]] = None
    definition: Optional[dict[str, Any]] = None


class CRMTariffOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    name: str
    description: Optional[str] = None
    status: CRMTariffStatus
    billing_period: CRMBillingPeriod
    base_fee_minor: int
    currency: str
    features: Optional[dict[str, Any]] = None
    limits_defaults: Optional[dict[str, Any]] = None
    created_at: datetime
    definition: Optional[dict[str, Any]] = None


class CRMSubscriptionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: int
    tariff_plan_id: str
    status: CRMSubscriptionStatus = CRMSubscriptionStatus.ACTIVE
    billing_cycle: CRMBillingCycle = CRMBillingCycle.MONTHLY
    billing_day: int = Field(1, ge=1, le=28)
    started_at: datetime
    paused_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    meta: Optional[dict[str, Any]] = None


class CRMSubscriptionOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    tenant_id: int
    client_id: str
    tariff_plan_id: str
    status: CRMSubscriptionStatus
    billing_cycle: CRMBillingCycle
    billing_day: int
    started_at: datetime
    paused_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    meta: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime


class CRMSubscriptionChangeTariff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_tariff_id: str
    effective_at: datetime


class CRMSubscriptionPreviewSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    tariff_plan_id: str
    segment_start: datetime
    segment_end: datetime
    status: str
    reason: str | None = None
    days_count: int


class CRMSubscriptionPreviewUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: str
    value: int
    limit_value: int | None = None
    overage: int | None = None
    segment_id: str | None = None


class CRMSubscriptionPreviewCharge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    amount: int
    quantity: int
    unit_price: int
    segment_id: str | None = None


class CRMSubscriptionPreviewOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    segments: list[CRMSubscriptionPreviewSegment]
    usage: list[CRMSubscriptionPreviewUsage]
    charges: list[CRMSubscriptionPreviewCharge]
    total: int


class CRMProfileCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: int
    name: str
    status: CRMProfileStatus = CRMProfileStatus.ACTIVE
    definition: dict[str, Any]


class CRMProfileOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    tenant_id: int
    name: str
    status: CRMProfileStatus
    definition: dict[str, Any]
    created_at: datetime


class CRMRiskProfileCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: int
    name: str
    status: CRMProfileStatus = CRMProfileStatus.ACTIVE
    risk_policy_id: str
    threshold_set_id: Optional[str] = None
    shadow_enabled: bool = False
    meta: Optional[dict[str, Any]] = None
    definition: Optional[dict[str, Any]] = None


class CRMRiskProfileOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    tenant_id: int
    name: str
    status: CRMProfileStatus
    risk_policy_id: str
    threshold_set_id: Optional[str] = None
    shadow_enabled: bool
    created_at: datetime
    meta: Optional[dict[str, Any]] = None


class CRMFeatureFlagOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    tenant_id: int
    client_id: str
    feature: CRMFeatureFlagType
    enabled: bool
    updated_at: datetime
    updated_by: Optional[str] = None


__all__ = [
    "CRMBillingCycle",
    "CRMBillingMode",
    "CRMBillingPeriod",
    "CRMClientCreate",
    "CRMClientOut",
    "CRMClientStatus",
    "CRMClientUpdate",
    "CRMContractCreate",
    "CRMContractOut",
    "CRMContractStatus",
    "CRMFeatureFlagOut",
    "CRMFeatureFlagType",
    "CRMProfileCreate",
    "CRMProfileOut",
    "CRMProfileStatus",
    "CRMRiskProfileCreate",
    "CRMRiskProfileOut",
    "CRMSubscriptionCreate",
    "CRMSubscriptionChangeTariff",
    "CRMSubscriptionOut",
    "CRMSubscriptionPreviewCharge",
    "CRMSubscriptionPreviewOut",
    "CRMSubscriptionPreviewSegment",
    "CRMSubscriptionPreviewUsage",
    "CRMSubscriptionStatus",
    "CRMTariffCreate",
    "CRMTariffOut",
    "CRMTariffStatus",
    "CRMTariffUpdate",
]
