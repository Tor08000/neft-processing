from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib import error as url_error
from urllib import request
from uuid import uuid4

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
    FleetTelegramBinding,
    FleetTelegramBindingScopeType,
    FleetTelegramBindingStatus,
    FuelCard,
    FuelCardGroup,
    FuelAnomaly,
    FuelLimitBreach,
    WebhookDeliveryAttempt,
)
from app.security.rbac.principal import Principal
from app.services import fleet_service
from app.services.case_event_redaction import redact_deep
from app.services.fleet_metrics import metrics as fleet_metrics
from app.services.notifications.email_sender import ConsoleEmailSender, EmailSender, SmtpEmailSender
from app.services.notifications.email_templates import render_notification_email
from app.services.notifications.telegram_sender import TelegramSendError, send_message
from app.services.notifications.telegram_templates import render_telegram_message
from app.services.notifications.stub_sender import process_stub_delivery_outcomes, send_stub_message
from app.services.notifications.webhook_signature import build_signature_headers, sign_webhook_v1
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


def _telegram_dedupe_key(client_id: str, event_ref_id: str, binding_id: str) -> str:
    return f"client:{client_id}:evt:{event_ref_id}:tg:{binding_id}"


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=False)


def sign_webhook_payload(
    payload: dict[str, Any],
    secret: str,
    *,
    timestamp: str,
    nonce: str,
    event_id: str,
) -> str:
    body = canonical_json(payload).encode("utf-8")
    return sign_webhook_v1(secret=secret, timestamp=timestamp, nonce=nonce, event_id=event_id, body=body)


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
) -> tuple[int | None, str | None, str, str]:
    secret = channel.secret_ref or ""
    timestamp = str(int(_now().timestamp()))
    nonce = str(uuid4())
    body = canonical_json(payload).encode("utf-8")
    signature = sign_webhook_payload(payload, secret, timestamp=timestamp, nonce=nonce, event_id=event_id)
    headers = {
        "Content-Type": "application/json",
        **build_signature_headers(event_id=event_id, timestamp=timestamp, nonce=nonce, signature=signature),
    }
    req = request.Request(
        channel.target,
        data=body,
        method="POST",
        headers=headers,
    )
    try:
        with request.urlopen(req, timeout=5) as response:
            body_text = response.read().decode("utf-8")[:500]
            return response.status, body_text, nonce, timestamp
    except url_error.HTTPError as exc:
        body_text = exc.read().decode("utf-8")[:500] if exc.fp else None
        return exc.code, body_text, nonce, timestamp


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


def _send_stub_notification(
    db: Session,
    *,
    outbox: FleetNotificationOutbox,
    channel: FleetNotificationChannel,
    payload: dict[str, Any],
    provider: str,
) -> str:
    if provider not in {"sms_stub", "voice_stub"}:
        raise RuntimeError("unsupported_stub_provider")
    tenant_id = payload.get("tenant_id")
    result = send_stub_message(
        db,
        tenant_id=str(tenant_id) if tenant_id else None,
        channel=channel.channel_type.value,
        provider=provider,
        recipient=channel.target,
        payload=payload,
    )
    return result.message_id


def _process_stub_delivery_outcomes(db: Session) -> None:
    sms_delay = int(os.getenv("SMS_STUB_DELIVERY_DELAY_MS", "1000"))
    sms_fail_rate = float(os.getenv("SMS_STUB_FAIL_RATE", "0.0"))
    voice_delay = int(os.getenv("VOICE_STUB_DELIVERY_DELAY_MS", "1000"))
    voice_fail_rate = float(os.getenv("VOICE_STUB_FAIL_RATE", "0.0"))
    process_stub_delivery_outcomes(
        db,
        provider="sms_stub",
        channel=FleetNotificationChannelType.SMS.value,
        delay_ms=sms_delay,
        fail_rate=sms_fail_rate,
    )
    process_stub_delivery_outcomes(
        db,
        provider="voice_stub",
        channel=FleetNotificationChannelType.VOICE.value,
        delay_ms=voice_delay,
        fail_rate=voice_fail_rate,
    )


def _parse_telegram_binding_id(channel: FleetNotificationChannel) -> str | None:
    if not channel.target.startswith("telegram:"):
        return None
    return channel.target.split("telegram:", 1)[-1] or None


def _sent_telegram_bindings(entries: list[Any]) -> set[str]:
    sent: set[str] = set()
    for entry in entries:
        if isinstance(entry, dict) and entry.get("channel") == FleetNotificationChannelType.TELEGRAM.value:
            if entry.get("status") == "sent" and entry.get("binding_id"):
                sent.add(str(entry["binding_id"]))
    return sent


def _attempted_channel_names(entries: list[Any]) -> list[str]:
    names: list[str] = []
    for entry in entries:
        if isinstance(entry, dict):
            channel = entry.get("channel")
            if channel:
                names.append(str(channel))
        elif isinstance(entry, str):
            names.append(entry)
    return names


def _log_webhook_attempt(
    db: Session,
    *,
    endpoint_id: str,
    event_id: str,
    attempt_no: int,
    status: str,
    http_status: int | None,
    response_body: str | None,
    next_retry_at: datetime | None,
) -> WebhookDeliveryAttempt:
    attempt = WebhookDeliveryAttempt(
        event_id=event_id,
        endpoint_id=endpoint_id,
        attempt_no=attempt_no,
        status=status,
        http_status=http_status,
        response_body_snippet=response_body[:500] if response_body else None,
        next_retry_at=next_retry_at,
        dedupe_key=f\"{endpoint_id}:{event_id}\",
    )
    db.add(attempt)
    db.flush()
    return attempt


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
    _process_stub_delivery_outcomes(db)
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
    dispatched = _dispatch_outbox_item(db, outbox, sender=sender, webpush_sender=webpush_sender)
    _process_stub_delivery_outcomes(db)
    return dispatched


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
    existing_attempts = outbox.channels_attempted or []
    attempted: list[Any] = list(existing_attempts) if isinstance(existing_attempts, list) else []
    sent_telegram = _sent_telegram_bindings(attempted)
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
            if channel.channel_type == FleetNotificationChannelType.TELEGRAM:
                binding_id = _parse_telegram_binding_id(channel)
                if not binding_id or binding_id in sent_telegram:
                    continue
                binding = db.query(FleetTelegramBinding).filter(FleetTelegramBinding.id == binding_id).one_or_none()
                if not binding or binding.status != FleetTelegramBindingStatus.ACTIVE:
                    continue
                if binding.scope_type == FleetTelegramBindingScopeType.GROUP and (
                    not payload.get("group_id") or str(binding.scope_id) != str(payload.get("group_id"))
                ):
                    continue
                message = render_telegram_message(payload)
                try:
                    result = send_message(binding.chat_id, message)
                except TelegramSendError as exc:
                    outbox.last_response_status = exc.status_code
                    outbox.last_response_body = exc.body
                    if exc.is_permanent:
                        binding.status = FleetTelegramBindingStatus.DISABLED
                        channel.status = FleetNotificationChannelStatus.DISABLED
                        binding.audit_event_id = fleet_service._emit_event(
                            db,
                            client_id=outbox.client_id,
                            principal=None,
                            request_id=None,
                            trace_id=None,
                            event_type=CaseEventType.FLEET_TELEGRAM_SEND_FAILED,
                            payload={
                                "binding_id": str(binding.id),
                                "chat_id": binding.chat_id,
                                "status_code": exc.status_code,
                            },
                        )
                    raise
                attempted.append(
                    {
                        "channel": FleetNotificationChannelType.TELEGRAM.value,
                        "binding_id": binding_id,
                        "status": "sent",
                        "dedupe_key": _telegram_dedupe_key(outbox.client_id, str(outbox.event_ref_id), binding_id),
                    }
                )
                sent_telegram.add(binding_id)
                if result.message_id:
                    outbox.delivery_message_id = result.message_id
                continue
            attempted.append(channel.channel_type.value)
            if channel.channel_type == FleetNotificationChannelType.WEBHOOK:
                attempt_no = outbox.attempts + 1
                next_retry_at: datetime | None = None
                status_code = None
                response_body = None
                delivery_status = "SENT"
                try:
                    status_code, response_body, _, _ = _send_webhook(
                        channel,
                        payload,
                        event_id=str(outbox.id),
                    )
                    outbox.last_response_status = status_code
                    outbox.last_response_body = response_body
                    if status_code:
                        fleet_metrics.mark_webhook_response(f"{status_code // 100}xx")
                    if status_code and status_code >= 400:
                        delivery_status = "FAILED"
                        raise RuntimeError(f"webhook_status_{status_code}")
                except Exception:
                    delivery_status = "FAILED"
                    next_retry_at = _next_attempt(attempt_no)
                    raise
                finally:
                    _log_webhook_attempt(
                        db,
                        endpoint_id=str(channel.id),
                        event_id=str(outbox.id),
                        attempt_no=attempt_no,
                        status=delivery_status,
                        http_status=status_code,
                        response_body=response_body,
                        next_retry_at=next_retry_at,
                    )
            elif channel.channel_type == FleetNotificationChannelType.EMAIL:
                outbox.delivery_message_id = _send_email(sender, channel, payload)
            elif channel.channel_type == FleetNotificationChannelType.PUSH:
                status_code, response_body = _send_push(db, webpush_sender, outbox.client_id, payload)
                outbox.last_response_status = status_code
                outbox.last_response_body = response_body[:500] if response_body else None
                if status_code and status_code >= 400:
                    raise RuntimeError(f"webpush_status_{status_code}")
            elif channel.channel_type == FleetNotificationChannelType.SMS:
                outbox.delivery_message_id = _send_stub_notification(
                    db,
                    outbox=outbox,
                    channel=channel,
                    payload=payload,
                    provider=os.getenv(\"SMS_PROVIDER\", \"sms_stub\"),
                )
            elif channel.channel_type == FleetNotificationChannelType.VOICE:
                outbox.delivery_message_id = _send_stub_notification(
                    db,
                    outbox=outbox,
                    channel=channel,
                    payload=payload,
                    provider=os.getenv(\"VOICE_PROVIDER\", \"voice_stub\"),
                )
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
            if isinstance(exc, TelegramSendError) and exc.retry_after:
                outbox.next_attempt_at = _now() + timedelta(seconds=exc.retry_after)
            else:
                outbox.next_attempt_at = _next_attempt(outbox.attempts)
        fleet_metrics.mark_notification_outbox(outbox.status.value, outbox.event_type)
    finally:
        elapsed = (_now() - start).total_seconds()
        attempted_channels = _attempted_channel_names(attempted)
        if attempted_channels:
            fleet_metrics.observe_notification_delivery("+".join(attempted_channels), elapsed)
    return outbox


def enqueue_anomaly_notification(
    db: Session,
    *,
    anomaly: FuelAnomaly,
    principal: Principal | None,
    request_id: str | None,
    trace_id: str | None,
) -> FleetNotificationOutbox:
    card_alias = None
    group_id = anomaly.group_id
    group_name = None
    link_id = None
    if anomaly.card_id:
        card = db.query(FuelCard).filter(FuelCard.id == anomaly.card_id).one_or_none()
        if card:
            card_alias = card.card_alias
            link_id = str(card.id)
            if not group_id:
                group_id = card.card_group_id
    if group_id:
        group = db.query(FuelCardGroup).filter(FuelCardGroup.id == group_id).one_or_none()
        if group:
            group_name = group.name
    payload = {
        "client_id": anomaly.client_id,
        "event_type": FleetNotificationEventType.ANOMALY.value,
        "severity": anomaly.severity.value,
        "card_id": str(anomaly.card_id) if anomaly.card_id else None,
        "group_id": str(group_id) if group_id else None,
        "alias": card_alias,
        "group_label": group_name,
        "tx_id": str(anomaly.tx_id) if anomaly.tx_id else None,
        "link_type": "card" if link_id else None,
        "link_id": link_id,
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
    card_alias = None
    group_id = None
    group_name = None
    link_id = None
    if breach.scope_type.value == "card":
        card = db.query(FuelCard).filter(FuelCard.id == breach.scope_id).one_or_none()
        if card:
            card_alias = card.card_alias
            link_id = str(card.id)
            group_id = card.card_group_id
    if breach.scope_type.value == "group":
        group_id = breach.scope_id
    if group_id:
        group = db.query(FuelCardGroup).filter(FuelCardGroup.id == group_id).one_or_none()
        if group:
            group_name = group.name
    payload = {
        "client_id": breach.client_id,
        "event_type": FleetNotificationEventType.LIMIT_BREACH.value,
        "severity": severity.value,
        "card_id": str(breach.scope_id) if breach.scope_type.value == "card" else None,
        "group_id": str(group_id) if group_id else None,
        "alias": card_alias,
        "group_label": group_name,
        "link_type": "card" if link_id else None,
        "link_id": link_id,
        "tx_id": str(breach.tx_id) if breach.tx_id else None,
        "route": "/client/fleet/notifications/alerts",
        "amount": str(breach.observed),
        "summary": {
            "breach_type": breach.breach_type.value,
            "threshold": str(breach.threshold),
            "observed": str(breach.observed),
            "delta": str(breach.delta),
            "period": breach.period.value,
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
