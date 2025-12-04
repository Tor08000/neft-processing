from __future__ import annotations

from collections import defaultdict
from datetime import date

from app.db import SessionLocal
from app.models.billing_summary import BillingSummary
from app.models.clearing import Clearing


async def generate_clearing_batches_for_date(clearing_date: date) -> None:
    """
    Aggregate billing summaries for the given date and upsert clearing batches.

    Group billing summaries by merchant and currency, sum the total amount and
    persist a clearing record per group. Details field stores the grouped
    billing summary entries for traceability.
    """

    session = SessionLocal()
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
    finally:
        session.close()
