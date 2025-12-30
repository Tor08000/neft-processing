from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

import requests
from neft_shared.logging_setup import get_logger
from neft_shared.settings import get_settings
from sqlalchemy import tuple_
from sqlalchemy.orm import Session

from app.models.bi import (
    BiClickhouseCursor,
    BiDailyMetric,
    BiDeclineEvent,
    BiOrderEvent,
    BiPayoutEvent,
)
from app.services.bi.metrics import metrics as bi_metrics

logger = get_logger(__name__)
settings = get_settings()


@dataclass(frozen=True)
class ClickhouseDataset:
    name: str
    table: str
    fetch_rows: Callable[[Session, BiClickhouseCursor | None, int], list[dict[str, Any]]]


def _cursor_filter(query, cursor: BiClickhouseCursor | None, occurred_at_col, id_col):
    if cursor and cursor.last_occurred_at is not None:
        if cursor.last_id:
            return query.filter(tuple_(occurred_at_col, id_col) > (cursor.last_occurred_at, cursor.last_id))
        return query.filter(occurred_at_col > cursor.last_occurred_at)
    return query


def _fetch_order_events(db: Session, cursor: BiClickhouseCursor | None, limit: int) -> list[dict[str, Any]]:
    query = db.query(BiOrderEvent).order_by(BiOrderEvent.occurred_at.asc(), BiOrderEvent.event_id.asc())
    query = _cursor_filter(query, cursor, BiOrderEvent.occurred_at, BiOrderEvent.event_id)
    rows = query.limit(limit).all()
    return [
        {
            "tenant_id": item.tenant_id,
            "client_id": item.client_id or "",
            "partner_id": item.partner_id or "",
            "entity_id": item.event_id,
            "order_id": item.order_id or "",
            "event_id": item.event_id,
            "event_type": item.event_type,
            "occurred_at": item.occurred_at.isoformat(),
            "status": item.status_after or "",
            "amount": int(item.amount or 0),
            "currency": item.currency or "",
            "correlation_id": item.correlation_id or "",
            "payload_json": json.dumps(item.payload or {}, ensure_ascii=False),
        }
        for item in rows
    ]


def _fetch_orders(db: Session, cursor: BiClickhouseCursor | None, limit: int) -> list[dict[str, Any]]:
    query = db.query(BiOrderEvent).order_by(BiOrderEvent.occurred_at.asc(), BiOrderEvent.event_id.asc())
    query = _cursor_filter(query, cursor, BiOrderEvent.occurred_at, BiOrderEvent.event_id)
    rows = query.limit(limit).all()
    return [
        {
            "tenant_id": item.tenant_id,
            "client_id": item.client_id or "",
            "partner_id": item.partner_id or "",
            "entity_id": item.order_id or item.event_id,
            "occurred_at": item.occurred_at.isoformat(),
            "status": item.status_after or "",
            "amount": int(item.amount or 0),
            "currency": item.currency or "",
            "service_id": item.service_id or "",
            "offer_id": item.offer_id or "",
            "correlation_id": item.correlation_id or "",
            "payload_json": json.dumps(item.payload or {}, ensure_ascii=False),
        }
        for item in rows
    ]


def _fetch_payout_events(db: Session, cursor: BiClickhouseCursor | None, limit: int) -> list[dict[str, Any]]:
    query = db.query(BiPayoutEvent).order_by(BiPayoutEvent.occurred_at.asc(), BiPayoutEvent.event_id.asc())
    query = _cursor_filter(query, cursor, BiPayoutEvent.occurred_at, BiPayoutEvent.event_id)
    rows = query.limit(limit).all()
    return [
        {
            "tenant_id": item.tenant_id,
            "partner_id": item.partner_id or "",
            "entity_id": item.event_id,
            "settlement_id": item.settlement_id or "",
            "payout_batch_id": item.payout_batch_id or "",
            "event_type": item.event_type,
            "occurred_at": item.occurred_at.isoformat(),
            "amount_gross": int(item.amount_gross or 0),
            "amount_net": int(item.amount_net or 0),
            "amount_commission": int(item.amount_commission or 0),
            "currency": item.currency or "",
            "correlation_id": item.correlation_id or "",
            "payload_json": json.dumps(item.payload or {}, ensure_ascii=False),
        }
        for item in rows
    ]


def _fetch_decline_events(db: Session, cursor: BiClickhouseCursor | None, limit: int) -> list[dict[str, Any]]:
    query = db.query(BiDeclineEvent).order_by(BiDeclineEvent.occurred_at.asc(), BiDeclineEvent.operation_id.asc())
    query = _cursor_filter(query, cursor, BiDeclineEvent.occurred_at, BiDeclineEvent.operation_id)
    rows = query.limit(limit).all()
    return [
        {
            "tenant_id": item.tenant_id,
            "client_id": item.client_id or "",
            "partner_id": item.partner_id or "",
            "entity_id": item.operation_id,
            "occurred_at": item.occurred_at.isoformat(),
            "primary_reason": item.primary_reason or "",
            "amount": int(item.amount or 0),
            "product_type": item.product_type or "",
            "station_id": item.station_id or "",
            "correlation_id": item.correlation_id or "",
            "payload_json": json.dumps(item.secondary_reasons or {}, ensure_ascii=False),
        }
        for item in rows
    ]


def _fetch_daily_metrics(db: Session, cursor: BiClickhouseCursor | None, limit: int) -> list[dict[str, Any]]:
    query = db.query(BiDailyMetric).order_by(BiDailyMetric.date.asc(), BiDailyMetric.id.asc())
    query = _cursor_filter(query, cursor, BiDailyMetric.updated_at, BiDailyMetric.id)
    rows = query.limit(limit).all()
    return [
        {
            "tenant_id": item.tenant_id,
            "scope_type": item.scope_type.value,
            "scope_id": item.scope_id,
            "occurred_at": datetime.combine(item.date, datetime.min.time()).replace(tzinfo=timezone.utc).isoformat(),
            "spend_total": int(item.spend_total or 0),
            "orders_total": int(item.orders_total or 0),
            "orders_completed": int(item.orders_completed or 0),
            "refunds_total": int(item.refunds_total or 0),
            "payouts_total": int(item.payouts_total or 0),
            "declines_total": int(item.declines_total or 0),
            "top_primary_reason": item.top_primary_reason or "",
            "_cursor_entity_id": item.id,
            "_cursor_ts": item.updated_at.isoformat() if item.updated_at else None,
        }
        for item in rows
    ]


DATASETS = [
    ClickhouseDataset("order_events", "ch_order_events", _fetch_order_events),
    ClickhouseDataset("orders", "ch_orders", _fetch_orders),
    ClickhouseDataset("payout_events", "ch_payout_events", _fetch_payout_events),
    ClickhouseDataset("decline_events", "ch_decline_events", _fetch_decline_events),
    ClickhouseDataset("daily_metrics", "ch_daily_metrics", _fetch_daily_metrics),
]


class ClickhouseSyncError(Exception):
    """ClickHouse sync failure."""


def _post_rows(table: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    endpoint = f"{settings.CLICKHOUSE_URL.rstrip('/')}/?database={settings.CLICKHOUSE_DB}"
    query = f"INSERT INTO {table} FORMAT JSONEachRow"
    sanitized = [
        {key: value for key, value in row.items() if not key.startswith("_cursor_")}
        for row in rows
    ]
    payload = "\n".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in sanitized) + "\n"
    response = requests.post(endpoint, params={"query": query}, data=payload.encode("utf-8"), timeout=30)
    if response.status_code >= 400:
        raise ClickhouseSyncError(response.text)


def _load_cursor(db: Session, dataset: str) -> BiClickhouseCursor | None:
    return db.query(BiClickhouseCursor).filter(BiClickhouseCursor.dataset == dataset).one_or_none()


def _save_cursor(db: Session, dataset: str, last_id: str | None, last_occurred_at: datetime | None) -> None:
    cursor = _load_cursor(db, dataset)
    if cursor is None:
        cursor = BiClickhouseCursor(dataset=dataset)
        db.add(cursor)
    cursor.last_id = last_id
    cursor.last_occurred_at = last_occurred_at
    db.flush()


def _extract_cursor(rows: list[dict[str, Any]], id_field: str = "entity_id") -> tuple[str | None, datetime | None]:
    if not rows:
        return None, None
    last = rows[-1]
    last_id = last.get(f"_cursor_{id_field}", last.get(id_field))
    occurred_at = last.get("_cursor_ts", last.get("occurred_at"))
    last_ts = None
    if isinstance(occurred_at, str):
        try:
            last_ts = datetime.fromisoformat(occurred_at)
        except ValueError:
            last_ts = None
    return (str(last_id) if last_id is not None else None), last_ts


def sync_clickhouse(db: Session, *, batch_size: int = 5000, retries: int = 3) -> dict[str, int]:
    if not settings.BI_CLICKHOUSE_ENABLED:
        logger.info("bi.clickhouse_disabled")
        return {"synced": 0}

    total_synced = 0
    for dataset in DATASETS:
        cursor = _load_cursor(db, dataset.name)
        try:
            rows = dataset.fetch_rows(db, cursor, batch_size)
            if not rows:
                bi_metrics.mark_clickhouse_sync(dataset.name, "empty")
                continue

            for attempt in range(retries):
                try:
                    _post_rows(dataset.table, rows)
                    break
                except ClickhouseSyncError:
                    if attempt + 1 == retries:
                        raise
                    time.sleep(2**attempt)

            last_id, last_ts = _extract_cursor(rows)
            _save_cursor(db, dataset.name, last_id, last_ts)
            total_synced += len(rows)
            if last_ts:
                lag_seconds = (datetime.now(timezone.utc) - last_ts).total_seconds()
                bi_metrics.mark_clickhouse_lag(dataset.name, lag_seconds)
            bi_metrics.mark_clickhouse_sync(dataset.name, "success")
            logger.info(
                "bi.clickhouse_sync",
                extra={"dataset": dataset.name, "row_count": len(rows), "cursor": last_id},
            )
        except Exception as exc:  # noqa: BLE001
            bi_metrics.mark_clickhouse_sync(dataset.name, "failed")
            logger.exception("bi.clickhouse_sync_failed", extra={"dataset": dataset.name})
            raise ClickhouseSyncError(str(exc)) from exc
    return {"synced": total_synced}


__all__ = ["ClickhouseSyncError", "sync_clickhouse"]
