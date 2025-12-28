from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.models.documents import ClosingPackage, ClosingPackageStatus
from app.models.audit_log import AuditVisibility
from app.schemas.closing_documents import ClosingPackageGenerateRequest, ClosingPackageGenerateResponse
from app.services.audit_service import AuditService, _sanitize_token_for_audit, request_context_from_request
from app.services.policy import Action, actor_from_token, audit_access_denied, PolicyEngine, ResourceContext
from app.services.closing_documents import ClosingDocumentsService

router = APIRouter(prefix="/closing-packages", tags=["closing-packages"])


@router.post("/generate", response_model=ClosingPackageGenerateResponse)
def generate_closing_package(
    request: Request,
    payload: ClosingPackageGenerateRequest,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> ClosingPackageGenerateResponse:
    if payload.date_from > payload.date_to:
        raise HTTPException(status_code=422, detail="invalid_period")

    service = ClosingDocumentsService(db)
    result = service.generate_package(
        tenant_id=payload.tenant_id,
        client_id=payload.client_id,
        period_from=payload.date_from,
        period_to=payload.date_to,
        force_new_version=payload.force_new_version,
        actor=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
    )

    return ClosingPackageGenerateResponse(
        package_id=str(result.package.id),
        version=result.package.version,
        documents=[
            {
                "type": doc_type.value,
                "id": str(document.id),
            }
            for doc_type, document in result.documents.items()
        ],
    )


@router.post("/{package_id}/finalize")
def finalize_closing_package(
    package_id: str,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> dict:
    service = ClosingDocumentsService(db)
    package = db.query(ClosingPackage).filter(ClosingPackage.id == package_id).one_or_none()
    if package is None:
        raise HTTPException(status_code=404, detail="closing_package_not_found")
    if package.status == ClosingPackageStatus.FINALIZED:
        return {"status": package.status.value}

    actor = actor_from_token(token)
    resource = ResourceContext(
        resource_type="CLOSING_PACKAGE",
        tenant_id=package.tenant_id,
        client_id=package.client_id,
        status=package.status.value,
    )
    decision = PolicyEngine().check(actor=actor, action=Action.CLOSING_PACKAGE_FINALIZE, resource=resource)
    if not decision.allowed:
        if decision.reason == "status_not_acknowledged":
            AuditService(db).audit(
                event_type="DOCUMENT_IMMUTABILITY_VIOLATION",
                entity_type="closing_package",
                entity_id=str(package.id),
                action="UPDATE",
                visibility=AuditVisibility.PUBLIC,
                after={"reason": "closing_package_not_acknowledged", "status": package.status.value},
                request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
            )
            raise HTTPException(status_code=409, detail="closing_package_not_acknowledged")
        audit_access_denied(
            db,
            actor=actor,
            action=Action.CLOSING_PACKAGE_FINALIZE,
            resource=resource,
            decision=decision,
            token=token,
        )
        raise HTTPException(status_code=403, detail=decision.reason or "forbidden")

    try:
        service.finalize_package(
            package,
            actor=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
        )
    except ValueError as exc:
        AuditService(db).audit(
            event_type="DOCUMENT_IMMUTABILITY_VIOLATION",
            entity_type="closing_package",
            entity_id=str(package.id),
            action="UPDATE",
            visibility=AuditVisibility.PUBLIC,
            after={"reason": str(exc), "status": package.status.value},
            request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
        )
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {"status": package.status.value}
