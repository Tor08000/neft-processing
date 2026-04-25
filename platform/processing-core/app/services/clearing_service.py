from __future__ import annotations

from collections import defaultdict
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import date

from sqlalchemy import MetaData, Table, select
from sqlalchemy.orm import Session

from app.db import get_sessionmaker
from app.models.billing_summary import BillingSummary, BillingSummaryStatus
from app.models.billing_job_run import BillingJobType
from app.models.clearing import Clearing
from app.services.billing_job_runs import BillingJobRunService


@dataclass(slots=True)
class _ClearingSummaryRow:
    id: str
    client_id: str | None
    merchant_id: str
    product_type: str | None
    currency: str | None
    total_amount: int
    total_quantity: float | None
    operations_count: int
    commission_amount: int


def _reflect_billing_summary_table(session: Session) -> Table:
    metadata = MetaData()
    return Table(BillingSummary.__tablename__, metadata, autoload_with=session.connection())


def _load_summary_rows(
    session: Session,
    *,
    clearing_date: date,
    status: str | None = None,
) -> list[_ClearingSummaryRow]:
    table = _reflect_billing_summary_table(session)
    filters = [table.c.billing_date == clearing_date]
    if status is not None and "status" in table.c:
        filters.append(table.c.status == status)

    stmt = select(
        table.c.id,
        table.c.client_id,
        table.c.merchant_id,
        table.c.product_type,
        table.c.currency,
        table.c.total_amount,
        table.c.total_quantity,
        table.c.operations_count,
        table.c.commission_amount,
    ).where(*filters)

    rows = session.execute(stmt).mappings().all()
    return [
        _ClearingSummaryRow(
            id=str(row["id"]),
            client_id=str(row["client_id"]) if row["client_id"] is not None else None,
            merchant_id=str(row["merchant_id"]),
            product_type=str(row["product_type"]) if row["product_type"] is not None else None,
            currency=str(row["currency"]) if row["currency"] is not None else None,
            total_amount=int(row["total_amount"] or 0),
            total_quantity=float(row["total_quantity"]) if row["total_quantity"] is not None else None,
            operations_count=int(row["operations_count"] or 0),
            commission_amount=int(row["commission_amount"] or 0),
        )
        for row in rows
    ]


async def generate_clearing_batches_for_date(
    clearing_date: date,
    *,
    session=None,
) -> list[Clearing]:
    """
    Aggregate billing summaries for the given date and upsert clearing batches.

    Group billing summaries by merchant and currency, sum the total amount and
    persist a clearing record per group. Details field stores the grouped
    billing summary entries for traceability.
    """

    should_close = session is None
    session = session or get_sessionmaker()()
    try:
        txn_context = nullcontext() if session.in_transaction() else session.begin()
        with txn_context:
            summaries = _load_summary_rows(session, clearing_date=clearing_date)

            if not summaries:
                return []

            grouped: dict[tuple[str, str], list[BillingSummary]] = defaultdict(list)
            for summary in summaries:
                grouped[(summary.merchant_id, summary.currency or "")].append(summary)

            existing = {
                (item.merchant_id, item.currency): item
                for item in session.query(Clearing)
                .filter(Clearing.batch_date == clearing_date)
                .all()
            }

            for (merchant_id, currency), items in grouped.items():
                total_amount = sum(int(item.total_amount or 0) for item in items)
                details = [
                    {
                        "id": item.id,
                        "client_id": item.client_id,
                        "product_type": item.product_type,
                        "currency": item.currency,
                        "total_amount": item.total_amount,
                        "total_quantity": item.total_quantity,
                        "operations_count": item.operations_count,
                        "commission_amount": item.commission_amount,
                    }
                    for item in items
                ]

                clearing = existing.get((merchant_id, currency))
                if clearing:
                    clearing.total_amount = total_amount
                    clearing.details = details
                else:
                    clearing = Clearing(
                        batch_date=clearing_date,
                        merchant_id=merchant_id,
                        currency=currency,
                        total_amount=total_amount,
                        details=details,
                    )
                    session.add(clearing)
            session.flush()
        updated_batches = (
            session.query(Clearing)
            .filter(Clearing.batch_date == clearing_date)
            .order_by(Clearing.merchant_id, Clearing.currency)
            .all()
        )
        return updated_batches
    finally:
        if should_close:
            session.close()


def _apply_filters(
    query, merchant_id: str | None, status: str | None, date_from: date | None, date_to: date | None
):
    if merchant_id:
        query = query.filter(Clearing.merchant_id == merchant_id)
    if status:
        query = query.filter(Clearing.status == status)
    if date_from:
        query = query.filter(Clearing.batch_date >= date_from)
    if date_to:
        query = query.filter(Clearing.batch_date <= date_to)
    return query


def run_admin_clearing(db: Session, *, clearing_date: date) -> dict:
    """
    Idempotent clearing run:
    - returns early with reason if no FINALIZED billing summaries
    - skips creation if clearing rows already exist for the date
    - records a billing_job_runs entry for observability
    """

    job_service = BillingJobRunService(db)
    job_run = job_service.start(BillingJobType.CLEARING, params={"clearing_date": str(clearing_date)})
    try:
        existing = db.query(Clearing).filter(Clearing.batch_date == clearing_date).first()
        if existing:
            metrics = {"created": 0, "reason": "already_exists"}
            job_service.succeed(job_run, metrics=metrics)
            db.commit()
            return metrics

        summaries = _load_summary_rows(
            db,
            clearing_date=clearing_date,
            status=BillingSummaryStatus.FINALIZED.value,
        )
        if not summaries:
            metrics = {"created": 0, "reason": "no_data"}
            job_service.succeed(job_run, metrics=metrics)
            db.commit()
            return metrics

        grouped: dict[tuple[str, str], list[BillingSummary]] = defaultdict(list)
        for summary in summaries:
            grouped[(summary.merchant_id, summary.currency or "XXX")].append(summary)

        created = 0
        for (merchant_id, currency), items in grouped.items():
            total_amount = sum(int(item.total_amount or 0) for item in items)
            details = [
                {
                    "id": item.id,
                    "client_id": item.client_id,
                    "product_type": item.product_type,
                    "currency": item.currency,
                    "total_amount": item.total_amount,
                    "total_quantity": item.total_quantity,
                    "operations_count": item.operations_count,
                    "commission_amount": item.commission_amount,
                }
                for item in items
            ]
            clearing = Clearing(
                batch_date=clearing_date,
                merchant_id=merchant_id,
                currency=currency,
                total_amount=total_amount,
                details=details,
            )
            db.add(clearing)
            created += 1

        metrics = {"created": created}
        job_service.succeed(job_run, metrics=metrics)
        db.commit()
        return metrics
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        job_service.fail(job_run, error=str(exc))
        db.commit()
        raise
