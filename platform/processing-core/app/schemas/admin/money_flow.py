from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.services.money_flow.states import MoneyFlowState, MoneyFlowType


class LedgerEntrySchema(BaseModel):
    account: str
    direction: str
    amount: int
    currency: str


class LedgerSummarySchema(BaseModel):
    ledger_transaction_id: str
    balanced: bool
    entries: list[LedgerEntrySchema]


class MoneyExplainResponse(BaseModel):
    flow_type: MoneyFlowType
    flow_ref_id: str
    state: MoneyFlowState
    ledger: LedgerSummarySchema | None
    invariants: dict[str, Any]
    risk: dict[str, Any] | None
    notes: list[str]
    event_id: str
    created_at: datetime


class MoneyHealthOffenderSchema(BaseModel):
    flow_type: str
    flow_ref_id: str
    state: str
    age_hours: int
    reason: str


class MoneyHealthResponse(BaseModel):
    orphan_ledger_transactions: int
    missing_ledger_postings: int
    invariant_violations: int
    stuck_authorized: int
    stuck_pending_settlement: int
    cross_period_anomalies: int
    top_offenders: list[MoneyHealthOffenderSchema]

