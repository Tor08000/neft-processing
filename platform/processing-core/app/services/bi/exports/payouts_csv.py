from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.bi import BiExportBatch, BiPayoutEvent, BiScopeType

HEADERS = [
    "tenant_id",
    "partner_id",
    "settlement_id",
    "payout_batch_id",
    "event_type",
    "occurred_at",
    "amount_gross",
    "amount_net",
    "amount_commission",
    "currency",
]


def _apply_scope(query, export: BiExportBatch):
    if export.scope_type == BiScopeType.PARTNER and export.scope_id:
        query = query.filter(BiPayoutEvent.partner_id == export.scope_id)
    return query


def fetch_rows(export: BiExportBatch, db: Session) -> list[dict[str, Any]]:
    date_from = datetime.combine(export.date_from, datetime.min.time()).replace(tzinfo=timezone.utc)
    date_to = datetime.combine(export.date_to, datetime.max.time()).replace(tzinfo=timezone.utc)

    query = (
        db.query(BiPayoutEvent)
        .filter(BiPayoutEvent.tenant_id == export.tenant_id)
        .filter(BiPayoutEvent.occurred_at >= date_from)
        .filter(BiPayoutEvent.occurred_at <= date_to)
    )
    query = _apply_scope(query, export)
    rows = query.order_by(BiPayoutEvent.occurred_at.asc()).all()

    return [
        OrderedDict(
            (
                ("tenant_id", item.tenant_id),
                ("partner_id", item.partner_id),
                ("settlement_id", item.settlement_id),
                ("payout_batch_id", item.payout_batch_id),
                ("event_type", item.event_type),
                ("occurred_at", item.occurred_at),
                ("amount_gross", item.amount_gross or 0),
                ("amount_net", item.amount_net or 0),
                ("amount_commission", item.amount_commission or 0),
                ("currency", item.currency),
            )
        )
        for item in rows
    ]

