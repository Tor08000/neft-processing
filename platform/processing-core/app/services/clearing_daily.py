from __future__ import annotations

from datetime import date

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_sessionmaker
from app.models.clearing_batch import ClearingBatch
from app.models.clearing_batch_operation import ClearingBatchOperation
from app.models.operation import Operation, OperationStatus
from app.services.billing.daily import _billing_window, _default_billing_date
from neft_shared.logging_setup import get_logger

logger = get_logger(__name__)

BILLABLE_STATUSES = {
    OperationStatus.CAPTURED,
    OperationStatus.COMPLETED,
    OperationStatus.REFUNDED,
    OperationStatus.REVERSED,
}


def _load_operations(session: Session, target_date: date):
    start_ts, end_ts = _billing_window(target_date)

    amount_value = func.coalesce(
        func.nullif(Operation.amount_settled, 0),
        func.nullif(Operation.captured_amount, 0),
        Operation.amount_original,
    )
    refund_delta = func.coalesce(Operation.refunded_amount, 0)
    net_amount = case(
        (Operation.status.in_({OperationStatus.REFUNDED, OperationStatus.REVERSED}), -amount_value),
        else_=amount_value - refund_delta,
    ).label("net_amount")

    return (
        session.query(Operation, net_amount)
        .filter(Operation.status.in_(BILLABLE_STATUSES))
        .filter(Operation.created_at >= start_ts)
        .filter(Operation.created_at <= end_ts)
        .all()
    )


def _find_or_create_batch(session: Session, merchant_id: str, target_date: date) -> ClearingBatch:
    batch = (
        session.query(ClearingBatch)
        .filter(ClearingBatch.merchant_id == merchant_id)
        .filter(ClearingBatch.date_from == target_date)
        .filter(ClearingBatch.date_to == target_date)
        .one_or_none()
    )
    if batch:
        return batch

    batch = ClearingBatch(
        merchant_id=merchant_id,
        date_from=target_date,
        date_to=target_date,
        total_amount=0,
        operations_count=0,
    )
    session.add(batch)
    session.flush()
    return batch


def _populate_batch(session: Session, batch: ClearingBatch, operations: list[tuple[Operation, int]]):
    if batch.status != "PENDING":
        return batch

    existing_op_ids = {op.operation_id for op in batch.operations} if batch.operations else set()

    new_operations = []
    total_amount = 0
    for operation, net_amount in operations:
        amount_value = int(net_amount)
        if operation.operation_id in existing_op_ids:
            total_amount += amount_value
            continue
        new_operations.append(
            ClearingBatchOperation(
                batch_id=batch.id,
                operation_id=operation.operation_id,
                amount=amount_value,
            )
        )
        total_amount += amount_value
    if new_operations:
        session.add_all(new_operations)

    batch.total_amount = int(total_amount)
    batch.operations_count = len(new_operations) + len(existing_op_ids)
    return batch


def run_clearing_daily(
    target_date: date | None = None,
    *,
    session: Session | None = None,
) -> list[ClearingBatch]:
    """Create clearing batches for operations captured on the target date."""

    clearing_date = target_date or _default_billing_date()
    should_close = session is None
    session = session or get_sessionmaker()()

    logger.info(
        "clearing.daily.start",
        extra={
            "clearing_date": str(clearing_date),
            "enabled": settings.NEFT_CLEARING_DAILY_ENABLED,
        },
    )

    if not settings.NEFT_CLEARING_DAILY_ENABLED:
        logger.info("clearing.daily.disabled")
        if should_close:
            session.close()
        return []

    try:
        with session.begin():
            operations = _load_operations(session, clearing_date)
            if not operations:
                logger.info("clearing.daily.no_operations", extra={"clearing_date": str(clearing_date)})
                return []

            grouped: dict[str, list[tuple[Operation, int]]] = {}
            for op, net_amount in operations:
                grouped.setdefault(op.merchant_id, []).append((op, int(net_amount)))

            batches: list[ClearingBatch] = []
            for merchant_id, ops in grouped.items():
                batch = _find_or_create_batch(session, merchant_id, clearing_date)
                batch = _populate_batch(session, batch, ops)
                batches.append(batch)

        logger.info("clearing.daily.completed", extra={"clearing_date": str(clearing_date), "batches": len(batches)})
        return batches
    finally:
        if should_close:
            session.close()
