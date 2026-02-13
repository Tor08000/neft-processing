from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.fuel import FuelLimitPeriod, FuelLimitScopeType, FuelLimitType, FuelTransactionStatus, FuelType


class DeclineCode(str, Enum):
    CARD_NOT_FOUND = "CARD_NOT_FOUND"
    CARD_BLOCKED = "CARD_BLOCKED"
    CARD_EXPIRED = "CARD_EXPIRED"
    STATION_NOT_FOUND = "STATION_NOT_FOUND"
    STATION_INACTIVE = "STATION_INACTIVE"
    NETWORK_NOT_SUPPORTED = "NETWORK_NOT_SUPPORTED"
    FUEL_TYPE_NOT_ALLOWED = "FUEL_TYPE_NOT_ALLOWED"
    LIMIT_EXCEEDED_AMOUNT = "LIMIT_EXCEEDED_AMOUNT"
    LIMIT_EXCEEDED_VOLUME = "LIMIT_EXCEEDED_VOLUME"
    LIMIT_EXCEEDED_COUNT = "LIMIT_EXCEEDED_COUNT"
    LIMIT_TIME_WINDOW = "LIMIT_TIME_WINDOW"
    RISK_BLOCK = "RISK_BLOCK"
    RISK_REVIEW_REQUIRED = "RISK_REVIEW_REQUIRED"
    CLIENT_BLOCKED = "CLIENT_BLOCKED"
    DUPLICATE_EXTERNAL_REF = "DUPLICATE_EXTERNAL_REF"
    INVALID_REQUEST = "INVALID_REQUEST"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class FuelAuthorizeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    card_token: str
    network_code: str
    station_code: Optional[str] = None
    occurred_at: datetime | None = None
    fuel_type: FuelType
    volume_liters: float = Field(..., gt=0)
    unit_price: int = Field(..., gt=0, description="Unit price in minor units")
    currency: str = "RUB"
    external_ref: Optional[str] = None
    vehicle_plate: Optional[str] = None
    driver_id: Optional[str] = None
    meta: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _validate_station(self):
        if not self.station_code:
            raise ValueError("station_code is required")
        return self


class LimitExplain(BaseModel):
    model_config = ConfigDict(extra="forbid")

    applied_limit_id: Optional[str] = None
    matched_on: list[str] = Field(default_factory=list)
    scope_type: FuelLimitScopeType
    scope_id: Optional[str]
    limit_type: FuelLimitType
    period: FuelLimitPeriod
    limit: int
    used: int
    attempt: int
    remaining: int
    time_window_start: Optional[str] = None
    time_window_end: Optional[str] = None
    timezone: Optional[str] = None


class RiskExplain(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: str
    score: Optional[int] = None
    thresholds: Optional[dict[str, Any]] = None
    policy: Optional[dict[str, Any] | str] = None
    policy_source: Optional[str] = None
    factors: Optional[list[str]] = None
    decision_hash: Optional[str] = None
    payload: Optional[dict[str, Any]] = None


class FraudSignalExplain(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    severity: int
    note: Optional[str] = None


class AccountantExplain(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: str
    decline_code: Optional[DeclineCode] = None
    amount: Optional[int] = None
    limit_remaining: Optional[int] = None
    period: Optional[FuelLimitPeriod] = None
    applied_limit: Optional[str] = None


class FleetManagerExplain(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: str
    decline_code: Optional[DeclineCode] = None
    signals: list[str] = Field(default_factory=list)
    recommendation: Optional[str] = None


class FuelDeclineExplain(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decline_code: DeclineCode
    message: Optional[str] = None
    limit_explain: Optional[LimitExplain] = None
    risk_explain: Optional[RiskExplain] = None
    fraud_signals: Optional[list[FraudSignalExplain]] = None
    accountant_explain: Optional[AccountantExplain] = None
    manager_explain: Optional[FleetManagerExplain] = None


class FuelAuthorizeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    transaction_id: Optional[str] = None
    decline_code: Optional[DeclineCode] = None
    explain: Optional[FuelDeclineExplain] = None


class FuelSettleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_id: str


class FuelReverseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_id: str


class FuelTransactionOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    tenant_id: int
    client_id: str
    card_id: str
    vehicle_id: Optional[str] = None
    driver_id: Optional[str] = None
    station_id: str
    network_id: str
    occurred_at: datetime
    fuel_type: FuelType
    volume_ml: int
    unit_price_minor: int
    amount_total_minor: int
    currency: str
    status: FuelTransactionStatus
    decline_code: Optional[str] = None
    risk_decision_id: Optional[str] = None
    ledger_transaction_id: Optional[str] = None
    external_ref: Optional[str] = None


class FuelNetworkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    provider_code: str
    status: str = "ACTIVE"


class FuelNetworkOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    name: str
    provider_code: str
    status: str
    created_at: datetime


class FuelStationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    network_id: str
    station_network_id: Optional[str] = None
    station_code: str
    name: str
    country: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    nav_url: Optional[str] = None
    geo_hash: Optional[str] = None
    status: str = "ACTIVE"


class FuelStationOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    network_id: str
    station_network_id: Optional[str] = None
    station_code: Optional[str] = None
    name: str
    country: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    nav_url: Optional[str] = None
    geo_hash: Optional[str] = None
    status: str
    created_at: datetime


class FuelCardGroupCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: int
    client_id: str
    name: str
    status: str = "ACTIVE"


class FuelCardGroupOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    tenant_id: int
    client_id: str
    name: str
    status: str
    created_at: datetime


class FuelStationNetworkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    meta: Optional[dict[str, Any]] = None


class FuelStationNetworkOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    name: str
    meta: Optional[dict[str, Any]] = None
    created_at: datetime


__all__ = [
    "DeclineCode",
    "AccountantExplain",
    "FleetManagerExplain",
    "FuelStationNetworkCreate",
    "FuelStationNetworkOut",
    "FuelAuthorizeRequest",
    "FuelAuthorizeResponse",
    "FuelDeclineExplain",
    "FuelReverseRequest",
    "FuelSettleRequest",
    "FuelTransactionOut",
    "LimitExplain",
    "RiskExplain",
    "FuelCardGroupCreate",
    "FuelCardGroupOut",
    "FuelNetworkCreate",
    "FuelNetworkOut",
    "FuelStationCreate",
    "FuelStationOut",
]
