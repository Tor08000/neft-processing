from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.bi import BiExportBatch, BiOrderEvent, BiScopeType

HEADERS = [
    "tenant_id",
    "client_id",
    "partner_id",
    "order_id",
    "created_at",
    "updated_at",
    "status",
    "amount",
    "currency",
    "service_id",
    "offer_id",
]


def _apply_scope(query, export: BiExportBatch):
    if export.scope_type == BiScopeType.CLIENT and export.scope_id:
        query = query.filter(BiOrderEvent.client_id == export.scope_id)
    if export.scope_type == BiScopeType.PARTNER and export.scope_id:
        query = query.filter(BiOrderEvent.partner_id == export.scope_id)
    return query


def fetch_rows(export: BiExportBatch, db: Session) -> list[dict[str, Any]]:
    date_from = datetime.combine(export.date_from, datetime.min.time()).replace(tzinfo=timezone.utc)
    date_to = datetime.combine(export.date_to, datetime.max.time()).replace(tzinfo=timezone.utc)

    query = (
        db.query(BiOrderEvent)
        .filter(BiOrderEvent.tenant_id == export.tenant_id)
        .filter(BiOrderEvent.occurred_at >= date_from)
        .filter(BiOrderEvent.occurred_at <= date_to)
    )
    query = _apply_scope(query, export)
    rows = query.order_by(BiOrderEvent.occurred_at.asc()).all()

    orders: dict[str, dict[str, Any]] = {}
    for item in rows:
        order_id = item.order_id or item.event_id
        if not order_id:
            continue
        record = orders.get(order_id)
        occurred_at = item.occurred_at
        if record is None:
            record = {
                "tenant_id": item.tenant_id,
                "client_id": item.client_id,
                "partner_id": item.partner_id,
                "order_id": order_id,
                "created_at": occurred_at,
                "updated_at": occurred_at,
                "status": item.status_after,
                "amount": item.amount or 0,
                "currency": item.currency,
                "service_id": item.service_id,
                "offer_id": item.offer_id,
            }
            orders[order_id] = record
            continue

        if occurred_at and record["created_at"] and occurred_at < record["created_at"]:
            record["created_at"] = occurred_at
        if occurred_at and record["updated_at"] and occurred_at > record["updated_at"]:
            record["updated_at"] = occurred_at
        record["status"] = item.status_after or record.get("status")
        record["amount"] = item.amount or record.get("amount") or 0
        record["currency"] = item.currency or record.get("currency")
        record["service_id"] = item.service_id or record.get("service_id")
        record["offer_id"] = item.offer_id or record.get("offer_id")

    ordered = [OrderedDict((header, record.get(header)) for header in HEADERS) for record in orders.values()]
    return sorted(ordered, key=lambda row: row["created_at"] or datetime.min.replace(tzinfo=timezone.utc))

