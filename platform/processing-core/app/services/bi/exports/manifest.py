from __future__ import annotations

from typing import Any

from app.models.bi import BiExportBatch, BiExportFormat, BiExportKind


DEFAULT_SCHEMA_VERSION = 1

DATASET_TABLES: dict[BiExportKind, str] = {
    BiExportKind.ORDERS: "neft_orders",
    BiExportKind.ORDER_EVENTS: "neft_order_events",
    BiExportKind.PAYOUTS: "neft_payouts",
    BiExportKind.DECLINES: "neft_declines",
    BiExportKind.DAILY_METRICS: "neft_daily_metrics",
}


FIELD_TYPES: dict[str, str] = {
    "tenant_id": "INTEGER",
    "client_id": "STRING",
    "partner_id": "STRING",
    "order_id": "STRING",
    "event_id": "STRING",
    "event_type": "STRING",
    "occurred_at": "TIMESTAMP",
    "created_at": "TIMESTAMP",
    "updated_at": "TIMESTAMP",
    "status": "STRING",
    "status_after": "STRING",
    "amount": "INTEGER",
    "amount_gross": "INTEGER",
    "amount_net": "INTEGER",
    "amount_commission": "INTEGER",
    "currency": "STRING",
    "service_id": "STRING",
    "offer_id": "STRING",
    "settlement_id": "STRING",
    "payout_batch_id": "STRING",
    "primary_reason": "STRING",
    "product_type": "STRING",
    "station_id": "STRING",
    "operation_id": "STRING",
    "secondary_reasons": "STRING",
    "scope_type": "STRING",
    "scope_id": "STRING",
    "spend_total": "INTEGER",
    "orders_total": "INTEGER",
    "orders_completed": "INTEGER",
    "refunds_total": "INTEGER",
    "payouts_total": "INTEGER",
    "declines_total": "INTEGER",
    "top_primary_reason": "STRING",
}


def build_manifest(
    export: BiExportBatch,
    *,
    headers: list[str],
    sha256: str,
    row_count: int,
) -> dict[str, Any]:
    table = DATASET_TABLES.get(export.kind, f"neft_{export.kind.value.lower()}")
    fields = [
        {"name": header, "type": FIELD_TYPES.get(header, "STRING")}
        for header in headers
    ]
    return {
        "dataset": export.kind.value.lower(),
        "format": export.format.value,
        "from": export.date_from.isoformat(),
        "to": export.date_to.isoformat(),
        "row_count": row_count,
        "sha256": sha256,
        "schema_version": DEFAULT_SCHEMA_VERSION,
        "recommended_bigquery_table": table,
        "fields": fields,
    }
