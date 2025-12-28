from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.services.money_flow.replay import MoneyReplayMode, MoneyReplayScope
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
    missing_money_flow_links: int
    missing_snapshots: int
    disconnected_graph: int
    cfo_explain_not_ready: int
    top_offenders: list[MoneyHealthOffenderSchema]


class CFOExplainTotalsSchema(BaseModel):
    total_with_tax: int
    amount_paid: int
    amount_due: int


class CFOExplainBreakdownSchema(BaseModel):
    base_fee: int
    overage: int
    fuel_usage: int
    logistics_usage: int


class CFOExplainLinksSchema(BaseModel):
    charges: list[str]
    usage: list[str]
    ledger_postings: list[str]
    payments: list[str]


class CFOExplainSnapshotsSchema(BaseModel):
    before_count: int
    after_count: int
    failed_count: int
    passed: bool


class CFOExplainResponse(BaseModel):
    invoice_id: str
    client_id: str
    currency: str
    totals: CFOExplainTotalsSchema
    breakdown: CFOExplainBreakdownSchema
    links: CFOExplainLinksSchema
    snapshots: CFOExplainSnapshotsSchema
    anomalies: list[str]


class MoneyReplayRequest(BaseModel):
    client_id: str
    billing_period_id: str
    mode: MoneyReplayMode
    scope: MoneyReplayScope


class MoneyReplayDiffSchema(BaseModel):
    mismatched_totals: list[str]
    missing_links: list[str]
    broken_snapshots: list[str]
    recommended_action: str


class MoneyReplayResponse(BaseModel):
    mode: MoneyReplayMode
    scope: MoneyReplayScope
    recompute_hash: str | None
    diff: MoneyReplayDiffSchema | None
    links_rebuilt: int | None
