from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import func, select, true
from sqlalchemy.orm import Session

from app.models.crm import CRMSubscriptionCharge, CRMSubscriptionPeriodSegment
from app.models.internal_ledger import InternalLedgerEntry, InternalLedgerTransaction
from app.models.invoice import Invoice
from app.models.money_flow import MoneyFlowEvent
from app.models.money_flow_v3 import (
    MoneyFlowLink,
    MoneyFlowLinkNodeType,
    MoneyFlowLinkType,
    MoneyInvariantSnapshot,
    MoneyInvariantSnapshotPhase,
)
from app.services.money_flow.states import MoneyFlowState, MoneyFlowType


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
    missing_money_flow_links: int
    invoices_missing_subscription_links: int
    charges_missing_invoice_links: int
    charge_key_duplicates: int
    segment_gaps_or_overlaps: int
    missing_snapshots: int
    missing_subscription_snapshots: int
    disconnected_graph: int
    cfo_explain_not_ready: int
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
        missing_money_flow_links=_count_missing_links(db),
        invoices_missing_subscription_links=_count_missing_subscription_links(db),
        charges_missing_invoice_links=_count_missing_charge_links(db),
        charge_key_duplicates=_count_charge_key_duplicates(db),
        segment_gaps_or_overlaps=_count_segment_gaps(db),
        missing_snapshots=_count_missing_snapshots(db),
        missing_subscription_snapshots=_count_missing_subscription_snapshots(db),
        disconnected_graph=_count_disconnected_graph(db),
        cfo_explain_not_ready=_count_cfo_not_ready(db),
        top_offenders=offenders[:20],
    )


def _count_missing_links(db: Session) -> int:
    invoices = db.execute(select(Invoice.id)).scalars().all()
    if not invoices:
        return 0
    links = (
        db.execute(
            select(MoneyFlowLink).where(
                (MoneyFlowLink.src_type == MoneyFlowLinkNodeType.INVOICE)
                | (MoneyFlowLink.dst_type == MoneyFlowLinkNodeType.INVOICE)
            )
        )
        .scalars()
        .all()
    )
    linked_invoice_ids = {
        link.src_id if link.src_type == MoneyFlowLinkNodeType.INVOICE else link.dst_id for link in links
    }
    return sum(1 for invoice_id in invoices if invoice_id not in linked_invoice_ids)


def _count_missing_subscription_links(db: Session) -> int:
    invoices = db.execute(select(Invoice.id)).scalars().all()
    if not invoices:
        return 0
    links = (
        db.execute(
            select(MoneyFlowLink).where(
                (MoneyFlowLink.src_type == MoneyFlowLinkNodeType.SUBSCRIPTION)
                & (MoneyFlowLink.dst_type == MoneyFlowLinkNodeType.INVOICE)
            )
        )
        .scalars()
        .all()
    )
    linked_invoice_ids = {link.dst_id for link in links}
    return sum(1 for invoice_id in invoices if invoice_id not in linked_invoice_ids)


def _count_missing_charge_links(db: Session) -> int:
    charge_ids = db.execute(select(CRMSubscriptionCharge.id)).scalars().all()
    if not charge_ids:
        return 0
    links = (
        db.execute(
            select(MoneyFlowLink).where(
                (MoneyFlowLink.src_type == MoneyFlowLinkNodeType.SUBSCRIPTION_CHARGE)
                & (MoneyFlowLink.dst_type == MoneyFlowLinkNodeType.INVOICE)
            )
        )
        .scalars()
        .all()
    )
    linked_charge_ids = {link.src_id for link in links}
    return sum(1 for charge_id in charge_ids if str(charge_id) not in linked_charge_ids)


def _count_charge_key_duplicates(db: Session) -> int:
    duplicates = (
        db.execute(
            select(
                CRMSubscriptionCharge.subscription_id,
                CRMSubscriptionCharge.billing_period_id,
                CRMSubscriptionCharge.charge_key,
                func.count(CRMSubscriptionCharge.id),
            )
            .where(CRMSubscriptionCharge.charge_key.isnot(None))
            .group_by(
                CRMSubscriptionCharge.subscription_id,
                CRMSubscriptionCharge.billing_period_id,
                CRMSubscriptionCharge.charge_key,
            )
            .having(func.count(CRMSubscriptionCharge.id) > 1)
        )
        .all()
    )
    return len(duplicates)


def _count_segment_gaps(db: Session) -> int:
    segments = (
        db.execute(
            select(CRMSubscriptionPeriodSegment).order_by(
                CRMSubscriptionPeriodSegment.subscription_id,
                CRMSubscriptionPeriodSegment.billing_period_id,
                CRMSubscriptionPeriodSegment.segment_start,
            )
        )
        .scalars()
        .all()
    )
    if not segments:
        return 0
    issues = set()
    previous = None
    for segment in segments:
        key = (segment.subscription_id, segment.billing_period_id)
        if previous and (previous.subscription_id, previous.billing_period_id) == key:
            if previous.segment_end < segment.segment_start or previous.segment_end > segment.segment_start:
                issues.add(key)
        previous = segment
    return len(issues)


def _count_missing_snapshots(db: Session) -> int:
    events = db.execute(select(MoneyFlowEvent.id)).scalars().all()
    if not events:
        return 0
    snapshots = (
        db.execute(select(MoneyInvariantSnapshot).where(MoneyInvariantSnapshot.event_id.in_(events)))
        .scalars()
        .all()
    )
    phases_by_event: dict[str, set[MoneyInvariantSnapshotPhase]] = {}
    for snapshot in snapshots:
        phases_by_event.setdefault(str(snapshot.event_id), set()).add(snapshot.phase)
    missing = 0
    for event_id in events:
        phases = phases_by_event.get(str(event_id), set())
        if MoneyInvariantSnapshotPhase.BEFORE not in phases or MoneyInvariantSnapshotPhase.AFTER not in phases:
            missing += 1
    return missing


def _count_missing_subscription_snapshots(db: Session) -> int:
    events = (
        db.execute(
            select(MoneyFlowEvent.id)
            .where(MoneyFlowEvent.flow_type == MoneyFlowType.SUBSCRIPTION_CHARGE)
        )
        .scalars()
        .all()
    )
    if not events:
        return 0
    snapshots = (
        db.execute(select(MoneyInvariantSnapshot).where(MoneyInvariantSnapshot.event_id.in_(events)))
        .scalars()
        .all()
    )
    phases_by_event: dict[str, set[MoneyInvariantSnapshotPhase]] = {}
    for snapshot in snapshots:
        phases_by_event.setdefault(str(snapshot.event_id), set()).add(snapshot.phase)
    missing = 0
    for event_id in events:
        phases = phases_by_event.get(str(event_id), set())
        if MoneyInvariantSnapshotPhase.BEFORE not in phases or MoneyInvariantSnapshotPhase.AFTER not in phases:
            missing += 1
    return missing


def _count_disconnected_graph(db: Session) -> int:
    invoices = db.execute(select(Invoice.id)).scalars().all()
    if not invoices:
        return 0
    links = (
        db.execute(
            select(MoneyFlowLink).where(
                (MoneyFlowLink.dst_type == MoneyFlowLinkNodeType.INVOICE)
                & (MoneyFlowLink.link_type == MoneyFlowLinkType.GENERATES)
                & (MoneyFlowLink.src_type == MoneyFlowLinkNodeType.SUBSCRIPTION_CHARGE)
            )
        )
        .scalars()
        .all()
    )
    connected = {link.dst_id for link in links}
    return sum(1 for invoice_id in invoices if invoice_id not in connected)


def _count_cfo_not_ready(db: Session) -> int:
    invoices = db.execute(select(Invoice.id)).scalars().all()
    if not invoices:
        return 0
    links = (
        db.execute(
            select(MoneyFlowLink).where(
                (MoneyFlowLink.src_type == MoneyFlowLinkNodeType.INVOICE)
                & (MoneyFlowLink.link_type == MoneyFlowLinkType.POSTS)
                & (MoneyFlowLink.dst_type == MoneyFlowLinkNodeType.LEDGER_TX)
            )
        )
        .scalars()
        .all()
    )
    ledger_ready = {link.src_id for link in links}
    snapshots = (
        db.execute(select(MoneyInvariantSnapshot).where(MoneyInvariantSnapshot.flow_ref_id.in_(invoices)))
        .scalars()
        .all()
    )
    snapshot_ready: dict[str, bool] = {}
    for snapshot in snapshots:
        if snapshot.passed is False:
            snapshot_ready[snapshot.flow_ref_id] = False
        else:
            snapshot_ready.setdefault(snapshot.flow_ref_id, True)
    not_ready = 0
    for invoice_id in invoices:
        if invoice_id not in ledger_ready or not snapshot_ready.get(invoice_id, False):
            not_ready += 1
    return not_ready


__all__ = ["MoneyHealthOffender", "MoneyHealthReport", "build_money_health"]
