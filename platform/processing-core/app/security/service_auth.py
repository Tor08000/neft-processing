from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.service_identities import ServiceTokenAuditAction, ServiceTokenActorType
from app.services.service_identities import ServiceTokenContext, resolve_service_token, log_service_token_audit


@dataclass(frozen=True)
class ServicePrincipal:
    service_name: str
    scopes: set[str]
    token_id: str
    identity_id: str


def _get_bearer_token(request: Request) -> str:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing_bearer_token")
    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="missing_bearer_token")
    return token


def _ensure_service_token(token_value: str) -> None:
    if not token_value.startswith("svc_"):
        raise HTTPException(status_code=401, detail="invalid_service_token")


def verify_service_token(
    request: Request,
    db: Session = Depends(get_db),
) -> ServicePrincipal:
    token_value = _get_bearer_token(request)
    _ensure_service_token(token_value)
    context: ServiceTokenContext = resolve_service_token(db, token_value=token_value, request=request)
    principal = ServicePrincipal(
        service_name=context.service_identity.service_name,
        scopes=context.scopes,
        token_id=context.token.id,
        identity_id=context.service_identity.id,
    )
    request.state.service_principal = principal
    return principal


def require_service_scope(scope: str):
    def dep(
        request: Request,
        principal: ServicePrincipal = Depends(verify_service_token),
        db: Session = Depends(get_db),
    ) -> ServicePrincipal:
        if scope not in principal.scopes:
            log_service_token_audit(
                db,
                service_token_id=principal.token_id,
                action=ServiceTokenAuditAction.DENIED,
                actor_type=ServiceTokenActorType.SYSTEM,
                actor_id=None,
                request=request,
                meta={"reason": "missing_scope", "scope": scope},
            )
            raise HTTPException(status_code=403, detail="missing_scope")
        return principal

    return dep


def require_scope(scope: str):
    def dep(request: Request, db: Session = Depends(get_db)) -> ServicePrincipal | None:
        token_value = _get_bearer_token(request)
        if not token_value.startswith("svc_"):
            return None
        principal = verify_service_token(request=request, db=db)
        if scope not in principal.scopes:
            log_service_token_audit(
                db,
                service_token_id=principal.token_id,
                action=ServiceTokenAuditAction.DENIED,
                actor_type=ServiceTokenActorType.SYSTEM,
                actor_id=None,
                request=request,
                meta={"reason": "missing_scope", "scope": scope},
            )
            raise HTTPException(status_code=403, detail="missing_scope")
        return principal

    return dep


__all__ = ["ServicePrincipal", "require_scope", "require_service_scope", "verify_service_token"]
