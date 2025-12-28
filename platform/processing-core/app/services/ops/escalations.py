from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.audit_log import ActorType
from app.models.ops import (
    OpsEscalation,
    OpsEscalationPriority,
    OpsEscalationSource,
    OpsEscalationStatus,
    OpsEscalationTarget,
)
from app.models.unified_explain import PrimaryReason, UnifiedExplainSnapshot
from app.services.audit_service import AuditService, RequestContext
from app.services.explain.escalation import ESCALATION_MAP, audit_sla_expired
from app.services.explain.sla import SLAClock
from app.services.ops.reason_codes import (
    OpsReasonCode,
    get_primary_reason,
    get_target_for_reason,
    is_valid_ack_reason,
    is_valid_close_reason,
)


@dataclass(frozen=True)
class EscalationCreateResult:
    escalation: OpsEscalation
    created: bool


def _build_idempotency_key(
    *,
    tenant_id: int,
    target: OpsEscalationTarget,
    subject_type: str,
    subject_id: str,
    primary_reason: PrimaryReason,
    sla_expires_at: datetime | None,
) -> str:
    expires_at = sla_expires_at.astimezone(timezone.utc).isoformat() if sla_expires_at else ""
    payload = f"{tenant_id}:{target.value}:{subject_type}:{subject_id}:{primary_reason.value}:{expires_at}"
    return sha256(payload.encode("utf-8")).hexdigest()


def _actor_label(request_ctx: RequestContext | None) -> str | None:
    if not request_ctx:
        return None
    return request_ctx.actor_id or request_ctx.actor_email or request_ctx.actor_type.value


def _audit_payload(
    escalation: OpsEscalation,
    *,
    reason: str | None = None,
    actor: str | None = None,
) -> dict[str, Any]:
    return {
        "escalation_id": str(escalation.id),
        "target": escalation.target.value,
        "status": escalation.status.value,
        "priority": escalation.priority.value,
        "primary_reason": escalation.primary_reason.value,
        "reason_code": escalation.reason_code,
        "subject_type": escalation.subject_type,
        "subject_id": escalation.subject_id,
        "client_id": escalation.client_id,
        "source": escalation.source.value,
        "sla_started_at": escalation.sla_started_at,
        "sla_expires_at": escalation.sla_expires_at,
        "snapshot_hash": escalation.unified_explain_snapshot_hash,
        "actor": actor,
        "ack_reason_code": escalation.ack_reason_code,
        "ack_reason_text": escalation.ack_reason_text,
        "close_reason_code": escalation.close_reason_code,
        "close_reason_text": escalation.close_reason_text,
        "reason": reason,
    }


def create_escalation_if_missing(
    db: Session,
    *,
    tenant_id: int,
    target: OpsEscalationTarget,
    priority: OpsEscalationPriority,
    primary_reason: PrimaryReason,
    subject_type: str,
    subject_id: str,
    source: OpsEscalationSource,
    client_id: str | None = None,
    sla_started_at: datetime | None = None,
    sla_expires_at: datetime | None = None,
    created_by_actor_type: str | None = None,
    created_by_actor_id: str | None = None,
    created_by_actor_email: str | None = None,
    meta: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
    reason_code: OpsReasonCode | str | None = None,
    unified_explain_snapshot_hash: str,
    unified_explain_snapshot: dict[str, Any],
    audit: AuditService | None = None,
    request_ctx: RequestContext | None = None,
) -> EscalationCreateResult:
    resolved_key = idempotency_key or _build_idempotency_key(
        tenant_id=tenant_id,
        target=target,
        subject_type=subject_type,
        subject_id=subject_id,
        primary_reason=primary_reason,
        sla_expires_at=sla_expires_at,
    )

    existing = db.query(OpsEscalation).filter(OpsEscalation.idempotency_key == resolved_key).one_or_none()
    if existing:
        return EscalationCreateResult(escalation=existing, created=False)

    if not unified_explain_snapshot_hash or unified_explain_snapshot is None:
        raise ValueError("unified_explain_snapshot_required")

    resolved_reason_code = _resolve_reason_code(
        reason_code=reason_code,
        primary_reason=primary_reason,
        target=target,
        unified_explain_snapshot=unified_explain_snapshot,
    )

    escalation = OpsEscalation(
        tenant_id=tenant_id,
        client_id=client_id,
        target=target,
        status=OpsEscalationStatus.OPEN,
        priority=priority,
        primary_reason=primary_reason,
        reason_code=resolved_reason_code.value,
        subject_type=subject_type,
        subject_id=subject_id,
        source=source,
        sla_started_at=sla_started_at,
        sla_expires_at=sla_expires_at,
        created_by_actor_type=created_by_actor_type,
        created_by_actor_id=created_by_actor_id,
        created_by_actor_email=created_by_actor_email,
        unified_explain_snapshot_hash=unified_explain_snapshot_hash,
        unified_explain_snapshot=unified_explain_snapshot,
        meta=meta,
        idempotency_key=resolved_key,
    )
    db.add(escalation)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.query(OpsEscalation).filter(OpsEscalation.idempotency_key == resolved_key).one_or_none()
        if existing:
            return EscalationCreateResult(escalation=existing, created=False)
        raise

    if audit and request_ctx:
        audit.audit(
            event_type="OPS_ESCALATION_CREATED",
            entity_type="ops_escalation",
            entity_id=str(escalation.id),
            action="CREATE",
            after=_audit_payload(escalation, actor=_actor_label(request_ctx)),
            request_ctx=request_ctx,
        )
    return EscalationCreateResult(escalation=escalation, created=True)


def ack_escalation(
    db: Session,
    *,
    escalation: OpsEscalation,
    reason_code: str,
    reason_text: str | None,
    actor: str | None,
    audit: AuditService | None = None,
    request_ctx: RequestContext | None = None,
) -> OpsEscalation:
    if not reason_code or not reason_code.strip():
        raise ValueError("ack_reason_code_required")
    normalized_code = reason_code.strip().upper()
    if not is_valid_ack_reason(normalized_code):
        raise ValueError("ack_reason_code_invalid")
    if normalized_code.endswith("_OTHER") and not (reason_text and reason_text.strip()):
        raise ValueError("ack_reason_text_required")
    if escalation.status != OpsEscalationStatus.OPEN:
        raise ValueError("invalid_state")
    escalation.status = OpsEscalationStatus.ACK
    if escalation.acked_at is None:
        escalation.acked_at = datetime.now(timezone.utc)
    escalation.acked_by = actor
    escalation.ack_reason_code = normalized_code
    escalation.ack_reason_text = reason_text.strip() if reason_text and reason_text.strip() else None
    db.flush()

    if audit and request_ctx:
        audit.audit(
            event_type="OPS_ESCALATION_ACKED",
            entity_type="ops_escalation",
            entity_id=str(escalation.id),
            action="ACK",
            after=_audit_payload(
                escalation,
                reason=escalation.ack_reason_text,
                actor=_actor_label(request_ctx),
            ),
            reason=escalation.ack_reason_text,
            request_ctx=request_ctx,
        )
    return escalation


def close_escalation(
    db: Session,
    *,
    escalation: OpsEscalation,
    reason_code: str,
    reason_text: str | None,
    actor: str | None,
    allow_from_open: bool = False,
    audit: AuditService | None = None,
    request_ctx: RequestContext | None = None,
) -> OpsEscalation:
    if not reason_code or not reason_code.strip():
        raise ValueError("close_reason_code_required")
    normalized_code = reason_code.strip().upper()
    if not is_valid_close_reason(normalized_code):
        raise ValueError("close_reason_code_invalid")
    if normalized_code.endswith("_OTHER") and not (reason_text and reason_text.strip()):
        raise ValueError("close_reason_text_required")
    if escalation.status == OpsEscalationStatus.CLOSED:
        raise ValueError("invalid_state")
    if escalation.status == OpsEscalationStatus.OPEN and not allow_from_open:
        raise PermissionError("forbidden")
    escalation.status = OpsEscalationStatus.CLOSED
    if escalation.closed_at is None:
        escalation.closed_at = datetime.now(timezone.utc)
    escalation.closed_by = actor
    escalation.close_reason_code = normalized_code
    escalation.close_reason_text = reason_text.strip() if reason_text and reason_text.strip() else None
    db.flush()

    if audit and request_ctx:
        audit.audit(
            event_type="OPS_ESCALATION_CLOSED",
            entity_type="ops_escalation",
            entity_id=str(escalation.id),
            action="CLOSE",
            after=_audit_payload(
                escalation,
                reason=escalation.close_reason_text,
                actor=_actor_label(request_ctx),
            ),
            reason=escalation.close_reason_text,
            request_ctx=request_ctx,
        )
    return escalation


def _resolve_reason_code(
    *,
    reason_code: OpsReasonCode | str | None,
    primary_reason: PrimaryReason,
    target: OpsEscalationTarget,
    unified_explain_snapshot: dict[str, Any] | None,
) -> OpsReasonCode:
    resolved = _normalize_reason_code(reason_code)
    if resolved is None:
        resolved = _infer_reason_code(primary_reason, unified_explain_snapshot or {})
    if get_primary_reason(resolved) != primary_reason:
        raise ValueError("reason_code_primary_mismatch")
    if get_target_for_reason(resolved) != target:
        raise ValueError("reason_code_target_mismatch")
    return resolved


def _normalize_reason_code(reason_code: OpsReasonCode | str | None) -> OpsReasonCode | None:
    if not reason_code:
        return None
    if isinstance(reason_code, OpsReasonCode):
        return reason_code
    normalized = str(reason_code).strip().upper()
    if not normalized:
        return None
    try:
        return OpsReasonCode(normalized)
    except ValueError as exc:
        raise ValueError("reason_code_invalid") from exc


def _infer_reason_code(primary_reason: PrimaryReason, snapshot: dict[str, Any]) -> OpsReasonCode:
    default_by_primary = {
        PrimaryReason.LIMIT: OpsReasonCode.LIMIT_EXCEEDED,
        PrimaryReason.RISK: OpsReasonCode.RISK_BLOCK,
        PrimaryReason.LOGISTICS: OpsReasonCode.LOGISTICS_DEVIATION,
        PrimaryReason.MONEY: OpsReasonCode.MONEY_INVARIANT_VIOLATION,
        PrimaryReason.POLICY: OpsReasonCode.FEATURE_DISABLED,
        PrimaryReason.UNKNOWN: OpsReasonCode.FEATURE_DISABLED,
    }

    result_payload = snapshot.get("result") if isinstance(snapshot, dict) else None
    decline_code = result_payload.get("decline_code") if isinstance(result_payload, dict) else None
    if decline_code:
        normalized = str(decline_code).upper()
        if normalized == OpsReasonCode.LIMIT_PERIOD_MISMATCH.value:
            return OpsReasonCode.LIMIT_PERIOD_MISMATCH
        if normalized.startswith("LIMIT_"):
            return OpsReasonCode.LIMIT_EXCEEDED
        if normalized == OpsReasonCode.RISK_REVIEW_REQUIRED.value:
            return OpsReasonCode.RISK_REVIEW_REQUIRED
        if normalized == OpsReasonCode.RISK_BLOCK.value:
            return OpsReasonCode.RISK_BLOCK

    sections_payload = snapshot.get("sections") if isinstance(snapshot, dict) else None
    logistics_section = sections_payload.get("logistics") if isinstance(sections_payload, dict) else None
    if primary_reason == PrimaryReason.LOGISTICS and isinstance(logistics_section, dict):
        deviation_events = logistics_section.get("deviation_events", [])
        if isinstance(deviation_events, list):
            for event in deviation_events:
                if str(event.get("event_type", "")).upper() in {"STOP_OUT_OF_RADIUS", "UNEXPECTED_STOP"}:
                    return OpsReasonCode.LOGISTICS_STOP_MISUSE
        return OpsReasonCode.LOGISTICS_DEVIATION

    money_section = sections_payload.get("money") if isinstance(sections_payload, dict) else None
    if primary_reason == PrimaryReason.MONEY and isinstance(money_section, dict):
        invariants = money_section.get("invariants")
        if isinstance(invariants, dict) and invariants.get("passed") is False:
            return OpsReasonCode.MONEY_INVARIANT_VIOLATION

    return default_by_primary.get(primary_reason, OpsReasonCode.FEATURE_DISABLED)


def list_escalations(
    db: Session,
    *,
    tenant_id: int,
    target: OpsEscalationTarget | None = None,
    status: OpsEscalationStatus | None = None,
    primary_reason: PrimaryReason | None = None,
    overdue: bool | None = None,
    client_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[OpsEscalation], int]:
    query = db.query(OpsEscalation).filter(OpsEscalation.tenant_id == tenant_id)
    if target:
        query = query.filter(OpsEscalation.target == target)
    if status:
        query = query.filter(OpsEscalation.status == status)
    if primary_reason:
        query = query.filter(OpsEscalation.primary_reason == primary_reason)
    if client_id:
        query = query.filter(OpsEscalation.client_id == client_id)
    if overdue is True:
        now = datetime.now(timezone.utc)
        query = query.filter(
            OpsEscalation.sla_expires_at.isnot(None),
            OpsEscalation.sla_expires_at <= now,
            OpsEscalation.status != OpsEscalationStatus.CLOSED,
        )
    elif overdue is False:
        now = datetime.now(timezone.utc)
        query = query.filter(
            or_(
                OpsEscalation.sla_expires_at.is_(None),
                OpsEscalation.sla_expires_at > now,
                OpsEscalation.status == OpsEscalationStatus.CLOSED,
            )
        )
    total = query.count()
    items = (
        query.order_by(OpsEscalation.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return items, total


def scan_explain_sla_expiry(
    db: Session,
    *,
    tenant_id: int | None = None,
    now: datetime | None = None,
    limit: int = 500,
    audit: AuditService | None = None,
) -> list[OpsEscalation]:
    current_time = now or datetime.now(timezone.utc)
    query = db.query(UnifiedExplainSnapshot)
    if tenant_id is not None:
        query = query.filter(UnifiedExplainSnapshot.tenant_id == tenant_id)
    snapshots = query.order_by(UnifiedExplainSnapshot.created_at.desc()).limit(limit).all()

    created_escalations: list[OpsEscalation] = []
    for snapshot in snapshots:
        snapshot_json = snapshot.snapshot_json or {}
        sla_payload = snapshot_json.get("sla") if isinstance(snapshot_json, dict) else None
        if not isinstance(sla_payload, dict):
            continue
        expires_at_raw = sla_payload.get("expires_at")
        started_at_raw = sla_payload.get("started_at")
        if not expires_at_raw:
            continue
        expires_at = _parse_iso_datetime(expires_at_raw)
        started_at = _parse_iso_datetime(started_at_raw) if started_at_raw else None
        if not expires_at or expires_at > current_time:
            continue

        primary_reason_raw = snapshot_json.get("primary_reason")
        if not primary_reason_raw:
            continue
        try:
            primary_reason = PrimaryReason(primary_reason_raw)
        except ValueError:
            continue

        target_raw = ESCALATION_MAP.get(primary_reason)
        if not target_raw:
            continue
        target = OpsEscalationTarget(target_raw)

        subject_payload = snapshot_json.get("subject") if isinstance(snapshot_json, dict) else None
        subject_type = (
            subject_payload.get("type") if isinstance(subject_payload, dict) else None
        ) or snapshot.subject_type
        subject_id = (
            subject_payload.get("id") if isinstance(subject_payload, dict) else None
        ) or snapshot.subject_id

        priority = _priority_from_reason(primary_reason)
        ids_payload = snapshot_json.get("ids") if isinstance(snapshot_json, dict) else None
        meta = _build_meta(snapshot, ids_payload)

        request_ctx = RequestContext(
            actor_type=ActorType.SYSTEM,
            tenant_id=snapshot.tenant_id,
        )
        if audit:
            sla_clock = SLAClock(
                started_at=started_at.isoformat() if started_at else "",
                expires_at=expires_at.isoformat(),
                remaining_minutes=0,
            )
            audit_sla_expired(
                audit,
                entity_type="unified_explain_snapshot",
                entity_id=str(snapshot.id),
                tenant_id=snapshot.tenant_id,
                primary_reason=primary_reason,
                target=target.value,
                sla=sla_clock,
            )

        result = create_escalation_if_missing(
            db,
            tenant_id=snapshot.tenant_id,
            target=target,
            priority=priority,
            primary_reason=primary_reason,
            subject_type=subject_type,
            subject_id=subject_id,
            source=OpsEscalationSource.AUTO_SLA_EXPIRED,
            client_id=subject_payload.get("client_id") if isinstance(subject_payload, dict) else None,
            sla_started_at=started_at,
            sla_expires_at=expires_at,
            created_by_actor_type=ActorType.SYSTEM.value,
            created_by_actor_id=None,
            created_by_actor_email=None,
            meta=meta,
            unified_explain_snapshot_hash=snapshot.snapshot_hash,
            unified_explain_snapshot=snapshot.snapshot_json,
            audit=audit,
            request_ctx=request_ctx,
        )
        if result.created:
            if audit:
                audit.audit(
                    event_type="OPS_ESCALATION_SLA_EXPIRED",
                    entity_type="ops_escalation",
                    entity_id=str(result.escalation.id),
                    action="ESCALATE",
                    after=_audit_payload(
                        result.escalation,
                        reason="sla_expired",
                        actor=_actor_label(request_ctx),
                    ),
                    reason="sla_expired",
                    request_ctx=request_ctx,
                )
            created_escalations.append(result.escalation)
    return created_escalations


def _priority_from_reason(primary_reason: PrimaryReason) -> OpsEscalationPriority:
    mapping = {
        PrimaryReason.RISK: OpsEscalationPriority.CRITICAL,
        PrimaryReason.MONEY: OpsEscalationPriority.HIGH,
        PrimaryReason.LIMIT: OpsEscalationPriority.MEDIUM,
        PrimaryReason.LOGISTICS: OpsEscalationPriority.MEDIUM,
    }
    return mapping.get(primary_reason, OpsEscalationPriority.LOW)


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _build_meta(snapshot: UnifiedExplainSnapshot, ids_payload: Any) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "snapshot_hash": snapshot.snapshot_hash,
    }
    if isinstance(ids_payload, dict):
        for key in ("risk_decision_id", "invoice_id"):
            if ids_payload.get(key):
                meta[key] = ids_payload.get(key)
        if ids_payload.get("document_ids"):
            meta["document_ids"] = ids_payload.get("document_ids")
    subject_meta = snapshot.snapshot_json.get("subject") if isinstance(snapshot.snapshot_json, dict) else None
    if isinstance(subject_meta, dict):
        if subject_meta.get("id") and subject_meta.get("type") == "ORDER":
            meta["order_id"] = subject_meta.get("id")
    return meta


__all__ = [
    "EscalationCreateResult",
    "ack_escalation",
    "close_escalation",
    "create_escalation_if_missing",
    "list_escalations",
    "scan_explain_sla_expiry",
]
