from __future__ import annotations

import hashlib
import json
from datetime import datetime
from decimal import Decimal
from typing import Iterable

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.config import settings
from app.models.audit_log import AuditVisibility
from app.models.billing_flow import BillingInvoice, BillingPayment
from app.models.erp_stub import ErpStubExport, ErpStubExportItem, ErpStubExportStatus, ErpStubExportType
from app.models.reconciliation import ReconciliationRun
from app.models.settlement_v1 import SettlementPeriod
from app.services.audit_service import AuditService, RequestContext
from app.services.job_locks import advisory_lock, make_lock_token, make_stable_key


class ErpStubServiceError(Exception):
    """Domain error for ERP stub provider."""


def _canonical_json(data: object) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _hash_payload(data: object) -> str:
    return hashlib.sha256(_canonical_json(data).encode("utf-8")).hexdigest()


def _serialize_value(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def _serialize_model(model: object) -> dict[str, object]:
    mapper = inspect(model)
    payload: dict[str, object] = {}
    for column in mapper.mapper.column_attrs:
        key = column.key
        payload[key] = _serialize_value(getattr(model, key))
    return payload


def _require_enabled() -> None:
    if not settings.ERP_STUB_ENABLED:
        raise ErpStubServiceError("erp_stub_disabled")


def _resolve_items(
    db: Session,
    *,
    export_type: ErpStubExportType,
    entity_ids: list[str] | None,
    period_from: datetime | None,
    period_to: datetime | None,
) -> list[tuple[str, str, dict[str, object]]]:
    if export_type == ErpStubExportType.INVOICES:
        query = db.query(BillingInvoice)
        if entity_ids:
            query = query.filter(BillingInvoice.id.in_(entity_ids))
        if period_from:
            query = query.filter(BillingInvoice.issued_at >= period_from)
        if period_to:
            query = query.filter(BillingInvoice.issued_at <= period_to)
        return [("invoice", str(item.id), _serialize_model(item)) for item in query.all()]

    if export_type == ErpStubExportType.PAYMENTS:
        query = db.query(BillingPayment)
        if entity_ids:
            query = query.filter(BillingPayment.id.in_(entity_ids))
        if period_from:
            query = query.filter(BillingPayment.captured_at >= period_from)
        if period_to:
            query = query.filter(BillingPayment.captured_at <= period_to)
        return [("payment", str(item.id), _serialize_model(item)) for item in query.all()]

    if export_type == ErpStubExportType.SETTLEMENT:
        query = db.query(SettlementPeriod)
        if entity_ids:
            query = query.filter(SettlementPeriod.id.in_(entity_ids))
        if period_from:
            query = query.filter(SettlementPeriod.period_start >= period_from)
        if period_to:
            query = query.filter(SettlementPeriod.period_end <= period_to)
        return [("settlement_period", str(item.id), _serialize_model(item)) for item in query.all()]

    if export_type == ErpStubExportType.RECONCILIATION:
        query = db.query(ReconciliationRun)
        if entity_ids:
            query = query.filter(ReconciliationRun.id.in_(entity_ids))
        if period_from:
            query = query.filter(ReconciliationRun.period_start >= period_from)
        if period_to:
            query = query.filter(ReconciliationRun.period_end <= period_to)
        return [("reconciliation_run", str(item.id), _serialize_model(item)) for item in query.all()]

    raise ErpStubServiceError("unsupported_export_type")


def create_export(
    db: Session,
    *,
    tenant_id: int,
    export_type: ErpStubExportType,
    entity_ids: list[str] | None,
    period_from: datetime | None,
    period_to: datetime | None,
    export_ref: str | None,
    actor: RequestContext | None,
) -> ErpStubExport:
    _require_enabled()
    scope_key = make_stable_key(
        "erp_stub_export",
        {
            "export_type": export_type.value,
            "entity_ids": entity_ids or [],
            "period_from": period_from.isoformat() if period_from else None,
            "period_to": period_to.isoformat() if period_to else None,
        },
        export_ref,
    )
    lock_token = make_lock_token("erp_stub_export", scope_key)
    with advisory_lock(db, lock_token) as acquired:
        if not acquired:
            raise ErpStubServiceError("erp_stub_export_locked")

        existing = db.query(ErpStubExport).filter(ErpStubExport.export_ref == scope_key).one_or_none()
        if existing:
            return existing

        items_payload = _resolve_items(
            db,
            export_type=export_type,
            entity_ids=entity_ids,
            period_from=period_from,
            period_to=period_to,
        )
        payload_hash = _hash_payload(
            [
                {
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "snapshot": snapshot,
                }
                for entity_type, entity_id, snapshot in items_payload
            ]
        )

        export = ErpStubExport(
            tenant_id=tenant_id,
            export_ref=scope_key,
            export_type=export_type,
            payload_hash=payload_hash,
            status=ErpStubExportStatus.ACKED if settings.ERP_STUB_AUTO_ACK else ErpStubExportStatus.SENT,
        )
        db.add(export)
        db.flush()

        for entity_type, entity_id, snapshot in items_payload:
            db.add(
                ErpStubExportItem(
                    export_id=export.id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    snapshot_json=snapshot,
                )
            )

        AuditService(db).audit(
            event_type="ERP_STUB_EXPORT_CREATED",
            entity_type="erp_stub_export",
            entity_id=str(export.id),
            action="created",
            visibility=AuditVisibility.INTERNAL,
            after={
                "export_ref": export.export_ref,
                "export_type": export.export_type.value,
                "payload_hash": export.payload_hash,
                "items": len(items_payload),
                "status": export.status.value,
            },
            request_ctx=actor,
        )
        if export.status == ErpStubExportStatus.ACKED:
            AuditService(db).audit(
                event_type="ERP_STUB_EXPORT_ACKED",
                entity_type="erp_stub_export",
                entity_id=str(export.id),
                action="acked",
                visibility=AuditVisibility.INTERNAL,
                after={"export_ref": export.export_ref, "export_type": export.export_type.value},
                request_ctx=actor,
            )

        return export


def get_export(db: Session, export_id: str) -> ErpStubExport | None:
    _require_enabled()
    return db.query(ErpStubExport).filter(ErpStubExport.id == export_id).one_or_none()


def ack_export(db: Session, *, export_id: str, actor: RequestContext | None) -> ErpStubExport:
    _require_enabled()
    export = db.query(ErpStubExport).filter(ErpStubExport.id == export_id).one_or_none()
    if export is None:
        raise ErpStubServiceError("erp_stub_export_not_found")
    if export.status == ErpStubExportStatus.ACKED:
        return export

    export.status = ErpStubExportStatus.ACKED
    AuditService(db).audit(
        event_type="ERP_STUB_EXPORT_ACKED",
        entity_type="erp_stub_export",
        entity_id=str(export.id),
        action="acked",
        visibility=AuditVisibility.INTERNAL,
        after={"export_ref": export.export_ref, "export_type": export.export_type.value},
        request_ctx=actor,
    )
    return export


__all__ = [
    "ErpStubServiceError",
    "ack_export",
    "create_export",
    "get_export",
]
