from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.models.fuel import FuelIngestJobStatus


class FleetIngestItemIn(BaseModel):
    provider_tx_id: str | None = None
    client_ref: str | None = None
    card_alias: str | None = None
    masked_pan: str | None = None
    occurred_at: datetime
    amount: Decimal
    currency: str | None = "RUB"
    volume_liters: Decimal | None = None
    category: str | None = None
    merchant_name: str | None = None
    station_id: str | None = None
    location: str | None = None
    external_ref: str | None = None
    raw_payload: dict[str, Any] | None = None


class FleetIngestRequestIn(BaseModel):
    provider_code: str
    batch_ref: str | None = None
    idempotency_key: str
    items: list[FleetIngestItemIn] = Field(default_factory=list)


class FleetIngestJobOut(BaseModel):
    id: str
    provider_code: str
    batch_ref: str | None = None
    idempotency_key: str
    status: FuelIngestJobStatus
    received_at: datetime
    total_count: int
    inserted_count: int
    deduped_count: int
    error: str | None = None
    audit_event_id: str | None = None

