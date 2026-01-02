from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.reconciliation import (
    ReconciliationDiscrepancyStatus,
    ReconciliationDiscrepancyType,
    ReconciliationRunStatus,
    ReconciliationScope,
)


class ReconciliationRunCreateRequest(BaseModel):
    period_start: datetime
    period_end: datetime


class ReconciliationExternalRunRequest(BaseModel):
    statement_id: str


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


class ReconciliationDiscrepancyListResponse(BaseModel):
    discrepancies: list[ReconciliationDiscrepancyResponse]


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


class ExternalStatementListResponse(BaseModel):
    statements: list[ExternalStatementResponse]


class ResolveDiscrepancyRequest(BaseModel):
    note: str


class IgnoreDiscrepancyRequest(BaseModel):
    reason: str
