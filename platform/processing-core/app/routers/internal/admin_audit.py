from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.api.dependencies.admin_capability import require_admin_capability
from app.db import get_db
from app.models.audit_log import ActorType, AuditVisibility
from app.schemas.internal_admin_audit import AdminUserAuditIngestRequest, AdminUserAuditIngestResponse
from app.services.audit_service import AuditService, request_context_from_request


router = APIRouter(prefix="/api/internal/admin/audit", tags=["internal-admin-audit"])


@router.post("/users", response_model=AdminUserAuditIngestResponse, include_in_schema=False)
def ingest_admin_user_audit(
    payload: AdminUserAuditIngestRequest,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
    _capability: dict = Depends(require_admin_capability("access", "manage")),
) -> AdminUserAuditIngestResponse:
    request_ctx = request_context_from_request(request, token=token, actor_type=ActorType.USER)
    audit = AuditService(db).audit(
        event_type="ADMIN_USER_CREATED" if payload.action == "create" else "ADMIN_USER_UPDATED",
        entity_type="admin_user",
        entity_id=payload.user_id,
        action=payload.action,
        visibility=AuditVisibility.INTERNAL,
        before=payload.before,
        after=payload.after,
        external_refs={
            "correlation_id": payload.correlation_id,
            "source_service": "auth-host",
            "source_surface": "admin_users",
        },
        reason=payload.reason,
        request_ctx=request_ctx,
    )
    db.commit()
    return AdminUserAuditIngestResponse(status="ok", audit_id=str(audit.id))


__all__ = ["router"]
