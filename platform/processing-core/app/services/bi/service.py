from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.bi import BiDailyMetric, BiScopeType
from app.models.bi import BiDeclineEvent, BiOfferMetric, BiOrderEvent, BiPayoutEvent, BiPriceVersionMetric
from app.models.crm import CRMClient
from app.models.operation import Operation, OperationStatus
from app.models.payout_batch import PayoutBatch, PayoutItem
from app.models.unified_explain import UnifiedExplainSnapshot
from app.services.bi import repository
from app.services.bi.metrics import metrics as bi_metrics


COMPLETED_STATUSES = {
    OperationStatus.COMPLETED.value,
    OperationStatus.CAPTURED.value,
    OperationStatus.AUTHORIZED.value,
}
REFUND_TYPES = {"REFUND", "REVERSE", "REVERSAL"}


@dataclass(frozen=True)
class IngestResult:
    inserted: int
    cursor_at: datetime | None


def _truncate_payload(payload: dict[str, Any], *, limit: int = 2000) -> dict[str, Any]:
    raw = json.dumps(payload, ensure_ascii=False)
    if len(raw) <= limit:
        return payload
    return {"_truncated": True}


def _extract_price_version_id(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    for key in ("price_version_id", "price_version", "priceVersionId"):
        value = payload.get(key)
        if value:
            return str(value)
    return None


def ingest_order_events(db: Session, *, limit: int = 5000) -> IngestResult:
    cursor = repository.get_cursor(db, "bi_orders")
    since = cursor.last_event_at if cursor else None

    query = (
        db.query(Operation, CRMClient.tenant_id)
        .outerjoin(CRMClient, CRMClient.id == Operation.client_id)
        .order_by(Operation.created_at.asc())
    )
    if since:
        query = query.filter(Operation.created_at > since)
    rows = query.limit(limit).all()

    payloads: list[dict[str, Any]] = []
    max_seen = since
    for operation, tenant_id in rows:
        occurred_at = operation.created_at
        if max_seen is None or occurred_at > max_seen:
            max_seen = occurred_at
        payload = _truncate_payload(
            {
                "operation_type": operation.operation_type.value,
                "status": operation.status.value,
                "merchant_id": operation.merchant_id,
                "terminal_id": operation.terminal_id,
                "product_type": operation.product_type.value if operation.product_type else None,
            }
        )
        payloads.append(
            {
                "event_id": str(operation.id),
                "tenant_id": int(tenant_id or 0),
                "client_id": operation.client_id,
                "partner_id": operation.merchant_id,
                "order_id": str(operation.id),
                "event_type": operation.operation_type.value,
                "occurred_at": occurred_at,
                "amount": int(operation.amount or 0),
                "currency": operation.currency,
                "service_id": operation.product_id,
                "offer_id": operation.tariff_id,
                "status_after": operation.status.value,
                "correlation_id": None,
                "payload": payload,
            }
        )
    inserted = repository.upsert_order_events(db, payloads)
    if rows:
        repository.upsert_cursor(db, "bi_orders", last_event_at=max_seen)
    return IngestResult(inserted=inserted, cursor_at=max_seen)


def ingest_decline_events(db: Session, *, limit: int = 5000) -> IngestResult:
    cursor = repository.get_cursor(db, "bi_declines")
    since = cursor.last_event_at if cursor else None

    query = (
        db.query(Operation, CRMClient.tenant_id)
        .outerjoin(CRMClient, CRMClient.id == Operation.client_id)
        .filter(Operation.status == OperationStatus.DECLINED)
        .order_by(Operation.created_at.asc())
    )
    if since:
        query = query.filter(Operation.created_at > since)
    rows = query.limit(limit).all()

    payloads: list[dict[str, Any]] = []
    max_seen = since
    for operation, tenant_id in rows:
        occurred_at = operation.created_at
        if max_seen is None or occurred_at > max_seen:
            max_seen = occurred_at
        snapshot = (
            db.query(UnifiedExplainSnapshot)
            .filter(UnifiedExplainSnapshot.subject_id == str(operation.id))
            .filter(UnifiedExplainSnapshot.tenant_id == int(tenant_id or 0))
            .order_by(UnifiedExplainSnapshot.created_at.desc())
            .first()
        )
        primary_reason = None
        secondary_reasons = None
        if snapshot and isinstance(snapshot.snapshot_json, dict):
            primary_reason = snapshot.snapshot_json.get("primary_reason")
            secondary_reasons = snapshot.snapshot_json.get("secondary_reasons")
            if primary_reason is None and isinstance(snapshot.snapshot_json.get("result"), dict):
                primary_reason = snapshot.snapshot_json["result"].get("primary_reason")
        payloads.append(
            {
                "operation_id": str(operation.id),
                "tenant_id": int(tenant_id or 0),
                "client_id": operation.client_id,
                "partner_id": operation.merchant_id,
                "occurred_at": occurred_at,
                "primary_reason": primary_reason,
                "secondary_reasons": secondary_reasons,
                "amount": int(operation.amount or 0),
                "product_type": operation.product_type.value if operation.product_type else None,
                "station_id": operation.terminal_id,
                "correlation_id": None,
            }
        )
    inserted = repository.upsert_decline_events(db, payloads)
    if rows:
        repository.upsert_cursor(db, "bi_declines", last_event_at=max_seen)
    return IngestResult(inserted=inserted, cursor_at=max_seen)


def _aggregate_payout_amounts(db: Session, batch_ids: list[str]) -> dict[str, dict[str, int]]:
    if not batch_ids:
        return {}
    rows = (
        db.query(
            PayoutItem.batch_id,
            func.coalesce(func.sum(PayoutItem.amount_gross), 0).label("amount_gross"),
            func.coalesce(func.sum(PayoutItem.amount_net), 0).label("amount_net"),
            func.coalesce(func.sum(PayoutItem.commission_amount), 0).label("amount_commission"),
        )
        .filter(PayoutItem.batch_id.in_(batch_ids))
        .group_by(PayoutItem.batch_id)
        .all()
    )
    totals: dict[str, dict[str, int]] = {}
    for row in rows:
        totals[str(row.batch_id)] = {
            "amount_gross": int(row.amount_gross or 0),
            "amount_net": int(row.amount_net or 0),
            "amount_commission": int(row.amount_commission or 0),
        }
    return totals


def ingest_payout_events(db: Session, *, limit: int = 2000) -> IngestResult:
    cursor = repository.get_cursor(db, "bi_payouts")
    since = cursor.last_event_at if cursor else None

    query = db.query(PayoutBatch).order_by(PayoutBatch.created_at.asc())
    if since:
        query = query.filter(
            or_(
                PayoutBatch.created_at > since,
                PayoutBatch.sent_at > since,
                PayoutBatch.settled_at > since,
            )
        )
    batches = query.limit(limit).all()

    totals = _aggregate_payout_amounts(db, [batch.id for batch in batches])

    payloads: list[dict[str, Any]] = []
    max_seen = since
    for batch in batches:
        batch_totals = totals.get(batch.id, {})
        base = {
            "tenant_id": int(batch.tenant_id),
            "partner_id": batch.partner_id,
            "settlement_id": None,
            "payout_batch_id": batch.id,
            "currency": None,
            "amount_gross": batch_totals.get("amount_gross", int(batch.total_amount or 0)),
            "amount_net": batch_totals.get("amount_net", int(batch.total_amount or 0)),
            "amount_commission": batch_totals.get("amount_commission", 0),
            "correlation_id": None,
            "payload": _truncate_payload({"state": batch.state.value}),
        }

        created_at = batch.created_at
        if created_at:
            payloads.append(
                {
                    "event_id": f"{batch.id}:CREATED",
                    "event_type": "CREATED",
                    "occurred_at": created_at,
                    **base,
                }
            )
            if max_seen is None or created_at > max_seen:
                max_seen = created_at
        if batch.sent_at:
            payloads.append(
                {
                    "event_id": f"{batch.id}:SENT",
                    "event_type": "SENT",
                    "occurred_at": batch.sent_at,
                    **base,
                }
            )
            if max_seen is None or batch.sent_at > max_seen:
                max_seen = batch.sent_at
        if batch.settled_at:
            payloads.append(
                {
                    "event_id": f"{batch.id}:SETTLED",
                    "event_type": "SETTLED",
                    "occurred_at": batch.settled_at,
                    **base,
                }
            )
            if max_seen is None or batch.settled_at > max_seen:
                max_seen = batch.settled_at

    inserted = repository.upsert_payout_events(db, payloads)
    if batches:
        repository.upsert_cursor(db, "bi_payouts", last_event_at=max_seen)
    return IngestResult(inserted=inserted, cursor_at=max_seen)


def ingest_events(db: Session) -> dict[str, IngestResult]:
    results: dict[str, IngestResult] = {}
    try:
        results["orders"] = ingest_order_events(db)
        results["declines"] = ingest_decline_events(db)
        results["payouts"] = ingest_payout_events(db)
        latest = max(
            (result.cursor_at for result in results.values() if result.cursor_at),
            default=None,
        )
        if latest:
            lag = datetime.now(timezone.utc) - latest
            bi_metrics.ingest_lag_seconds = max(lag.total_seconds(), 0.0)
        bi_metrics.mark_ingest("success")
    except Exception:
        bi_metrics.mark_ingest("failed")
        raise
    return results


def _scope_value(
    scope_type: BiScopeType,
    tenant_id: int,
    client_id: str | None,
    partner_id: str | None,
    station_id: str | None,
) -> str | None:
    if scope_type == BiScopeType.TENANT:
        return str(tenant_id)
    if scope_type == BiScopeType.CLIENT:
        return client_id
    if scope_type == BiScopeType.PARTNER:
        return partner_id
    if scope_type == BiScopeType.STATION:
        return station_id
    return None


def aggregate_daily(db: Session, *, date_from: date, date_to: date) -> int:
    start_dt = datetime.combine(date_from, time.min).replace(tzinfo=timezone.utc)
    end_dt = datetime.combine(date_to, time.max).replace(tzinfo=timezone.utc)

    aggregates: dict[tuple[int, date, BiScopeType, str], dict[str, Any]] = defaultdict(
        lambda: {
            "spend_total": 0,
            "orders_total": 0,
            "orders_completed": 0,
            "refunds_total": 0,
            "payouts_total": 0,
            "declines_total": 0,
            "top_primary_reason": None,
        }
    )

    scope_types = [BiScopeType.TENANT, BiScopeType.CLIENT, BiScopeType.PARTNER]

    order_rows = (
        db.query(
            BiOrderEvent.occurred_at.label("occurred_at"),
            BiOrderEvent.tenant_id.label("tenant_id"),
            BiOrderEvent.client_id.label("client_id"),
            BiOrderEvent.partner_id.label("partner_id"),
            BiOrderEvent.status_after.label("status_after"),
            BiOrderEvent.event_type.label("event_type"),
            BiOrderEvent.amount.label("amount"),
        )
        .filter(BiOrderEvent.occurred_at >= start_dt)
        .filter(BiOrderEvent.occurred_at <= end_dt)
        .all()
    )

    for row in order_rows:
        day = row.occurred_at.date()
        tenant_id = int(row.tenant_id or 0)
        for scope_type in scope_types:
            scope_id = _scope_value(scope_type, tenant_id, row.client_id, row.partner_id, None)
            if scope_id is None:
                continue
            key = (tenant_id, day, scope_type, scope_id)
            bucket = aggregates[key]
            bucket["orders_total"] += 1
            if row.status_after in COMPLETED_STATUSES:
                bucket["orders_completed"] += 1
                bucket["spend_total"] += int(row.amount or 0)
            if row.event_type in REFUND_TYPES:
                bucket["refunds_total"] += int(row.amount or 0)

    payout_rows = (
        db.query(
            func.date(BiPayoutEvent.occurred_at).label("day"),
            BiPayoutEvent.tenant_id.label("tenant_id"),
            BiPayoutEvent.partner_id.label("partner_id"),
            func.coalesce(func.sum(BiPayoutEvent.amount_net), 0).label("amount_net"),
        )
        .filter(BiPayoutEvent.occurred_at >= start_dt)
        .filter(BiPayoutEvent.occurred_at <= end_dt)
        .group_by(BiPayoutEvent.tenant_id, BiPayoutEvent.partner_id, func.date(BiPayoutEvent.occurred_at))
        .all()
    )
    for row in payout_rows:
        day = row.day
        tenant_id = int(row.tenant_id or 0)
        for scope_type in [BiScopeType.TENANT, BiScopeType.PARTNER]:
            scope_id = _scope_value(scope_type, tenant_id, None, row.partner_id, None)
            if scope_id is None:
                continue
            key = (tenant_id, day, scope_type, scope_id)
            aggregates[key]["payouts_total"] += int(row.amount_net or 0)

    decline_rows = (
        db.query(
            BiDeclineEvent.occurred_at.label("occurred_at"),
            BiDeclineEvent.tenant_id.label("tenant_id"),
            BiDeclineEvent.client_id.label("client_id"),
            BiDeclineEvent.partner_id.label("partner_id"),
            BiDeclineEvent.station_id.label("station_id"),
        )
        .filter(BiDeclineEvent.occurred_at >= start_dt)
        .filter(BiDeclineEvent.occurred_at <= end_dt)
        .all()
    )
    for row in decline_rows:
        day = row.occurred_at.date()
        tenant_id = int(row.tenant_id or 0)
        for scope_type in [BiScopeType.TENANT, BiScopeType.CLIENT, BiScopeType.PARTNER, BiScopeType.STATION]:
            scope_id = _scope_value(
                scope_type,
                tenant_id,
                row.client_id,
                row.partner_id,
                row.station_id,
            )
            if scope_id is None:
                continue
            key = (tenant_id, day, scope_type, scope_id)
            aggregates[key]["declines_total"] += 1

    reason_rows = (
        db.query(
            BiDeclineEvent.tenant_id,
            BiDeclineEvent.primary_reason,
            BiDeclineEvent.client_id,
            BiDeclineEvent.partner_id,
            BiDeclineEvent.station_id,
            BiDeclineEvent.occurred_at,
        )
        .filter(BiDeclineEvent.occurred_at >= start_dt)
        .filter(BiDeclineEvent.occurred_at <= end_dt)
        .all()
    )
    reasons: dict[tuple[int, date, BiScopeType, str], dict[str, int]] = defaultdict(dict)
    for snapshot in reason_rows:
        primary_reason = snapshot.primary_reason
        if not primary_reason:
            continue
        day = snapshot.occurred_at.date()
        tenant_id = int(snapshot.tenant_id or 0)
        scope_values = [
            (BiScopeType.TENANT, str(tenant_id)),
            (BiScopeType.CLIENT, snapshot.client_id),
            (BiScopeType.PARTNER, snapshot.partner_id),
            (BiScopeType.STATION, snapshot.station_id),
        ]
        for scope_type, scope_id in scope_values:
            if not scope_id:
                continue
            key = (tenant_id, day, scope_type, str(scope_id))
            reasons[key][primary_reason] = reasons[key].get(primary_reason, 0) + 1

    rows_to_upsert: list[dict[str, Any]] = []
    for (tenant_id, day, scope_type, scope_id), data in aggregates.items():
        reason_counts = reasons.get((tenant_id, day, scope_type, scope_id), {})
        top_reason = None
        if reason_counts:
            top_reason = max(reason_counts.items(), key=lambda item: item[1])[0]
        rows_to_upsert.append(
            {
                "tenant_id": tenant_id,
                "date": day,
                "scope_type": scope_type,
                "scope_id": scope_id,
                "spend_total": data["spend_total"],
                "orders_total": data["orders_total"],
                "orders_completed": data["orders_completed"],
                "refunds_total": data["refunds_total"],
                "payouts_total": data["payouts_total"],
                "declines_total": data["declines_total"],
                "top_primary_reason": top_reason,
            }
        )

    try:
        updated = repository.upsert_daily_metrics(db, rows_to_upsert)
        bi_metrics.mark_aggregate("success")
    except Exception:
        bi_metrics.mark_aggregate("failed")
        raise
    return updated


def aggregate_price_version_metrics(db: Session, *, date_from: date, date_to: date) -> int:
    start_dt = datetime.combine(date_from, time.min).replace(tzinfo=timezone.utc)
    end_dt = datetime.combine(date_to, time.max).replace(tzinfo=timezone.utc)

    aggregates: dict[tuple[int, str, str, date], dict[str, int]] = defaultdict(
        lambda: {
            "orders_count": 0,
            "completed_orders_count": 0,
            "revenue_total": 0,
            "refunds_count": 0,
        }
    )

    rows = (
        db.query(
            BiOrderEvent.occurred_at.label("occurred_at"),
            BiOrderEvent.tenant_id.label("tenant_id"),
            BiOrderEvent.partner_id.label("partner_id"),
            BiOrderEvent.status_after.label("status_after"),
            BiOrderEvent.event_type.label("event_type"),
            BiOrderEvent.amount.label("amount"),
            BiOrderEvent.payload.label("payload"),
        )
        .filter(BiOrderEvent.occurred_at >= start_dt)
        .filter(BiOrderEvent.occurred_at <= end_dt)
        .all()
    )

    for row in rows:
        if not row.partner_id:
            continue
        price_version_id = _extract_price_version_id(row.payload)
        if not price_version_id:
            continue
        day = row.occurred_at.date()
        tenant_id = int(row.tenant_id or 0)
        key = (tenant_id, str(row.partner_id), price_version_id, day)
        bucket = aggregates[key]
        bucket["orders_count"] += 1
        if row.status_after in COMPLETED_STATUSES:
            bucket["completed_orders_count"] += 1
            bucket["revenue_total"] += int(row.amount or 0)
        if row.event_type in REFUND_TYPES:
            bucket["refunds_count"] += 1

    rows_to_upsert: list[dict[str, Any]] = []
    for (tenant_id, partner_id, price_version_id, day), data in aggregates.items():
        completed = data["completed_orders_count"]
        avg_order_value = int(data["revenue_total"] / completed) if completed else 0
        rows_to_upsert.append(
            {
                "tenant_id": tenant_id,
                "partner_id": partner_id,
                "price_version_id": price_version_id,
                "date": day,
                "orders_count": data["orders_count"],
                "completed_orders_count": completed,
                "revenue_total": data["revenue_total"],
                "avg_order_value": avg_order_value,
                "refunds_count": data["refunds_count"],
            }
        )

    try:
        updated = repository.upsert_price_version_metrics(db, rows_to_upsert)
        bi_metrics.mark_aggregate("success")
    except Exception:
        bi_metrics.mark_aggregate("failed")
        raise
    return updated


def aggregate_offer_metrics(db: Session, *, date_from: date, date_to: date) -> int:
    start_dt = datetime.combine(date_from, time.min).replace(tzinfo=timezone.utc)
    end_dt = datetime.combine(date_to, time.max).replace(tzinfo=timezone.utc)

    aggregates: dict[tuple[int, str, str, date], dict[str, int]] = defaultdict(
        lambda: {
            "orders_count": 0,
            "revenue_total": 0,
        }
    )

    rows = (
        db.query(
            BiOrderEvent.occurred_at.label("occurred_at"),
            BiOrderEvent.tenant_id.label("tenant_id"),
            BiOrderEvent.partner_id.label("partner_id"),
            BiOrderEvent.offer_id.label("offer_id"),
            BiOrderEvent.status_after.label("status_after"),
            BiOrderEvent.amount.label("amount"),
        )
        .filter(BiOrderEvent.occurred_at >= start_dt)
        .filter(BiOrderEvent.occurred_at <= end_dt)
        .all()
    )

    for row in rows:
        if not row.partner_id or not row.offer_id:
            continue
        day = row.occurred_at.date()
        tenant_id = int(row.tenant_id or 0)
        key = (tenant_id, str(row.partner_id), str(row.offer_id), day)
        bucket = aggregates[key]
        bucket["orders_count"] += 1
        if row.status_after in COMPLETED_STATUSES:
            bucket["revenue_total"] += int(row.amount or 0)

    rows_to_upsert: list[dict[str, Any]] = []
    for (tenant_id, partner_id, offer_id, day), data in aggregates.items():
        orders_count = data["orders_count"]
        avg_price = int(data["revenue_total"] / orders_count) if orders_count else 0
        rows_to_upsert.append(
            {
                "tenant_id": tenant_id,
                "partner_id": partner_id,
                "offer_id": offer_id,
                "date": day,
                "views_count": None,
                "orders_count": orders_count,
                "conversion_rate": None,
                "avg_price": avg_price,
                "revenue_total": data["revenue_total"],
            }
        )

    try:
        updated = repository.upsert_offer_metrics(db, rows_to_upsert)
        bi_metrics.mark_aggregate("success")
    except Exception:
        bi_metrics.mark_aggregate("failed")
        raise
    return updated


def list_price_version_metrics(
    db: Session,
    *,
    tenant_id: int,
    partner_id: str,
    date_from: date,
    date_to: date,
) -> list[dict[str, Any]]:
    rows = (
        db.query(
            BiPriceVersionMetric.price_version_id.label("price_version_id"),
            func.min(BiPriceVersionMetric.date).label("published_date"),
            func.coalesce(func.sum(BiPriceVersionMetric.orders_count), 0).label("orders_count"),
            func.coalesce(func.sum(BiPriceVersionMetric.completed_orders_count), 0).label("completed_orders_count"),
            func.coalesce(func.sum(BiPriceVersionMetric.revenue_total), 0).label("revenue_total"),
            func.coalesce(func.sum(BiPriceVersionMetric.refunds_count), 0).label("refunds_count"),
        )
        .filter(BiPriceVersionMetric.tenant_id == tenant_id)
        .filter(BiPriceVersionMetric.partner_id == partner_id)
        .filter(BiPriceVersionMetric.date >= date_from)
        .filter(BiPriceVersionMetric.date <= date_to)
        .group_by(BiPriceVersionMetric.price_version_id)
        .order_by(func.min(BiPriceVersionMetric.date).desc())
        .all()
    )

    results: list[dict[str, Any]] = []
    for row in rows:
        completed = int(row.completed_orders_count or 0)
        revenue_total = int(row.revenue_total or 0)
        avg_order_value = int(revenue_total / completed) if completed else 0
        results.append(
            {
                "price_version_id": row.price_version_id,
                "published_at": datetime.combine(row.published_date, time.min, tzinfo=timezone.utc)
                if row.published_date
                else None,
                "orders_count": int(row.orders_count or 0),
                "revenue_total": revenue_total,
                "avg_order_value": avg_order_value,
                "refunds_count": int(row.refunds_count or 0),
            }
        )
    return results


def list_offer_metrics(
    db: Session,
    *,
    tenant_id: int,
    partner_id: str,
    date_from: date,
    date_to: date,
) -> list[dict[str, Any]]:
    rows = (
        db.query(
            BiOfferMetric.offer_id.label("offer_id"),
            func.coalesce(func.sum(BiOfferMetric.orders_count), 0).label("orders_count"),
            func.coalesce(func.sum(BiOfferMetric.views_count), 0).label("views_count"),
            func.coalesce(func.sum(BiOfferMetric.revenue_total), 0).label("revenue_total"),
        )
        .filter(BiOfferMetric.tenant_id == tenant_id)
        .filter(BiOfferMetric.partner_id == partner_id)
        .filter(BiOfferMetric.date >= date_from)
        .filter(BiOfferMetric.date <= date_to)
        .group_by(BiOfferMetric.offer_id)
        .all()
    )

    results: list[dict[str, Any]] = []
    for row in rows:
        orders_count = int(row.orders_count or 0)
        views_count = int(row.views_count or 0)
        revenue_total = int(row.revenue_total or 0)
        avg_price = int(revenue_total / orders_count) if orders_count else 0
        conversion_rate = None
        if views_count > 0:
            conversion_rate = orders_count / views_count
        results.append(
            {
                "offer_id": row.offer_id,
                "orders_count": orders_count,
                "conversion_rate": conversion_rate,
                "avg_price": avg_price,
                "revenue_total": revenue_total,
            }
        )
    return results


def list_price_version_series(
    db: Session,
    *,
    tenant_id: int,
    partner_id: str,
    price_version_id: str,
    date_from: date,
    date_to: date,
) -> list[dict[str, Any]]:
    return [
        {
            "date": metric.date,
            "orders_count": int(metric.orders_count or 0),
            "revenue_total": int(metric.revenue_total or 0),
        }
        for metric in (
            db.query(BiPriceVersionMetric)
            .filter(BiPriceVersionMetric.tenant_id == tenant_id)
            .filter(BiPriceVersionMetric.partner_id == partner_id)
            .filter(BiPriceVersionMetric.price_version_id == price_version_id)
            .filter(BiPriceVersionMetric.date >= date_from)
            .filter(BiPriceVersionMetric.date <= date_to)
            .order_by(BiPriceVersionMetric.date.asc())
            .all()
        )
    ]


def build_price_insights(
    metrics: list[dict[str, Any]],
    *,
    date_from: date,
    date_to: date,
) -> list[dict[str, Any]]:
    if len(metrics) < 2:
        return []
    latest, previous = metrics[0], metrics[1]
    prev_orders = previous.get("orders_count", 0) or 0
    curr_orders = latest.get("orders_count", 0) or 0
    if prev_orders <= 0:
        return []
    delta_pct = round(((curr_orders - prev_orders) / prev_orders) * 100)
    if delta_pct >= 0:
        return []
    period_days = (date_to - date_from).days + 1
    message = (
        f"После публикации версии {latest['price_version_id']} количество заказов "
        f"снизилось на {abs(delta_pct)}% за {period_days} дней."
    )
    return [
        {
            "type": "PRICE_INCREASE_EFFECT",
            "severity": "INFO",
            "message": message,
            "price_version_id": latest["price_version_id"],
        }
    ]

def backfill(db: Session, *, date_from: date, date_to: date) -> dict[str, Any]:
    ingest_events(db)
    updated = aggregate_daily(db, date_from=date_from, date_to=date_to)
    updated += aggregate_price_version_metrics(db, date_from=date_from, date_to=date_to)
    updated += aggregate_offer_metrics(db, date_from=date_from, date_to=date_to)
    return {"aggregated": updated}


def list_daily_metrics(
    db: Session,
    *,
    tenant_id: int,
    scope_type: BiScopeType,
    scope_id: str,
    date_from: date,
    date_to: date,
) -> list[BiDailyMetric]:
    return (
        db.query(BiDailyMetric)
        .filter(BiDailyMetric.tenant_id == tenant_id)
        .filter(BiDailyMetric.scope_type == scope_type)
        .filter(BiDailyMetric.scope_id == scope_id)
        .filter(BiDailyMetric.date >= date_from)
        .filter(BiDailyMetric.date <= date_to)
        .order_by(BiDailyMetric.date.asc())
        .all()
    )


__all__ = [
    "IngestResult",
    "aggregate_daily",
    "aggregate_offer_metrics",
    "aggregate_price_version_metrics",
    "backfill",
    "build_price_insights",
    "ingest_events",
    "ingest_decline_events",
    "ingest_order_events",
    "ingest_payout_events",
    "list_daily_metrics",
    "list_offer_metrics",
    "list_price_version_metrics",
    "list_price_version_series",
]
