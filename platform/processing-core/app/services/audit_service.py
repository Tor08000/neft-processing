from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Iterable
from uuid import UUID

from fastapi import Request
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.db.types import new_uuid_str
from app.models.audit_log import ActorType, AuditLog, AuditVisibility
from app.services.audit_metrics import metrics as audit_metrics


SENSITIVE_KEYS = {"password", "pin", "secret", "token"}
MAX_JSON_BYTES = 32 * 1024
GENESIS_HASH = "GENESIS"
AUDIT_TOKEN_ALLOWLIST = {"user_id", "sub", "client_id", "email", "roles", "role", "tenant_id"}


@dataclass(frozen=True)
class RequestContext:
    actor_type: ActorType
    actor_id: str | None = None
    actor_email: str | None = None
    actor_roles: list[str] | None = None
    ip: str | None = None
    user_agent: str | None = None
    request_id: str | None = None
    trace_id: str | None = None
    tenant_id: int | None = None


def request_context_from_request(
    request: Request | None,
    *,
    token: dict | None = None,
    actor_type: ActorType | None = None,
) -> RequestContext:
    resolved_actor_type = actor_type
    actor_id = None
    actor_email = None
    actor_roles: list[str] | None = None
    tenant_id = None

    if token:
        resolved_actor_type = resolved_actor_type or ActorType.USER
        actor_id = token.get("user_id") or token.get("sub") or token.get("client_id")
        actor_email = token.get("email")
        roles = token.get("roles") or []
        if isinstance(roles, str):
            roles = [roles]
        role = token.get("role")
        if role and role not in roles:
            roles.append(role)
        actor_roles = [str(item) for item in roles] if roles else None
        tenant_id = token.get("tenant_id")

    resolved_actor_type = resolved_actor_type or ActorType.SYSTEM

    ip = request.client.host if request and request.client else None
    user_agent = request.headers.get("user-agent") if request else None
    request_id = request.headers.get("x-request-id") if request else None
    trace_id = request.headers.get("x-trace-id") if request else None

    return RequestContext(
        actor_type=resolved_actor_type,
        actor_id=actor_id,
        actor_email=actor_email,
        actor_roles=actor_roles,
        ip=ip,
        user_agent=user_agent,
        request_id=request_id,
        trace_id=trace_id,
        tenant_id=tenant_id,
    )


def _sanitize_token_for_audit(token: dict | None) -> dict | None:
    if not token:
        return None
    return {key: token[key] for key in AUDIT_TOKEN_ALLOWLIST if key in token}


def _normalize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        if isinstance(value, datetime):
            value = value.astimezone(timezone.utc)
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _normalize_value(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple, set)):
        return [_normalize_value(item) for item in value]
    return value


def _canonical_json(data: Any) -> str:
    normalized = _normalize_value(data)
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _mask_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        masked = {}
        for key, item in value.items():
            key_name = key.lower() if isinstance(key, str) else ""
            if key_name and any(token in key_name for token in SENSITIVE_KEYS):
                masked[key] = "***"
            else:
                masked[key] = _mask_sensitive(item)
        return masked
    if isinstance(value, list):
        return [_mask_sensitive(item) for item in value]
    return value


def _truncate_payload(payload: Any) -> Any:
    if payload is None:
        return None
    serialized = _canonical_json(payload)
    size_bytes = len(serialized.encode("utf-8"))
    if size_bytes <= MAX_JSON_BYTES:
        return payload
    return {
        "_truncated": True,
        "hash": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
        "size_bytes": size_bytes,
    }


def _sanitize_payload(payload: Any) -> Any:
    masked = _mask_sensitive(payload)
    return _truncate_payload(masked)


def _compact_dict(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None}


def _diff_payload(before: dict | None, after: dict | None) -> dict | None:
    if not before or not after:
        return None
    diff: dict[str, dict[str, Any]] = {}
    keys = set(before) | set(after)
    for key in keys:
        if before.get(key) != after.get(key):
            diff[key] = {"before": before.get(key), "after": after.get(key)}
    return diff or None


class AuditService:
    def __init__(self, db: Session):
        self.db = db

    def _latest_hash(self, tenant_id: int | None) -> str:
        query = self.db.query(AuditLog)
        if tenant_id is None:
            query = query.filter(AuditLog.tenant_id.is_(None))
        else:
            query = query.filter(AuditLog.tenant_id == tenant_id)
        latest = query.order_by(desc(AuditLog.ts), desc(AuditLog.id)).first()
        if latest:
            return latest.hash
        return GENESIS_HASH

    def _hash_payload(self, data: dict[str, Any], prev_hash: str) -> str:
        payload = _canonical_json(data)
        return hashlib.sha256(f"{payload}{prev_hash}".encode("utf-8")).hexdigest()

    def _hash_data_for_record(self, record: AuditLog) -> dict[str, Any]:
        return _compact_dict(
            {
                "id": record.id,
                "ts": record.ts,
                "tenant_id": record.tenant_id,
                "actor_type": record.actor_type,
                "actor_id": record.actor_id,
                "actor_email": record.actor_email,
                "actor_roles": record.actor_roles,
                "ip": record.ip,
                "user_agent": record.user_agent,
                "request_id": record.request_id,
                "trace_id": record.trace_id,
                "event_type": record.event_type,
                "entity_type": record.entity_type,
                "entity_id": record.entity_id,
                "action": record.action,
                "visibility": record.visibility,
                "before": record.before,
                "after": record.after,
                "diff": record.diff,
                "external_refs": record.external_refs,
                "reason": record.reason,
                "attachment_key": record.attachment_key,
            }
        )

    def audit(
        self,
        *,
        event_type: str,
        entity_type: str,
        entity_id: str,
        action: str,
        visibility: AuditVisibility = AuditVisibility.INTERNAL,
        before: dict | None = None,
        after: dict | None = None,
        diff: dict | None = None,
        external_refs: dict | None = None,
        reason: str | None = None,
        attachment_key: str | None = None,
        request_ctx: RequestContext | None = None,
    ) -> AuditLog:
        ctx = request_ctx or RequestContext(actor_type=ActorType.SYSTEM)
        ts = datetime.now(timezone.utc)

        sanitized_before = _sanitize_payload(before)
        sanitized_after = _sanitize_payload(after)
        sanitized_diff = _sanitize_payload(diff or _diff_payload(before, after))
        sanitized_external_refs = _sanitize_payload(external_refs)

        prev_hash = self._latest_hash(ctx.tenant_id)
        record_id = new_uuid_str()
        record_data = _compact_dict(
            {
                "id": record_id,
                "ts": ts,
                "tenant_id": ctx.tenant_id,
                "actor_type": ctx.actor_type,
                "actor_id": ctx.actor_id,
                "actor_email": ctx.actor_email,
                "actor_roles": ctx.actor_roles,
                "ip": ctx.ip,
                "user_agent": ctx.user_agent,
                "request_id": ctx.request_id,
                "trace_id": ctx.trace_id,
                "event_type": event_type,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "action": action,
                "visibility": visibility,
                "before": sanitized_before,
                "after": sanitized_after,
                "diff": sanitized_diff,
                "external_refs": sanitized_external_refs,
                "reason": reason,
                "attachment_key": attachment_key,
            }
        )
        record_hash = self._hash_payload(record_data, prev_hash)

        record = AuditLog(
            id=record_id,
            ts=ts,
            tenant_id=ctx.tenant_id,
            actor_type=ctx.actor_type,
            actor_id=ctx.actor_id,
            actor_email=ctx.actor_email,
            actor_roles=ctx.actor_roles,
            ip=ctx.ip,
            user_agent=ctx.user_agent,
            request_id=ctx.request_id,
            trace_id=ctx.trace_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            visibility=visibility,
            before=sanitized_before,
            after=sanitized_after,
            diff=sanitized_diff,
            external_refs=sanitized_external_refs,
            reason=reason,
            attachment_key=attachment_key,
            prev_hash=prev_hash,
            hash=record_hash,
        )
        try:
            self.db.add(record)
            self.db.flush()
            audit_metrics.mark_event(event_type)
            return record
        except Exception:
            audit_metrics.mark_write_error()
            raise

    def verify_chain(
        self,
        *,
        date_from: datetime,
        date_to: datetime,
        tenant_id: int | None,
    ) -> dict[str, Any]:
        query = self.db.query(AuditLog).filter(AuditLog.ts >= date_from, AuditLog.ts <= date_to)
        if tenant_id is None:
            query = query.filter(AuditLog.tenant_id.is_(None))
        else:
            query = query.filter(AuditLog.tenant_id == tenant_id)
        records: Iterable[AuditLog] = query.order_by(AuditLog.ts.asc(), AuditLog.id.asc()).all()

        expected_prev = GENESIS_HASH
        checked = 0
        for record in records:
            checked += 1
            if record.prev_hash != expected_prev:
                audit_metrics.mark_verify_broken()
                return {
                    "status": "BROKEN",
                    "checked": checked,
                    "broken_at_id": record.id,
                    "message": "prev_hash mismatch",
                }
            data = self._hash_data_for_record(record)
            expected_hash = self._hash_payload(data, record.prev_hash)
            if record.hash != expected_hash:
                audit_metrics.mark_verify_broken()
                return {
                    "status": "BROKEN",
                    "checked": checked,
                    "broken_at_id": record.id,
                    "message": "hash mismatch",
                }
            expected_prev = record.hash

        return {"status": "OK", "checked": checked, "broken_at_id": None, "message": ""}


__all__ = ["AuditService", "RequestContext", "request_context_from_request"]
