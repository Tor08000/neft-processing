from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.fleet_intelligence import DriverBehaviorLevel, StationTrustLevel


class FleetDriverScoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: int
    client_id: str
    driver_id: str
    computed_at: datetime
    window_days: int
    score: int
    level: DriverBehaviorLevel
    explain: dict[str, Any] | None


class FleetVehicleEfficiencyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: int
    client_id: str
    vehicle_id: str
    computed_at: datetime
    window_days: int
    efficiency_score: int | None
    baseline_ml_per_100km: float | None
    actual_ml_per_100km: float | None
    delta_pct: float | None
    explain: dict[str, Any] | None


class FleetStationTrustOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: int
    station_id: str
    network_id: str | None
    computed_at: datetime
    window_days: int
    trust_score: int
    level: StationTrustLevel
    explain: dict[str, Any] | None


__all__ = [
    "FleetDriverScoreOut",
    "FleetVehicleEfficiencyOut",
    "FleetStationTrustOut",
]
