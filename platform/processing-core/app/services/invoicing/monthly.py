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
from app.models.invoice import Invoice, InvoiceLine, InvoiceStatus
from app.repositories.billing_repository import BillingInvoiceData, BillingLineData, BillingRepository
from app.models.billing_job_run import BillingJobRun, BillingJobStatus, BillingJobType
from app.services.billing_job_runs import BillingJobRunService
from app.services.invoice_state_machine import InvoiceStateMachine
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

    try:
        summaries = (
            session.query(BillingSummary)
            .filter(BillingSummary.billing_date >= period_from)
            .filter(BillingSummary.billing_date <= period_to)
            .filter(BillingSummary.status == BillingSummaryStatus.FINALIZED)
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
                    ),
                    auto_commit=False,
                )
                metrics["created"] = int(metrics["created"]) + 1  # type: ignore[arg-type]
            created.append(invoice)

        session.commit()
        for invoice in created:
            session.refresh(invoice)

        logger.info(
            "invoice.monthly.completed",
            extra={
                "period_from": str(period_from),
                "period_to": str(period_to),
                "created": len(created),
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
