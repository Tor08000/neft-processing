from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.db.types import new_uuid_str
from app.models.cases import Case, CaseEvent, CaseEventType
from app.services.case_event_hashing import canonical_json, strip_redaction_hash
from app.services.case_event_redaction import redact_for_audit
from app.services.audit_signing import AuditSignature, AuditSigningError, AuditSigningService

GENESIS_HASH = "GENESIS"


@dataclass(frozen=True)
class CaseEventActor:
    id: str | None = None
    email: str | None = None


@dataclass(frozen=True)
class CaseEventChange:
    field: str
    before: Any
    after: Any


@dataclass(frozen=True)
class CaseEventArtifact:
    kind: str
    id: str
    url: str | None = None


@dataclass(frozen=True)
class CaseEventChainIntegrityResult:
    verified: bool
    count: int
    broken_index: int | None = None
    expected_hash: str | None = None
    actual_hash: str | None = None
    tail_hash: str | None = None


@dataclass(frozen=True)
class CaseEventSignatureIntegrityResult:
    verified: bool
    broken_index: int | None = None
    key_id: str | None = None


def _lock_case(db: Session, case_id: str) -> None:
    if db.bind and db.bind.dialect.name == "sqlite":
        result = db.execute(sa.text("UPDATE cases SET id = id WHERE id = :case_id"), {"case_id": case_id})
        if result.rowcount == 0:
            raise ValueError("Case not found for event lock")
        return
    db.query(Case).filter(Case.id == case_id).with_for_update().one()


def _redact_changes(changes: list[CaseEventChange] | None) -> list[dict[str, Any]] | None:
    if not changes:
        return None
    redacted: list[dict[str, Any]] = []
    for change in changes:
        redacted.append(
            {
                "field": change.field,
                "from": redact_for_audit(change.field, change.before),
                "to": redact_for_audit(change.field, change.after),
            }
        )
    return redacted


def _build_payload(
    *,
    event_id: str,
    case_id: str,
    at: datetime,
    event_type: CaseEventType,
    actor: CaseEventActor | None,
    request_id: str | None,
    trace_id: str | None,
    changes: list[CaseEventChange] | None,
    artifact: CaseEventArtifact | None,
    reason: str | None,
    extra_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": event_id,
        "case_id": case_id,
        "at": at.astimezone(timezone.utc).isoformat(),
        "type": event_type.value,
        "source": "backend",
    }
    if actor and (actor.id or actor.email):
        payload["actor"] = {"id": actor.id, "email": actor.email}
    else:
        payload["actor"] = None
    if request_id is not None:
        payload["request_id"] = request_id
    if trace_id is not None:
        payload["trace_id"] = trace_id
    redacted_changes = _redact_changes(changes)
    if redacted_changes:
        payload["changes"] = redacted_changes
    if artifact:
        payload["artifact"] = {"kind": artifact.kind, "id": artifact.id, "url": artifact.url}
    if reason is not None:
        payload["reason"] = redact_for_audit("reason", reason)
    if extra_payload:
        for key, value in extra_payload.items():
            if key not in payload:
                payload[key] = value
    return payload


def _compute_hash(prev_hash: str, payload: dict[str, Any]) -> str:
    canonical = canonical_json(strip_redaction_hash(payload))
    material = f"{prev_hash}\n{canonical}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def emit_case_event(
    db: Session,
    *,
    case_id: str,
    event_type: CaseEventType,
    actor: CaseEventActor | None,
    request_id: str | None,
    trace_id: str | None,
    changes: list[CaseEventChange] | None = None,
    artifact: CaseEventArtifact | None = None,
    reason: str | None = None,
    extra_payload: dict[str, Any] | None = None,
    at: datetime | None = None,
) -> CaseEvent:
    _lock_case(db, case_id)
    event_id = new_uuid_str()
    now = at or datetime.now(timezone.utc)
    next_seq = (
        db.query(sa.func.coalesce(sa.func.max(CaseEvent.seq), 0) + 1)
        .filter(CaseEvent.case_id == case_id)
        .scalar()
    )
    prev_hash = GENESIS_HASH
    if next_seq and next_seq > 1:
        prev_hash = (
            db.query(CaseEvent.hash)
            .filter(CaseEvent.case_id == case_id, CaseEvent.seq == next_seq - 1)
            .scalar()
        )
        if prev_hash is None:
            raise ValueError("Missing previous hash for case event chain")
    payload_redacted = _build_payload(
        event_id=event_id,
        case_id=case_id,
        at=now,
        event_type=event_type,
        actor=actor,
        request_id=request_id,
        trace_id=trace_id,
        changes=changes,
        artifact=artifact,
        reason=reason,
        extra_payload=extra_payload,
    )
    event_hash = _compute_hash(prev_hash, payload_redacted)
    signature: AuditSignature | None = None
    signing_service = AuditSigningService()
    try:
        signature = signing_service.sign(bytes.fromhex(event_hash))
    except AuditSigningError:
        raise
    event = CaseEvent(
        id=event_id,
        case_id=case_id,
        seq=next_seq,
        at=now,
        type=event_type,
        actor_user_id=actor.id if actor else None,
        actor_email=actor.email if actor else None,
        request_id=request_id,
        trace_id=trace_id,
        payload_redacted=payload_redacted,
        prev_hash=prev_hash,
        hash=event_hash,
        signature=signature.signature if signature else None,
        signature_alg=signature.alg if signature else None,
        signing_key_id=signature.key_id if signature else None,
        signed_at=signature.signed_at if signature else None,
    )
    db.add(event)
    return event


def list_case_events(db: Session, *, case_id: str, limit: int = 200, offset: int = 0) -> list[CaseEvent]:
    return (
        db.query(CaseEvent)
        .filter(CaseEvent.case_id == case_id)
        .order_by(CaseEvent.seq.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def verify_case_event_chain(db: Session, *, case_id: str) -> CaseEventChainIntegrityResult:
    events = (
        db.query(CaseEvent)
        .filter(CaseEvent.case_id == case_id)
        .order_by(CaseEvent.seq.asc())
        .all()
    )
    prev_hash = GENESIS_HASH
    for index, event in enumerate(events):
        payload = event.payload_redacted or {}
        expected_hash = _compute_hash(prev_hash, payload)
        if event.prev_hash != prev_hash or event.hash != expected_hash:
            return CaseEventChainIntegrityResult(
                verified=False,
                count=len(events),
                broken_index=index,
                expected_hash=expected_hash,
                actual_hash=event.hash,
                tail_hash=event.hash,
            )
        prev_hash = event.hash
    return CaseEventChainIntegrityResult(
        verified=True,
        count=len(events),
        tail_hash=prev_hash if events else GENESIS_HASH,
    )


def verify_case_event_signatures(db: Session, *, case_id: str) -> CaseEventSignatureIntegrityResult:
    events = (
        db.query(CaseEvent)
        .filter(CaseEvent.case_id == case_id)
        .order_by(CaseEvent.seq.asc())
        .all()
    )
    signing_service = AuditSigningService()
    for index, event in enumerate(events):
        if not event.signature or not event.signature_alg or not event.signing_key_id:
            return CaseEventSignatureIntegrityResult(
                verified=False,
                broken_index=index,
                key_id=event.signing_key_id,
            )
        try:
            message = bytes.fromhex(event.hash)
        except ValueError:
            return CaseEventSignatureIntegrityResult(
                verified=False,
                broken_index=index,
                key_id=event.signing_key_id,
            )
        if not signing_service.verify(
            message=message,
            signature_b64=event.signature,
            alg=event.signature_alg,
            key_id=event.signing_key_id,
        ):
            return CaseEventSignatureIntegrityResult(
                verified=False,
                broken_index=index,
                key_id=event.signing_key_id,
            )
    return CaseEventSignatureIntegrityResult(verified=True)
