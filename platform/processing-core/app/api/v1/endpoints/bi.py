from __future__ import annotations

import os
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.dependencies.bi import bi_user_dep
from app.db import get_db
from app.models.bi import (
    BiDeclineEvent,
    BiExportStatus,
    BiOrderEvent,
    BiPayoutEvent,
    BiScopeType,
)
from app.schemas.bi import (
    BiDailyMetricOut,
    BiDeclineEventOut,
    BiExportCreateRequest,
    BiExportOut,
    BiOrderEventOut,
    BiPayoutEventOut,
    BiTopReasonOut,
)
from app.services.bi import exports as bi_exports
from app.services.bi import service as bi_service
from app.services.s3_storage import S3Storage
from app.tasks.bi_analytics import generate_export_task


router = APIRouter(prefix="/api/v1/bi", tags=["bi"])


def _enforce_scope(token: dict, *, client_id: str | None, partner_id: str | None) -> None:
    token_client = token.get("client_id")
    if token_client and client_id and token_client != client_id:
        raise HTTPException(status_code=403, detail="forbidden_client_scope")

    token_partner = token.get("partner_id")
    if token_partner and partner_id and token_partner != partner_id:
        raise HTTPException(status_code=403, detail="forbidden_partner_scope")


@router.get("/metrics/daily", response_model=list[BiDailyMetricOut])
def list_daily_metrics(
    scope_type: BiScopeType = Query(...),
    scope_id: str = Query(...),
    date_from: date = Query(..., alias="from"),
    date_to: date = Query(..., alias="to"),
    token: dict = Depends(bi_user_dep),
    db: Session = Depends(get_db),
) -> list[BiDailyMetricOut]:
    tenant_id = int(token.get("tenant_id"))
    if scope_type == BiScopeType.CLIENT:
        _enforce_scope(token, client_id=scope_id, partner_id=None)
    if scope_type == BiScopeType.PARTNER:
        _enforce_scope(token, client_id=None, partner_id=scope_id)
    metrics = bi_service.list_daily_metrics(
        db,
        tenant_id=tenant_id,
        scope_type=scope_type,
        scope_id=scope_id,
        date_from=date_from,
        date_to=date_to,
    )
    return [BiDailyMetricOut.model_validate(item) for item in metrics]


@router.get("/orders", response_model=list[BiOrderEventOut])
def list_orders(
    date_from: datetime = Query(..., alias="from"),
    date_to: datetime = Query(..., alias="to"),
    client_id: str | None = Query(default=None),
    partner_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    token: dict = Depends(bi_user_dep),
    db: Session = Depends(get_db),
) -> list[BiOrderEventOut]:
    tenant_id = int(token.get("tenant_id"))
    _enforce_scope(token, client_id=client_id, partner_id=partner_id)
    query = (
        db.query(BiOrderEvent)
        .filter(BiOrderEvent.tenant_id == tenant_id)
        .filter(BiOrderEvent.occurred_at >= date_from)
        .filter(BiOrderEvent.occurred_at <= date_to)
    )
    if client_id:
        query = query.filter(BiOrderEvent.client_id == client_id)
    if partner_id:
        query = query.filter(BiOrderEvent.partner_id == partner_id)
    if status:
        query = query.filter(BiOrderEvent.status_after == status)
    items = query.order_by(BiOrderEvent.occurred_at.desc()).limit(5000).all()
    return [BiOrderEventOut.model_validate(item) for item in items]


@router.get("/payouts", response_model=list[BiPayoutEventOut])
def list_payouts(
    date_from: datetime = Query(..., alias="from"),
    date_to: datetime = Query(..., alias="to"),
    partner_id: str | None = Query(default=None),
    token: dict = Depends(bi_user_dep),
    db: Session = Depends(get_db),
) -> list[BiPayoutEventOut]:
    tenant_id = int(token.get("tenant_id"))
    _enforce_scope(token, client_id=None, partner_id=partner_id)
    query = (
        db.query(BiPayoutEvent)
        .filter(BiPayoutEvent.tenant_id == tenant_id)
        .filter(BiPayoutEvent.occurred_at >= date_from)
        .filter(BiPayoutEvent.occurred_at <= date_to)
    )
    if partner_id:
        query = query.filter(BiPayoutEvent.partner_id == partner_id)
    items = query.order_by(BiPayoutEvent.occurred_at.desc()).limit(5000).all()
    return [BiPayoutEventOut.model_validate(item) for item in items]


@router.get("/declines", response_model=list[BiDeclineEventOut])
def list_declines(
    date_from: datetime = Query(..., alias="from"),
    date_to: datetime = Query(..., alias="to"),
    reason: str | None = Query(default=None),
    station_id: str | None = Query(default=None),
    client_id: str | None = Query(default=None),
    partner_id: str | None = Query(default=None),
    token: dict = Depends(bi_user_dep),
    db: Session = Depends(get_db),
) -> list[BiDeclineEventOut]:
    tenant_id = int(token.get("tenant_id"))
    _enforce_scope(token, client_id=client_id, partner_id=partner_id)
    query = (
        db.query(BiDeclineEvent)
        .filter(BiDeclineEvent.tenant_id == tenant_id)
        .filter(BiDeclineEvent.occurred_at >= date_from)
        .filter(BiDeclineEvent.occurred_at <= date_to)
    )
    if reason:
        query = query.filter(BiDeclineEvent.primary_reason == reason)
    if station_id:
        query = query.filter(BiDeclineEvent.station_id == station_id)
    if client_id:
        query = query.filter(BiDeclineEvent.client_id == client_id)
    if partner_id:
        query = query.filter(BiDeclineEvent.partner_id == partner_id)
    items = query.order_by(BiDeclineEvent.occurred_at.desc()).limit(5000).all()
    return [BiDeclineEventOut.model_validate(item) for item in items]


@router.get("/top-reasons", response_model=list[BiTopReasonOut])
def top_reasons(
    date_from: datetime = Query(..., alias="from"),
    date_to: datetime = Query(..., alias="to"),
    scope_type: BiScopeType | None = Query(default=None),
    scope_id: str | None = Query(default=None),
    token: dict = Depends(bi_user_dep),
    db: Session = Depends(get_db),
) -> list[BiTopReasonOut]:
    tenant_id = int(token.get("tenant_id"))
    query = (
        db.query(
            BiDeclineEvent.primary_reason,
            func.count().label("total"),
        )
        .filter(BiDeclineEvent.tenant_id == tenant_id)
        .filter(BiDeclineEvent.occurred_at >= date_from)
        .filter(BiDeclineEvent.occurred_at <= date_to)
    )
    if scope_type == BiScopeType.CLIENT and scope_id:
        _enforce_scope(token, client_id=scope_id, partner_id=None)
        query = query.filter(BiDeclineEvent.client_id == scope_id)
    if scope_type == BiScopeType.PARTNER and scope_id:
        _enforce_scope(token, client_id=None, partner_id=scope_id)
        query = query.filter(BiDeclineEvent.partner_id == scope_id)
    if scope_type == BiScopeType.STATION and scope_id:
        query = query.filter(BiDeclineEvent.station_id == scope_id)
    rows = (
        query.filter(BiDeclineEvent.primary_reason.isnot(None))
        .group_by(BiDeclineEvent.primary_reason)
        .order_by(func.count().desc())
        .limit(20)
        .all()
    )
    return [BiTopReasonOut(primary_reason=row.primary_reason, count=row.total) for row in rows]


@router.post("/exports", response_model=BiExportOut)
def create_export(
    payload: BiExportCreateRequest,
    token: dict = Depends(bi_user_dep),
    db: Session = Depends(get_db),
) -> BiExportOut:
    tenant_id = int(token.get("tenant_id"))
    if payload.scope_type == BiScopeType.CLIENT and payload.scope_id:
        _enforce_scope(token, client_id=payload.scope_id, partner_id=None)
    if payload.scope_type == BiScopeType.PARTNER and payload.scope_id:
        _enforce_scope(token, client_id=None, partner_id=payload.scope_id)

    export = bi_exports.create_export_batch(
        db,
        tenant_id=tenant_id,
        kind=payload.kind,
        scope_type=payload.scope_type,
        scope_id=payload.scope_id,
        date_from=payload.date_from,
        date_to=payload.date_to,
        export_format=payload.format,
    )

    if os.getenv("DISABLE_CELERY", "0") == "1":
        export = bi_exports.generate_export(db, export.id)
    else:
        generate_export_task.delay(export.id)
    return BiExportOut.model_validate(export)


@router.get("/exports/{export_id}", response_model=BiExportOut)
def get_export(
    export_id: str,
    token: dict = Depends(bi_user_dep),
    db: Session = Depends(get_db),
) -> BiExportOut:
    export = bi_exports.load_export(db, export_id)
    if not export:
        raise HTTPException(status_code=404, detail="export_not_found")
    if export.tenant_id != int(token.get("tenant_id")):
        raise HTTPException(status_code=403, detail="forbidden")
    return BiExportOut.model_validate(export)


@router.get("/exports/{export_id}/download")
def download_export(
    export_id: str,
    token: dict = Depends(bi_user_dep),
    db: Session = Depends(get_db),
) -> dict:
    export = bi_exports.load_export(db, export_id)
    if not export:
        raise HTTPException(status_code=404, detail="export_not_found")
    if export.tenant_id != int(token.get("tenant_id")):
        raise HTTPException(status_code=403, detail="forbidden")
    if not export.object_key or not export.bucket:
        raise HTTPException(status_code=404, detail="export_not_ready")
    storage = S3Storage(bucket=export.bucket)
    url = storage.presign(export.object_key)
    if url is None:
        raise HTTPException(status_code=500, detail="presign_failed")
    return {"url": url, "sha256": export.sha256, "status": export.status.value}


@router.post("/exports/{export_id}/confirm", response_model=BiExportOut)
def confirm_export(
    export_id: str,
    token: dict = Depends(bi_user_dep),
    db: Session = Depends(get_db),
) -> BiExportOut:
    export = bi_exports.load_export(db, export_id)
    if not export:
        raise HTTPException(status_code=404, detail="export_not_found")
    if export.tenant_id != int(token.get("tenant_id")):
        raise HTTPException(status_code=403, detail="forbidden")
    if export.status not in {BiExportStatus.DELIVERED, BiExportStatus.GENERATED}:
        raise HTTPException(status_code=409, detail="invalid_export_state")
    export = bi_exports.confirm_export(db, export)
    return BiExportOut.model_validate(export)
