from __future__ import annotations

from collections import OrderedDict
from typing import Any

from sqlalchemy.orm import Session

from app.models.bi import BiDailyMetric, BiExportBatch

HEADERS = [
    "tenant_id",
    "date",
    "scope_type",
    "scope_id",
    "spend_total",
    "orders_total",
    "orders_completed",
    "refunds_total",
    "payouts_total",
    "declines_total",
    "top_primary_reason",
]


def fetch_rows(export: BiExportBatch, db: Session) -> list[dict[str, Any]]:
    query = (
        db.query(BiDailyMetric)
        .filter(BiDailyMetric.tenant_id == export.tenant_id)
        .filter(BiDailyMetric.date >= export.date_from)
        .filter(BiDailyMetric.date <= export.date_to)
    )
    if export.scope_type and export.scope_id:
        query = query.filter(BiDailyMetric.scope_type == export.scope_type)
        query = query.filter(BiDailyMetric.scope_id == export.scope_id)
    rows = query.order_by(BiDailyMetric.date.asc()).all()

    return [
        OrderedDict(
            (
                ("tenant_id", item.tenant_id),
                ("date", item.date),
                ("scope_type", item.scope_type.value),
                ("scope_id", item.scope_id),
                ("spend_total", item.spend_total or 0),
                ("orders_total", item.orders_total or 0),
                ("orders_completed", item.orders_completed or 0),
                ("refunds_total", item.refunds_total or 0),
                ("payouts_total", item.payouts_total or 0),
                ("declines_total", item.declines_total or 0),
                ("top_primary_reason", item.top_primary_reason),
            )
        )
        for item in rows
    ]
