from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, case, func
from sqlalchemy.orm import Session

from app.models.accounting_export_batch import AccountingExportBatch, AccountingExportState
from app.models.bi import BiDailyMetric, BiScopeType
from app.models.invoice import Invoice
from app.models.payout_batch import PayoutBatch, PayoutBatchState
from app.schemas.kpi import KpiItem, KpiSummary

ADMIN_KPI_KEYS = (
    "billing_errors",
    "exports_ontime_percent",
    "declines_total",
    "payout_batches_settled",
    "audit_chain_breaks",
    "spend_total",
)

CLIENT_KPI_KEYS = (
    "spend_total",
    "declines_total",
    "invoices_due_overdue",
    "orders_completed",
    "balance",
)

_EXPORTS_ONTIME_STATES = {
    AccountingExportState.GENERATED,
    AccountingExportState.UPLOADED,
    AccountingExportState.DOWNLOADED,
    AccountingExportState.CONFIRMED,
}


def _window_bounds(window_days: int) -> tuple[datetime, datetime, datetime]:
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=window_days)
    prev_start = start - timedelta(days=window_days)
    return prev_start, start, now


def _window_dates(start: datetime, end: datetime) -> tuple[datetime.date, datetime.date]:
    return start.date(), end.date()


def _percent_change(current: float, previous: float) -> float | None:
    if previous <= 0:
        return None
    return ((current - previous) / previous) * 100


def _progress(value: float, target: float | None, good_when: str) -> float | None:
    if target is None:
        return None
    if good_when == "up":
        if target <= 0:
            return None
        return min(max(value / target, 0), 1)
    if good_when == "down":
        if target <= 0:
            return 1.0 if value == 0 else 0.0
        return min(max(1 - (value / target), 0), 1)
    return None


def _default_meta(source: str) -> dict[str, str]:
    return {"source": source, "delta_mode": "percent"}


def _aggregate_daily_metrics(
    db: Session,
    *,
    tenant_id: int,
    scope_type: BiScopeType,
    scope_id: str,
    start_date: datetime.date,
    end_date: datetime.date,
    prev_start_date: datetime.date,
) -> dict[str, float]:
    query = (
        db.query(
            func.coalesce(
                func.sum(
                    case(
                        (and_(BiDailyMetric.date >= start_date, BiDailyMetric.date < end_date), BiDailyMetric.spend_total),
                        else_=0,
                    )
                ),
                0,
            ).label("spend_total_current"),
            func.coalesce(
                func.sum(
                    case(
                        (and_(BiDailyMetric.date >= prev_start_date, BiDailyMetric.date < start_date), BiDailyMetric.spend_total),
                        else_=0,
                    )
                ),
                0,
            ).label("spend_total_prev"),
            func.coalesce(
                func.sum(
                    case(
                        (and_(BiDailyMetric.date >= start_date, BiDailyMetric.date < end_date), BiDailyMetric.declines_total),
                        else_=0,
                    )
                ),
                0,
            ).label("declines_total_current"),
            func.coalesce(
                func.sum(
                    case(
                        (and_(BiDailyMetric.date >= prev_start_date, BiDailyMetric.date < start_date), BiDailyMetric.declines_total),
                        else_=0,
                    )
                ),
                0,
            ).label("declines_total_prev"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            and_(BiDailyMetric.date >= start_date, BiDailyMetric.date < end_date),
                            BiDailyMetric.orders_completed,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("orders_completed_current"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            and_(BiDailyMetric.date >= prev_start_date, BiDailyMetric.date < start_date),
                            BiDailyMetric.orders_completed,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("orders_completed_prev"),
        )
        .filter(BiDailyMetric.tenant_id == tenant_id)
        .filter(BiDailyMetric.scope_type == scope_type)
        .filter(BiDailyMetric.scope_id == scope_id)
        .filter(BiDailyMetric.date >= prev_start_date)
        .filter(BiDailyMetric.date < end_date)
    )
    row = query.one()
    return {
        "spend_total_current": float(row.spend_total_current or 0),
        "spend_total_prev": float(row.spend_total_prev or 0),
        "declines_total_current": float(row.declines_total_current or 0),
        "declines_total_prev": float(row.declines_total_prev or 0),
        "orders_completed_current": float(row.orders_completed_current or 0),
        "orders_completed_prev": float(row.orders_completed_prev or 0),
    }


def _aggregate_exports(
    db: Session,
    *,
    tenant_id: int,
    prev_start: datetime,
    start: datetime,
    end: datetime,
) -> dict[str, int]:
    query = (
        db.query(
            func.sum(
                case(
                    (and_(AccountingExportBatch.created_at >= start, AccountingExportBatch.created_at < end), 1),
                    else_=0,
                )
            ).label("total_current"),
            func.sum(
                case(
                    (
                        and_(
                            AccountingExportBatch.created_at >= start,
                            AccountingExportBatch.created_at < end,
                            AccountingExportBatch.state.in_(_EXPORTS_ONTIME_STATES),
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("ontime_current"),
            func.sum(
                case(
                    (and_(AccountingExportBatch.created_at >= prev_start, AccountingExportBatch.created_at < start), 1),
                    else_=0,
                )
            ).label("total_prev"),
            func.sum(
                case(
                    (
                        and_(
                            AccountingExportBatch.created_at >= prev_start,
                            AccountingExportBatch.created_at < start,
                            AccountingExportBatch.state.in_(_EXPORTS_ONTIME_STATES),
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("ontime_prev"),
        )
        .filter(AccountingExportBatch.tenant_id == tenant_id)
        .filter(AccountingExportBatch.created_at >= prev_start)
        .filter(AccountingExportBatch.created_at < end)
    )
    row = query.one()
    return {
        "total_current": int(row.total_current or 0),
        "ontime_current": int(row.ontime_current or 0),
        "total_prev": int(row.total_prev or 0),
        "ontime_prev": int(row.ontime_prev or 0),
    }


def _aggregate_payout_batches(
    db: Session,
    *,
    tenant_id: int,
    prev_start: datetime,
    start: datetime,
    end: datetime,
) -> dict[str, int]:
    query = (
        db.query(
            func.sum(
                case(
                    (
                        and_(
                            PayoutBatch.state == PayoutBatchState.SETTLED,
                            PayoutBatch.settled_at >= start,
                            PayoutBatch.settled_at < end,
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("settled_current"),
            func.sum(
                case(
                    (
                        and_(
                            PayoutBatch.state == PayoutBatchState.SETTLED,
                            PayoutBatch.settled_at >= prev_start,
                            PayoutBatch.settled_at < start,
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("settled_prev"),
        )
        .filter(PayoutBatch.tenant_id == tenant_id)
        .filter(PayoutBatch.settled_at.isnot(None))
        .filter(PayoutBatch.settled_at >= prev_start)
        .filter(PayoutBatch.settled_at < end)
    )
    row = query.one()
    return {
        "settled_current": int(row.settled_current or 0),
        "settled_prev": int(row.settled_prev or 0),
    }


def _count_invoices_due_overdue(
    db: Session,
    *,
    client_id: str | None,
    cutoff_date: datetime.date,
) -> int:
    if not client_id:
        return 0
    return (
        db.query(func.count(Invoice.id))
        .filter(Invoice.client_id == client_id)
        .filter(Invoice.due_date.isnot(None))
        .filter(Invoice.due_date < cutoff_date)
        .filter(Invoice.amount_due > 0)
        .scalar()
        or 0
    )


def build_kpi_summary(
    db: Session,
    *,
    tenant_id: int,
    window_days: int,
    client_id: str | None = None,
) -> KpiSummary:
    prev_start, start, end = _window_bounds(window_days)
    start_date, end_date = _window_dates(start, end)
    prev_start_date = (start - timedelta(days=window_days)).date()

    scope_type = BiScopeType.CLIENT if client_id else BiScopeType.TENANT
    scope_id = client_id or str(tenant_id)

    daily_metrics = _aggregate_daily_metrics(
        db,
        tenant_id=tenant_id,
        scope_type=scope_type,
        scope_id=scope_id,
        start_date=start_date,
        end_date=end_date,
        prev_start_date=prev_start_date,
    )

    spend_total = daily_metrics["spend_total_current"]
    spend_prev = daily_metrics["spend_total_prev"]
    declines_total = daily_metrics["declines_total_current"]
    declines_prev = daily_metrics["declines_total_prev"]
    orders_completed = daily_metrics["orders_completed_current"]
    orders_completed_prev = daily_metrics["orders_completed_prev"]

    exports = _aggregate_exports(db, tenant_id=tenant_id, prev_start=prev_start, start=start, end=end)
    payouts = _aggregate_payout_batches(db, tenant_id=tenant_id, prev_start=prev_start, start=start, end=end)

    exports_percent = (exports["ontime_current"] / exports["total_current"] * 100) if exports["total_current"] else 0.0
    exports_prev_percent = (exports["ontime_prev"] / exports["total_prev"] * 100) if exports["total_prev"] else 0.0

    invoices_due = _count_invoices_due_overdue(db, client_id=client_id, cutoff_date=end.date())

    kpis: list[KpiItem] = []

    if client_id:
        kpis.extend(
            [
                KpiItem(
                    key="spend_total",
                    title="Spend total",
                    value=spend_total,
                    unit="money",
                    delta=_percent_change(spend_total, spend_prev),
                    good_when="neutral",
                    target=None,
                    progress=None,
                    meta=_default_meta("bi_daily_metrics"),
                ),
                KpiItem(
                    key="declines_total",
                    title="Declines total",
                    value=declines_total,
                    unit="count",
                    delta=_percent_change(declines_total, declines_prev),
                    good_when="down",
                    target=0,
                    progress=_progress(declines_total, 0, "down"),
                    meta=_default_meta("bi_daily_metrics"),
                ),
                KpiItem(
                    key="invoices_due_overdue",
                    title="Invoices due / overdue",
                    value=float(invoices_due),
                    unit="count",
                    delta=None,
                    good_when="down",
                    target=0,
                    progress=_progress(float(invoices_due), 0, "down"),
                    meta=_default_meta("invoices"),
                ),
                KpiItem(
                    key="orders_completed",
                    title="Orders completed",
                    value=orders_completed,
                    unit="count",
                    delta=_percent_change(orders_completed, orders_completed_prev),
                    good_when="up",
                    target=None,
                    progress=None,
                    meta=_default_meta("bi_daily_metrics"),
                ),
                KpiItem(
                    key="balance",
                    title="Balance",
                    value=0.0,
                    unit="money",
                    delta=None,
                    good_when="neutral",
                    target=None,
                    progress=None,
                    meta=_default_meta("internal_ledger"),
                ),
            ]
        )
    else:
        billing_errors = 0.0
        audit_chain_breaks = 0.0
        kpis.extend(
            [
                KpiItem(
                    key="billing_errors",
                    title="Billing errors",
                    value=billing_errors,
                    unit="count",
                    delta=None,
                    good_when="down",
                    target=0,
                    progress=_progress(billing_errors, 0, "down"),
                    meta=_default_meta("billing_job_runs"),
                ),
                KpiItem(
                    key="exports_ontime_percent",
                    title="Exports on-time",
                    value=exports_percent,
                    unit="percent",
                    delta=_percent_change(exports_percent, exports_prev_percent),
                    good_when="up",
                    target=95,
                    progress=_progress(exports_percent, 95, "up"),
                    meta=_default_meta("accounting_export_batches"),
                ),
                KpiItem(
                    key="declines_total",
                    title="Declines total",
                    value=declines_total,
                    unit="count",
                    delta=_percent_change(declines_total, declines_prev),
                    good_when="down",
                    target=0,
                    progress=_progress(declines_total, 0, "down"),
                    meta=_default_meta("bi_daily_metrics"),
                ),
                KpiItem(
                    key="payout_batches_settled",
                    title="Payout batches settled",
                    value=float(payouts["settled_current"]),
                    unit="count",
                    delta=_percent_change(float(payouts["settled_current"]), float(payouts["settled_prev"])),
                    good_when="up",
                    target=None,
                    progress=None,
                    meta=_default_meta("payout_batches"),
                ),
                KpiItem(
                    key="audit_chain_breaks",
                    title="Audit chain breaks",
                    value=audit_chain_breaks,
                    unit="count",
                    delta=None,
                    good_when="down",
                    target=0,
                    progress=_progress(audit_chain_breaks, 0, "down"),
                    meta=_default_meta("audit_log"),
                ),
                KpiItem(
                    key="spend_total",
                    title="Spend total",
                    value=spend_total,
                    unit="money",
                    delta=_percent_change(spend_total, spend_prev),
                    good_when="neutral",
                    target=None,
                    progress=None,
                    meta=_default_meta("bi_daily_metrics"),
                ),
            ]
        )

    return KpiSummary(window_days=window_days, as_of=end, kpis=kpis)


__all__ = ["build_kpi_summary", "ADMIN_KPI_KEYS", "CLIENT_KPI_KEYS"]
