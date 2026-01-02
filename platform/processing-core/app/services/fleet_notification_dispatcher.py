from __future__ import annotations

import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib import request

from sqlalchemy.orm import Session

from app.models.cases import CaseEventType
from app.models.fuel import (
    FleetNotificationChannel,
    FleetNotificationChannelStatus,
    FleetNotificationChannelType,
    FleetNotificationEventType,
    FleetNotificationOutbox,
    FleetNotificationOutboxStatus,
    FleetNotificationPolicy,
    FleetNotificationPolicyScopeType,
    FleetNotificationSeverity,
    FuelAnomaly,
    FuelLimitBreach,
)
from app.security.rbac.principal import Principal
from app.services import fleet_service
from app.services.case_event_redaction import redact_deep
from app.services.fleet_metrics import metrics as fleet_metrics

logger = logging.getLogger(__name__)

BACKOFF_SECONDS = [60, 300, 900, 3600, 9000, 18000, 36000, 72000, 144000, 288000]
MAX_ATTEMPTS = 10


@dataclass(frozen=True)
class DeliveryTarget:
    channel: FleetNotificationChannel
    payload: dict[str, Any]


class EmailSender:
    def send(self, *, to_address: str, subject: str, body: str) -> None:
        raise NotImplementedError


class ConsoleEmailSender(EmailSender):
    def send(self, *, to_address: str, subject: str, body: str) -> None:
        logger.info("Email to %s: %s\n%s", to_address, subject, body)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _severity_rank(severity: FleetNotificationSeverity) -> int:
    return {
        FleetNotificationSeverity.LOW: 1,
        FleetNotificationSeverity.MEDIUM: 2,
        FleetNotificationSeverity.HIGH: 3,
        FleetNotificationSeverity.CRITICAL: 4,
    }[severity]


def _dedupe_key(client_id: str, event_type: str, event_ref_id: str, severity: str) -> str:
    return f"{client_id}:{event_type}:{event_ref_id}:{severity}"


def _next_attempt(attempts: int) -> datetime:
    delay = BACKOFF_SECONDS[min(attempts, len(BACKOFF_SECONDS) - 1)]
    return _now() + timedelta(seconds=delay)


def sign_webhook_payload(payload: dict[str, Any], secret: str) -> str:
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return signature


def enqueue_notification(
    db: Session,
    *,
    client_id: str,
    event_type: FleetNotificationEventType,
    severity: FleetNotificationSeverity,
    event_ref_type: str,
    event_ref_id: str,
    payload: dict[str, Any],
    principal: Principal | None,
    request_id: str | None,
    trace_id: str | None,
) -> FleetNotificationOutbox:
    dedupe = _dedupe_key(client_id, event_type.value, event_ref_id, severity.value)
    existing = db.query(FleetNotificationOutbox).filter(FleetNotificationOutbox.dedupe_key == dedupe).one_or_none()
    if existing:
        return existing
    audit_event_id = fleet_service._emit_event(
        db,
        client_id=client_id,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
        event_type=CaseEventType.FLEET_NOTIFICATION_ENQUEUED,
        payload={"event_type": event_type.value, "dedupe_key": dedupe, "event_ref_id": event_ref_id},
    )
    outbox = FleetNotificationOutbox(
        client_id=client_id,
        event_type=event_type.value,
        severity=severity.value,
        event_ref_type=event_ref_type,
        event_ref_id=event_ref_id,
        payload_redacted=redact_deep(payload, "", include_hash=True),
        channels_attempted=[],
        status=FleetNotificationOutboxStatus.PENDING,
        attempts=0,
        next_attempt_at=_now(),
        dedupe_key=dedupe,
        audit_event_id=audit_event_id,
    )
    db.add(outbox)
    db.flush()
    fleet_metrics.mark_notification_outbox(outbox.status.value, outbox.event_type)
    return outbox


def _policy_matches_scope(policy: FleetNotificationPolicy, payload: dict[str, Any]) -> bool:
    if policy.scope_type == FleetNotificationPolicyScopeType.CLIENT:
        return True
    if policy.scope_type == FleetNotificationPolicyScopeType.GROUP:
        return payload.get("group_id") and str(policy.scope_id) == str(payload.get("group_id"))
    if policy.scope_type == FleetNotificationPolicyScopeType.CARD:
        return payload.get("card_id") and str(policy.scope_id) == str(payload.get("card_id"))
    return False


def _resolve_channels(
    db: Session,
    *,
    client_id: str,
    event_type: FleetNotificationEventType,
    severity: FleetNotificationSeverity,
    payload: dict[str, Any],
) -> list[FleetNotificationChannel]:
    policies = (
        db.query(FleetNotificationPolicy)
        .filter(FleetNotificationPolicy.client_id == client_id)
        .filter(FleetNotificationPolicy.event_type == event_type)
        .filter(FleetNotificationPolicy.active.is_(True))
        .all()
    )
    allowed_channels: set[FleetNotificationChannelType] = set()
    for policy in policies:
        if not _policy_matches_scope(policy, payload):
            continue
        if _severity_rank(severity) < _severity_rank(policy.severity_min):
            continue
        for channel in policy.channels or []:
            allowed_channels.add(FleetNotificationChannelType(channel))
    if not allowed_channels:
        return []
    return (
        db.query(FleetNotificationChannel)
        .filter(FleetNotificationChannel.client_id == client_id)
        .filter(FleetNotificationChannel.status == FleetNotificationChannelStatus.ACTIVE)
        .filter(FleetNotificationChannel.channel_type.in_(list(allowed_channels)))
        .all()
    )


def _send_webhook(channel: FleetNotificationChannel, payload: dict[str, Any], *, event_id: str, event_type: str) -> None:
    secret = channel.secret_ref or ""
    signature = sign_webhook_payload(payload, secret)
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        channel.target,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-NEFT-Signature": f"sha256={signature}",
            "X-NEFT-Event-Id": event_id,
            "X-NEFT-Event-Type": event_type,
        },
    )
    with request.urlopen(req, timeout=5):
        return None


def _send_email(sender: EmailSender, channel: FleetNotificationChannel, payload: dict[str, Any]) -> None:
    subject = f"[NEFT] Fleet alert: {payload.get('event_type')} {payload.get('severity')}"
    body = payload.get("summary") or "Fleet alert notification."
    sender.send(to_address=channel.target, subject=subject, body=body)


def dispatch_pending_outbox(db: Session, *, sender: EmailSender | None = None) -> list[FleetNotificationOutbox]:
    sender = sender or ConsoleEmailSender()
    ready = (
        db.query(FleetNotificationOutbox)
        .filter(FleetNotificationOutbox.status == FleetNotificationOutboxStatus.PENDING)
        .filter(FleetNotificationOutbox.next_attempt_at <= _now())
        .all()
    )
    processed: list[FleetNotificationOutbox] = []
    for outbox in ready:
        payload = outbox.payload_redacted or {}
        event_type = FleetNotificationEventType(outbox.event_type)
        severity = FleetNotificationSeverity(outbox.severity)
        channels = _resolve_channels(db, client_id=outbox.client_id, event_type=event_type, severity=severity, payload=payload)
        attempted: list[str] = []
        error: str | None = None
        start = _now()
        try:
            if not channels:
                raise RuntimeError("no_active_channels")
            for channel in channels:
                attempted.append(channel.channel_type.value)
                if channel.channel_type == FleetNotificationChannelType.WEBHOOK:
                    _send_webhook(channel, payload, event_id=str(outbox.id), event_type=outbox.event_type)
                elif channel.channel_type == FleetNotificationChannelType.EMAIL:
                    _send_email(sender, channel, payload)
            outbox.status = FleetNotificationOutboxStatus.SENT
            outbox.last_error = None
            outbox.channels_attempted = attempted
            fleet_metrics.mark_notification_outbox(outbox.status.value, outbox.event_type)
        except Exception as exc:  # pragma: no cover - defensive
            error = str(exc)[:500]
            outbox.attempts += 1
            outbox.last_error = error
            outbox.channels_attempted = attempted
            if outbox.attempts >= MAX_ATTEMPTS:
                outbox.status = FleetNotificationOutboxStatus.DEAD
            else:
                outbox.status = FleetNotificationOutboxStatus.FAILED
                outbox.next_attempt_at = _next_attempt(outbox.attempts)
            fleet_metrics.mark_notification_outbox(outbox.status.value, outbox.event_type)
        finally:
            elapsed = (_now() - start).total_seconds()
            if attempted:
                fleet_metrics.observe_notification_delivery("+".join(attempted), elapsed)
        processed.append(outbox)
    return processed


def enqueue_anomaly_notification(
    db: Session,
    *,
    anomaly: FuelAnomaly,
    principal: Principal | None,
    request_id: str | None,
    trace_id: str | None,
) -> FleetNotificationOutbox:
    payload = {
        "client_id": anomaly.client_id,
        "event_type": FleetNotificationEventType.ANOMALY.value,
        "severity": anomaly.severity.value,
        "card_id": str(anomaly.card_id) if anomaly.card_id else None,
        "group_id": str(anomaly.group_id) if anomaly.group_id else None,
        "tx_id": str(anomaly.tx_id) if anomaly.tx_id else None,
        "summary": {
            "anomaly_type": anomaly.anomaly_type.value,
            "occurred_at": anomaly.occurred_at.isoformat(),
        },
    }
    return enqueue_notification(
        db,
        client_id=anomaly.client_id,
        event_type=FleetNotificationEventType.ANOMALY,
        severity=anomaly.severity,
        event_ref_type="anomaly",
        event_ref_id=str(anomaly.id),
        payload=payload,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )


def _breach_severity(breach: FuelLimitBreach) -> FleetNotificationSeverity:
    if breach.breach_type.value in {"CATEGORY", "STATION"}:
        return FleetNotificationSeverity.HIGH
    if breach.threshold and breach.threshold > 0:
        ratio = breach.observed / breach.threshold
        if ratio >= 2:
            return FleetNotificationSeverity.CRITICAL
        if ratio >= 1.5:
            return FleetNotificationSeverity.HIGH
    return FleetNotificationSeverity.MEDIUM


def enqueue_breach_notification(
    db: Session,
    *,
    breach: FuelLimitBreach,
    principal: Principal | None,
    request_id: str | None,
    trace_id: str | None,
) -> FleetNotificationOutbox:
    severity = _breach_severity(breach)
    payload = {
        "client_id": breach.client_id,
        "event_type": FleetNotificationEventType.LIMIT_BREACH.value,
        "severity": severity.value,
        "card_id": str(breach.scope_id) if breach.scope_type.value == "card" else None,
        "group_id": str(breach.scope_id) if breach.scope_type.value == "group" else None,
        "tx_id": str(breach.tx_id) if breach.tx_id else None,
        "summary": {
            "breach_type": breach.breach_type.value,
            "threshold": str(breach.threshold),
            "observed": str(breach.observed),
            "occurred_at": breach.occurred_at.isoformat(),
        },
    }
    return enqueue_notification(
        db,
        client_id=breach.client_id,
        event_type=FleetNotificationEventType.LIMIT_BREACH,
        severity=severity,
        event_ref_type="limit_breach",
        event_ref_id=str(breach.id),
        payload=payload,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )


def enqueue_ingest_failed_notification(
    db: Session,
    *,
    client_id: str,
    job_id: str,
    error: str,
    principal: Principal | None,
    request_id: str | None,
    trace_id: str | None,
) -> FleetNotificationOutbox:
    payload = {
        "client_id": client_id,
        "event_type": FleetNotificationEventType.INGEST_FAILED.value,
        "severity": FleetNotificationSeverity.HIGH.value,
        "summary": {"job_id": job_id, "error": error},
    }
    return enqueue_notification(
        db,
        client_id=client_id,
        event_type=FleetNotificationEventType.INGEST_FAILED,
        severity=FleetNotificationSeverity.HIGH,
        event_ref_type="ingest_job",
        event_ref_id=job_id,
        payload=payload,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )


__all__ = [
    "ConsoleEmailSender",
    "EmailSender",
    "dispatch_pending_outbox",
    "enqueue_anomaly_notification",
    "enqueue_breach_notification",
    "enqueue_ingest_failed_notification",
    "enqueue_notification",
    "sign_webhook_payload",
]
