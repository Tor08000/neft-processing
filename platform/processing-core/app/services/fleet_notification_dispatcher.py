from __future__ import annotations

import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib import error as url_error
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
    FleetPushSubscription,
    FuelAnomaly,
    FuelLimitBreach,
)
from app.security.rbac.principal import Principal
from app.services import fleet_service
from app.services.case_event_redaction import redact_deep
from app.services.fleet_metrics import metrics as fleet_metrics
from app.services.notifications.email_sender import ConsoleEmailSender, EmailSender, SmtpEmailSender
from app.services.notifications.email_templates import render_notification_email
from app.services.notifications.webpush_sender import WebPushSender

logger = logging.getLogger(__name__)

BACKOFF_SECONDS = [60, 300, 900, 3600, 9000, 18000, 36000, 72000, 144000, 288000]
MAX_ATTEMPTS = 10


@dataclass(frozen=True)
class DeliveryTarget:
    channel: FleetNotificationChannel
    payload: dict[str, Any]


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


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=False)


def sign_webhook_payload(payload: dict[str, Any], secret: str, *, timestamp: str) -> str:
    body = canonical_json(payload)
    signature_payload = f"{timestamp}.{body}".encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), signature_payload, hashlib.sha256).hexdigest()
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
    override_channels = payload.get("channels_override")
    if override_channels:
        return (
            db.query(FleetNotificationChannel)
            .filter(FleetNotificationChannel.client_id == client_id)
            .filter(FleetNotificationChannel.status == FleetNotificationChannelStatus.ACTIVE)
            .filter(FleetNotificationChannel.channel_type.in_(override_channels))
            .all()
        )
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


def _send_webhook(
    channel: FleetNotificationChannel,
    payload: dict[str, Any],
    *,
    event_id: str,
    event_type: str,
) -> tuple[int | None, str | None]:
    secret = channel.secret_ref or ""
    timestamp = str(int(_now().timestamp()))
    signature = sign_webhook_payload(payload, secret, timestamp=timestamp)
    body = canonical_json(payload).encode("utf-8")
    req = request.Request(
        channel.target,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-NEFT-Signature": f"sha256={signature}",
            "X-NEFT-Signature-Timestamp": timestamp,
            "X-NEFT-Event-Id": event_id,
            "X-NEFT-Event-Type": event_type,
        },
    )
    try:
        with request.urlopen(req, timeout=5) as response:
            body_text = response.read().decode("utf-8")[:500]
            return response.status, body_text
    except url_error.HTTPError as exc:
        body_text = exc.read().decode("utf-8")[:500] if exc.fp else None
        return exc.code, body_text


def _send_email(sender: EmailSender, channel: FleetNotificationChannel, payload: dict[str, Any]) -> str | None:
    subject, html_body, text_body = render_notification_email(payload)
    return sender.send(to=channel.target, subject=subject, html=html_body, text=text_body, headers=None)


def _send_push(db: Session, sender: WebPushSender, client_id: str, payload: dict[str, Any]) -> tuple[int | None, str | None]:
    subscriptions = (
        db.query(FleetPushSubscription)
        .filter(FleetPushSubscription.client_id == client_id)
        .filter(FleetPushSubscription.active.is_(True))
        .all()
    )
    if not subscriptions:
        raise RuntimeError("no_push_subscriptions")
    last_status = None
    last_body = None
    for subscription in subscriptions:
        response = sender.send(
            {
                "endpoint": subscription.endpoint,
                "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
            },
            payload,
        )
        subscription.last_sent_at = _now()
        last_status = response.status_code
        last_body = response.body
    return last_status, last_body


def dispatch_pending_outbox(
    db: Session,
    *,
    sender: EmailSender | None = None,
    webpush_sender: WebPushSender | None = None,
) -> list[FleetNotificationOutbox]:
    sender = sender or _default_email_sender()
    webpush_sender = webpush_sender or WebPushSender()
    ready = (
        db.query(FleetNotificationOutbox)
        .filter(FleetNotificationOutbox.status == FleetNotificationOutboxStatus.PENDING)
        .filter(FleetNotificationOutbox.next_attempt_at <= _now())
        .all()
    )
    processed: list[FleetNotificationOutbox] = []
    for outbox in ready:
        processed.append(
            _dispatch_outbox_item(db, outbox, sender=sender, webpush_sender=webpush_sender),
        )
    return processed


def dispatch_outbox_item(
    db: Session,
    *,
    outbox_id: str,
    sender: EmailSender | None = None,
    webpush_sender: WebPushSender | None = None,
) -> FleetNotificationOutbox:
    sender = sender or _default_email_sender()
    webpush_sender = webpush_sender or WebPushSender()
    outbox = db.query(FleetNotificationOutbox).filter(FleetNotificationOutbox.id == outbox_id).one_or_none()
    if not outbox:
        raise RuntimeError("outbox_not_found")
    return _dispatch_outbox_item(db, outbox, sender=sender, webpush_sender=webpush_sender)


def _default_email_sender() -> EmailSender:
    if _smtp_enabled():
        return SmtpEmailSender()
    return ConsoleEmailSender()


def _smtp_enabled() -> bool:
    return bool(SmtpEmailSender().host)


def _dispatch_outbox_item(
    db: Session,
    outbox: FleetNotificationOutbox,
    *,
    sender: EmailSender,
    webpush_sender: WebPushSender,
) -> FleetNotificationOutbox:
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
            if channel.channel_type == FleetNotificationChannelType.EMAIL and _severity_rank(severity) < _severity_rank(
                FleetNotificationSeverity.HIGH
            ):
                continue
            if channel.channel_type == FleetNotificationChannelType.PUSH and _severity_rank(severity) < _severity_rank(
                FleetNotificationSeverity.HIGH
            ):
                continue
            attempted.append(channel.channel_type.value)
            if channel.channel_type == FleetNotificationChannelType.WEBHOOK:
                status_code, response_body = _send_webhook(
                    channel,
                    payload,
                    event_id=str(outbox.id),
                    event_type=outbox.event_type,
                )
                outbox.last_response_status = status_code
                outbox.last_response_body = response_body
                if status_code:
                    fleet_metrics.mark_webhook_response(f"{status_code // 100}xx")
                if status_code and status_code >= 400:
                    raise RuntimeError(f"webhook_status_{status_code}")
            elif channel.channel_type == FleetNotificationChannelType.EMAIL:
                outbox.delivery_message_id = _send_email(sender, channel, payload)
            elif channel.channel_type == FleetNotificationChannelType.PUSH:
                status_code, response_body = _send_push(db, webpush_sender, outbox.client_id, payload)
                outbox.last_response_status = status_code
                outbox.last_response_body = response_body[:500] if response_body else None
                if status_code and status_code >= 400:
                    raise RuntimeError(f"webpush_status_{status_code}")
        outbox.status = FleetNotificationOutboxStatus.SENT
        outbox.last_status = "sent"
        outbox.last_error = None
        outbox.channels_attempted = attempted
        fleet_metrics.mark_notification_outbox(outbox.status.value, outbox.event_type)
    except Exception as exc:  # pragma: no cover - defensive
        error = str(exc)[:500]
        outbox.attempts += 1
        outbox.last_error = error
        outbox.channels_attempted = attempted
        outbox.last_status = "failed"
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
    return outbox


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
        "route": "/client/fleet/notifications/alerts",
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
        "route": "/client/fleet/notifications/alerts",
        "amount": str(breach.observed),
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
        "route": "/client/fleet/notifications/alerts",
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
    "dispatch_outbox_item",
    "dispatch_pending_outbox",
    "enqueue_anomaly_notification",
    "enqueue_breach_notification",
    "enqueue_ingest_failed_notification",
    "enqueue_notification",
    "canonical_json",
    "sign_webhook_payload",
]
