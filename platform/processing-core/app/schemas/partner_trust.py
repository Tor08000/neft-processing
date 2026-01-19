from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.export_jobs import ExportJobFormat, ExportJobStatus


class FeeExplainOut(BaseModel):
    amount: Decimal
    basis: str
    rate: Decimal | None = None
    explain: str


class PenaltySourceRefOut(BaseModel):
    audit_event_id: str | None = None
    sla_event_id: str | None = None


class SettlementPenaltyOut(BaseModel):
    type: str
    amount: Decimal
    reason: str | None = None
    source_ref: PenaltySourceRefOut | None = None


class SettlementSnapshotOut(BaseModel):
    settlement_snapshot_id: str | None = None
    finalized_at: datetime | None = None
    hash: str | None = None


class PartnerOrderSettlementOut(BaseModel):
    order_id: str
    currency: str
    gross_amount: Decimal
    platform_fee: FeeExplainOut
    penalties: list[SettlementPenaltyOut] = Field(default_factory=list)
    partner_net: Decimal
    snapshot: SettlementSnapshotOut | None = None


class LedgerExplainOut(BaseModel):
    entry_id: str
    operation: str
    amount: Decimal
    currency: str
    direction: str
    source_type: str | None = None
    source_id: str | None = None
    source_label: str | None = None
    formula: str | None = None


class PayoutTraceOrderOut(BaseModel):
    order_id: str
    gross_amount: Decimal
    platform_fee: Decimal
    penalties: Decimal
    partner_net: Decimal
    currency: str
    settlement_snapshot_id: str | None = None
    finalized_at: datetime | None = None
    hash: str | None = None


class PayoutTraceSummaryOut(BaseModel):
    gross_total: Decimal
    fee_total: Decimal
    penalties_total: Decimal
    net_total: Decimal


class PayoutTraceOut(BaseModel):
    payout_id: str
    payout_state: str
    date_from: date
    date_to: date
    created_at: datetime
    total_amount: Decimal
    summary: PayoutTraceSummaryOut
    orders: list[PayoutTraceOrderOut] = Field(default_factory=list)


class SettlementChainExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_: date = Field(..., alias="from")
    to: date
    format: ExportJobFormat


class PartnerExportJobCreateResponse(BaseModel):
    id: str
    status: ExportJobStatus


class PartnerExportJobOut(BaseModel):
    id: str
    org_id: str
    created_by_user_id: str
    report_type: str
    format: ExportJobFormat
    status: ExportJobStatus
    filters: dict
    file_name: str | None = None
    content_type: str | None = None
    row_count: int | None = None
    processed_rows: int
    progress_percent: int | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    expires_at: datetime | None = None


class PartnerExportJobListResponse(BaseModel):
    items: list[PartnerExportJobOut]
