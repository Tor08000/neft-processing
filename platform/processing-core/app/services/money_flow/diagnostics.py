from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import select, true
from sqlalchemy.orm import Session

from app.models.internal_ledger import InternalLedgerEntry, InternalLedgerTransaction
from app.models.money_flow import MoneyFlowEvent
from app.services.money_flow.states import MoneyFlowState


@dataclass(frozen=True)
class MoneyHealthOffender:
    flow_type: str
    flow_ref_id: str
    state: str
    age_hours: int
    reason: str


@dataclass(frozen=True)
class MoneyHealthReport:
    orphan_ledger_transactions: int
    missing_ledger_postings: int
    invariant_violations: int
    stuck_authorized: int
    stuck_pending_settlement: int
    cross_period_anomalies: int
    top_offenders: list[MoneyHealthOffender]


def _ledger_invariant_violations(entries: Iterable[InternalLedgerEntry]) -> bool:
    debit_total = 0
    credit_total = 0
    currencies = set()
    for entry in entries:
        currencies.add(entry.currency)
        if entry.direction.value == "DEBIT":
            debit_total += entry.amount
        else:
            credit_total += entry.amount
    if debit_total != credit_total:
        return True
    if len(currencies) > 1:
        return True
    return False


def build_money_health(db: Session, *, stale_hours: int = 24) -> MoneyHealthReport:
    now = datetime.now(timezone.utc)
    stale_before = now - timedelta(hours=stale_hours)

    ledger_ids = db.execute(select(MoneyFlowEvent.ledger_transaction_id).where(MoneyFlowEvent.ledger_transaction_id.isnot(None))).all()
    ledger_id_set = {row[0] for row in ledger_ids if row[0]}
    orphan_condition = (
        InternalLedgerTransaction.id.notin_(ledger_id_set)
        if ledger_id_set
        else true()
    )
    orphan_ledger_transactions = (
        db.execute(select(InternalLedgerTransaction).where(orphan_condition)).scalars().all()
    )

    missing_ledger_postings = (
        db.execute(
            select(MoneyFlowEvent)
            .where(MoneyFlowEvent.state_to == MoneyFlowState.SETTLED)
            .where(MoneyFlowEvent.ledger_transaction_id.is_(None))
        )
        .scalars()
        .all()
    )

    settled_events = (
        db.execute(
            select(MoneyFlowEvent)
            .where(MoneyFlowEvent.state_to == MoneyFlowState.SETTLED)
            .where(MoneyFlowEvent.ledger_transaction_id.isnot(None))
        )
        .scalars()
        .all()
    )
    invariant_violations = 0
    for event in settled_events:
        entries = (
            db.execute(
                select(InternalLedgerEntry).where(
                    InternalLedgerEntry.ledger_transaction_id == event.ledger_transaction_id
                )
            )
            .scalars()
            .all()
        )
        if entries and _ledger_invariant_violations(entries):
            invariant_violations += 1

    all_events = (
        db.execute(select(MoneyFlowEvent).order_by(MoneyFlowEvent.created_at.desc()))
        .scalars()
        .all()
    )
    latest_by_flow: dict[tuple[str, str], MoneyFlowEvent] = {}
    for event in all_events:
        key = (event.flow_type.value, event.flow_ref_id)
        if key not in latest_by_flow:
            latest_by_flow[key] = event

    stuck_authorized = 0
    stuck_pending_settlement = 0
    cross_period_anomalies = 0
    offenders: list[MoneyHealthOffender] = []
    for event in latest_by_flow.values():
        if event.meta and isinstance(event.meta, dict) and event.meta.get("cross_period"):
            cross_period_anomalies += 1
        if event.created_at is None:
            continue
        if event.created_at < stale_before and event.state_to == MoneyFlowState.AUTHORIZED:
            stuck_authorized += 1
            offenders.append(
                MoneyHealthOffender(
                    flow_type=event.flow_type.value,
                    flow_ref_id=event.flow_ref_id,
                    state=event.state_to.value,
                    age_hours=int((now - event.created_at).total_seconds() // 3600),
                    reason="authorized_stale",
                )
            )
        if event.created_at < stale_before and event.state_to == MoneyFlowState.PENDING_SETTLEMENT:
            stuck_pending_settlement += 1
            offenders.append(
                MoneyHealthOffender(
                    flow_type=event.flow_type.value,
                    flow_ref_id=event.flow_ref_id,
                    state=event.state_to.value,
                    age_hours=int((now - event.created_at).total_seconds() // 3600),
                    reason="pending_settlement_stale",
                )
            )

    return MoneyHealthReport(
        orphan_ledger_transactions=len(orphan_ledger_transactions),
        missing_ledger_postings=len(missing_ledger_postings),
        invariant_violations=invariant_violations,
        stuck_authorized=stuck_authorized,
        stuck_pending_settlement=stuck_pending_settlement,
        cross_period_anomalies=cross_period_anomalies,
        top_offenders=offenders[:20],
    )


__all__ = ["MoneyHealthOffender", "MoneyHealthReport", "build_money_health"]
