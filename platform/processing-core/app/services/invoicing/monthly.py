from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_sessionmaker
from app.models.billing_summary import BillingSummary, BillingSummaryStatus
from app.models.invoice import Invoice
from app.repositories.billing_repository import BillingInvoiceData, BillingLineData, BillingRepository
from neft_shared.logging_setup import get_logger

logger = get_logger(__name__)


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
) -> list[Invoice]:
    """Generate monthly invoices from finalized billing summaries."""

    month_anchor = target_month or _default_month()
    period_from, period_to = _month_bounds(month_anchor)
    should_close = session is None
    session = session or get_sessionmaker()()

    logger.info(
        "invoice.monthly.start",
        extra={
            "period_from": str(period_from),
            "period_to": str(period_to),
            "enabled": settings.NEFT_INVOICE_MONTHLY_ENABLED,
        },
    )

    if not settings.NEFT_INVOICE_MONTHLY_ENABLED:
        if should_close:
            session.close()
        logger.info("invoice.monthly.disabled")
        return []

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
            return []

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
            if existing:
                continue

            lines = [_build_lines(items) for items in payload["items"].values()]
            invoice = repo.create_invoice(
                BillingInvoiceData(
                    client_id=str(client_id),
                    period_from=period_from,
                    period_to=period_to,
                    currency=currency,
                    lines=lines,
                ),
                auto_commit=False,
            )
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
        return created
    finally:
        if should_close:
            session.close()
