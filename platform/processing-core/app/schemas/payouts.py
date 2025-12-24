from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.payout_batch import PayoutBatch, PayoutBatchState


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
