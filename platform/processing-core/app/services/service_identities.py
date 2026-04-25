from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.models.service_identities import (
    ServiceIdentity,
    ServiceIdentityStatus,
    ServiceToken,
    ServiceTokenActorType,
    ServiceTokenAudit,
    ServiceTokenAuditAction,
    ServiceTokenStatus,
)


ALLOWED_SERVICE_SCOPES = {
    "documents:read",
    "documents:write",
    "edo:send",
    "edo:status",
    "edo:receive",
    "billing:run",
    "bi:sync",
    "integrations:export",
    "integrations:import",
    "notifications:dispatch",
    "rules:evaluate",
    "marketplace:settlement",
}

TOKEN_VERSION = "v1"
TOKEN_PREFIX_LEN = 16


@dataclass(frozen=True)
class ServiceTokenContext:
    service_identity: ServiceIdentity
    token: ServiceToken
    scopes: set[str]


def _coerce_utc_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def normalize_scopes(scopes: Iterable[str]) -> list[str]:
    normalized = sorted({scope.strip() for scope in scopes if scope and scope.strip()})
    invalid = [scope for scope in normalized if scope not in ALLOWED_SERVICE_SCOPES]
    if invalid:
        raise HTTPException(status_code=400, detail={"error": "invalid_scopes", "scopes": invalid})
    return normalized


def build_token_prefix(env: str) -> str:
    env_value = "test" if env == "test" else "live"
    return f"svc_{env_value}_{TOKEN_VERSION}_"


def generate_service_token(env: str) -> tuple[str, str, str]:
    prefix = build_token_prefix(env)
    random_suffix = secrets.token_urlsafe(32)
    token = f"{prefix}{random_suffix}"
    token_prefix = token[:TOKEN_PREFIX_LEN]
    token_hash = hash_service_token(token)
    return token, token_prefix, token_hash


def hash_service_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def log_service_token_audit(
    db: Session,
    *,
    service_token_id: str | None,
    action: ServiceTokenAuditAction,
    actor_type: ServiceTokenActorType,
    actor_id: str | None,
    request: Request | None,
    meta: dict | None = None,
) -> None:
    ip = request.client.host if request and request.client else None
    user_agent = request.headers.get("user-agent") if request else None
    audit = ServiceTokenAudit(
        service_token_id=service_token_id,
        action=action,
        actor_type=actor_type,
        actor_id=actor_id,
        ip=ip,
        user_agent=user_agent,
        meta=meta,
    )
    db.add(audit)
    db.flush()


def issue_service_token(
    db: Session,
    *,
    service_identity: ServiceIdentity,
    scopes: Iterable[str],
    expires_at: datetime,
    actor_id: str | None,
    request: Request | None,
    env: str = "live",
) -> tuple[ServiceToken, str]:
    if service_identity.status != ServiceIdentityStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="service_identity_disabled")
    normalized_scopes = normalize_scopes(scopes)
    token, prefix, token_hash = generate_service_token(env)
    record = ServiceToken(
        service_identity_id=service_identity.id,
        token_hash=token_hash,
        prefix=prefix,
        scopes=normalized_scopes,
        expires_at=expires_at,
        status=ServiceTokenStatus.ACTIVE,
    )
    db.add(record)
    db.flush()
    log_service_token_audit(
        db,
        service_token_id=record.id,
        action=ServiceTokenAuditAction.ISSUED,
        actor_type=ServiceTokenActorType.ADMIN,
        actor_id=actor_id,
        request=request,
        meta={"scopes": normalized_scopes, "expires_at": expires_at.isoformat()},
    )
    return record, token


def rotate_service_token(
    db: Session,
    *,
    token: ServiceToken,
    actor_id: str | None,
    request: Request | None,
    grace_hours: int | None = None,
    env: str = "live",
    expires_at: datetime | None = None,
) -> tuple[ServiceToken, str]:
    if token.status != ServiceTokenStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="service_token_inactive")
    new_token, prefix, token_hash = generate_service_token(env)
    record = ServiceToken(
        service_identity_id=token.service_identity_id,
        token_hash=token_hash,
        prefix=prefix,
        scopes=token.scopes,
        expires_at=expires_at or token.expires_at,
        rotated_from_id=token.id,
        status=ServiceTokenStatus.ACTIVE,
    )
    db.add(record)

    grace_until = None
    if grace_hours is not None:
        grace_until = datetime.now(timezone.utc) + timedelta(hours=grace_hours)
        token.rotation_grace_until = grace_until
    db.flush()

    log_service_token_audit(
        db,
        service_token_id=token.id,
        action=ServiceTokenAuditAction.ROTATED,
        actor_type=ServiceTokenActorType.ADMIN,
        actor_id=actor_id,
        request=request,
        meta={"grace_until": grace_until.isoformat() if grace_until else None},
    )
    log_service_token_audit(
        db,
        service_token_id=record.id,
        action=ServiceTokenAuditAction.ISSUED,
        actor_type=ServiceTokenActorType.ADMIN,
        actor_id=actor_id,
        request=request,
        meta={"rotated_from": token.id},
    )
    return record, new_token


def revoke_service_token(
    db: Session,
    *,
    token: ServiceToken,
    actor_id: str | None,
    request: Request | None,
    reason: str | None = None,
) -> None:
    token.status = ServiceTokenStatus.REVOKED
    token.rotation_grace_until = None
    log_service_token_audit(
        db,
        service_token_id=token.id,
        action=ServiceTokenAuditAction.REVOKED,
        actor_type=ServiceTokenActorType.ADMIN,
        actor_id=actor_id,
        request=request,
        meta={"reason": reason},
    )


def _apply_expiry(token: ServiceToken, now: datetime) -> bool:
    expires_at = _coerce_utc_datetime(token.expires_at)
    if expires_at and now >= expires_at:
        token.status = ServiceTokenStatus.EXPIRED
        return True
    return False


def _apply_rotation_grace(token: ServiceToken, now: datetime) -> bool:
    rotation_grace_until = _coerce_utc_datetime(token.rotation_grace_until)
    if rotation_grace_until and now > rotation_grace_until:
        token.status = ServiceTokenStatus.EXPIRED
        return True
    return False


def resolve_service_token(
    db: Session,
    *,
    token_value: str,
    request: Request | None,
) -> ServiceTokenContext:
    prefix = token_value[:TOKEN_PREFIX_LEN]
    candidates = (
        db.query(ServiceToken)
        .filter(ServiceToken.prefix == prefix)
        .filter(ServiceToken.status == ServiceTokenStatus.ACTIVE)
        .all()
    )
    if not candidates:
        log_service_token_audit(
            db,
            service_token_id=None,
            action=ServiceTokenAuditAction.DENIED,
            actor_type=ServiceTokenActorType.SYSTEM,
            actor_id=None,
            request=request,
            meta={"reason": "unknown_prefix", "prefix": prefix},
        )
        raise HTTPException(status_code=401, detail="invalid_service_token")

    token_hash = hash_service_token(token_value)
    now = datetime.now(timezone.utc)

    for candidate in candidates:
        if candidate.token_hash != token_hash:
            continue
        if _apply_expiry(candidate, now) or _apply_rotation_grace(candidate, now):
            log_service_token_audit(
                db,
                service_token_id=candidate.id,
                action=ServiceTokenAuditAction.DENIED,
                actor_type=ServiceTokenActorType.SYSTEM,
                actor_id=None,
                request=request,
                meta={"reason": "expired"},
            )
            raise HTTPException(status_code=401, detail="service_token_expired")
        if candidate.status != ServiceTokenStatus.ACTIVE:
            log_service_token_audit(
                db,
                service_token_id=candidate.id,
                action=ServiceTokenAuditAction.DENIED,
                actor_type=ServiceTokenActorType.SYSTEM,
                actor_id=None,
                request=request,
                meta={"reason": "inactive"},
            )
            raise HTTPException(status_code=401, detail="service_token_inactive")

        identity = db.query(ServiceIdentity).filter(ServiceIdentity.id == candidate.service_identity_id).one_or_none()
        if not identity or identity.status != ServiceIdentityStatus.ACTIVE:
            log_service_token_audit(
                db,
                service_token_id=candidate.id,
                action=ServiceTokenAuditAction.DENIED,
                actor_type=ServiceTokenActorType.SYSTEM,
                actor_id=None,
                request=request,
                meta={"reason": "identity_inactive"},
            )
            raise HTTPException(status_code=403, detail="service_identity_inactive")

        candidate.last_used_at = now
        log_service_token_audit(
            db,
            service_token_id=candidate.id,
            action=ServiceTokenAuditAction.USED,
            actor_type=ServiceTokenActorType.SYSTEM,
            actor_id=None,
            request=request,
            meta={"service_name": identity.service_name},
        )
        return ServiceTokenContext(service_identity=identity, token=candidate, scopes=set(candidate.scopes))

    log_service_token_audit(
        db,
        service_token_id=None,
        action=ServiceTokenAuditAction.DENIED,
        actor_type=ServiceTokenActorType.SYSTEM,
        actor_id=None,
        request=request,
        meta={"reason": "hash_mismatch", "prefix": prefix},
    )
    raise HTTPException(status_code=401, detail="invalid_service_token")


__all__ = [
    "ALLOWED_SERVICE_SCOPES",
    "ServiceTokenContext",
    "log_service_token_audit",
    "hash_service_token",
    "issue_service_token",
    "normalize_scopes",
    "resolve_service_token",
    "revoke_service_token",
    "rotate_service_token",
]
