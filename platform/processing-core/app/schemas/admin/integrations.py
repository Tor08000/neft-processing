from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.integrations import (
    BankStatementStatus,
    IntegrationExportStatus,
    IntegrationType,
    ReconciliationDiffReason,
    ReconciliationDiffSource,
    ReconciliationMatchType,
    ReconciliationRunStatus,
)


class OnecExportRequest(BaseModel):
    period_start: date
    period_end: date
    mapping_version: str = Field(default="2026.01")
    seller_name: str
    seller_inn: str
    seller_kpp: str | None = None


class IntegrationExportResponse(BaseModel):
    id: str
    integration_type: IntegrationType
    entity_type: str
    period_start: date
    period_end: date
    status: IntegrationExportStatus
    file_id: str | None
    created_at: datetime


class IntegrationExportListResponse(BaseModel):
    exports: list[IntegrationExportResponse]


class BankStatementImportRequest(BaseModel):
    bank_code: str
    period_start: datetime
    period_end: datetime
    file_name: str
    content_type: str
    content: str


class BankStatementResponse(BaseModel):
    id: str
    bank_code: str
    period_start: datetime
    period_end: datetime
    status: BankStatementStatus
    file_id: str | None
    created_at: datetime


class BankStatementListResponse(BaseModel):
    statements: list[BankStatementResponse]


class BankReconciliationRunResponse(BaseModel):
    id: str
    statement_id: str
    status: ReconciliationRunStatus
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class BankReconciliationDiffResponse(BaseModel):
    id: str
    run_id: str
    source: ReconciliationDiffSource
    tx_id: str
    reason: ReconciliationDiffReason
    created_at: datetime


class BankReconciliationMatchResponse(BaseModel):
    id: str
    run_id: str
    bank_tx_id: str
    invoice_id: str | None
    match_type: ReconciliationMatchType
    score: Decimal
    created_at: datetime


class BankReconciliationRunListResponse(BaseModel):
    runs: list[BankReconciliationRunResponse]


class BankReconciliationDiffListResponse(BaseModel):
    diffs: list[BankReconciliationDiffResponse]


class BankReconciliationMatchListResponse(BaseModel):
    matches: list[BankReconciliationMatchResponse]
