from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.config import settings
from app.db import get_db
from app.schemas.admin.erp_stub import ErpStubExportCreateRequest, ErpStubExportResponse
from app.services.audit_service import _sanitize_token_for_audit, request_context_from_request
from app.services.erp_stub_service import ErpStubServiceError, ack_export, create_export, get_export
from app.security.rbac.guard import require_permission


router = APIRouter(
    prefix="/erp_stub",
    tags=["admin", "erp_stub"],
    dependencies=[Depends(require_permission("admin:billing:*"))],
)


def _require_enabled() -> None:
    if not settings.ERP_STUB_ENABLED:
        raise HTTPException(status_code=404, detail="erp_stub_disabled")


@router.post("/exports", response_model=ErpStubExportResponse, status_code=status.HTTP_201_CREATED)
def create_stub_export(
    payload: ErpStubExportCreateRequest,
    request: Request,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> ErpStubExportResponse:
    _require_enabled()
    if payload.period_from and payload.period_to and payload.period_from > payload.period_to:
        raise HTTPException(status_code=422, detail="invalid_period")
    tenant_id = int(token.get("tenant_id") or 0)
    actor = request_context_from_request(request, token=_sanitize_token_for_audit(token))
    try:
        export = create_export(
            db,
            tenant_id=tenant_id,
            export_type=payload.export_type,
            entity_ids=payload.entity_ids,
            period_from=payload.period_from,
            period_to=payload.period_to,
            export_ref=payload.export_ref,
            actor=actor,
        )
        db.commit()
    except ErpStubServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ErpStubExportResponse.model_validate(export)


@router.get("/exports/{export_id}", response_model=ErpStubExportResponse)
def get_stub_export(export_id: str, db: Session = Depends(get_db)) -> ErpStubExportResponse:
    _require_enabled()
    export = get_export(db, export_id)
    if export is None:
        raise HTTPException(status_code=404, detail="erp_stub_export_not_found")
    return ErpStubExportResponse.model_validate(export)


@router.post("/exports/{export_id}/ack", response_model=ErpStubExportResponse)
def ack_stub_export(
    export_id: str,
    request: Request,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> ErpStubExportResponse:
    _require_enabled()
    actor = request_context_from_request(request, token=_sanitize_token_for_audit(token))
    try:
        export = ack_export(db, export_id=export_id, actor=actor)
        db.commit()
    except ErpStubServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ErpStubExportResponse.model_validate(export)
