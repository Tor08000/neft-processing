from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

from app.models.fuel import FuelFraudSignalType


class FraudSignalOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    tenant_id: int
    client_id: str
    signal_type: FuelFraudSignalType
    severity: int
    ts: datetime
    fuel_tx_id: Optional[str] = None
    order_id: Optional[str] = None
    vehicle_id: Optional[str] = None
    driver_id: Optional[str] = None
    station_id: Optional[str] = None
    network_id: Optional[str] = None
    explain: dict[str, Any] | None = None


class StationReputationDailyOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    tenant_id: int
    network_id: str
    station_id: str
    day: date
    tx_count: int
    decline_count: int
    risk_block_count: int
    avg_liters: Optional[int] = None
    avg_amount: Optional[int] = None
    outlier_score: int
    created_at: datetime


__all__ = ["FraudSignalOut", "StationReputationDailyOut"]
