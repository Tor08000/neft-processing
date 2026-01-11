from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.integrations.fuel.models import FuelProviderBatch
from app.models.fuel import (
    FleetOfflineDiscrepancy,
    FleetOfflineDiscrepancyReason,
    FleetOfflineReconciliationRun,
    FleetOfflineReconciliationStatus,
    FuelCard,
    FuelCardStatus,
    FuelTransaction,
    FuelTransactionAuthType,
)


def _period_window(period_key: str) -> tuple[datetime, datetime]:
    start = datetime.strptime(period_key + "-01", "%Y-%m-%d").replace(tzinfo=timezone.utc)
    if start.month == 12:
        end = datetime(start.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(start.year, start.month + 1, 1, tzinfo=timezone.utc)
    return start, end


def reconcile_offline_batches(db: Session, *, client_id: str, period_key: str) -> FleetOfflineReconciliationRun:
    run = FleetOfflineReconciliationRun(
        client_id=client_id,
        period_key=period_key,
        status=FleetOfflineReconciliationStatus.STARTED,
    )
    db.add(run)
    db.flush()

    start, end = _period_window(period_key)
    offline_txs = (
        db.query(FuelTransaction)
        .filter(FuelTransaction.client_id == client_id)
        .filter(FuelTransaction.auth_type == FuelTransactionAuthType.OFFLINE)
        .filter(FuelTransaction.occurred_at >= start)
        .filter(FuelTransaction.occurred_at < end)
        .all()
    )

    daily_totals: dict[tuple[str, datetime], dict[str, Decimal]] = defaultdict(lambda: {"amount": Decimal("0"), "count": Decimal("0")})
    for tx in offline_txs:
        key = (str(tx.card_id), tx.occurred_at.date())
        daily_totals[key]["amount"] += Decimal(str(tx.amount or 0))
        daily_totals[key]["count"] += Decimal("1")

    for tx in offline_txs:
        snapshot = _resolve_snapshot(db, tx)
        if not snapshot:
            continue
        _check_offline_tx(db, run=run, tx=tx, snapshot=snapshot, daily_totals=daily_totals)

    run.status = FleetOfflineReconciliationStatus.FINISHED
    db.flush()
    return run


def _resolve_snapshot(db: Session, tx: FuelTransaction) -> dict | None:
    if tx.provider_batch_key:
        batch = (
            db.query(FuelProviderBatch)
            .filter(FuelProviderBatch.provider_code == tx.provider_code)
            .filter(FuelProviderBatch.batch_key == tx.provider_batch_key)
            .one_or_none()
        )
        if batch and batch.offline_profile_snapshot:
            return batch.offline_profile_snapshot
    return None


def _check_offline_tx(
    db: Session,
    *,
    run: FleetOfflineReconciliationRun,
    tx: FuelTransaction,
    snapshot: dict,
    daily_totals: dict[tuple[str, datetime], dict[str, Decimal]],
) -> None:
    card = db.query(FuelCard).filter(FuelCard.id == tx.card_id).one_or_none()
    if card and card.status != FuelCardStatus.ACTIVE:
        _add_discrepancy(
            db,
            run=run,
            tx=tx,
            reason=FleetOfflineDiscrepancyReason.CARD_BLOCKED_AT_TIME,
            details={"status": card.status.value},
        )

    allowed_products = snapshot.get("allowed_products") or []
    if allowed_products:
        normalized = {str(item).upper() for item in allowed_products}
        if tx.category and tx.category.upper() not in normalized:
            _add_discrepancy(
                db,
                run=run,
                tx=tx,
                reason=FleetOfflineDiscrepancyReason.UNEXPECTED_PRODUCT,
                details={"product_code": tx.category},
            )

    allowed_stations = snapshot.get("allowed_stations") or []
    if allowed_stations and tx.station_external_id not in allowed_stations:
        _add_discrepancy(
            db,
            run=run,
            tx=tx,
            reason=FleetOfflineDiscrepancyReason.UNEXPECTED_PRODUCT,
            details={"station_id": tx.station_external_id},
        )

    amount_limit = snapshot.get("daily_amount_limit")
    txn_limit = snapshot.get("daily_txn_limit")
    totals = daily_totals.get((str(tx.card_id), tx.occurred_at.date()), {})
    if amount_limit is not None:
        limit = Decimal(str(amount_limit))
        if totals.get("amount", Decimal("0")) > limit:
            _add_discrepancy(
                db,
                run=run,
                tx=tx,
                reason=FleetOfflineDiscrepancyReason.OFFLINE_LIMIT_EXCEEDED,
                details={"daily_amount": str(totals.get("amount")), "limit": str(limit)},
            )

    if txn_limit is not None:
        if totals.get("count", Decimal("0")) > Decimal(str(txn_limit)):
            _add_discrepancy(
                db,
                run=run,
                tx=tx,
                reason=FleetOfflineDiscrepancyReason.OFFLINE_LIMIT_EXCEEDED,
                details={"daily_count": str(totals.get("count")), "limit": str(txn_limit)},
            )

    raw_amount = None
    if tx.raw_payload:
        raw_amount = tx.raw_payload.get("amount")
    if raw_amount is not None and Decimal(str(raw_amount)) != Decimal(str(tx.amount or 0)):
        _add_discrepancy(
            db,
            run=run,
            tx=tx,
            reason=FleetOfflineDiscrepancyReason.AMOUNT_MISMATCH,
            details={"raw_amount": str(raw_amount), "stored_amount": str(tx.amount or 0)},
        )


def _add_discrepancy(
    db: Session,
    *,
    run: FleetOfflineReconciliationRun,
    tx: FuelTransaction,
    reason: FleetOfflineDiscrepancyReason,
    details: dict,
) -> None:
    discrepancy = FleetOfflineDiscrepancy(
        run_id=run.id,
        provider_tx_id=tx.provider_tx_id,
        tx_id=tx.id,
        reason=reason,
        details=details,
    )
    db.add(discrepancy)
