from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.payout_batch import PayoutBatch, PayoutBatchState
from app.models.payout_export_file import PayoutExportFile, PayoutExportFormat, PayoutExportState


class PayoutClosePeriodRequest(BaseModel):
    tenant_id: int
    partner_id: str = Field(..., min_length=1, max_length=64)
    date_from: date
    date_to: date


class PayoutMarkRequest(BaseModel):
    provider: str = Field(..., min_length=1, max_length=64)
    external_ref: str = Field(..., min_length=1, max_length=128)


class PayoutBatchSummary(BaseModel):
    batch_id: str
    state: str
    total_amount: Decimal
    total_qty: Decimal
    operations_count: int
    items_count: int

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_batch(cls, batch: PayoutBatch) -> "PayoutBatchSummary":
        state_value = batch.state.value if isinstance(batch.state, PayoutBatchState) else str(batch.state)
        items_count = len(batch.items) if batch.items else 0
        return cls(
            batch_id=batch.id,
            state=state_value,
            total_amount=Decimal(batch.total_amount or 0),
            total_qty=Decimal(batch.total_qty or 0),
            operations_count=int(batch.operations_count or 0),
            items_count=items_count,
        )


class PayoutBatchItemOut(BaseModel):
    id: str
    azs_id: str | None = None
    product_id: str | None = None
    amount_gross: Decimal
    commission_amount: Decimal
    amount_net: Decimal
    qty: Decimal
    operations_count: int
    meta: dict | None = None

    model_config = ConfigDict(from_attributes=True)


class PayoutBatchDetail(BaseModel):
    id: str
    tenant_id: int
    partner_id: str
    date_from: date
    date_to: date
    state: str
    total_amount: Decimal
    total_qty: Decimal
    operations_count: int
    created_at: datetime
    sent_at: datetime | None = None
    settled_at: datetime | None = None
    provider: str | None = None
    external_ref: str | None = None
    meta: dict | None = None
    items: list[PayoutBatchItemOut]

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_batch(cls, batch: PayoutBatch) -> "PayoutBatchDetail":
        state_value = batch.state.value if isinstance(batch.state, PayoutBatchState) else str(batch.state)
        items = [PayoutBatchItemOut.model_validate(item) for item in (batch.items or [])]
        return cls(
            id=batch.id,
            tenant_id=batch.tenant_id,
            partner_id=batch.partner_id,
            date_from=batch.date_from,
            date_to=batch.date_to,
            state=state_value,
            total_amount=Decimal(batch.total_amount or 0),
            total_qty=Decimal(batch.total_qty or 0),
            operations_count=int(batch.operations_count or 0),
            created_at=batch.created_at,
            sent_at=batch.sent_at,
            settled_at=batch.settled_at,
            provider=batch.provider,
            external_ref=batch.external_ref,
            meta=batch.meta,
            items=items,
        )


class PayoutBatchListResponse(BaseModel):
    items: list[PayoutBatchSummary]
    total: int
    limit: int
    offset: int


class PayoutReconcileResponse(BaseModel):
    batch_id: str
    computed: dict
    recorded: dict
    diff: dict
    status: str


class PayoutExportCreateRequest(BaseModel):
    format: PayoutExportFormat = Field(..., description="CSV or XLSX")
    provider: str | None = Field(default=None, max_length=64)
    external_ref: str | None = Field(default=None, max_length=128)
    bank_format_code: str | None = Field(default=None, max_length=64)


class PayoutExportOut(BaseModel):
    export_id: str
    batch_id: str
    format: str
    state: str
    provider: str | None = None
    external_ref: str | None = None
    bank_format_code: str | None = None
    object_key: str
    bucket: str
    sha256: str | None = None
    size_bytes: int | None = None
    generated_at: datetime | None = None
    uploaded_at: datetime | None = None
    error_message: str | None = None
    meta: dict | None = None
    download_url: str

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_export(cls, export: PayoutExportFile) -> "PayoutExportOut":
        return cls(
            export_id=export.id,
            batch_id=export.batch_id,
            format=export.format.value if isinstance(export.format, PayoutExportFormat) else str(export.format),
            state=export.state.value if isinstance(export.state, PayoutExportState) else str(export.state),
            provider=export.provider,
            external_ref=export.external_ref,
            bank_format_code=export.bank_format_code,
            object_key=export.object_key,
            bucket=export.bucket,
            sha256=export.sha256,
            size_bytes=export.size_bytes,
            generated_at=export.generated_at,
            uploaded_at=export.uploaded_at,
            error_message=export.error_message,
            meta=export.meta,
            download_url=f"/api/v1/payouts/exports/{export.id}/download",
        )


class PayoutExportListResponse(BaseModel):
    items: list[PayoutExportOut]


class PayoutExportFormatInfo(BaseModel):
    code: str
    title: str


class PayoutExportFormatListResponse(BaseModel):
    items: list[PayoutExportFormatInfo]
