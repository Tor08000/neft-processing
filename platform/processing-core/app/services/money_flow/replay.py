from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.billing_period import BillingPeriod
from app.models.fuel import FuelTransaction, FuelTransactionStatus
from app.models.internal_ledger import InternalLedgerEntry, InternalLedgerEntryDirection, InternalLedgerTransaction, InternalLedgerTransactionType
from app.models.invoice import Invoice, InvoiceLine
from app.models.money_flow_v3 import MoneyFlowLink, MoneyFlowLinkNodeType, MoneyFlowLinkType
from app.services.money_flow.diff import MoneyFlowDiff, diff_snapshots
from app.services.money_flow.graph import MoneyFlowGraphBuilder, ensure_money_flow_links


class MoneyReplayMode(str, Enum):
    DRY_RUN = "DRY_RUN"
    COMPARE = "COMPARE"
    REBUILD_LINKS = "REBUILD_LINKS"


class MoneyReplayScope(str, Enum):
    SUBSCRIPTIONS = "SUBSCRIPTIONS"
    FUEL = "FUEL"
    ALL = "ALL"


@dataclass(frozen=True)
class MoneyReplayResult:
    mode: MoneyReplayMode
    scope: MoneyReplayScope
    recompute_hash: str | None
    diff: MoneyFlowDiff | None
    links_rebuilt: int | None
    summary: dict[str, Any] | None


def build_recompute_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256(canonical.encode("utf-8")).hexdigest()


def run_money_flow_replay(
    db: Session,
    *,
    client_id: str,
    billing_period_id: str,
    mode: MoneyReplayMode,
    scope: MoneyReplayScope,
    expected_snapshot: dict[str, Any] | None = None,
    actual_snapshot: dict[str, Any] | None = None,
) -> MoneyReplayResult:
    recompute_hash = None
    diff = None
    links_rebuilt = None
    summary = None

    if scope == MoneyReplayScope.FUEL:
        period = db.get(BillingPeriod, billing_period_id)
        if period is None:
            raise ValueError("billing period not found")
        fuel_totals = _fuel_totals(db, client_id=client_id, period=period)
        summary = fuel_totals.copy()

        if mode == MoneyReplayMode.DRY_RUN:
            recompute_hash = build_recompute_hash(
                {
                    "client_id": client_id,
                    "billing_period_id": billing_period_id,
                    "scope": scope.value,
                    "fuel_totals": fuel_totals,
                }
            )
        elif mode == MoneyReplayMode.COMPARE:
            diff = _compare_fuel_replay(db, client_id=client_id, period=period, fuel_totals=fuel_totals)
        elif mode == MoneyReplayMode.REBUILD_LINKS:
            links_rebuilt = _rebuild_fuel_links(db, client_id=client_id, period=period)
    else:
        if mode == MoneyReplayMode.DRY_RUN:
            recompute_hash = build_recompute_hash(
                {
                    "client_id": client_id,
                    "billing_period_id": billing_period_id,
                    "scope": scope.value,
                }
            )
        elif mode == MoneyReplayMode.COMPARE:
            diff = diff_snapshots(expected_snapshot or {}, actual_snapshot or {})
        elif mode == MoneyReplayMode.REBUILD_LINKS:
            links_rebuilt = 0

    return MoneyReplayResult(
        mode=mode,
        scope=scope,
        recompute_hash=recompute_hash,
        diff=diff,
        links_rebuilt=links_rebuilt,
        summary=summary,
    )


def _fuel_totals(db: Session, *, client_id: str, period: BillingPeriod) -> dict[str, int]:
    totals = (
        db.execute(
            select(
                func.count(FuelTransaction.id),
                func.coalesce(func.sum(FuelTransaction.volume_ml), 0),
                func.coalesce(func.sum(FuelTransaction.amount_total_minor), 0),
            )
            .where(FuelTransaction.client_id == client_id)
            .where(FuelTransaction.status == FuelTransactionStatus.SETTLED)
            .where(FuelTransaction.occurred_at >= period.start_at)
            .where(FuelTransaction.occurred_at <= period.end_at)
        )
        .one()
    )
    return {
        "tx_count": int(totals[0] or 0),
        "volume_ml": int(totals[1] or 0),
        "amount_minor": int(totals[2] or 0),
    }


def _fuel_ledger_summary(db: Session, *, fuel_tx_ids: list[str]) -> dict[str, int]:
    if not fuel_tx_ids:
        return {"tx_count": 0, "amount_minor": 0}
    ledger_transactions = (
        db.execute(
            select(InternalLedgerTransaction)
            .where(InternalLedgerTransaction.transaction_type == InternalLedgerTransactionType.FUEL_SETTLEMENT)
            .where(InternalLedgerTransaction.external_ref_id.in_(fuel_tx_ids))
        )
        .scalars()
        .all()
    )
    ledger_ids = [tx.id for tx in ledger_transactions]
    if not ledger_ids:
        return {"tx_count": 0, "amount_minor": 0}
    amount_total = (
        db.execute(
            select(func.coalesce(func.sum(InternalLedgerEntry.amount), 0))
            .where(InternalLedgerEntry.ledger_transaction_id.in_(ledger_ids))
            .where(InternalLedgerEntry.direction == InternalLedgerEntryDirection.DEBIT)
        )
        .scalar_one()
    )
    return {"tx_count": len(ledger_transactions), "amount_minor": int(amount_total or 0)}


def _fuel_invoice_summary(db: Session, *, client_id: str, period: BillingPeriod) -> dict[str, int]:
    invoices = (
        db.execute(
            select(Invoice).where(
                (Invoice.client_id == client_id)
                & (Invoice.billing_period_id == str(period.id))
            )
        )
        .scalars()
        .all()
    )
    if not invoices:
        return {"amount_minor": 0, "volume_ml": 0}
    invoice_ids = [invoice.id for invoice in invoices]
    lines = (
        db.execute(select(InvoiceLine).where(InvoiceLine.invoice_id.in_(invoice_ids)))
        .scalars()
        .all()
    )
    fuel_lines = [line for line in lines if "fuel" in (line.product_id or "").lower()]
    amount_total = sum(int(line.line_amount or 0) for line in fuel_lines)
    volume_ml = 0
    for line in fuel_lines:
        if line.liters is None:
            continue
        volume_ml += int(float(line.liters) * 1000)
    return {"amount_minor": int(amount_total), "volume_ml": int(volume_ml)}


def _compare_fuel_replay(
    db: Session,
    *,
    client_id: str,
    period: BillingPeriod,
    fuel_totals: dict[str, int],
) -> MoneyFlowDiff:
    fuel_transactions = (
        db.execute(
            select(FuelTransaction)
            .where(FuelTransaction.client_id == client_id)
            .where(FuelTransaction.status == FuelTransactionStatus.SETTLED)
            .where(FuelTransaction.occurred_at >= period.start_at)
            .where(FuelTransaction.occurred_at <= period.end_at)
        )
        .scalars()
        .all()
    )
    fuel_tx_ids = [str(tx.id) for tx in fuel_transactions]
    missing_ledger_postings = sum(1 for tx in fuel_transactions if not tx.ledger_transaction_id)
    missing_link_types: list[str] = []
    missing_links_count = 0
    if fuel_tx_ids:
        invoice_ids = (
            db.execute(
                select(Invoice.id).where(
                    (Invoice.client_id == client_id)
                    & (Invoice.billing_period_id == str(period.id))
                )
            )
            .scalars()
            .all()
        )
        link_rows = (
            db.execute(
                select(MoneyFlowLink).where(
                    MoneyFlowLink.src_type == MoneyFlowLinkNodeType.FUEL_TX,
                    MoneyFlowLink.src_id.in_(fuel_tx_ids),
                )
            )
            .scalars()
            .all()
        )
        ledger_links = {
            link.src_id for link in link_rows
            if link.link_type == MoneyFlowLinkType.POSTS and link.dst_type == MoneyFlowLinkNodeType.LEDGER_TX
        }
        period_links = {
            link.src_id for link in link_rows
            if link.link_type == MoneyFlowLinkType.RELATES and link.dst_type == MoneyFlowLinkNodeType.BILLING_PERIOD
        }
        invoice_links = {
            link.src_id for link in link_rows
            if link.link_type == MoneyFlowLinkType.FEEDS and link.dst_type == MoneyFlowLinkNodeType.INVOICE
        }
        missing_ledger_links = [tx_id for tx_id in fuel_tx_ids if tx_id not in ledger_links]
        missing_period_links = [tx_id for tx_id in fuel_tx_ids if tx_id not in period_links]
        missing_invoice_links = []
        if invoice_ids:
            missing_invoice_links = [tx_id for tx_id in fuel_tx_ids if tx_id not in invoice_links]
        if missing_ledger_links:
            missing_link_types.append("fuel_tx_ledger_link")
        if missing_period_links:
            missing_link_types.append("fuel_tx_billing_period_link")
        if missing_invoice_links:
            missing_link_types.append("fuel_tx_invoice_link")
        missing_links_count = len(missing_ledger_links) + len(missing_period_links) + len(missing_invoice_links)

    ledger_summary = _fuel_ledger_summary(db, fuel_tx_ids=fuel_tx_ids)
    invoice_summary = _fuel_invoice_summary(db, client_id=client_id, period=period)

    mismatched_totals: list[str] = []
    if ledger_summary["tx_count"] != fuel_totals["tx_count"]:
        mismatched_totals.append("tx_count")
    if ledger_summary["amount_minor"] != fuel_totals["amount_minor"]:
        mismatched_totals.append("amount_minor")

    mismatched_invoice: list[str] = []
    if invoice_summary["amount_minor"] and invoice_summary["amount_minor"] != fuel_totals["amount_minor"]:
        mismatched_invoice.append("amount_minor")
    if invoice_summary["volume_ml"] and invoice_summary["volume_ml"] != fuel_totals["volume_ml"]:
        mismatched_invoice.append("volume_ml")

    recommended_action = "NONE"
    if missing_links_count:
        recommended_action = "REBUILD_LINKS"
    elif missing_ledger_postings:
        recommended_action = "REBUILD_POSTINGS"
    elif mismatched_totals or mismatched_invoice:
        recommended_action = "REVIEW_TOTALS"

    return MoneyFlowDiff(
        mismatched_totals=mismatched_totals,
        missing_links=missing_link_types,
        broken_snapshots=[],
        recommended_action=recommended_action,
        missing_links_count=missing_links_count,
        missing_ledger_postings=missing_ledger_postings,
        mismatched_invoice_aggregation=mismatched_invoice,
    )


def _rebuild_fuel_links(db: Session, *, client_id: str, period: BillingPeriod) -> int:
    fuel_transactions = (
        db.execute(
            select(FuelTransaction)
            .where(FuelTransaction.client_id == client_id)
            .where(FuelTransaction.status.in_({FuelTransactionStatus.SETTLED, FuelTransactionStatus.REVERSED}))
            .where(FuelTransaction.occurred_at >= period.start_at)
            .where(FuelTransaction.occurred_at <= period.end_at)
        )
        .scalars()
        .all()
    )
    if not fuel_transactions:
        return 0

    invoices = (
        db.execute(
            select(Invoice).where(
                (Invoice.client_id == client_id)
                & (Invoice.billing_period_id == str(period.id))
            )
        )
        .scalars()
        .all()
    )
    invoices_by_currency = {invoice.currency: invoice for invoice in invoices}
    builders: dict[int, MoneyFlowGraphBuilder] = {}
    for tx in fuel_transactions:
        builder = builders.get(tx.tenant_id)
        if builder is None:
            builder = MoneyFlowGraphBuilder(tenant_id=tx.tenant_id, client_id=tx.client_id)
            builders[tx.tenant_id] = builder
        builder.add_link(
            src_type=MoneyFlowLinkNodeType.FUEL_TX,
            src_id=str(tx.id),
            link_type=MoneyFlowLinkType.RELATES,
            dst_type=MoneyFlowLinkNodeType.BILLING_PERIOD,
            dst_id=str(period.id),
            meta={"occurred_at": tx.occurred_at.isoformat()},
        )
        if tx.ledger_transaction_id:
            builder.add_link(
                src_type=MoneyFlowLinkNodeType.FUEL_TX,
                src_id=str(tx.id),
                link_type=MoneyFlowLinkType.POSTS,
                dst_type=MoneyFlowLinkNodeType.LEDGER_TX,
                dst_id=str(tx.ledger_transaction_id),
            )
        invoice = invoices_by_currency.get(tx.currency)
        if invoice:
            builder.add_link(
                src_type=MoneyFlowLinkNodeType.FUEL_TX,
                src_id=str(tx.id),
                link_type=MoneyFlowLinkType.FEEDS,
                dst_type=MoneyFlowLinkNodeType.INVOICE,
                dst_id=invoice.id,
            )

    created = 0
    for tenant_id, builder in builders.items():
        records = ensure_money_flow_links(
            db,
            tenant_id=tenant_id,
            client_id=client_id,
            links=builder.build(),
        )
        created += len(records)
    return created


__all__ = [
    "MoneyReplayMode",
    "MoneyReplayScope",
    "MoneyReplayResult",
    "build_recompute_hash",
    "run_money_flow_replay",
]
