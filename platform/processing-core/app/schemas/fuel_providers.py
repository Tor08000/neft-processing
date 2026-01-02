from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.integrations.fuel.models import FuelProviderAuthType, FuelProviderConnectionStatus
from app.models.fuel import FuelIngestJobStatus


class FuelProviderConnectionCreateIn(BaseModel):
    provider_code: str
    auth_type: FuelProviderAuthType
    secret_ref: str | None = None
    config: dict[str, Any] | None = None


class FuelProviderConnectionOut(BaseModel):
    id: str
    client_id: str
    provider_code: str
    status: FuelProviderConnectionStatus
    auth_type: FuelProviderAuthType
    config: dict[str, Any] | None = None
    last_sync_at: datetime | None = None
    created_at: datetime


class FuelProviderConnectionListResponse(BaseModel):
    items: list[FuelProviderConnectionOut] = Field(default_factory=list)


class FuelProviderSyncNowOut(BaseModel):
    job_id: str | None = None
    status: str


class FuelProviderBackfillIn(BaseModel):
    period_start: datetime
    period_end: datetime
    batch_hours: int = 24


class FuelProviderBackfillOut(BaseModel):
    job_ids: list[str] = Field(default_factory=list)
    status: str


class FuelProviderSyncJobOut(BaseModel):
    id: str
    provider_code: str
    client_id: str | None
    status: FuelIngestJobStatus
    received_at: datetime
    mode: str | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None
    total_count: int
    inserted_count: int
    deduped_count: int
    error: str | None = None


class FuelProviderRawEventOut(BaseModel):
    id: str
    client_id: str
    provider_code: str
    event_type: str
    provider_event_id: str | None
    occurred_at: datetime | None
    payload_redacted: dict[str, Any] | None
    payload_hash: str
    ingest_job_id: str | None
    created_at: datetime


class FuelProviderDisableIn(BaseModel):
    reason: str | None = None


class FuelProviderStatusOut(BaseModel):
    id: str
    status: FuelProviderConnectionStatus
    last_sync_at: datetime | None
    last_sync_cursor: str | None


class FuelProviderEdiIngestIn(BaseModel):
    provider_code: str
    client_ref: str
    file_type: str
    payload_base64: str | None = None
    payload_url: str | None = None
    idempotency_key: str
