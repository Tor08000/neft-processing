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
    "event_id",
    "event_type",
    "occurred_at",
    "amount",
    "currency",
    "service_id",
    "offer_id",
    "status_after",
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

    return [
        OrderedDict(
            (
                ("tenant_id", item.tenant_id),
                ("client_id", item.client_id),
                ("partner_id", item.partner_id),
                ("order_id", item.order_id),
                ("event_id", item.event_id),
                ("event_type", item.event_type),
                ("occurred_at", item.occurred_at),
                ("amount", item.amount or 0),
                ("currency", item.currency),
                ("service_id", item.service_id),
                ("offer_id", item.offer_id),
                ("status_after", item.status_after),
            )
        )
        for item in rows
    ]

