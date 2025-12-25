from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.accounting_export_batch import (
    AccountingExportFormat,
    AccountingExportState,
    AccountingExportType,
)


class AccountingExportCreateRequest(BaseModel):
    period_id: str = Field(..., description="Billing period id")
    export_type: AccountingExportType
    format: AccountingExportFormat
    version: int = Field(1, ge=1)
    force: bool = False


class AccountingExportBatchRead(BaseModel):
    id: str
    tenant_id: int
    billing_period_id: str
    export_type: AccountingExportType
    format: AccountingExportFormat
    state: AccountingExportState
    idempotency_key: str
    checksum_sha256: str | None = None
    records_count: int
    object_key: str | None = None
    bucket: str | None = None
    size_bytes: int | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    generated_at: datetime | None = None
    uploaded_at: datetime | None = None
    downloaded_at: datetime | None = None
    confirmed_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AccountingExportBatchListResponse(BaseModel):
    items: list[AccountingExportBatchRead]
    total: int
    limit: int
    offset: int


__all__ = [
    "AccountingExportBatchListResponse",
    "AccountingExportBatchRead",
    "AccountingExportCreateRequest",
]
