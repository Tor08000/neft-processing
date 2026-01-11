from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.service_identities import ServiceTokenAuditAction, ServiceTokenActorType
from app.services import admin_auth
from app.services.client_auth import verify_client_token
from app.services.partner_auth import verify_partner_token
from app.services.abac.engine import AbacContext, AbacDecision, AbacEngine, AbacPrincipal, AbacResource
from app.services.service_identities import resolve_service_token, log_service_token_audit


@dataclass(frozen=True)
class AbacResourceData:
    type: str
    attributes: dict[str, Any]
    entitlements: dict[str, Any]


def _get_bearer_token(request: Request) -> str:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing_bearer_token")
    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="missing_bearer_token")
    return token


def _parse_scopes(claims: dict) -> set[str]:
    scopes = claims.get("scopes") or claims.get("scope") or []
    if isinstance(scopes, str):
        return {scope for scope in scopes.split() if scope}
    if isinstance(scopes, (list, tuple, set)):
        return {str(scope) for scope in scopes if str(scope)}
    return set()


def _principal_from_claims(claims: dict) -> AbacPrincipal:
    roles = claims.get("roles") or []
    if isinstance(roles, str):
        roles = [roles]
    role = claims.get("role")
    if role and role not in roles:
        roles.append(role)
    roles_set = {str(item) for item in roles if item}

    client_id = claims.get("client_id")
    partner_id = claims.get("partner_id")
    principal_type = "USER"
    if partner_id:
        principal_type = "PARTNER"
    elif client_id:
        principal_type = "CLIENT"

    return AbacPrincipal(
        type=principal_type,
        user_id=claims.get("user_id") or claims.get("sub"),
        client_id=client_id,
        partner_id=partner_id,
        service_name=None,
        roles=roles_set,
        scopes=_parse_scopes(claims),
        region=claims.get("region"),
        raw=claims,
    )


def get_abac_principal(request: Request, db: Session = Depends(get_db)) -> AbacPrincipal:
    token = _get_bearer_token(request)
    if token.startswith("svc_"):
        cached = getattr(request.state, "service_principal", None)
        if cached:
            return AbacPrincipal(
                type="SERVICE",
                user_id=None,
                client_id=None,
                partner_id=None,
                service_name=cached.service_name,
                roles=set(),
                scopes=set(cached.scopes),
                region=None,
                raw={"service_name": cached.service_name, "token_id": cached.token_id},
            )
        context = resolve_service_token(db, token_value=token, request=request)
        return AbacPrincipal(
            type="SERVICE",
            user_id=None,
            client_id=None,
            partner_id=None,
            service_name=context.service_identity.service_name,
            roles=set(),
            scopes=set(context.scopes),
            region=None,
            raw={"service_name": context.service_identity.service_name, "token_id": context.token.id},
        )

    exceptions: list[HTTPException] = []
    for verifier in (admin_auth.verify_admin_token, verify_client_token, verify_partner_token):
        try:
            claims = verifier(token)
            return _principal_from_claims(claims)
        except HTTPException as exc:
            exceptions.append(exc)

    if any(exc.status_code == 403 for exc in exceptions):
        raise HTTPException(status_code=403, detail="forbidden")
    raise HTTPException(status_code=401, detail="invalid_token")


def require_abac(
    action: str,
    resource_loader: Callable[..., AbacResourceData],
):
    def dep(
        request: Request,
        db: Session = Depends(get_db),
        principal: AbacPrincipal = Depends(get_abac_principal),
        resource_data: AbacResourceData = Depends(resource_loader),
    ) -> AbacDecision:
        context = AbacContext(
            ip=request.client.host if request.client else None,
            region=request.headers.get("x-region"),
            timestamp=datetime.now(timezone.utc),
        )
        decision = AbacEngine(db).evaluate(
            principal=principal,
            action=action,
            resource=AbacResource(resource_data.type, resource_data.attributes),
            entitlements=resource_data.entitlements,
            context=context,
        )
        if not decision.allowed:
            if principal.type == "SERVICE":
                log_service_token_audit(
                    db,
                    service_token_id=principal.raw.get("token_id"),
                    action=ServiceTokenAuditAction.DENIED,
                    actor_type=ServiceTokenActorType.SYSTEM,
                    actor_id=None,
                    request=request,
                    meta={"reason": "abac_deny", "action": action, "policy": decision.reason_code},
                )
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "abac_deny",
                    "reason_code": decision.reason_code,
                    "matched_policies": decision.matched_policies,
                    "explain": decision.explain,
                },
            )
        return decision

    return dep


__all__ = ["AbacResourceData", "get_abac_principal", "require_abac"]
