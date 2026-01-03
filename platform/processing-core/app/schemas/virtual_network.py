from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class VirtualNetworkConfigOut(BaseModel):
    config: dict[str, Any]


class VirtualNetworkReloadOut(BaseModel):
    status: str
    config: dict[str, Any]


class VirtualNetworkSeedStationsIn(BaseModel):
    count: int = Field(gt=0, le=500)
    region: str | None = None
    city: str | None = None
    seed: int | None = None
    brand: str | None = None
    persist_db: bool = True


class VirtualNetworkSeedStationsOut(BaseModel):
    created: int
    stations: list[dict[str, Any]]


class VirtualNetworkSetPricesIn(BaseModel):
    prices: dict[str, dict[str, Decimal]]


class VirtualNetworkSetPricesOut(BaseModel):
    updated: int


class VirtualNetworkEnableAnomaliesIn(BaseModel):
    anomalies: list[dict[str, Any]]


class VirtualNetworkEnableAnomaliesOut(BaseModel):
    updated: int


class VirtualNetworkGenerateTxnsIn(BaseModel):
    client_id: str
    card_alias: str
    count: int = Field(default=1, gt=0, le=500)
    station_id: str | None = None
    liters: Decimal | None = None
    amount: Decimal | None = None
    currency: str = "RUB"
    anomaly_type: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    seed: int | None = None


class VirtualNetworkGenerateTxnsOut(BaseModel):
    created: int
    items: list[dict[str, Any]]
