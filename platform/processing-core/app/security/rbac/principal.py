from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from fastapi import HTTPException, Request

from app.services import admin_auth, client_auth, partner_auth
from app.services.jwt_support import detect_token_kind, get_unverified_claims

from .roles import canonical_role_for_subject_type, canonicalize_roles


@dataclass(frozen=True)
class Principal:
    user_id: UUID | None
    roles: set[str]
    scopes: set[str]
    client_id: UUID | str | None
    partner_id: UUID | str | None
    is_admin: bool
    raw_claims: dict


def principal_context(principal: Principal) -> dict[str, Any]:
    raw_claims = principal.raw_claims if isinstance(principal.raw_claims, dict) else {}
    actor_type = (
        "admin"
        if principal.is_admin
        else "client"
        if principal.client_id or raw_claims.get("client_id")
        else "partner"
        if principal.partner_id or raw_claims.get("partner_id")
        else "user"
    )
    actor_id = principal.user_id or principal.client_id or principal.partner_id or raw_claims.get("sub")
    org_id = raw_claims.get("org_id") or principal.client_id or principal.partner_id
    partner_id = principal.partner_id or raw_claims.get("partner_id")
    return {
        "actor_type": actor_type,
        "actor_id": str(actor_id) if actor_id is not None else None,
        "org_id": str(org_id) if org_id is not None else None,
        "partner_id": str(partner_id) if partner_id is not None else None,
        "roles": sorted(principal.roles),
        "scopes": sorted(principal.scopes),
    }


def _get_bearer_token(request: Request) -> str:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return token


def _parse_uuid(value: Any) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _parse_context_id(value: Any) -> UUID | str | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    text = str(value).strip()
    if not text:
        return None
    parsed_uuid = _parse_uuid(text)
    return parsed_uuid or text


def _collect_raw_roles(claims: dict) -> list[str]:
    raw_roles: list[str] = []
    roles = claims.get("roles") or []
    if isinstance(roles, str):
        roles = [roles]
    raw_roles.extend([str(role) for role in roles])
    role = claims.get("role")
    if role:
        raw_roles.append(str(role))
    return raw_roles


def _parse_scopes(claims: dict) -> set[str]:
    scopes = claims.get("scopes") or claims.get("scope") or []
    if isinstance(scopes, str):
        return {scope for scope in scopes.split() if scope}
    if isinstance(scopes, (list, tuple, set)):
        return {str(scope) for scope in scopes if str(scope)}
    return set()


def _principal_from_claims(claims: dict) -> Principal:
    raw_roles = _collect_raw_roles(claims)
    roles = canonicalize_roles(raw_roles)
    subject_role = canonical_role_for_subject_type(claims.get("subject_type"))
    if subject_role:
        roles.add(subject_role)

    user_id = _parse_uuid(claims.get("user_id") or claims.get("sub"))
    client_id = _parse_context_id(claims.get("client_id"))
    partner_id = _parse_context_id(claims.get("partner_id"))
    scopes = _parse_scopes(claims)

    return Principal(
        user_id=user_id,
        roles=roles,
        scopes=scopes,
        client_id=client_id,
        partner_id=partner_id,
        is_admin="admin" in roles,
        raw_claims=claims,
    )


def _resolve_partner_context(principal: Principal) -> Principal:
    raw_claims = principal.raw_claims if isinstance(principal.raw_claims, dict) else {}
    subject_type = str(raw_claims.get("subject_type") or "").strip().lower()
    raw_partner_id = raw_claims.get("partner_id")
    if subject_type != "partner_user":
        return principal
    if isinstance(principal.partner_id, UUID):
        return principal
    if raw_partner_id and _parse_uuid(raw_partner_id):
        return principal

    try:
        from app.db import get_sessionmaker
        from app.services.partner_context import resolve_partner_id_from_claims
    except Exception:
        return principal

    db = get_sessionmaker()()
    try:
        canonical_partner_id = resolve_partner_id_from_claims(db, claims=raw_claims)
    except Exception:
        canonical_partner_id = None
    finally:
        db.close()

    resolved_partner_id = _parse_context_id(canonical_partner_id)
    if resolved_partner_id is None:
        return principal

    resolved_claims = dict(raw_claims)
    resolved_claims["partner_id"] = str(resolved_partner_id)
    return Principal(
        user_id=principal.user_id,
        roles=principal.roles,
        scopes=principal.scopes,
        client_id=principal.client_id,
        partner_id=resolved_partner_id,
        is_admin=principal.is_admin,
        raw_claims=resolved_claims,
    )


def get_principal(request: Request) -> Principal:
    token = _get_bearer_token(request)
    last_exc: HTTPException | None = None
    for verifier in (
        admin_auth.verify_admin_token,
        partner_auth.verify_partner_token,
        client_auth.verify_client_token,
    ):
        try:
            verified_claims = verifier(token)
        except HTTPException as exc:
            last_exc = exc
            continue
        return _resolve_partner_context(_principal_from_claims(verified_claims))
    raise HTTPException(status_code=401, detail="Invalid bearer token") from last_exc


def get_portal_principal(request: Request) -> Principal:
    token = _get_bearer_token(request)
    claims = get_unverified_claims(token)
    token_kind = detect_token_kind(claims)
    verifier_map = {
        "admin": admin_auth.verify_admin_token,
        "client": client_auth.verify_client_token,
        "partner": partner_auth.verify_partner_token,
    }
    verifier = verifier_map.get(token_kind, client_auth.verify_client_token)
    verified_claims = verifier(token)
    return _resolve_partner_context(_principal_from_claims(verified_claims))


__all__ = ["Principal", "get_principal", "get_portal_principal", "principal_context"]
