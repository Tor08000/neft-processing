from __future__ import annotations

from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.crm import CRMSubscription
from app.models.documents import Document
from app.models.internal_ledger import InternalLedgerEntry, InternalLedgerTransaction
from app.models.invoice import Invoice
from app.models.money_flow import MoneyFlowEvent
from app.models.money_flow_v3 import MoneyFlowLink, MoneyInvariantSnapshot
from app.services.crm import repository
from app.services.money_flow.snapshots import snapshot_status
from app.services.money_flow.states import MoneyFlowType


def _build_invoice_idempotency_keys(subscription_id: str, period_id: str) -> list[str]:
    return [
        f"subscription:{subscription_id}:period:{period_id}:v2",
        f"subscription:{subscription_id}:period:{period_id}:v1",
    ]


def build_subscription_cfo_explain(
    db: Session,
    *,
    subscription_id: str,
    billing_period_id: str,
) -> dict[str, Any]:
    subscription = db.get(CRMSubscription, subscription_id)
    if subscription is None:
        raise ValueError("subscription not found")

    segments = repository.list_subscription_segments(
        db,
        subscription_id=subscription_id,
        billing_period_id=billing_period_id,
    )
    counters = repository.list_usage_counters(
        db,
        subscription_id=subscription_id,
        billing_period_id=billing_period_id,
    )
    charges = repository.list_subscription_charges(
        db,
        subscription_id=subscription_id,
        billing_period_id=billing_period_id,
    )

    invoice = None
    for key in _build_invoice_idempotency_keys(subscription_id, billing_period_id):
        invoice = db.execute(select(Invoice).where(Invoice.external_number == key)).scalars().first()
        if invoice:
            break

    documents: list[Document] = []
    if invoice is not None:
        documents = (
            db.execute(
                select(Document)
                .where(Document.client_id == subscription.client_id)
                .where(Document.period_from == invoice.period_from)
                .where(Document.period_to == invoice.period_to)
            )
            .scalars()
            .all()
        )

    ledger_summary = None
    if invoice is not None:
        ledger_tx = (
            db.execute(
                select(InternalLedgerTransaction)
                .where(InternalLedgerTransaction.external_ref_type == "INVOICE")
                .where(InternalLedgerTransaction.external_ref_id == invoice.id)
            )
            .scalars()
            .first()
        )
        if ledger_tx:
            entries = (
                db.execute(
                    select(InternalLedgerEntry).where(InternalLedgerEntry.ledger_transaction_id == ledger_tx.id)
                )
                .scalars()
                .all()
            )
            debit_total = sum(entry.amount for entry in entries if entry.direction.value == "DEBIT")
            credit_total = sum(entry.amount for entry in entries if entry.direction.value == "CREDIT")
            balanced = debit_total == credit_total
            ledger_summary = {
                "ledger_transaction_id": str(ledger_tx.id),
                "balanced": balanced,
                "entries": [
                    {
                        "account": str(entry.account_id),
                        "direction": entry.direction.value,
                        "amount": int(entry.amount),
                        "currency": entry.currency,
                    }
                    for entry in entries
                ],
            }

    link_conditions = [MoneyFlowLink.src_id == subscription_id, MoneyFlowLink.dst_id == subscription_id]
    if invoice is not None:
        link_conditions.extend([MoneyFlowLink.src_id == invoice.id, MoneyFlowLink.dst_id == invoice.id])
    link_query = select(MoneyFlowLink).where(or_(*link_conditions))
    links = db.execute(link_query).scalars().all()

    snapshots = []
    if invoice is not None:
        snapshots = (
            db.execute(select(MoneyInvariantSnapshot).where(MoneyInvariantSnapshot.flow_ref_id == invoice.id))
            .scalars()
            .all()
        )

    money_flow_events = []
    if invoice is not None:
        money_flow_events = (
            db.execute(
                select(MoneyFlowEvent)
                .where(MoneyFlowEvent.flow_type == MoneyFlowType.SUBSCRIPTION_CHARGE)
                .where(MoneyFlowEvent.flow_ref_id == invoice.id)
            )
            .scalars()
            .all()
        )

    invoice_payload = None
    if invoice is not None:
        invoice_payload = {
            "invoice_id": invoice.id,
            "status": invoice.status.value,
            "total_with_tax": int(invoice.total_with_tax or 0),
            "amount_paid": int(invoice.amount_paid or 0),
            "amount_due": int(invoice.amount_due or 0),
        }

    segments_payload = [
        {
            "id": str(segment.id),
            "segment_start": segment.segment_start,
            "segment_end": segment.segment_end,
            "tariff_plan_id": segment.tariff_plan_id,
            "status": segment.status.value,
            "reason": segment.reason.value if segment.reason else None,
            "days_count": segment.days_count,
        }
        for segment in segments
    ]

    usage_payload = [
        {
            "id": str(counter.id),
            "metric": counter.metric.value,
            "value": int(counter.value),
            "limit_value": int(counter.limit_value) if counter.limit_value is not None else None,
            "overage": int(counter.overage) if counter.overage is not None else None,
            "segment_id": str(counter.segment_id) if counter.segment_id else None,
        }
        for counter in counters
    ]

    charges_payload = [
        {
            "id": str(charge.id),
            "code": charge.code,
            "amount": int(charge.amount),
            "quantity": int(charge.quantity),
            "unit_price": int(charge.unit_price),
            "segment_id": str(charge.segment_id) if charge.segment_id else None,
            "charge_key": charge.charge_key,
            "explain": charge.explain,
        }
        for charge in charges
    ]

    money_flow_summary = {
        "link_count": len(links),
        "event_count": len(money_flow_events),
    }

    replay_payload = {"status": "not_run"}

    snapshot_summary = snapshot_status(snapshots)

    return {
        "subscription_id": subscription_id,
        "billing_period_id": billing_period_id,
        "segments": segments_payload,
        "usage_counters": usage_payload,
        "charges": charges_payload,
        "invoice": invoice_payload,
        "documents": [str(document.id) for document in documents],
        "ledger": ledger_summary,
        "money_flow": money_flow_summary,
        "snapshots": snapshot_summary,
        "replay": replay_payload,
        "charge_ids": [str(charge.id) for charge in charges],
        "counter_ids": [str(counter.id) for counter in counters],
        "money_flow_event_ids": [str(event.id) for event in money_flow_events],
        "snapshot_ids": [str(snapshot.id) for snapshot in snapshots],
        "link_ids": [str(link.id) for link in links],
    }


__all__ = ["build_subscription_cfo_explain"]
