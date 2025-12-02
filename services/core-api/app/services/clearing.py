from __future__ import annotations

import json
from datetime import date, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.billing_summary import BillingSummary
from app.models.clearing_batch import ClearingBatch
from app.models.clearing_batch_operation import ClearingBatchOperation
from app.models.operation import Operation


def _daterange_bounds(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    start = datetime.combine(date_from, datetime.min.time())
    end = datetime.combine(date_to, datetime.max.time())
    return start, end


def _load_billing_total(db: Session, date_from: date, date_to: date, merchant_id: str):
    summary = (
        db.query(BillingSummary)
        .filter(BillingSummary.date >= date_from)
        .filter(BillingSummary.date <= date_to)
        .filter(BillingSummary.merchant_id == merchant_id)
        .all()
    )
    total_amount = sum(item.total_captured_amount for item in summary)
    operations_count = sum(item.operations_count for item in summary)
    return total_amount, operations_count


def build_clearing_batch_for_period(
    db: Session, date_from: date, date_to: date, merchant_id: str
) -> ClearingBatch:
    start, end = _daterange_bounds(date_from, date_to)

    captures = (
        db.query(Operation)
        .filter(Operation.operation_type == "CAPTURE")
        .filter(Operation.merchant_id == merchant_id)
        .filter(Operation.created_at >= start)
        .filter(Operation.created_at <= end)
        .all()
    )

    total_amount, operations_count = _load_billing_total(
        db, date_from=date_from, date_to=date_to, merchant_id=merchant_id
    )
    if total_amount == 0 and captures:
        total_amount = sum(op.amount for op in captures)
        operations_count = len(captures)

    batch = ClearingBatch(
        id=str(uuid4()),
        merchant_id=merchant_id,
        date_from=date_from,
        date_to=date_to,
        total_amount=total_amount,
        operations_count=operations_count or len(captures),
    )
    db.add(batch)
    db.flush()

    operations = [
        ClearingBatchOperation(
            batch_id=batch.id,
            operation_id=op.operation_id,
            amount=op.amount,
        )
        for op in captures
    ]
    db.add_all(operations)
    db.commit()
    db.refresh(batch)
    return batch


def get_batch(db: Session, batch_id: str) -> ClearingBatch | None:
    return db.query(ClearingBatch).filter(ClearingBatch.id == batch_id).first()


def list_batches(
    db: Session, merchant_id: str | None = None, status: str | None = None
) -> list[ClearingBatch]:
    query = db.query(ClearingBatch)
    if merchant_id:
        query = query.filter(ClearingBatch.merchant_id == merchant_id)
    if status:
        query = query.filter(ClearingBatch.status == status)
    return query.order_by(ClearingBatch.created_at.desc()).all()


def mark_batch_sent(db: Session, batch_id: str) -> ClearingBatch:
    batch = get_batch(db, batch_id)
    if not batch:
        raise ValueError("batch not found")
    batch.status = "SENT"
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


def mark_batch_confirmed(db: Session, batch_id: str) -> ClearingBatch:
    batch = get_batch(db, batch_id)
    if not batch:
        raise ValueError("batch not found")
    batch.status = "CONFIRMED"
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch
