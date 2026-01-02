from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.models.fleet import EmployeeStatus, FuelGroupRole
from app.models.fuel import (
    FuelCardStatus,
    FuelLimitBreachStatus,
    FuelLimitPeriod,
    FuelLimitScopeType,
)


class FleetCardCreateIn(BaseModel):
    card_alias: str
    masked_pan: str
    token_ref: str | None = None
    currency: str | None = "RUB"
    issued_at: datetime | None = None


class FleetCardOut(BaseModel):
    id: str
    card_alias: str | None = None
    masked_pan: str | None = None
    token_ref: str | None = None
    status: FuelCardStatus
    currency: str | None = None
    issued_at: datetime | None = None
    created_at: datetime


class FleetCardListResponse(BaseModel):
    items: list[FleetCardOut]


class FleetCardStatusUpdateIn(BaseModel):
    status: FuelCardStatus


class FleetGroupCreateIn(BaseModel):
    name: str
    description: str | None = None


class FleetGroupOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    created_at: datetime


class FleetGroupListResponse(BaseModel):
    items: list[FleetGroupOut]


class FleetGroupMemberChangeIn(BaseModel):
    card_id: str


class FleetEmployeeInviteIn(BaseModel):
    email: str


class FleetEmployeeOut(BaseModel):
    id: str
    email: str
    status: EmployeeStatus
    created_at: datetime


class FleetEmployeeListResponse(BaseModel):
    items: list[FleetEmployeeOut]


class FleetAccessGrantIn(BaseModel):
    employee_id: str
    role: FuelGroupRole


class FleetAccessRevokeIn(BaseModel):
    employee_id: str


class FleetAccessOut(BaseModel):
    id: str
    employee_id: str
    role: FuelGroupRole
    created_at: datetime
    revoked_at: datetime | None = None


class FleetAccessListResponse(BaseModel):
    items: list[FleetAccessOut]


class FleetLimitSetIn(BaseModel):
    scope_type: FuelLimitScopeType
    scope_id: str
    period: FuelLimitPeriod
    amount_limit: Decimal | None = None
    volume_limit_liters: Decimal | None = None
    categories: dict[str, Any] | None = None
    stations_allowlist: dict[str, Any] | None = None
    effective_from: datetime | None = None


class FleetLimitRevokeIn(BaseModel):
    limit_id: str


class FleetLimitOut(BaseModel):
    id: str
    scope_type: FuelLimitScopeType
    scope_id: str | None
    period: FuelLimitPeriod
    amount_limit: Decimal | None = None
    volume_limit_liters: Decimal | None = None
    categories: dict[str, Any] | None = None
    stations_allowlist: dict[str, Any] | None = None
    active: bool
    effective_from: datetime | None = None
    created_at: datetime


class FleetLimitListResponse(BaseModel):
    items: list[FleetLimitOut]


class FleetTransactionIn(BaseModel):
    card_id: str
    occurred_at: datetime
    amount: Decimal
    currency: str
    volume_liters: Decimal | None = None
    category: str | None = None
    merchant_name: str | None = None
    station_id: str | None = None
    location: str | None = None
    external_ref: str | None = None
    raw_payload: dict[str, Any] | None = None


class FleetTransactionsIngestIn(BaseModel):
    items: list[FleetTransactionIn]


class FleetTransactionOut(BaseModel):
    id: str
    card_id: str
    occurred_at: datetime
    amount: Decimal | None = None
    currency: str | None = None
    volume_liters: Decimal | None = None
    category: str | None = None
    merchant_name: str | None = None
    merchant_key: str | None = None
    station_id: str | None = None
    location: str | None = None
    external_ref: str | None = None
    provider_code: str | None = None
    provider_tx_id: str | None = None
    limit_check_status: str | None = None
    created_at: datetime


class FleetTransactionListResponse(BaseModel):
    items: list[FleetTransactionOut]


class FleetSpendSummaryRow(BaseModel):
    key: str
    amount: Decimal = Field(..., decimal_places=2)
    volume_liters: Decimal | None = None


class FleetSpendSummaryTotals(BaseModel):
    amount: Decimal = Field(..., decimal_places=2)
    volume_liters: Decimal = Field(..., decimal_places=2)


class FleetSpendSummaryOut(BaseModel):
    group_by: str
    totals: FleetSpendSummaryTotals
    rows: list[FleetSpendSummaryRow]
    top_merchants: list[FleetSpendSummaryRow] = Field(default_factory=list)
    top_categories: list[FleetSpendSummaryRow] = Field(default_factory=list)


class FleetAlertOut(BaseModel):
    id: str
    status: FuelLimitBreachStatus
    scope_type: str
    scope_id: str
    period: FuelLimitPeriod
    breach_type: str
    threshold: Decimal
    observed: Decimal
    delta: Decimal
    occurred_at: datetime
    tx_id: str | None = None
    limit_id: str


class FleetAlertListResponse(BaseModel):
    items: list[FleetAlertOut]


class FleetAlertIgnoreIn(BaseModel):
    reason: str | None = None


class FleetTransactionsExportOut(BaseModel):
    export_id: str
    url: str
    expires_in: int
    content_sha256: str | None = None
    artifact_signature: str | None = None
    artifact_signature_alg: str | None = None
    artifact_signing_key_id: str | None = None
