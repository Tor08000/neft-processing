from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.bi import BiDeclineEvent, BiExportBatch, BiScopeType

HEADERS = [
    "tenant_id",
    "client_id",
    "partner_id",
    "operation_id",
    "occurred_at",
    "primary_reason",
    "amount",
    "product_type",
    "station_id",
    "secondary_reasons",
]


def _apply_scope(query, export: BiExportBatch):
    if export.scope_type == BiScopeType.CLIENT and export.scope_id:
        query = query.filter(BiDeclineEvent.client_id == export.scope_id)
    if export.scope_type == BiScopeType.PARTNER and export.scope_id:
        query = query.filter(BiDeclineEvent.partner_id == export.scope_id)
    if export.scope_type == BiScopeType.STATION and export.scope_id:
        query = query.filter(BiDeclineEvent.station_id == export.scope_id)
    return query


def fetch_rows(export: BiExportBatch, db: Session) -> list[dict[str, Any]]:
    date_from = datetime.combine(export.date_from, datetime.min.time()).replace(tzinfo=timezone.utc)
    date_to = datetime.combine(export.date_to, datetime.max.time()).replace(tzinfo=timezone.utc)

    query = (
        db.query(BiDeclineEvent)
        .filter(BiDeclineEvent.tenant_id == export.tenant_id)
        .filter(BiDeclineEvent.occurred_at >= date_from)
        .filter(BiDeclineEvent.occurred_at <= date_to)
    )
    query = _apply_scope(query, export)
    rows = query.order_by(BiDeclineEvent.occurred_at.asc()).all()

    return [
        OrderedDict(
            (
                ("tenant_id", item.tenant_id),
                ("client_id", item.client_id),
                ("partner_id", item.partner_id),
                ("operation_id", item.operation_id),
                ("occurred_at", item.occurred_at),
                ("primary_reason", item.primary_reason),
                ("amount", item.amount or 0),
                ("product_type", item.product_type),
                ("station_id", item.station_id),
                ("secondary_reasons", item.secondary_reasons),
            )
        )
        for item in rows
    ]

