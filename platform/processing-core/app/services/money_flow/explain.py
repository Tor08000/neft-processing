from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.internal_ledger import InternalLedgerAccount, InternalLedgerEntry, InternalLedgerTransaction
from app.models.money_flow import MoneyFlowEvent
from app.models.risk_decision import RiskDecision
from app.services.money_flow.errors import MoneyFlowNotFound
from app.services.money_flow.states import MoneyFlowState, MoneyFlowType


@dataclass(frozen=True)
class LedgerEntrySummary:
    account: str
    direction: str
    amount: int
    currency: str


@dataclass(frozen=True)
class LedgerSummary:
    ledger_transaction_id: str
    balanced: bool
    entries: list[LedgerEntrySummary]


@dataclass(frozen=True)
class MoneyExplain:
    flow_type: MoneyFlowType
    flow_ref_id: str
    state: MoneyFlowState
    ledger: LedgerSummary | None
    invariants: dict[str, Any]
    risk: dict[str, Any] | None
    notes: list[str]
    event_id: str
    created_at: datetime


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def build_explain_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    canonical_payload = json.loads(_canonical_json(payload))
    digest = sha256(_canonical_json(canonical_payload).encode("utf-8")).hexdigest()
    return {"hash": digest, "payload": canonical_payload}


def _build_ledger_summary(entries: Iterable[InternalLedgerEntry], account_map: dict[str, InternalLedgerAccount]) -> LedgerSummary:
    entry_summaries: list[LedgerEntrySummary] = []
    debit_total = 0
    credit_total = 0
    currencies = set()
    ledger_transaction_id = None
    for entry in entries:
        account = account_map.get(entry.account_id)
        account_type = account.account_type.value if account else "UNKNOWN"
        ledger_transaction_id = entry.ledger_transaction_id
        entry_summaries.append(
            LedgerEntrySummary(
                account=account_type,
                direction=entry.direction.value,
                amount=entry.amount,
                currency=entry.currency,
            )
        )
        currencies.add(entry.currency)
        if entry.direction.value == "DEBIT":
            debit_total += entry.amount
        else:
            credit_total += entry.amount

    balanced = debit_total == credit_total and len(currencies) <= 1
    return LedgerSummary(
        ledger_transaction_id=str(ledger_transaction_id) if ledger_transaction_id else "",
        balanced=balanced,
        entries=entry_summaries,
    )


def build_money_explain(db: Session, flow_type: MoneyFlowType, flow_ref_id: str) -> MoneyExplain:
    event = (
        db.execute(
            select(MoneyFlowEvent)
            .where(MoneyFlowEvent.flow_type == flow_type)
            .where(MoneyFlowEvent.flow_ref_id == flow_ref_id)
            .order_by(MoneyFlowEvent.created_at.desc())
        )
        .scalars()
        .first()
    )
    if event is None:
        raise MoneyFlowNotFound("money_flow_not_found")

    ledger_summary = None
    invariant_checks: list[str] = []
    invariant_failed: list[str] = []
    if event.ledger_transaction_id:
        entries = (
            db.execute(
                select(InternalLedgerEntry).where(
                    InternalLedgerEntry.ledger_transaction_id == event.ledger_transaction_id
                )
            )
            .scalars()
            .all()
        )
        account_ids = {entry.account_id for entry in entries}
        accounts = (
            db.execute(select(InternalLedgerAccount).where(InternalLedgerAccount.id.in_(account_ids)))
            .scalars()
            .all()
        )
        account_map = {account.id: account for account in accounts}
        ledger_summary = _build_ledger_summary(entries, account_map)

        invariant_checks = ["ledger_balanced", "currency_match"]
        if ledger_summary.balanced:
            pass
        else:
            invariant_failed = ["ledger_balanced", "currency_match"]

    invariants = {
        "passed": len(invariant_failed) == 0,
        "checks": invariant_checks,
        "failed_checks": invariant_failed,
    }

    risk_payload = None
    if event.risk_decision_id:
        risk_decision = db.get(RiskDecision, event.risk_decision_id)
        if risk_decision is not None:
            risk_payload = {
                "decision_id": risk_decision.decision_id,
                "outcome": risk_decision.outcome.value,
                "score": risk_decision.score,
            }

    notes = []
    if event.state_from == event.state_to:
        notes.append("idempotent")
    if event.meta and isinstance(event.meta, dict) and event.meta.get("cross_period"):
        notes.append("cross_period")

    return MoneyExplain(
        flow_type=event.flow_type,
        flow_ref_id=event.flow_ref_id,
        state=event.state_to,
        ledger=ledger_summary,
        invariants=invariants,
        risk=risk_payload,
        notes=notes,
        event_id=event.id,
        created_at=event.created_at,
    )


__all__ = ["MoneyExplain", "build_explain_snapshot", "build_money_explain"]
