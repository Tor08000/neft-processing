from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.models.billing_period import BillingPeriodStatus, BillingPeriodType
from app.models.operation import Operation, OperationStatus
from app.models.payout_batch import PayoutBatch, PayoutBatchState, PayoutItem
from app.services.billing_periods import BillingPeriodService, period_bounds_for_dates
from app.services.payout_metrics import metrics as payout_metrics
from app.services.policy import Action, PolicyAccessDenied, PolicyEngine, actor_from_token, audit_access_denied
from app.services.policy.resources import ResourceContext


class PayoutError(Exception):
    """Domain error for payout lifecycle violations."""


class PayoutConflictError(PayoutError):
    """Raised when external references conflict."""


@dataclass(frozen=True)
class PayoutReconcileResult:
    batch: PayoutBatch
    computed_amount: Decimal
    computed_count: int
    recorded_amount: Decimal
    recorded_count: int


@dataclass(frozen=True)
class PayoutBatchResult:
    batch: PayoutBatch
    created: bool


@dataclass(frozen=True)
class PayoutStateResult:
    batch: PayoutBatch
    previous_state: PayoutBatchState
    is_replay: bool


def _operations_query(
    db: Session,
    *,
    partner_id: str,
    date_from: date,
    date_to: date,
):
    return (
        db.query(Operation)
        .filter(Operation.merchant_id == partner_id)
        .filter(Operation.status.in_([OperationStatus.CAPTURED, OperationStatus.COMPLETED]))
        .filter(func.date(Operation.created_at) >= date_from)
        .filter(func.date(Operation.created_at) <= date_to)
    )


def close_payout_period(
    db: Session,
    *,
    tenant_id: int,
    partner_id: str,
    date_from: date,
    date_to: date,
    token: dict | None = None,
) -> PayoutBatchResult:
    if date_from > date_to:
        raise ValueError("invalid_period")
    period_service = BillingPeriodService(db)
    period_start, period_end = period_bounds_for_dates(
        date_from=date_from,
        date_to=date_to,
        tz=settings.NEFT_BILLING_TZ,
    )
    period = period_service.get_or_create(
        period_type=BillingPeriodType.ADHOC,
        start_at=period_start,
        end_at=period_end,
        tz=settings.NEFT_BILLING_TZ,
    )
    actor = actor_from_token(token)
    resource = ResourceContext(
        resource_type="PAYOUT_BATCH",
        tenant_id=actor.tenant_id or tenant_id,
        client_id=None,
        status=period.status.value if period.status else None,
    )
    decision = PolicyEngine().check(actor=actor, action=Action.PAYOUT_EXPORT_CREATE, resource=resource)
    if not decision.allowed:
        audit_access_denied(
            db,
            actor=actor,
            action=Action.PAYOUT_EXPORT_CREATE,
            resource=resource,
            decision=decision,
            token=token,
        )
        raise PolicyAccessDenied(decision)
    if period.status not in {BillingPeriodStatus.FINALIZED, BillingPeriodStatus.LOCKED}:
        raise PayoutError("billing_period_not_finalized")

    existing = (
        db.query(PayoutBatch)
        .filter(PayoutBatch.tenant_id == tenant_id)
        .filter(PayoutBatch.partner_id == partner_id)
        .filter(PayoutBatch.date_from == date_from)
        .filter(PayoutBatch.date_to == date_to)
        .one_or_none()
    )
    if existing:
        return PayoutBatchResult(batch=existing, created=False)

    amount_expr = func.coalesce(Operation.amount_settled, Operation.amount)
    total_amount, total_qty, operations_count = (
        db.query(
            func.coalesce(func.sum(amount_expr), 0),
            func.coalesce(func.sum(Operation.quantity), 0),
            func.count(Operation.id),
        )
        .select_from(Operation)
        .filter(Operation.merchant_id == partner_id)
        .filter(Operation.status.in_([OperationStatus.CAPTURED, OperationStatus.COMPLETED]))
        .filter(func.date(Operation.created_at) >= date_from)
        .filter(func.date(Operation.created_at) <= date_to)
        .one()
    )

    total_amount_decimal = Decimal(total_amount or 0)
    total_qty_decimal = Decimal(total_qty or 0)
    operations_count_int = int(operations_count or 0)

    batch = PayoutBatch(
        tenant_id=tenant_id,
        partner_id=partner_id,
        date_from=date_from,
        date_to=date_to,
        state=PayoutBatchState.READY,
        total_amount=total_amount_decimal,
        total_qty=total_qty_decimal,
        operations_count=operations_count_int,
        meta={"billing_period_id": str(period.id)},
    )
    item = PayoutItem(
        amount_gross=total_amount_decimal,
        commission_amount=Decimal("0"),
        amount_net=total_amount_decimal,
        qty=total_qty_decimal,
        operations_count=operations_count_int,
    )
    batch.items.append(item)

    db.add(batch)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        existing = (
            db.query(PayoutBatch)
            .filter(PayoutBatch.tenant_id == tenant_id)
            .filter(PayoutBatch.partner_id == partner_id)
            .filter(PayoutBatch.date_from == date_from)
            .filter(PayoutBatch.date_to == date_to)
            .one_or_none()
        )
        if existing:
            return existing
        payout_metrics.mark_error()
        raise PayoutError("payout_batch_create_failed") from exc

    db.commit()
    payout_metrics.mark_created(total_amount_decimal)
    db.refresh(batch)
    return PayoutBatchResult(batch=batch, created=True)


def list_payout_batches(
    db: Session,
    *,
    partner_id: str | None,
    state: str | None,
    date_from: date | None,
    date_to: date | None,
    limit: int,
    offset: int,
) -> tuple[list[PayoutBatch], int]:
    query = db.query(PayoutBatch)
    if partner_id:
        query = query.filter(PayoutBatch.partner_id == partner_id)
    if state:
        query = query.filter(PayoutBatch.state == state)
    if date_from:
        query = query.filter(PayoutBatch.date_from >= date_from)
    if date_to:
        query = query.filter(PayoutBatch.date_to <= date_to)

    total = query.count()
    items = (
        query.order_by(PayoutBatch.date_from.desc(), PayoutBatch.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return items, total


def load_payout_batch(db: Session, batch_id: str) -> PayoutBatch | None:
    return (
        db.query(PayoutBatch)
        .options(selectinload(PayoutBatch.items))
        .filter(PayoutBatch.id == batch_id)
        .one_or_none()
    )


def mark_batch_sent(
    db: Session,
    *,
    batch_id: str,
    provider: str,
    external_ref: str,
) -> PayoutStateResult:
    batch = db.query(PayoutBatch).filter(PayoutBatch.id == batch_id).one_or_none()
    if not batch:
        raise PayoutError("batch_not_found")

    if batch.state in {PayoutBatchState.SENT, PayoutBatchState.SETTLED}:
        if batch.provider == provider and batch.external_ref == external_ref:
            return PayoutStateResult(batch=batch, previous_state=batch.state, is_replay=True)
        raise PayoutConflictError("external_ref_conflict")

    if batch.state != PayoutBatchState.READY:
        raise PayoutError("invalid_state")

    conflict = (
        db.query(PayoutBatch)
        .filter(PayoutBatch.provider == provider)
        .filter(PayoutBatch.external_ref == external_ref)
        .filter(PayoutBatch.id != batch.id)
        .one_or_none()
    )
    if conflict:
        raise PayoutConflictError("external_ref_conflict")

    previous_state = batch.state
    batch.state = PayoutBatchState.SENT
    batch.provider = provider
    batch.external_ref = external_ref
    batch.sent_at = datetime.now(timezone.utc)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise PayoutConflictError("external_ref_conflict") from exc

    db.refresh(batch)
    return PayoutStateResult(batch=batch, previous_state=previous_state, is_replay=False)


def mark_batch_settled(
    db: Session,
    *,
    batch_id: str,
    provider: str,
    external_ref: str,
    token: dict | None = None,
) -> PayoutStateResult:
    batch = db.query(PayoutBatch).filter(PayoutBatch.id == batch_id).one_or_none()
    if not batch:
        raise PayoutError("batch_not_found")

    actor = actor_from_token(token)
    resource = ResourceContext(
        resource_type="PAYOUT_BATCH",
        tenant_id=actor.tenant_id or int(batch.tenant_id),
        client_id=None,
        status=None,
    )
    decision = PolicyEngine().check(actor=actor, action=Action.PAYOUT_EXPORT_CONFIRM, resource=resource)
    if not decision.allowed:
        audit_access_denied(
            db,
            actor=actor,
            action=Action.PAYOUT_EXPORT_CONFIRM,
            resource=resource,
            decision=decision,
            token=token,
        )
        raise PolicyAccessDenied(decision)

    if batch.state == PayoutBatchState.SETTLED:
        if batch.provider == provider and batch.external_ref == external_ref:
            return PayoutStateResult(batch=batch, previous_state=batch.state, is_replay=True)
        raise PayoutConflictError("external_ref_conflict")

    if batch.state != PayoutBatchState.SENT:
        raise PayoutError("invalid_state")

    if batch.provider != provider or batch.external_ref != external_ref:
        raise PayoutConflictError("external_ref_conflict")

    previous_state = batch.state
    batch.state = PayoutBatchState.SETTLED
    batch.settled_at = datetime.now(timezone.utc)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise PayoutConflictError("external_ref_conflict") from exc

    payout_metrics.mark_settled()
    db.refresh(batch)
    return PayoutStateResult(batch=batch, previous_state=previous_state, is_replay=False)


def reconcile_batch(db: Session, batch_id: str) -> PayoutReconcileResult:
    batch = (
        db.query(PayoutBatch)
        .options(selectinload(PayoutBatch.items))
        .filter(PayoutBatch.id == batch_id)
        .one_or_none()
    )
    if not batch:
        raise PayoutError("batch_not_found")

    amount_expr = func.coalesce(Operation.amount_settled, Operation.amount)
    computed_amount, computed_count = (
        db.query(
            func.coalesce(func.sum(amount_expr), 0),
            func.count(Operation.id),
        )
        .select_from(Operation)
        .filter(Operation.merchant_id == batch.partner_id)
        .filter(Operation.status.in_([OperationStatus.CAPTURED, OperationStatus.COMPLETED]))
        .filter(func.date(Operation.created_at) >= batch.date_from)
        .filter(func.date(Operation.created_at) <= batch.date_to)
        .one()
    )

    recorded_amount = Decimal("0")
    recorded_count = 0
    if batch.items:
        for item in batch.items:
            recorded_amount += Decimal(item.amount_net or 0)
            recorded_count += int(item.operations_count or 0)
    else:
        recorded_amount = Decimal(batch.total_amount or 0)
        recorded_count = int(batch.operations_count or 0)

    computed_amount_decimal = Decimal(computed_amount or 0)
    computed_count_int = int(computed_count or 0)

    if computed_amount_decimal != recorded_amount or computed_count_int != recorded_count:
        payout_metrics.mark_reconcile_mismatch()

    return PayoutReconcileResult(
        batch=batch,
        computed_amount=computed_amount_decimal,
        computed_count=computed_count_int,
        recorded_amount=recorded_amount,
        recorded_count=recorded_count,
    )


__all__ = [
    "PayoutConflictError",
    "PayoutError",
    "PayoutReconcileResult",
    "PayoutBatchResult",
    "PayoutStateResult",
    "close_payout_period",
    "list_payout_batches",
    "load_payout_batch",
    "mark_batch_sent",
    "mark_batch_settled",
    "reconcile_batch",
]
