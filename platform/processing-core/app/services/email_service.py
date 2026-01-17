from __future__ import annotations

import logging
import os
import smtplib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from typing import Mapping

from app.celery_client import celery_client
from app.db import get_sessionmaker
from app.models.audit_log import ActorType, AuditVisibility
from app.models.client_notification import ClientNotification
from app.models.email_outbox import EmailOutbox, EmailOutboxStatus
from app.services.audit_service import AuditService, RequestContext
from app.services.email_templates import render_email_template

logger = logging.getLogger(__name__)

BACKOFF_SECONDS = [60, 300, 900, 3600, 21600]
MAX_ATTEMPTS = 6


@dataclass(frozen=True)
class SendResult:
    status: str
    provider_message_id: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class EmailSettings:
    mode: str
    host: str
    port: int
    username: str | None
    password: str | None
    use_tls: bool
    use_ssl: bool
    from_email: str
    from_name: str | None
    reply_to: str | None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _next_retry_at(attempts_count: int) -> datetime:
    index = min(attempts_count - 1, len(BACKOFF_SECONDS) - 1)
    return _now() + timedelta(seconds=BACKOFF_SECONDS[index])


def _load_settings() -> EmailSettings:
    mode = os.getenv("NEFT_EMAIL_MODE", "mailpit").lower()
    host = os.getenv("NEFT_EMAIL_HOST", "")
    port = int(os.getenv("NEFT_EMAIL_PORT", "587"))
    username = os.getenv("NEFT_EMAIL_USERNAME")
    password = os.getenv("NEFT_EMAIL_PASSWORD")
    use_tls = os.getenv("NEFT_EMAIL_USE_TLS", "true").lower() in {"1", "true", "yes"}
    use_ssl = os.getenv("NEFT_EMAIL_USE_SSL", "false").lower() in {"1", "true", "yes"}
    from_email = os.getenv("NEFT_EMAIL_FROM_EMAIL", "") or username or "no-reply@neft.local"
    from_name = os.getenv("NEFT_EMAIL_FROM_NAME")
    reply_to = os.getenv("NEFT_EMAIL_REPLY_TO")

    if mode == "mailpit":
        host = host or "mailpit"
        port = int(os.getenv("NEFT_EMAIL_PORT", "1025"))
        use_tls = os.getenv("NEFT_EMAIL_USE_TLS", "false").lower() in {"1", "true", "yes"}
        use_ssl = os.getenv("NEFT_EMAIL_USE_SSL", "false").lower() in {"1", "true", "yes"}

    return EmailSettings(
        mode=mode,
        host=host,
        port=port,
        username=username,
        password=password,
        use_tls=use_tls,
        use_ssl=use_ssl,
        from_email=from_email,
        from_name=from_name,
        reply_to=reply_to,
    )


def _smtp_recipient_error_code(exc: smtplib.SMTPRecipientsRefused) -> int | None:
    codes = []
    for response in exc.recipients.values():
        if isinstance(response, tuple) and response:
            try:
                codes.append(int(response[0]))
            except (TypeError, ValueError):
                continue
    return max(codes) if codes else None


def _is_retryable_smtp_error(exc: Exception) -> tuple[bool, int | None]:
    if isinstance(exc, smtplib.SMTPResponseException):
        if 400 <= exc.smtp_code < 500:
            return True, None
        return False, None
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        code = _smtp_recipient_error_code(exc)
        if code is not None and 400 <= code < 500:
            return True, None
        return False, None
    if isinstance(
        exc,
        (
            smtplib.SMTPServerDisconnected,
            smtplib.SMTPConnectError,
            smtplib.SMTPHeloError,
            TimeoutError,
        ),
    ):
        return True, None
    return False, None


def _send_smtp_email(
    *,
    settings: EmailSettings,
    to: list[str],
    subject: str,
    text_body: str,
    html_body: str | None,
    tags: Mapping[str, str] | None,
) -> str:
    if not settings.host:
        raise RuntimeError("smtp_host_missing")
    message = EmailMessage()
    message_id = make_msgid(domain="neft.local")
    message["Message-ID"] = message_id
    message["From"] = formataddr((settings.from_name, settings.from_email)) if settings.from_name else settings.from_email
    message["To"] = ", ".join(to)
    message["Subject"] = subject
    if settings.reply_to:
        message["Reply-To"] = settings.reply_to
    if tags:
        for key, value in tags.items():
            message[f"X-Tag-{key}"] = str(value)

    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype="html")

    smtp_factory = smtplib.SMTP_SSL if settings.use_ssl else smtplib.SMTP
    with smtp_factory(settings.host, settings.port, timeout=10) as smtp:
        if settings.use_tls and not settings.use_ssl:
            smtp.starttls()
        if settings.username and settings.password:
            smtp.login(settings.username, settings.password)
        smtp.send_message(message)
    return message_id


def _audit_email_event(
    db,
    *,
    event_type: str,
    outbox: EmailOutbox,
    error: str | None = None,
) -> None:
    request_ctx = RequestContext(actor_type=ActorType.SERVICE, actor_id="email_service")
    AuditService(db).audit(
        event_type=event_type,
        entity_type="email_outbox",
        entity_id=str(outbox.id),
        action=event_type,
        visibility=AuditVisibility.INTERNAL,
        after={
            "status": outbox.status.value,
            "subject": outbox.subject,
            "provider": outbox.provider,
            "provider_message_id": outbox.provider_message_id,
            "error": error,
        },
        request_ctx=request_ctx,
    )


def enqueue_email(
    db,
    *,
    to: list[str],
    subject: str,
    text_body: str,
    html_body: str | None,
    tags: Mapping[str, str] | None,
    idempotency_key: str,
    org_id: str | None,
    user_id: str | None,
    template_key: str | None,
) -> EmailOutbox:
    existing = db.query(EmailOutbox).filter(EmailOutbox.idempotency_key == idempotency_key).one_or_none()
    if existing:
        if existing.status == EmailOutboxStatus.FAILED:
            existing.status = EmailOutboxStatus.QUEUED
            existing.next_retry_at = _now()
        return existing

    outbox = EmailOutbox(
        org_id=org_id,
        user_id=user_id,
        idempotency_key=idempotency_key,
        to_emails=to,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        tags=dict(tags) if tags else None,
        template_key=template_key,
        status=EmailOutboxStatus.QUEUED,
        attempts_count=0,
        next_retry_at=_now(),
    )
    db.add(outbox)
    db.flush()

    try:
        celery_client.send_task("emails.send_outbox", args=[str(outbox.id)])
    except Exception as exc:  # noqa: BLE001
        logger.warning("email_outbox.enqueue_failed", extra={"outbox_id": str(outbox.id), "error": str(exc)})

    return outbox


def enqueue_templated_email(
    db,
    *,
    template_key: str,
    to: list[str],
    idempotency_key: str,
    org_id: str | None,
    user_id: str | None,
    context: dict[str, str],
    tags: Mapping[str, str] | None = None,
) -> EmailOutbox:
    subject, text_body, html_body = render_email_template(template_key, context)
    return enqueue_email(
        db,
        to=to,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        tags=tags,
        idempotency_key=idempotency_key,
        org_id=org_id,
        user_id=user_id,
        template_key=template_key,
    )


def build_idempotency_key(event_type: str, org_id: str, entity_id: str, job_id: str | None = None) -> str:
    parts = [event_type, org_id, entity_id]
    if job_id:
        parts.append(job_id)
    return ":".join(parts)


def deliver_outbox_email(db, *, outbox: EmailOutbox) -> tuple[SendResult, int | None]:
    if outbox.status == EmailOutboxStatus.SENT:
        return SendResult(status="SKIPPED"), None
    if outbox.attempts_count >= MAX_ATTEMPTS:
        outbox.status = EmailOutboxStatus.FAILED
        outbox.last_error = outbox.last_error or "max_attempts_reached"
        outbox.next_retry_at = None
        return SendResult(status="FAILED", error=outbox.last_error), None

    settings = _load_settings()
    if settings.mode == "disabled":
        outbox.status = EmailOutboxStatus.FAILED
        outbox.last_error = "email_disabled"
        outbox.next_retry_at = None
        _audit_email_event(db, event_type="email_failed", outbox=outbox, error=outbox.last_error)
        return SendResult(status="FAILED", error=outbox.last_error), None

    outbox.attempts_count += 1
    try:
        message_id = _send_smtp_email(
            settings=settings,
            to=list(outbox.to_emails or []),
            subject=outbox.subject,
            text_body=outbox.text_body or "",
            html_body=outbox.html_body,
            tags=outbox.tags,
        )
        outbox.status = EmailOutboxStatus.SENT
        outbox.provider = "SMTP" if settings.mode == "smtp" else "MAILPIT"
        outbox.provider_message_id = message_id
        outbox.sent_at = _now()
        outbox.next_retry_at = None
        outbox.last_error = None
        _audit_email_event(db, event_type="email_sent", outbox=outbox)

        notification_id = None
        if isinstance(outbox.tags, dict):
            notification_id = outbox.tags.get("client_notification_id")
        if notification_id:
            notification = db.query(ClientNotification).filter(ClientNotification.id == notification_id).one_or_none()
            if notification and not notification.delivered_email_at:
                notification.delivered_email_at = _now()
        return SendResult(status="SENT", provider_message_id=message_id), None
    except Exception as exc:  # noqa: BLE001
        retryable, _ = _is_retryable_smtp_error(exc)
        outbox.last_error = str(exc)
        if retryable and outbox.attempts_count < MAX_ATTEMPTS:
            outbox.status = EmailOutboxStatus.QUEUED
            outbox.next_retry_at = _next_retry_at(outbox.attempts_count)
            _audit_email_event(db, event_type="email_failed", outbox=outbox, error=outbox.last_error)
            delay = int((outbox.next_retry_at - _now()).total_seconds())
            return SendResult(status="FAILED", error=outbox.last_error), max(delay, 1)
        outbox.status = EmailOutboxStatus.FAILED
        outbox.next_retry_at = None
        _audit_email_event(db, event_type="email_failed", outbox=outbox, error=outbox.last_error)
        return SendResult(status="FAILED", error=outbox.last_error), None


def deliver_outbox_email_by_id(outbox_id: str) -> SendResult:
    session = get_sessionmaker()()
    try:
        outbox = session.get(EmailOutbox, outbox_id)
        if not outbox:
            return SendResult(status="FAILED", error="outbox_not_found")
        if outbox.status == EmailOutboxStatus.SENT:
            return SendResult(status="SKIPPED")
        if outbox.next_retry_at and outbox.next_retry_at > _now():
            return SendResult(status="SKIPPED")
        result, _ = deliver_outbox_email(session, outbox=outbox)
        session.commit()
        return result
    except Exception:  # noqa: BLE001
        session.rollback()
        raise
    finally:
        session.close()


__all__ = [
    "EmailOutboxStatus",
    "SendResult",
    "deliver_outbox_email",
    "deliver_outbox_email_by_id",
    "build_idempotency_key",
    "enqueue_email",
    "enqueue_templated_email",
]
