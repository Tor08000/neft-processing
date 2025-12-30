from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timezone
from io import StringIO

from sqlalchemy.orm import Session

from app.models.bi import (
    BiDailyMetric,
    BiDeclineEvent,
    BiExportBatch,
    BiExportFormat,
    BiExportKind,
    BiExportStatus,
    BiOrderEvent,
    BiPayoutEvent,
    BiScopeType,
)
from app.services.bi.metrics import metrics as bi_metrics
from app.services.s3_storage import S3Storage


class BiExportError(Exception):
    """Domain error for BI exports."""


@dataclass(frozen=True)
class BiExportResult:
    export: BiExportBatch
    created: bool


def _build_object_key(batch: BiExportBatch) -> str:
    scope = batch.scope_type.value if batch.scope_type else "TENANT"
    scope_id = batch.scope_id or f"tenant-{batch.tenant_id}"
    date_from = batch.date_from.isoformat()
    date_to = batch.date_to.isoformat()
    return f"bi/{batch.tenant_id}/{batch.kind.value}/{scope}/{scope_id}/{date_from}_{date_to}/{batch.id}.csv"


def create_export_batch(
    db: Session,
    *,
    tenant_id: int,
    kind: BiExportKind,
    scope_type: BiScopeType | None,
    scope_id: str | None,
    date_from: date,
    date_to: date,
    export_format: BiExportFormat,
) -> BiExportBatch:
    export = BiExportBatch(
        tenant_id=tenant_id,
        kind=kind,
        scope_type=scope_type,
        scope_id=scope_id,
        date_from=date_from,
        date_to=date_to,
        format=export_format,
        status=BiExportStatus.CREATED,
    )
    db.add(export)
    db.commit()
    db.refresh(export)
    return export


def _render_rows(export: BiExportBatch, db: Session) -> tuple[list[str], list[list[str]]]:
    date_from = datetime.combine(export.date_from, datetime.min.time()).replace(tzinfo=timezone.utc)
    date_to = datetime.combine(export.date_to, datetime.max.time()).replace(tzinfo=timezone.utc)

    if export.kind == BiExportKind.ORDERS:
        query = (
            db.query(BiOrderEvent)
            .filter(BiOrderEvent.tenant_id == export.tenant_id)
            .filter(BiOrderEvent.occurred_at >= date_from)
            .filter(BiOrderEvent.occurred_at <= date_to)
        )
        if export.scope_type == BiScopeType.CLIENT and export.scope_id:
            query = query.filter(BiOrderEvent.client_id == export.scope_id)
        if export.scope_type == BiScopeType.PARTNER and export.scope_id:
            query = query.filter(BiOrderEvent.partner_id == export.scope_id)
        headers = [
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
        rows = [
            [
                str(item.tenant_id),
                item.client_id or "",
                item.partner_id or "",
                item.order_id or "",
                item.event_id,
                item.event_type,
                item.occurred_at.isoformat(),
                str(item.amount or 0),
                item.currency or "",
                item.service_id or "",
                item.offer_id or "",
                item.status_after or "",
            ]
            for item in query.order_by(BiOrderEvent.occurred_at.asc()).all()
        ]
        return headers, rows

    if export.kind == BiExportKind.PAYOUTS:
        query = (
            db.query(BiPayoutEvent)
            .filter(BiPayoutEvent.tenant_id == export.tenant_id)
            .filter(BiPayoutEvent.occurred_at >= date_from)
            .filter(BiPayoutEvent.occurred_at <= date_to)
        )
        if export.scope_type == BiScopeType.PARTNER and export.scope_id:
            query = query.filter(BiPayoutEvent.partner_id == export.scope_id)
        headers = [
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
        rows = [
            [
                str(item.tenant_id),
                item.partner_id or "",
                item.settlement_id or "",
                item.payout_batch_id or "",
                item.event_type,
                item.occurred_at.isoformat(),
                str(item.amount_gross or 0),
                str(item.amount_net or 0),
                str(item.amount_commission or 0),
                item.currency or "",
            ]
            for item in query.order_by(BiPayoutEvent.occurred_at.asc()).all()
        ]
        return headers, rows

    if export.kind == BiExportKind.DECLINES:
        query = (
            db.query(BiDeclineEvent)
            .filter(BiDeclineEvent.tenant_id == export.tenant_id)
            .filter(BiDeclineEvent.occurred_at >= date_from)
            .filter(BiDeclineEvent.occurred_at <= date_to)
        )
        if export.scope_type == BiScopeType.CLIENT and export.scope_id:
            query = query.filter(BiDeclineEvent.client_id == export.scope_id)
        if export.scope_type == BiScopeType.PARTNER and export.scope_id:
            query = query.filter(BiDeclineEvent.partner_id == export.scope_id)
        if export.scope_type == BiScopeType.STATION and export.scope_id:
            query = query.filter(BiDeclineEvent.station_id == export.scope_id)
        headers = [
            "tenant_id",
            "client_id",
            "partner_id",
            "operation_id",
            "occurred_at",
            "primary_reason",
            "amount",
            "product_type",
            "station_id",
        ]
        rows = [
            [
                str(item.tenant_id),
                item.client_id or "",
                item.partner_id or "",
                item.operation_id,
                item.occurred_at.isoformat(),
                item.primary_reason or "",
                str(item.amount or 0),
                item.product_type or "",
                item.station_id or "",
            ]
            for item in query.order_by(BiDeclineEvent.occurred_at.asc()).all()
        ]
        return headers, rows

    if export.kind == BiExportKind.DAILY_METRICS:
        query = (
            db.query(BiDailyMetric)
            .filter(BiDailyMetric.tenant_id == export.tenant_id)
            .filter(BiDailyMetric.date >= export.date_from)
            .filter(BiDailyMetric.date <= export.date_to)
        )
        if export.scope_type and export.scope_id:
            query = query.filter(BiDailyMetric.scope_type == export.scope_type)
            query = query.filter(BiDailyMetric.scope_id == export.scope_id)
        headers = [
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
        rows = [
            [
                str(item.tenant_id),
                item.date.isoformat(),
                item.scope_type.value,
                item.scope_id,
                str(item.spend_total or 0),
                str(item.orders_total or 0),
                str(item.orders_completed or 0),
                str(item.refunds_total or 0),
                str(item.payouts_total or 0),
                str(item.declines_total or 0),
                item.top_primary_reason or "",
            ]
            for item in query.order_by(BiDailyMetric.date.asc()).all()
        ]
        return headers, rows

    raise BiExportError("unsupported_export_kind")


def _render_csv(headers: list[str], rows: list[list[str]]) -> bytes:
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def generate_export(db: Session, export_id: str) -> BiExportBatch:
    export = db.query(BiExportBatch).filter(BiExportBatch.id == export_id).one_or_none()
    if not export:
        raise BiExportError("export_not_found")

    if export.status not in {BiExportStatus.CREATED, BiExportStatus.GENERATED}:
        raise BiExportError("invalid_export_state")

    headers, rows = _render_rows(export, db)
    payload = _render_csv(headers, rows)
    checksum = hashlib.sha256(payload).hexdigest()
    object_key = _build_object_key(export)
    storage = S3Storage()

    export.status = BiExportStatus.GENERATED
    export.sha256 = checksum
    export.row_count = len(rows)
    db.commit()
    db.refresh(export)

    try:
        storage.ensure_bucket()
        storage.put_bytes(object_key, payload, content_type="text/csv")
    except Exception as exc:  # noqa: BLE001
        export.status = BiExportStatus.FAILED
        export.error_message = str(exc)
        db.commit()
        db.refresh(export)
        bi_metrics.mark_export_failed()
        raise

    export.status = BiExportStatus.DELIVERED
    export.object_key = object_key
    export.bucket = storage.bucket
    export.sha256 = checksum
    export.row_count = len(rows)
    export.delivered_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(export)
    bi_metrics.mark_export_generated()
    return export


def load_export(db: Session, export_id: str) -> BiExportBatch | None:
    return db.query(BiExportBatch).filter(BiExportBatch.id == export_id).one_or_none()


def confirm_export(db: Session, export: BiExportBatch) -> BiExportBatch:
    export.status = BiExportStatus.CONFIRMED
    export.confirmed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(export)
    return export


__all__ = [
    "BiExportError",
    "BiExportResult",
    "confirm_export",
    "create_export_batch",
    "generate_export",
    "load_export",
]
