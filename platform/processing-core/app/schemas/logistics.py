from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.logistics import (
    LogisticsETAMethod,
    LogisticsOrderStatus,
    LogisticsOrderType,
    LogisticsRouteStatus,
    LogisticsDeviationEventType,
    LogisticsDeviationSeverity,
    LogisticsFuelRouteLinkType,
    LogisticsRiskSignalType,
    LogisticsStopStatus,
    LogisticsStopType,
    LogisticsTrackingEventType,
)


class LogisticsOrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: int
    client_id: str
    order_type: LogisticsOrderType
    status: LogisticsOrderStatus | None = None
    vehicle_id: str | None = None
    driver_id: str | None = None
    planned_start_at: datetime | None = None
    planned_end_at: datetime | None = None
    origin_text: str | None = None
    destination_text: str | None = None
    meta: dict[str, Any] | None = None


class LogisticsOrderOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    tenant_id: int
    client_id: str
    order_type: LogisticsOrderType
    status: LogisticsOrderStatus
    vehicle_id: str | None = None
    driver_id: str | None = None
    planned_start_at: datetime | None = None
    planned_end_at: datetime | None = None
    actual_start_at: datetime | None = None
    actual_end_at: datetime | None = None
    origin_text: str | None = None
    destination_text: str | None = None
    meta: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class LogisticsRouteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    distance_km: float | None = None
    planned_duration_minutes: int | None = None


class LogisticsRouteOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    order_id: str
    version: int
    status: LogisticsRouteStatus
    distance_km: float | None = None
    planned_duration_minutes: int | None = None
    created_at: datetime


class LogisticsStopIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    sequence: int = Field(..., ge=0)
    stop_type: LogisticsStopType
    name: str | None = None
    address_text: str | None = None
    lat: float | None = None
    lon: float | None = None
    planned_arrival_at: datetime | None = None
    planned_departure_at: datetime | None = None
    actual_arrival_at: datetime | None = None
    actual_departure_at: datetime | None = None
    status: LogisticsStopStatus | None = None
    fuel_tx_id: str | None = None
    meta: dict[str, Any] | None = None


class LogisticsStopOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    route_id: str
    sequence: int
    stop_type: LogisticsStopType
    name: str | None = None
    address_text: str | None = None
    lat: float | None = None
    lon: float | None = None
    planned_arrival_at: datetime | None = None
    planned_departure_at: datetime | None = None
    actual_arrival_at: datetime | None = None
    actual_departure_at: datetime | None = None
    status: LogisticsStopStatus
    fuel_tx_id: str | None = None
    meta: dict[str, Any] | None = None


class LogisticsRouteDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route: LogisticsRouteOut
    stops: list[LogisticsStopOut]


class LogisticsTrackingEventIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: LogisticsTrackingEventType
    ts: datetime | None = None
    vehicle_id: str | None = None
    driver_id: str | None = None
    lat: float | None = None
    lon: float | None = None
    speed_kmh: float | None = None
    heading_deg: float | None = None
    odometer_km: float | None = None
    stop_id: str | None = None
    status_from: str | None = None
    status_to: str | None = None
    meta: dict[str, Any] | None = None


class LogisticsTrackingEventOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    order_id: str
    vehicle_id: str | None = None
    driver_id: str | None = None
    event_type: LogisticsTrackingEventType
    ts: datetime
    lat: float | None = None
    lon: float | None = None
    speed_kmh: float | None = None
    heading_deg: float | None = None
    odometer_km: float | None = None
    stop_id: str | None = None
    status_from: str | None = None
    status_to: str | None = None
    meta: dict[str, Any] | None = None


class LogisticsETASnapshotOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    order_id: str
    computed_at: datetime
    eta_end_at: datetime
    eta_confidence: int
    method: LogisticsETAMethod
    inputs: dict[str, Any] | None = None
    created_at: datetime


class LogisticsDeviationEventOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    order_id: str
    route_id: str
    event_type: LogisticsDeviationEventType
    ts: datetime
    lat: float | None = None
    lon: float | None = None
    distance_from_route_m: int | None = None
    stop_id: str | None = None
    severity: LogisticsDeviationSeverity
    explain: dict[str, Any] | None = None
    created_at: datetime


class LogisticsETAAccuracyOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    order_id: str
    computed_at: datetime
    eta_end_at: datetime
    actual_end_at: datetime | None = None
    error_minutes: int | None = None
    method: LogisticsETAMethod
    confidence: int
    created_at: datetime


class FuelRouteLinkOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    fuel_tx_id: str
    order_id: str
    route_id: str | None = None
    stop_id: str | None = None
    link_type: LogisticsFuelRouteLinkType
    distance_to_stop_m: int | None = None
    time_delta_minutes: int | None = None
    created_at: datetime


class LogisticsRiskSignalOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    tenant_id: int
    client_id: str
    order_id: str
    vehicle_id: str | None = None
    driver_id: str | None = None
    signal_type: LogisticsRiskSignalType
    severity: int
    ts: datetime
    explain: dict[str, Any] | None = None
    created_at: datetime
