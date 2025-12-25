from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.schemas.closing_documents import ClosingPackageGenerateRequest, ClosingPackageGenerateResponse
from app.services.audit_service import _sanitize_token_for_audit, request_context_from_request
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
