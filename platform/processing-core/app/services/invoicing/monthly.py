from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from dataclasses import dataclass
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_sessionmaker
from app.models.billing_summary import BillingSummary, BillingSummaryStatus
from app.models.billing_period import BillingPeriodStatus, BillingPeriodType
from app.models.fuel import FuelTransaction, FuelTransactionStatus
from app.models.invoice import Invoice, InvoiceLine, InvoiceStatus
from app.models.legal_graph import LegalEdgeType, LegalNodeType
from app.models.money_flow_v3 import MoneyFlowLinkNodeType, MoneyFlowLinkType
from app.repositories.billing_repository import BillingInvoiceData, BillingLineData, BillingRepository
from app.models.billing_job_run import BillingJobRun, BillingJobStatus, BillingJobType
from app.services.billing_job_runs import BillingJobRunService
from app.services.invoice_state_machine import InvoiceStateMachine
from app.services.billing_periods import BillingPeriodConflict, BillingPeriodService, period_bounds_for_dates
from app.services.finance_invariants import FinancialInvariantChecker
from app.services.legal_graph.registry import LegalGraphRegistry
from app.services.money_flow.graph import MoneyFlowGraphBuilder, ensure_money_flow_links
from neft_shared.logging_setup import get_logger

logger = get_logger(__name__)


@dataclass
class MonthlyInvoiceRunOutcome:
    invoices: list[Invoice]
    job_run: "BillingJobRun"
    metrics: dict[str, object]


def _default_month(now: datetime | None = None) -> date:
    tz = ZoneInfo(settings.NEFT_BILLING_TZ)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(tz).date()
    first_of_month = current.replace(day=1)
    previous_month_last_day = first_of_month - timedelta(days=1)
    return previous_month_last_day.replace(day=1)


def _month_bounds(target_month: date) -> tuple[date, date]:
    last_day = calendar.monthrange(target_month.year, target_month.month)[1]
    start = target_month.replace(day=1)
    end = target_month.replace(day=last_day)
    return start, end


def _group_summaries(summaries: list[BillingSummary]):
    grouped: dict[tuple[str, str], dict] = {}
    for summary in summaries:
        key = (summary.client_id, summary.currency or "RUB")
        bucket = grouped.setdefault(
            key,
            {"items": defaultdict(list)},
        )
        bucket["items"][summary.product_type or "UNKNOWN"].append(summary)
    return grouped


def _build_lines(product_summaries: list[BillingSummary]) -> BillingLineData:
    total_amount = sum(int(item.total_amount or 0) for item in product_summaries)
    total_quantity = None
    quantities = [item.total_quantity for item in product_summaries if item.total_quantity is not None]
    if quantities:
        total_quantity = sum(quantities)

    return BillingLineData(
        product_id=str(product_summaries[0].product_type or "UNKNOWN"),
        liters=total_quantity,
        unit_price=None,
        line_amount=total_amount,
        tax_amount=0,
    )


def _fuel_period_bounds(period_from: date, period_to: date) -> tuple[datetime, datetime]:
    tz = ZoneInfo(settings.NEFT_BILLING_TZ)
    start = datetime.combine(period_from, datetime.min.time()).replace(tzinfo=tz)
    end = datetime.combine(period_to, datetime.max.time()).replace(tzinfo=tz)
    return (
        start.astimezone(timezone.utc).replace(tzinfo=None),
        end.astimezone(timezone.utc).replace(tzinfo=None),
    )


def _link_fuel_transactions_to_invoice(session: Session, *, invoice: Invoice) -> None:
    start_ts, end_ts = _fuel_period_bounds(invoice.period_from, invoice.period_to)
    fuel_txs = (
        session.query(FuelTransaction)
        .filter(FuelTransaction.client_id == invoice.client_id)
        .filter(FuelTransaction.status == FuelTransactionStatus.SETTLED)
        .filter(FuelTransaction.occurred_at >= start_ts)
        .filter(FuelTransaction.occurred_at <= end_ts)
        .all()
    )
    if not fuel_txs:
        return
    registry = LegalGraphRegistry(session)
    invoice_nodes: dict[int, object] = {}
    money_flow_builders: dict[int, MoneyFlowGraphBuilder] = {}
    for tx in fuel_txs:
        invoice_node = invoice_nodes.get(tx.tenant_id)
        if invoice_node is None:
            invoice_node = registry.get_or_create_node(
                tenant_id=tx.tenant_id,
                node_type=LegalNodeType.INVOICE,
                ref_id=str(invoice.id),
                ref_table="invoices",
            ).node
            invoice_nodes[tx.tenant_id] = invoice_node
        tx_node = registry.get_or_create_node(
            tenant_id=tx.tenant_id,
            node_type=LegalNodeType.FUEL_TRANSACTION,
            ref_id=str(tx.id),
            ref_table="fuel_transactions",
        ).node
        registry.link(
            tenant_id=tx.tenant_id,
            src_node_id=tx_node.id,
            dst_node_id=invoice_node.id,
            edge_type=LegalEdgeType.RELATES_TO,
        )
        builder = money_flow_builders.get(tx.tenant_id)
        if builder is None:
            builder = MoneyFlowGraphBuilder(tenant_id=tx.tenant_id, client_id=invoice.client_id)
            money_flow_builders[tx.tenant_id] = builder
        builder.add_link(
            src_type=MoneyFlowLinkNodeType.FUEL_TX,
            src_id=str(tx.id),
            link_type=MoneyFlowLinkType.FEEDS,
            dst_type=MoneyFlowLinkNodeType.INVOICE,
            dst_id=invoice.id,
            meta={"billing_period_id": str(invoice.billing_period_id) if invoice.billing_period_id else None},
        )
    for tenant_id, builder in money_flow_builders.items():
        ensure_money_flow_links(
            session,
            tenant_id=tenant_id,
            client_id=invoice.client_id,
            links=builder.build(),
        )


def run_invoice_monthly(
    target_month: date | None = None,
    *,
    session: Session | None = None,
    correlation_id: str | None = None,
    celery_task_id: str | None = None,
    job_run: BillingJobRun | None = None,
) -> MonthlyInvoiceRunOutcome:
    """Generate monthly invoices from finalized billing summaries."""

    month_anchor = target_month or _default_month()
    period_from, period_to = _month_bounds(month_anchor)
    should_close = session is None
    session = session or get_sessionmaker()()
    job_service = BillingJobRunService(session)
    if job_run is None:
        job_run = job_service.start(
            BillingJobType.INVOICE_MONTHLY,
            params={"period_from": str(period_from), "period_to": str(period_to)},
            correlation_id=correlation_id,
            celery_task_id=celery_task_id,
        )
    else:
        job_run.status = BillingJobStatus.STARTED
        job_run.params = job_run.params or {"period_from": str(period_from), "period_to": str(period_to)}
        job_run.celery_task_id = celery_task_id or job_run.celery_task_id
        job_run.correlation_id = correlation_id or job_run.correlation_id
        session.add(job_run)
        session.flush()

    logger.info(
        "invoice.monthly.start",
        extra={
            "period_from": str(period_from),
            "period_to": str(period_to),
            "enabled": settings.NEFT_INVOICE_MONTHLY_ENABLED,
        },
    )

    metrics: dict[str, object] = {
        "created": 0,
        "rebuilt": 0,
        "skipped": 0,
        "period_from": str(period_from),
        "period_to": str(period_to),
    }

    if not settings.NEFT_INVOICE_MONTHLY_ENABLED:
        metrics["enabled"] = False
        job_service.succeed(job_run, metrics=metrics)
        if should_close:
            session.close()
        logger.info("invoice.monthly.disabled")
        return MonthlyInvoiceRunOutcome(invoices=[], job_run=job_run, metrics=metrics)

    period_service = BillingPeriodService(session)
    period_start, period_end = period_bounds_for_dates(
        date_from=period_from,
        date_to=period_to,
        tz=settings.NEFT_BILLING_TZ,
    )
    period = period_service.get_or_create(
        period_type=BillingPeriodType.MONTHLY,
        start_at=period_start,
        end_at=period_end,
        tz=settings.NEFT_BILLING_TZ,
    )
    if period.status != BillingPeriodStatus.OPEN:
        job_service.fail(
            job_run,
            error=f"Billing period {period.id} is {period.status.value}",
        )
        raise BillingPeriodConflict(f"Billing period {period.id} is {period.status.value}")

    try:
        summaries = (
            session.query(BillingSummary)
            .filter(BillingSummary.billing_date >= period_from)
            .filter(BillingSummary.billing_date <= period_to)
            .filter(BillingSummary.status == BillingSummaryStatus.FINALIZED)
            .filter(BillingSummary.billing_period_id == period.id)
            .all()
        )
        if not summaries:
            logger.info("invoice.monthly.no_data", extra={"period_from": str(period_from), "period_to": str(period_to)})
            metrics["no_data"] = True
            job_service.succeed(job_run, metrics=metrics)
            return MonthlyInvoiceRunOutcome(invoices=[], job_run=job_run, metrics=metrics)

        grouped = _group_summaries(summaries)
        repo = BillingRepository(session)
        created: list[Invoice] = []

        for (client_id, currency), payload in grouped.items():
            existing = repo.find_invoices(
                client_id=client_id,
                period_from=period_from,
                period_to=period_to,
                exclude_cancelled=True,
            )
            invoice = existing[0] if existing else None
            if invoice and invoice.status != InvoiceStatus.DRAFT:
                metrics["skipped"] = int(metrics["skipped"]) + 1  # type: ignore[arg-type]
                continue

            lines = [_build_lines(items) for items in payload["items"].values()]
            if invoice:
                if not invoice.billing_period_id:
                    invoice.billing_period_id = period.id
                session.query(InvoiceLine).filter(InvoiceLine.invoice_id == invoice.id).delete(
                    synchronize_session=False
                )
                invoice.lines = []
                invoice.lines.extend(
                    [
                        InvoiceLine(
                            invoice_id=invoice.id,
                            product_id=line.product_id,
                            liters=line.liters,
                            unit_price=line.unit_price,
                            line_amount=line.line_amount,
                            tax_amount=line.tax_amount,
                        )
                        for line in lines
                    ]
                )
                invoice.total_amount = sum(int(line.line_amount or 0) for line in invoice.lines)
                invoice.tax_amount = sum(int(line.tax_amount or 0) for line in invoice.lines)
                invoice.total_with_tax = invoice.total_amount + invoice.tax_amount
                InvoiceStateMachine(invoice, db=session).transition(
                    to=InvoiceStatus.DRAFT,
                    actor="invoice_monthly",
                    reason="rebuild_invoice",
                )
                metrics["rebuilt"] = int(metrics["rebuilt"]) + 1  # type: ignore[arg-type]
                session.add(invoice)
            else:
                invoice = repo.create_invoice(
                    BillingInvoiceData(
                        client_id=str(client_id),
                        period_from=period_from,
                        period_to=period_to,
                        currency=currency,
                        lines=lines,
                        status=InvoiceStatus.ISSUED,
                        billing_period_id=str(period.id),
                    ),
                    auto_commit=False,
                )
                FinancialInvariantChecker(session).check_invoice(invoice)
                metrics["created"] = int(metrics["created"]) + 1  # type: ignore[arg-type]
            created.append(invoice)

        session.commit()
        for invoice in created:
            session.refresh(invoice)
            _link_fuel_transactions_to_invoice(session, invoice=invoice)

        logger.info(
            "invoice.monthly.completed",
            extra={
                "period_from": str(period_from),
                "period_to": str(period_to),
                "invoices_created": len(created),
            },
        )
        metrics["invoices"] = [invoice.id for invoice in created]
        job_service.succeed(job_run, metrics=metrics)
        return MonthlyInvoiceRunOutcome(invoices=created, job_run=job_run, metrics=metrics)
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        job_service.fail(job_run, error=str(exc))
        raise
    finally:
        if should_close:
            session.close()
