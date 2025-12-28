from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.invoice import Invoice, InvoiceLine
from app.models.money_flow_v3 import MoneyFlowLink, MoneyFlowLinkNodeType, MoneyFlowLinkType, MoneyInvariantSnapshot
from app.services.money_flow.errors import MoneyFlowNotFound
from app.services.money_flow.snapshots import snapshot_status


@dataclass(frozen=True)
class CFOExplainTotals:
    total_with_tax: int
    amount_paid: int
    amount_due: int


@dataclass(frozen=True)
class CFOExplainBreakdown:
    base_fee: int
    overage: int
    fuel_usage: int
    logistics_usage: int


@dataclass(frozen=True)
class CFOExplainLinks:
    charges: list[str]
    usage: list[str]
    ledger_postings: list[str]
    payments: list[str]


@dataclass(frozen=True)
class CFOExplainSnapshotStatus:
    before_count: int
    after_count: int
    failed_count: int
    passed: bool


@dataclass(frozen=True)
class CFOExplainResponse:
    invoice_id: str
    client_id: str
    currency: str
    totals: CFOExplainTotals
    breakdown: CFOExplainBreakdown
    links: CFOExplainLinks
    snapshots: CFOExplainSnapshotStatus
    anomalies: list[str]


def _classify_line(line: InvoiceLine) -> str:
    product_id = (line.product_id or "").lower()
    if "fuel" in product_id:
        return "fuel_usage"
    if "logistics" in product_id:
        return "logistics_usage"
    if "overage" in product_id or "proration" in product_id or "usage" in product_id:
        return "overage"
    return "base_fee"


def summarize_invoice_lines(lines: Iterable[InvoiceLine]) -> CFOExplainBreakdown:
    totals = {
        "base_fee": 0,
        "overage": 0,
        "fuel_usage": 0,
        "logistics_usage": 0,
    }
    for line in lines:
        bucket = _classify_line(line)
        totals[bucket] += int(line.line_amount or 0)
    return CFOExplainBreakdown(**totals)


def _build_links(links: Iterable[MoneyFlowLink]) -> CFOExplainLinks:
    charges: list[str] = []
    usage: list[str] = []
    ledger_postings: list[str] = []
    payments: list[str] = []

    for link in links:
        if link.link_type == MoneyFlowLinkType.GENERATES and link.src_type == MoneyFlowLinkNodeType.SUBSCRIPTION_CHARGE:
            charges.append(link.src_id)
        if link.link_type == MoneyFlowLinkType.FEEDS and link.src_type == MoneyFlowLinkNodeType.FUEL_TX:
            usage.append(link.src_id)
        if link.link_type == MoneyFlowLinkType.POSTS and link.dst_type == MoneyFlowLinkNodeType.LEDGER_TX:
            ledger_postings.append(link.dst_id)
        if link.link_type == MoneyFlowLinkType.SETTLES and link.src_type == MoneyFlowLinkNodeType.PAYMENT:
            payments.append(link.src_id)

    return CFOExplainLinks(
        charges=sorted(set(charges)),
        usage=sorted(set(usage)),
        ledger_postings=sorted(set(ledger_postings)),
        payments=sorted(set(payments)),
    )


def build_cfo_explain(db: Session, *, invoice_id: str) -> CFOExplainResponse:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise MoneyFlowNotFound("invoice_not_found")

    lines = (
        db.execute(select(InvoiceLine).where(InvoiceLine.invoice_id == invoice_id))
        .scalars()
        .all()
    )
    breakdown = summarize_invoice_lines(lines)

    links = (
        db.execute(
            select(MoneyFlowLink).where(
                (MoneyFlowLink.src_id == invoice_id)
                | (MoneyFlowLink.dst_id == invoice_id)
            )
        )
        .scalars()
        .all()
    )
    links_summary = _build_links(links)

    snapshots = (
        db.execute(select(MoneyInvariantSnapshot).where(MoneyInvariantSnapshot.flow_ref_id == invoice_id))
        .scalars()
        .all()
    )
    snapshot_summary = snapshot_status(snapshots)
    snapshot_status_obj = CFOExplainSnapshotStatus(
        before_count=int(snapshot_summary["before_count"]),
        after_count=int(snapshot_summary["after_count"]),
        failed_count=int(snapshot_summary["failed_count"]),
        passed=bool(snapshot_summary["passed"]),
    )

    anomalies: list[str] = []
    if not links_summary.ledger_postings:
        anomalies.append("missing_ledger_posting")
    if not links_summary.charges:
        anomalies.append("missing_charge_links")
    if not snapshot_status_obj.passed:
        anomalies.append("snapshot_invariants_failed")

    return CFOExplainResponse(
        invoice_id=invoice.id,
        client_id=invoice.client_id,
        currency=invoice.currency,
        totals=CFOExplainTotals(
            total_with_tax=int(invoice.total_with_tax or 0),
            amount_paid=int(invoice.amount_paid or 0),
            amount_due=int(invoice.amount_due or 0),
        ),
        breakdown=breakdown,
        links=links_summary,
        snapshots=snapshot_status_obj,
        anomalies=anomalies,
    )


__all__ = [
    "CFOExplainResponse",
    "CFOExplainTotals",
    "CFOExplainBreakdown",
    "CFOExplainLinks",
    "CFOExplainSnapshotStatus",
    "build_cfo_explain",
    "summarize_invoice_lines",
]
