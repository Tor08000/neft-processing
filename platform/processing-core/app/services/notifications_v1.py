from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.notifications import (
    NotificationChannel,
    NotificationDelivery,
    NotificationDeliveryStatus,
    NotificationMessage,
    NotificationOutboxStatus,
    NotificationPreference,
    NotificationPriority,
    NotificationSubjectType,
    NotificationTemplate,
    NotificationTemplateContentType,
    NotificationWebPushSubscription,
)
from app.services.notifications.email_sender import EmailSender, SmtpEmailSender
from app.services.notifications.telegram_sender import TelegramSendError, send_message
from app.services.notifications.webpush_sender import WebPushSender

logger = logging.getLogger(__name__)

BACKOFF_SECONDS = [60, 300, 900, 1800, 3600]
MAX_ATTEMPTS = 5


@dataclass(frozen=True)
class DeliveryTarget:
    channel: NotificationChannel
    recipient: str
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class DeliveryOutcome:
    status: NotificationDeliveryStatus
    provider: str
    provider_message_id: str | None
    response_status: int | None
    response_body: str | None
    error: str | None
    retry_after: int | None
    is_fatal: bool


class NotificationSendError(RuntimeError):
    def __init__(self, message: str, *, is_fatal: bool = False, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.is_fatal = is_fatal
        self.retry_after = retry_after


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _next_attempt(attempts: int, retry_after: int | None = None) -> datetime:
    if retry_after:
        return _now() + timedelta(seconds=retry_after)
    delay = BACKOFF_SECONDS[min(attempts, len(BACKOFF_SECONDS) - 1)]
    return _now() + timedelta(seconds=delay)


def _default_channels(event_type: str) -> list[NotificationChannel]:
    if event_type == "INVOICE_ISSUED":
        return [NotificationChannel.EMAIL]
    if event_type in {"SECURITY_OTP", "SECURITY/OTP"}:
        return [NotificationChannel.SMS]
    if event_type == "SYSTEM_ALERT":
        return [NotificationChannel.TELEGRAM]
    if event_type == "WEBHOOK_TEST":
        return [NotificationChannel.WEBHOOK]
    return []


def enqueue_notification_message(
    db: Session,
    *,
    event_type: str,
    subject_type: NotificationSubjectType,
    subject_id: str,
    template_code: str,
    template_vars: dict[str, Any] | None,
    priority: NotificationPriority = NotificationPriority.NORMAL,
    dedupe_key: str,
    channels: list[NotificationChannel] | None = None,
    aggregate_type: str | None = None,
    aggregate_id: str | None = None,
    tenant_client_id: str | None = None,
) -> NotificationMessage:
    existing = db.query(NotificationMessage).filter(NotificationMessage.dedupe_key == dedupe_key).one_or_none()
    if existing:
        return existing
    resolved_aggregate_type = aggregate_type or (
        subject_type.value.lower() if isinstance(subject_type, NotificationSubjectType) else str(subject_type).lower()
    )
    resolved_aggregate_id = str(aggregate_id or subject_id or dedupe_key)
    resolved_tenant_client_id = tenant_client_id
    if resolved_tenant_client_id is None:
        subject_type_value = subject_type.value if isinstance(subject_type, NotificationSubjectType) else str(subject_type)
        if subject_type_value.upper() == NotificationSubjectType.CLIENT.value:
            resolved_tenant_client_id = str(subject_id)
    message = NotificationMessage(
        event_type=event_type,
        subject_type=subject_type,
        subject_id=str(subject_id),
        aggregate_type=resolved_aggregate_type,
        aggregate_id=resolved_aggregate_id,
        tenant_client_id=str(resolved_tenant_client_id) if resolved_tenant_client_id is not None else None,
        channels=[
            channel.value if isinstance(channel, NotificationChannel) else str(channel) for channel in channels
        ]
        if channels
        else None,
        template_code=template_code,
        template_vars=template_vars or {},
        priority=priority,
        dedupe_key=dedupe_key,
        status=NotificationOutboxStatus.PENDING,
        attempts=0,
        next_attempt_at=_now(),
    )
    db.add(message)
    db.flush()
    return message


def _resolve_preferences(
    db: Session,
    *,
    subject_type: NotificationSubjectType,
    subject_id: str,
    event_type: str,
) -> dict[NotificationChannel, NotificationPreference]:
    prefs = (
        db.query(NotificationPreference)
        .filter(NotificationPreference.subject_type == subject_type)
        .filter(NotificationPreference.subject_id == str(subject_id))
        .filter(NotificationPreference.event_type == event_type)
        .all()
    )
    return {NotificationChannel(pref.channel): pref for pref in prefs}


def _resolve_recipient_from_subject(
    db: Session,
    *,
    subject_type: NotificationSubjectType,
    subject_id: str,
    channel: NotificationChannel,
    template_vars: dict[str, Any],
) -> str | None:
    if channel == NotificationChannel.EMAIL and subject_type == NotificationSubjectType.CLIENT:
        client = db.query(Client).filter(Client.id == subject_id).one_or_none()
        return client.email if client else None
    if channel == NotificationChannel.TELEGRAM:
        chat_id = template_vars.get("telegram_chat_id")
        return str(chat_id) if chat_id is not None else None
    if channel == NotificationChannel.SMS:
        phone = template_vars.get("phone")
        return str(phone) if phone is not None else None
    if channel == NotificationChannel.WEBHOOK:
        webhook_url = template_vars.get("webhook_url")
        return str(webhook_url) if webhook_url else None
    return None


def _resolve_delivery_targets(db: Session, message: NotificationMessage) -> list[DeliveryTarget]:
    channels = message.channels or []
    if channels:
        resolved_channels = [NotificationChannel(channel) for channel in channels]
    else:
        resolved_channels = _default_channels(message.event_type)

    preferences = _resolve_preferences(
        db,
        subject_type=message.subject_type,
        subject_id=message.subject_id,
        event_type=message.event_type,
    )
    targets: list[DeliveryTarget] = []
    template_vars = message.template_vars or {}

    for channel in resolved_channels:
        preference = preferences.get(channel)
        if preference and not preference.enabled:
            continue
        if channel == NotificationChannel.PUSH:
            subscriptions = (
                db.query(NotificationWebPushSubscription)
                .filter(NotificationWebPushSubscription.subject_type == message.subject_type)
                .filter(NotificationWebPushSubscription.subject_id == message.subject_id)
                .all()
            )
            for subscription in subscriptions:
                targets.append(
                    DeliveryTarget(
                        channel=channel,
                        recipient=subscription.endpoint,
                        metadata={
                            "subscription": {
                                "endpoint": subscription.endpoint,
                                "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
                            }
                        },
                    )
                )
            continue

        recipient = preference.address_override if preference and preference.address_override else None
        if not recipient:
            recipient = _resolve_recipient_from_subject(
                db,
                subject_type=message.subject_type,
                subject_id=message.subject_id,
                channel=channel,
                template_vars=template_vars,
            )
        if recipient:
            targets.append(DeliveryTarget(channel=channel, recipient=recipient))
    return targets


def _validate_required_vars(template: NotificationTemplate, template_vars: dict[str, Any]) -> None:
    required = template.required_vars or []
    missing = [key for key in required if key not in template_vars]
    if missing:
        raise NotificationSendError(f"missing_template_vars:{','.join(missing)}", is_fatal=True)


def _render_template(template: NotificationTemplate, template_vars: dict[str, Any]) -> tuple[str | None, str | None]:
    _validate_required_vars(template, template_vars)

    class Default(dict):
        def __missing__(self, key: str) -> str:
            return ""

    values = Default(template_vars)
    body = template.body.format_map(values)
    subject = template.subject.format_map(values) if template.subject else None
    if template.content_type == NotificationTemplateContentType.HTML:
        return subject, body
    return subject, body


def _signature_for_webhook(body: bytes, secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8") + body).hexdigest()


def _send_email(
    sender: EmailSender,
    *,
    to: str,
    subject: str,
    body: str,
    content_type: NotificationTemplateContentType,
) -> DeliveryOutcome:
    html = body if content_type == NotificationTemplateContentType.HTML else None
    text = body if content_type != NotificationTemplateContentType.HTML else None
    try:
        message_id = sender.send(to=to, subject=subject, html=html, text=text)
        return DeliveryOutcome(
            status=NotificationDeliveryStatus.SENT,
            provider="SMTP",
            provider_message_id=message_id,
            response_status=None,
            response_body=None,
            error=None,
            retry_after=None,
            is_fatal=False,
        )
    except Exception as exc:
        is_fatal = isinstance(exc, NotificationSendError) and exc.is_fatal
        return DeliveryOutcome(
            status=NotificationDeliveryStatus.FAILED,
            provider="SMTP",
            provider_message_id=None,
            response_status=None,
            response_body=None,
            error=str(exc),
            retry_after=getattr(exc, "retry_after", None),
            is_fatal=is_fatal,
        )


def _send_sms(to: str, body: str) -> DeliveryOutcome:
    url = os.getenv("SMS_PROVIDER_URL", "")
    token = os.getenv("SMS_PROVIDER_TOKEN", "")
    if not url:
        return DeliveryOutcome(
            status=NotificationDeliveryStatus.FAILED,
            provider="SMS_HTTP",
            provider_message_id=None,
            response_status=None,
            response_body=None,
            error="sms_provider_url_missing",
            retry_after=None,
            is_fatal=True,
        )
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload = {"to": to, "message": body}
    try:
        with httpx.Client(timeout=10) as client:
            response = client.post(url, headers=headers, json=payload)
        if response.status_code >= 500 or response.status_code == 429:
            return DeliveryOutcome(
                status=NotificationDeliveryStatus.RETRYING,
                provider="SMS_HTTP",
                provider_message_id=None,
                response_status=response.status_code,
                response_body=response.text[:500],
                error=f"sms_provider_error:{response.status_code}",
                retry_after=None,
                is_fatal=False,
            )
        if response.status_code >= 400:
            return DeliveryOutcome(
                status=NotificationDeliveryStatus.FAILED,
                provider="SMS_HTTP",
                provider_message_id=None,
                response_status=response.status_code,
                response_body=response.text[:500],
                error=f"sms_provider_error:{response.status_code}",
                retry_after=None,
                is_fatal=True,
            )
        provider_message_id = None
        try:
            payload_json = response.json()
            provider_message_id = str(payload_json.get("message_id")) if isinstance(payload_json, dict) else None
        except Exception:
            provider_message_id = None
        return DeliveryOutcome(
            status=NotificationDeliveryStatus.SENT,
            provider="SMS_HTTP",
            provider_message_id=provider_message_id,
            response_status=response.status_code,
            response_body=response.text[:500],
            error=None,
            retry_after=None,
            is_fatal=False,
        )
    except httpx.RequestError as exc:
        return DeliveryOutcome(
            status=NotificationDeliveryStatus.RETRYING,
            provider="SMS_HTTP",
            provider_message_id=None,
            response_status=None,
            response_body=None,
            error=str(exc),
            retry_after=None,
            is_fatal=False,
        )


def _send_telegram(chat_id: int, body: str) -> DeliveryOutcome:
    try:
        result = send_message(chat_id, body)
        return DeliveryOutcome(
            status=NotificationDeliveryStatus.SENT,
            provider="TELEGRAM_BOT",
            provider_message_id=result.message_id,
            response_status=result.status_code,
            response_body=result.body,
            error=None,
            retry_after=None,
            is_fatal=False,
        )
    except TelegramSendError as exc:
        status = NotificationDeliveryStatus.FAILED if exc.is_permanent else NotificationDeliveryStatus.RETRYING
        return DeliveryOutcome(
            status=status,
            provider="TELEGRAM_BOT",
            provider_message_id=None,
            response_status=exc.status_code,
            response_body=exc.body,
            error=str(exc),
            retry_after=exc.retry_after,
            is_fatal=exc.is_permanent,
        )


def _send_webhook(url: str, payload: dict[str, Any]) -> DeliveryOutcome:
    secret = os.getenv("WEBHOOK_SIGNING_SECRET", "")
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if secret:
        signature = _signature_for_webhook(body, secret)
        headers["X-Signature"] = signature
    try:
        with httpx.Client(timeout=10) as client:
            response = client.post(url, content=body, headers=headers)
        if response.status_code >= 500 or response.status_code == 429:
            return DeliveryOutcome(
                status=NotificationDeliveryStatus.RETRYING,
                provider="WEBHOOK",
                provider_message_id=None,
                response_status=response.status_code,
                response_body=response.text[:500],
                error=f"webhook_error:{response.status_code}",
                retry_after=None,
                is_fatal=False,
            )
        if response.status_code >= 400:
            return DeliveryOutcome(
                status=NotificationDeliveryStatus.FAILED,
                provider="WEBHOOK",
                provider_message_id=None,
                response_status=response.status_code,
                response_body=response.text[:500],
                error=f"webhook_error:{response.status_code}",
                retry_after=None,
                is_fatal=True,
            )
        return DeliveryOutcome(
            status=NotificationDeliveryStatus.SENT,
            provider="WEBHOOK",
            provider_message_id=None,
            response_status=response.status_code,
            response_body=response.text[:500],
            error=None,
            retry_after=None,
            is_fatal=False,
        )
    except httpx.RequestError as exc:
        return DeliveryOutcome(
            status=NotificationDeliveryStatus.RETRYING,
            provider="WEBHOOK",
            provider_message_id=None,
            response_status=None,
            response_body=None,
            error=str(exc),
            retry_after=None,
            is_fatal=False,
        )


def _send_webpush(subscription: dict[str, Any], payload: dict[str, Any]) -> DeliveryOutcome:
    sender = WebPushSender()
    try:
        response = sender.send(subscription, payload)
        if response.status_code >= 500:
            return DeliveryOutcome(
                status=NotificationDeliveryStatus.RETRYING,
                provider="WEBPUSH",
                provider_message_id=None,
                response_status=response.status_code,
                response_body=response.body,
                error="webpush_error",
                retry_after=None,
                is_fatal=False,
            )
        if response.status_code in {404, 410}:
            return DeliveryOutcome(
                status=NotificationDeliveryStatus.FAILED,
                provider="WEBPUSH",
                provider_message_id=None,
                response_status=response.status_code,
                response_body=response.body,
                error="webpush_gone",
                retry_after=None,
                is_fatal=True,
            )
        return DeliveryOutcome(
            status=NotificationDeliveryStatus.SENT,
            provider="WEBPUSH",
            provider_message_id=None,
            response_status=response.status_code,
            response_body=response.body,
            error=None,
            retry_after=None,
            is_fatal=False,
        )
    except Exception as exc:
        return DeliveryOutcome(
            status=NotificationDeliveryStatus.RETRYING,
            provider="WEBPUSH",
            provider_message_id=None,
            response_status=None,
            response_body=None,
            error=str(exc),
            retry_after=None,
            is_fatal=False,
        )


def _deliver_to_target(
    db: Session,
    *,
    message: NotificationMessage,
    target: DeliveryTarget,
    template: NotificationTemplate,
) -> DeliveryOutcome:
    template_vars = message.template_vars or {}
    subject, body = _render_template(template, template_vars)
    if target.channel == NotificationChannel.EMAIL:
        if not subject:
            raise NotificationSendError("email_subject_missing", is_fatal=True)
        sender = SmtpEmailSender()
        return _send_email(
            sender,
            to=target.recipient,
            subject=subject,
            body=body,
            content_type=template.content_type,
        )
    if target.channel == NotificationChannel.SMS:
        return _send_sms(target.recipient, body)
    if target.channel == NotificationChannel.TELEGRAM:
        return _send_telegram(int(target.recipient), body)
    if target.channel == NotificationChannel.WEBHOOK:
        payload = {
            "event_type": message.event_type,
            "message_id": str(message.id),
            "timestamp": _now().isoformat(),
            "data": template_vars,
        }
        return _send_webhook(target.recipient, payload)
    if target.channel == NotificationChannel.PUSH:
        payload = {
            "title": template_vars.get("title") or message.event_type,
            "body": body,
        }
        subscription = target.metadata.get("subscription") if target.metadata else None
        if not subscription:
            raise NotificationSendError("webpush_subscription_missing", is_fatal=True)
        return _send_webpush(subscription, payload)
    raise NotificationSendError("unsupported_channel", is_fatal=True)


def _load_template(db: Session, message: NotificationMessage, channel: NotificationChannel) -> NotificationTemplate:
    template = (
        db.query(NotificationTemplate)
        .filter(NotificationTemplate.code == message.template_code)
        .filter(NotificationTemplate.channel == channel)
        .filter(NotificationTemplate.is_active.is_(True))
        .one_or_none()
    )
    if not template:
        raise NotificationSendError("template_missing", is_fatal=True)
    return template


def _get_or_create_delivery(db: Session, message: NotificationMessage, target: DeliveryTarget) -> NotificationDelivery:
    delivery = (
        db.query(NotificationDelivery)
        .filter(NotificationDelivery.message_id == message.id)
        .filter(NotificationDelivery.channel == target.channel)
        .filter(NotificationDelivery.recipient == target.recipient)
        .one_or_none()
    )
    if delivery:
        return delivery
    delivery = NotificationDelivery(
        message_id=message.id,
        event_type=message.event_type,
        channel=target.channel,
        provider="",
        recipient=target.recipient,
        status=NotificationDeliveryStatus.PENDING,
        attempt=0,
    )
    db.add(delivery)
    db.flush()
    return delivery


def dispatch_pending_notifications(db: Session, *, limit: int = 50) -> list[NotificationMessage]:
    now = _now()
    messages = (
        db.query(NotificationMessage)
        .filter(NotificationMessage.status == NotificationOutboxStatus.PENDING)
        .filter(NotificationMessage.next_attempt_at <= now)
        .order_by(NotificationMessage.created_at)
        .limit(limit)
        .all()
    )

    for message in messages:
        targets = _resolve_delivery_targets(db, message)
        if not targets:
            message.status = NotificationOutboxStatus.FAILED
            message.last_error = "no_delivery_targets"
            message.attempts += 1
            message.next_attempt_at = None
            continue

        overall_retry = False
        overall_failed = False
        last_error = None
        for target in targets:
            delivery = _get_or_create_delivery(db, message, target)
            if delivery.status in {NotificationDeliveryStatus.SENT, NotificationDeliveryStatus.DELIVERED}:
                continue
            if delivery.attempt >= MAX_ATTEMPTS:
                delivery.status = NotificationDeliveryStatus.FAILED
                delivery.last_error = delivery.last_error or "max_attempts_reached"
                overall_failed = True
                last_error = delivery.last_error
                continue
            try:
                template = _load_template(db, message, target.channel)
                outcome = _deliver_to_target(db, message=message, target=target, template=template)
            except NotificationSendError as exc:
                outcome = DeliveryOutcome(
                    status=NotificationDeliveryStatus.FAILED,
                    provider="",
                    provider_message_id=None,
                    response_status=None,
                    response_body=None,
                    error=str(exc),
                    retry_after=exc.retry_after,
                    is_fatal=exc.is_fatal,
                )
            delivery.attempt += 1
            delivery.provider = outcome.provider
            delivery.provider_message_id = outcome.provider_message_id
            delivery.response_status = outcome.response_status
            delivery.response_body = outcome.response_body
            delivery.last_error = outcome.error
            if outcome.status == NotificationDeliveryStatus.RETRYING and not outcome.is_fatal:
                delivery.status = NotificationDeliveryStatus.RETRYING
                overall_retry = True
            elif outcome.status == NotificationDeliveryStatus.SENT:
                delivery.status = NotificationDeliveryStatus.SENT
                delivery.sent_at = _now()
            else:
                delivery.status = NotificationDeliveryStatus.FAILED
                overall_failed = True
                last_error = delivery.last_error

        message.attempts += 1
        if overall_retry and message.attempts < MAX_ATTEMPTS:
            message.status = NotificationOutboxStatus.PENDING
            message.next_attempt_at = _next_attempt(message.attempts)
        elif overall_failed:
            message.status = NotificationOutboxStatus.FAILED
            message.last_error = last_error
            message.next_attempt_at = None
        else:
            message.status = NotificationOutboxStatus.SENT
            message.next_attempt_at = None
    return messages


def replay_delivery(db: Session, delivery_id: str) -> NotificationDelivery | None:
    delivery = db.query(NotificationDelivery).filter(NotificationDelivery.id == delivery_id).one_or_none()
    if not delivery:
        return None
    message = db.query(NotificationMessage).filter(NotificationMessage.id == delivery.message_id).one_or_none()
    if not message:
        return delivery
    message.status = NotificationOutboxStatus.PENDING
    message.next_attempt_at = _now()
    delivery.status = NotificationDeliveryStatus.RETRYING
    return delivery


__all__ = [
    "dispatch_pending_notifications",
    "enqueue_notification_message",
    "replay_delivery",
]
