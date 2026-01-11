from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Callable

from neft_shared.logging_setup import get_logger
from neft_shared.settings import get_settings
from sqlalchemy.orm import Session

from app.models.bi import (
    BiExport,
    BiExportBatch,
    BiExportFormat,
    BiExportKind,
    BiExportStatus,
    BiScopeType,
)
from app.services.bi.metrics import metrics as bi_metrics
from app.services.s3_storage import S3Storage

from . import daily_metrics_csv, declines_csv, order_events_csv, orders_csv, payouts_csv
from .manifest import build_manifest
from .serializers import render_csv, render_jsonl

logger = get_logger(__name__)
settings = get_settings()


class BiExportError(Exception):
    """Domain error for BI exports."""


@dataclass(frozen=True)
class BiExportResult:
    export: BiExportBatch
    created: bool


@dataclass(frozen=True)
class ExporterConfig:
    headers: list[str]
    fetch_rows: Callable[[BiExportBatch, Session], list[dict[str, object]]]


EXPORTERS: dict[BiExportKind, ExporterConfig] = {
    BiExportKind.ORDERS: ExporterConfig(headers=orders_csv.HEADERS, fetch_rows=orders_csv.fetch_rows),
    BiExportKind.ORDER_EVENTS: ExporterConfig(
        headers=order_events_csv.HEADERS, fetch_rows=order_events_csv.fetch_rows
    ),
    BiExportKind.PAYOUTS: ExporterConfig(headers=payouts_csv.HEADERS, fetch_rows=payouts_csv.fetch_rows),
    BiExportKind.DECLINES: ExporterConfig(headers=declines_csv.HEADERS, fetch_rows=declines_csv.fetch_rows),
    BiExportKind.DAILY_METRICS: ExporterConfig(
        headers=daily_metrics_csv.HEADERS, fetch_rows=daily_metrics_csv.fetch_rows
    ),
}


def _build_object_key(batch: BiExportBatch) -> str:
    scope = batch.scope_type.value if batch.scope_type else "TENANT"
    scope_id = batch.scope_id or f"tenant-{batch.tenant_id}"
    date_from = batch.date_from.isoformat()
    date_to = batch.date_to.isoformat()
    extension = batch.format.value.lower()
    if extension == "jsonl":
        extension = "jsonl"
    elif extension == "parquet":
        extension = "parquet"
    else:
        extension = "csv"
    return (
        f"bi/{batch.tenant_id}/{batch.kind.value.lower()}/{scope}/{scope_id}/"
        f"{date_from}_{date_to}/{batch.id}.{extension}"
    )


def _render_payload(export: BiExportBatch, *, headers: list[str], rows: list[dict[str, object]]) -> bytes:
    if export.format == BiExportFormat.CSV:
        return render_csv(headers, rows)
    if export.format == BiExportFormat.JSONL:
        return render_jsonl(headers, rows)
    raise BiExportError("unsupported_export_format")


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
    created_by: str | None,
) -> BiExportBatch:
    if not settings.BI_CLICKHOUSE_ENABLED:
        raise BiExportError("bi_disabled")
    if kind not in EXPORTERS:
        raise BiExportError("unsupported_export_kind")
    if export_format == BiExportFormat.PARQUET:
        raise BiExportError("unsupported_export_format")

    resolved_scope = scope_type or BiScopeType.TENANT
    active = (
        db.query(BiExportBatch)
        .filter(BiExportBatch.tenant_id == tenant_id)
        .filter(BiExportBatch.kind == kind)
        .filter(BiExportBatch.status.in_({BiExportStatus.CREATED, BiExportStatus.GENERATED, BiExportStatus.DELIVERED}))
        .first()
    )
    if active:
        raise BiExportError("export_in_progress")

    export = BiExportBatch(
        tenant_id=tenant_id,
        kind=kind,
        scope_type=resolved_scope,
        scope_id=scope_id,
        date_from=date_from,
        date_to=date_to,
        format=export_format,
        status=BiExportStatus.CREATED,
        created_by=created_by,
    )
    db.add(export)
    db.commit()
    db.refresh(export)
    return export


def generate_export(db: Session, export_id: str) -> BiExportBatch:
    if not settings.BI_CLICKHOUSE_ENABLED:
        raise BiExportError("bi_disabled")
    export = db.query(BiExportBatch).filter(BiExportBatch.id == export_id).one_or_none()
    if not export:
        raise BiExportError("export_not_found")

    if export.status not in {BiExportStatus.CREATED, BiExportStatus.GENERATED}:
        raise BiExportError("invalid_export_state")

    exporter = EXPORTERS.get(export.kind)
    if not exporter:
        raise BiExportError("unsupported_export_kind")

    started_at = datetime.now(timezone.utc)
    rows = exporter.fetch_rows(export, db)
    payload = _render_payload(export, headers=exporter.headers, rows=rows)
    checksum = hashlib.sha256(payload).hexdigest()
    object_key = _build_object_key(export)
    storage = S3Storage()

    export.status = BiExportStatus.GENERATED
    export.sha256 = checksum
    export.row_count = len(rows)
    db.commit()
    db.refresh(export)

    manifest_key: str | None = None
    try:
        storage.ensure_bucket()
        content_type = "text/csv" if export.format == BiExportFormat.CSV else "application/json"
        storage.put_bytes(object_key, payload, content_type=content_type)

        manifest_payload = build_manifest(export, headers=exporter.headers, sha256=checksum, row_count=len(rows))
        manifest_key = f"{object_key}.manifest.json"
        storage.put_bytes(
            manifest_key,
            json.dumps(manifest_payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            content_type="application/json",
        )
    except Exception as exc:  # noqa: BLE001
        export.status = BiExportStatus.FAILED
        export.error_message = str(exc)
        db.commit()
        db.refresh(export)
        bi_metrics.mark_export_failed(export.kind.value.lower(), export.format.value, export.status.value)
        raise

    export.status = BiExportStatus.DELIVERED
    export.object_key = object_key
    export.manifest_key = manifest_key
    export.bucket = storage.bucket
    export.sha256 = checksum
    export.row_count = len(rows)
    export.delivered_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(export)

    export_record = BiExport(
        tenant_id=export.tenant_id,
        mart_name=export.kind.value.lower(),
        period=f"{export.date_from.isoformat()}:{export.date_to.isoformat()}",
        format=export.format.value,
        file_ref=export.object_key or "",
    )
    db.add(export_record)
    db.commit()

    duration = (datetime.now(timezone.utc) - started_at).total_seconds()
    bi_metrics.mark_export_generated(export.kind.value.lower(), export.format.value, export.status.value, duration)
    logger.info(
        "bi.export_generated",
        extra={
            "export_id": export.id,
            "dataset": export.kind.value,
            "row_count": export.row_count,
            "sha256": export.sha256,
        },
    )
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
