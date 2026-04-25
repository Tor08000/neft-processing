from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.internal_ledger import InternalLedgerAccountType, InternalLedgerEntryDirection, InternalLedgerTransactionType
from app.models.reconciliation import (
    ReconciliationDiscrepancyStatus,
    ReconciliationDiscrepancyType,
    ReconciliationLinkDirection,
    ReconciliationLinkStatus,
    ReconciliationRunStatus,
    ReconciliationScope,
)


class ReconciliationRunCreateRequest(BaseModel):
    period_start: datetime
    period_end: datetime


class ReconciliationExternalRunRequest(BaseModel):
    statement_id: str


class ReconciliationAuditEvent(BaseModel):
    ts: datetime
    event_type: str
    entity_type: str
    entity_id: str
    action: str
    reason: str | None = None
    actor_id: str | None = None
    actor_email: str | None = None
    before: dict[str, object] | None = None
    after: dict[str, object] | None = None


class ReconciliationLinkCounts(BaseModel):
    matched: int = 0
    mismatched: int = 0
    pending: int = 0


class ReconciliationStatementSummary(BaseModel):
    id: str
    provider: str
    period_start: datetime
    period_end: datetime
    currency: str
    total_in: Decimal | None = None
    total_out: Decimal | None = None
    closing_balance: Decimal | None = None
    created_at: datetime
    source_hash: str
    audit_event_id: str | None = None


class ReconciliationStatementTotalCheck(BaseModel):
    kind: str
    status: str
    external_amount: Decimal | None = None
    internal_amount: Decimal | None = None
    delta: Decimal | None = None
    discrepancy_id: str | None = None
    discrepancy_status: ReconciliationDiscrepancyStatus | None = None


class ExternalStatementExplain(BaseModel):
    related_run_id: str | None = None
    related_run_status: ReconciliationRunStatus | None = None
    relation_source: str | None = None
    line_count: int = 0
    matched_links: int = 0
    mismatched_links: int = 0
    pending_links: int = 0
    unmatched_external: int = 0
    unmatched_internal: int = 0
    mismatched_amount: int = 0
    open_discrepancies: int = 0
    resolved_discrepancies: int = 0
    ignored_discrepancies: int = 0
    adjusted_discrepancies: int = 0
    total_checks: list[ReconciliationStatementTotalCheck] = Field(default_factory=list)


class ReconciliationAdjustmentPosting(BaseModel):
    account_id: str
    account_type: InternalLedgerAccountType
    client_id: str | None = None
    direction: InternalLedgerEntryDirection
    amount: int
    currency: str
    entry_hash: str


class ReconciliationAdjustmentExplain(BaseModel):
    adjustment_tx_id: str
    transaction_type: InternalLedgerTransactionType | None = None
    external_ref_type: str | None = None
    external_ref_id: str | None = None
    tenant_id: int | None = None
    currency: str | None = None
    total_amount: int | None = None
    posted_at: datetime | None = None
    meta: dict[str, object] | None = None
    entries: list[ReconciliationAdjustmentPosting] = Field(default_factory=list)
    audit_events: list[ReconciliationAuditEvent] = Field(default_factory=list)


class ReconciliationRunResponse(BaseModel):
    id: str
    scope: ReconciliationScope
    provider: str | None
    period_start: datetime
    period_end: datetime
    status: ReconciliationRunStatus
    created_at: datetime
    created_by_user_id: str | None
    summary: dict[str, object] | None = None
    audit_event_id: str | None
    statement: ReconciliationStatementSummary | None = None
    timeline: list[ReconciliationAuditEvent] = Field(default_factory=list)
    link_counts: ReconciliationLinkCounts | None = None


class ReconciliationRunListResponse(BaseModel):
    runs: list[ReconciliationRunResponse]


class ReconciliationDiscrepancyResponse(BaseModel):
    id: str
    run_id: str
    ledger_account_id: str | None
    currency: str
    discrepancy_type: ReconciliationDiscrepancyType
    internal_amount: Decimal | None = None
    external_amount: Decimal | None = None
    delta: Decimal | None = None
    details: dict[str, object] | None = None
    status: ReconciliationDiscrepancyStatus
    resolution: dict[str, object] | None = None
    created_at: datetime
    timeline: list[ReconciliationAuditEvent] = Field(default_factory=list)
    adjustment_explain: ReconciliationAdjustmentExplain | None = None


class ReconciliationDiscrepancyListResponse(BaseModel):
    discrepancies: list[ReconciliationDiscrepancyResponse]


class ReconciliationLinkResponse(BaseModel):
    id: str
    run_id: str | None = None
    entity_type: str
    entity_id: str
    provider: str
    currency: str
    expected_amount: Decimal
    direction: ReconciliationLinkDirection
    expected_at: datetime
    match_key: str | None = None
    status: ReconciliationLinkStatus
    created_at: datetime
    discrepancy_ids: list[str] = Field(default_factory=list)
    review_status: ReconciliationDiscrepancyStatus | None = None


class ReconciliationLinkListResponse(BaseModel):
    links: list[ReconciliationLinkResponse]


class ExternalStatementUploadRequest(BaseModel):
    provider: str
    period_start: datetime
    period_end: datetime
    currency: str
    total_in: Decimal | None = Field(default=None)
    total_out: Decimal | None = Field(default=None)
    closing_balance: Decimal | None = Field(default=None)
    lines: list[dict[str, object]] | None = Field(default=None)


class ExternalStatementResponse(BaseModel):
    id: str
    provider: str
    period_start: datetime
    period_end: datetime
    currency: str
    total_in: Decimal | None = None
    total_out: Decimal | None = None
    closing_balance: Decimal | None = None
    lines: list[dict[str, object]] | None = None
    created_at: datetime
    source_hash: str
    audit_event_id: str | None
    explain: ExternalStatementExplain | None = None
    timeline: list[ReconciliationAuditEvent] = Field(default_factory=list)


class ExternalStatementListResponse(BaseModel):
    statements: list[ExternalStatementResponse]


class ResolveDiscrepancyRequest(BaseModel):
    note: str


class IgnoreDiscrepancyRequest(BaseModel):
    reason: str


class ReconciliationRunExportResponse(BaseModel):
    exported_at: datetime
    run: ReconciliationRunResponse
    discrepancies: list[ReconciliationDiscrepancyResponse] = Field(default_factory=list)
    links: list[ReconciliationLinkResponse] = Field(default_factory=list)


class ReconciliationDiscrepancyResult(BaseModel):
    discrepancy: ReconciliationDiscrepancyResponse
