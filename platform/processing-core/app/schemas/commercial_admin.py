from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class CommercialOrgInfo(BaseModel):
    id: int
    name: str | None = None
    status: str | None = None


class CommercialSubscription(BaseModel):
    plan_code: str | None = None
    plan_version: int | None = None
    status: str | None = None
    billing_cycle: str | None = None
    support_plan: str | None = None
    slo_tier: str | None = None


class CommercialAddonOut(BaseModel):
    addon_code: str
    status: str
    price_override: Decimal | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    config_json: dict[str, Any] | None = None


class CommercialOverrideOut(BaseModel):
    feature_key: str
    availability: str
    limits_json: dict[str, Any] | None = None


class CommercialSnapshotOut(BaseModel):
    hash: str | None = None
    computed_at: datetime | None = None
    version: int | None = None


class CommercialOrgStateOut(BaseModel):
    org: CommercialOrgInfo
    subscription: CommercialSubscription | None = None
    addons: list[CommercialAddonOut]
    overrides: list[CommercialOverrideOut]
    entitlements_snapshot: CommercialSnapshotOut | None = None


class CommercialPlanChangeRequest(BaseModel):
    plan_code: str
    plan_version: int
    billing_cycle: str
    status: str
    reason: str | None = None
    effective_at: datetime | None = None


class CommercialAddonEnableRequest(BaseModel):
    addon_code: str
    price_override: Decimal | None = None
    status: str
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    config_json: dict[str, Any] | None = None
    reason: str | None = None


class CommercialAddonDisableRequest(BaseModel):
    addon_code: str
    reason: str | None = None


class CommercialOverrideUpsertRequest(BaseModel):
    feature_key: str
    availability: str
    limits_json: dict[str, Any] | None = None
    reason: str | None = None


class CommercialStatusChangeRequest(BaseModel):
    status: str
    reason: str | None = None


class CommercialRecomputeRequest(BaseModel):
    reason: str | None = None


class CommercialRecomputeResponse(BaseModel):
    hash: str
    computed_at: datetime
    version: int


class CommercialOrgRoleRequest(BaseModel):
    role: str
    reason: str | None = None


class CommercialOrgRolesResponse(BaseModel):
    org_id: int
    roles: list[str]
