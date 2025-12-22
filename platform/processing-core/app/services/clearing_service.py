from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlalchemy.orm import Session

from app.db import get_sessionmaker
from app.models.billing_summary import BillingSummary, BillingSummaryStatus
from app.models.billing_job_run import BillingJobType
from app.models.clearing import Clearing
from app.services.billing_job_runs import BillingJobRunService


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
        with session.begin():
            summaries = (
                session.query(BillingSummary)
                .filter(BillingSummary.billing_date == clearing_date)
                .all()
            )

            if not summaries:
                return

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
                        "product_type": item.product_type.value if item.product_type else None,
                        "currency": item.currency,
                        "total_amount": int(item.total_amount or 0),
                        "total_quantity": float(item.total_quantity)
                        if item.total_quantity is not None
                        else None,
                        "operations_count": int(item.operations_count or 0),
                        "commission_amount": int(item.commission_amount or 0),
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


def list_clearing_batches(
    db,
    *,
    date_from: date | None,
    date_to: date | None,
    merchant_id: str | None,
    status: str | None,
    limit: int,
    offset: int,
) -> tuple[list[Clearing], int]:
    query = db.query(Clearing)
    query = _apply_filters(query, merchant_id, status, date_from, date_to)
    total = query.count()
    batches = (
        query.order_by(Clearing.batch_date.desc(), Clearing.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return batches, total


def load_clearing_batch(db, batch_id: str) -> Clearing | None:
    return db.query(Clearing).filter(Clearing.id == batch_id).first()


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

        summaries = (
            db.query(BillingSummary)
            .filter(BillingSummary.billing_date == clearing_date)
            .filter(BillingSummary.status == BillingSummaryStatus.FINALIZED)
            .all()
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
                    "product_type": item.product_type.value if item.product_type else None,
                    "currency": item.currency,
                    "total_amount": int(item.total_amount or 0),
                    "total_quantity": float(item.total_quantity) if item.total_quantity is not None else None,
                    "operations_count": int(item.operations_count or 0),
                    "commission_amount": int(item.commission_amount or 0),
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
