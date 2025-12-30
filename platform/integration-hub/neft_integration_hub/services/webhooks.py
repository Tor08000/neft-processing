from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from neft_integration_hub.events import build_event, publish_event
from neft_integration_hub.metrics import (
    WEBHOOK_DELIVERY_LATENCY_SECONDS,
    WEBHOOK_DELIVERY_SLA_BREACHES_TOTAL,
)
from neft_integration_hub.models import (
    WebhookAlert,
    WebhookAlertType,
    WebhookDelivery,
    WebhookDeliveryStatus,
    WebhookEndpoint,
    WebhookEndpointStatus,
    WebhookReplay,
    WebhookSigningAlgo,
    WebhookSubscription,
)
from neft_integration_hub.schemas import WebhookEventEnvelope, WebhookOwner
from neft_integration_hub.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


_BACKOFF_MINUTES = [1, 2, 5, 10, 30, 60, 180]
_SLA_WINDOW_SECONDS = {"5m": 300, "15m": 900, "1h": 3600, "30m": 1800}
_ALERT_WINDOW = "30m"
_PAUSE_ALERT_SECONDS = 3600


def generate_secret() -> str:
    return secrets.token_hex(32)


def _derive_key_bytes(key: str) -> bytes:
    return hashlib.sha256(key.encode("utf-8")).digest()


def encrypt_secret(secret: str) -> str:
    key_bytes = _derive_key_bytes(settings.webhook_secret_key)
    secret_bytes = secret.encode("utf-8")
    cipher = bytes(byte ^ key_bytes[idx % len(key_bytes)] for idx, byte in enumerate(secret_bytes))
    return base64.urlsafe_b64encode(cipher).decode("utf-8")


def decrypt_secret(secret_encrypted: str) -> str:
    key_bytes = _derive_key_bytes(settings.webhook_secret_key)
    cipher = base64.urlsafe_b64decode(secret_encrypted.encode("utf-8"))
    secret_bytes = bytes(byte ^ key_bytes[idx % len(key_bytes)] for idx, byte in enumerate(cipher))
    return secret_bytes.decode("utf-8")


def build_event_envelope(
    *,
    event_id: str,
    event_type: str,
    correlation_id: str,
    owner: WebhookOwner,
    payload: dict,
    schema_version: int = 1,
    occurred_at: datetime | None = None,
    ) -> WebhookEventEnvelope:
    return WebhookEventEnvelope(
        event_id=event_id,
        event_type=event_type,
        occurred_at=(occurred_at or datetime.now(timezone.utc)).isoformat(),
        schema_version=schema_version,
        correlation_id=correlation_id,
        owner=owner,
        payload=payload,
    )


def _parse_occurred_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def create_endpoint(
    db: Session,
    *,
    owner_type: str,
    owner_id: str,
    url: str,
    signing_algo: str = WebhookSigningAlgo.HMAC_SHA256.value,
) -> tuple[WebhookEndpoint, str]:
    secret = generate_secret()
    endpoint = WebhookEndpoint(
        owner_type=owner_type,
        owner_id=owner_id,
        url=url,
        status=WebhookEndpointStatus.ACTIVE.value,
        signing_algo=signing_algo,
        secret_encrypted=encrypt_secret(secret),
    )
    db.add(endpoint)
    db.commit()
    db.refresh(endpoint)
    return endpoint, secret


def rotate_secret(db: Session, endpoint: WebhookEndpoint) -> str:
    secret = generate_secret()
    endpoint.secret_encrypted = encrypt_secret(secret)
    db.add(endpoint)
    db.commit()
    return secret


def create_subscription(
    db: Session,
    *,
    endpoint_id: str,
    event_type: str,
    schema_version: int,
    filters: dict | None,
    enabled: bool,
) -> WebhookSubscription:
    subscription = WebhookSubscription(
        endpoint_id=endpoint_id,
        event_type=event_type,
        schema_version=schema_version,
        filters=filters,
        enabled=enabled,
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription


def list_endpoints(db: Session, *, owner_type: str | None = None, owner_id: str | None = None) -> list[WebhookEndpoint]:
    query = db.query(WebhookEndpoint)
    if owner_type:
        query = query.filter(WebhookEndpoint.owner_type == owner_type)
    if owner_id:
        query = query.filter(WebhookEndpoint.owner_id == owner_id)
    return query.order_by(WebhookEndpoint.created_at.desc()).all()


def list_deliveries(
    db: Session,
    *,
    endpoint_id: str | None = None,
    status: str | None = None,
) -> list[WebhookDelivery]:
    query = db.query(WebhookDelivery)
    if endpoint_id:
        query = query.filter(WebhookDelivery.endpoint_id == endpoint_id)
    if status:
        query = query.filter(WebhookDelivery.status == status)
    return query.order_by(WebhookDelivery.created_at.desc()).all()


def enqueue_delivery(
    db: Session,
    *,
    endpoint: WebhookEndpoint,
    envelope: WebhookEventEnvelope,
) -> WebhookDelivery:
    if not endpoint.delivery_paused:
        existing = (
            db.query(WebhookDelivery)
            .filter(WebhookDelivery.endpoint_id == endpoint.id)
            .filter(WebhookDelivery.event_id == envelope.event_id)
            .filter(WebhookDelivery.replay_id.is_(None))
            .first()
        )
        if existing is not None:
            return existing

    occurred_at = _parse_occurred_at(envelope.occurred_at) or datetime.now(timezone.utc)
    status = WebhookDeliveryStatus.PAUSED.value if endpoint.delivery_paused else WebhookDeliveryStatus.PENDING.value
    delivery = WebhookDelivery(
        endpoint_id=endpoint.id,
        event_id=envelope.event_id,
        event_type=envelope.event_type,
        payload=envelope.model_dump(),
        status=status,
        attempt=0,
        next_retry_at=None if endpoint.delivery_paused else datetime.now(timezone.utc),
        occurred_at=occurred_at,
    )
    db.add(delivery)
    db.commit()
    db.refresh(delivery)
    return delivery


def _make_signature(secret: str, timestamp: str, body: bytes) -> str:
    payload = timestamp.encode("utf-8") + b"." + body
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return digest


def _serialize_payload(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _next_retry(attempt: int) -> datetime | None:
    if attempt >= settings.webhook_max_attempts:
        return None
    if attempt <= len(_BACKOFF_MINUTES):
        minutes = _BACKOFF_MINUTES[attempt - 1]
    else:
        minutes = _BACKOFF_MINUTES[-1] * (2 ** (attempt - len(_BACKOFF_MINUTES)))
    return datetime.now(timezone.utc) + timedelta(minutes=minutes)


def deliver_webhook(db: Session, delivery: WebhookDelivery) -> WebhookDelivery:
    endpoint = db.query(WebhookEndpoint).filter(WebhookEndpoint.id == delivery.endpoint_id).first()
    if endpoint is None:
        delivery.status = WebhookDeliveryStatus.DEAD.value
        delivery.last_error = "endpoint_not_found"
        db.add(delivery)
        db.commit()
        return delivery

    if endpoint.status != WebhookEndpointStatus.ACTIVE.value:
        delivery.attempt += 1
        delivery.status = WebhookDeliveryStatus.FAILED.value
        delivery.last_error = "endpoint_disabled"
        delivery.next_retry_at = _next_retry(delivery.attempt)
        db.add(delivery)
        db.commit()
        return delivery

    if endpoint.delivery_paused:
        delivery.status = WebhookDeliveryStatus.PAUSED.value
        delivery.last_error = "endpoint_paused"
        delivery.next_retry_at = None
        db.add(delivery)
        db.commit()
        return delivery

    payload = delivery.payload or {}
    body = _serialize_payload(payload)
    timestamp = str(int(datetime.now(timezone.utc).timestamp()))
    secret = decrypt_secret(endpoint.secret_encrypted)
    signature = _make_signature(secret, timestamp, body)

    headers = {
        "Content-Type": "application/json",
        "X-NEFT-Signature": signature,
        "X-NEFT-Timestamp": timestamp,
        "X-NEFT-Event-Id": delivery.event_id,
    }

    delivery.status = WebhookDeliveryStatus.SENT.value
    status_code = None
    error_message = None
    try:
        request = Request(endpoint.url, data=body, headers=headers, method="POST")
        with urlopen(request, timeout=settings.webhook_request_timeout_seconds) as response:
            status_code = response.status
    except HTTPError as exc:
        status_code = exc.code
        error_message = exc.read().decode("utf-8") if exc.fp else str(exc)
    except URLError as exc:
        error_message = str(exc)
    except Exception as exc:  # noqa: BLE001
        error_message = str(exc)

    delivery.attempt += 1
    delivery.last_http_status = status_code
    delivery.last_error = error_message

    if status_code and 200 <= status_code < 300:
        delivery.status = WebhookDeliveryStatus.DELIVERED.value
        delivery.next_retry_at = None
        delivery.delivered_at = datetime.now(timezone.utc)
        latency_source = delivery.occurred_at or delivery.created_at or delivery.delivered_at
        delivery.latency_ms = int((delivery.delivered_at - latency_source).total_seconds() * 1000)
        WEBHOOK_DELIVERY_LATENCY_SECONDS.labels(endpoint_id=endpoint.id, partner_id=endpoint.owner_id).observe(
            delivery.latency_ms / 1000
        )
        if delivery.latency_ms / 1000 > settings.webhook_sla_seconds:
            WEBHOOK_DELIVERY_SLA_BREACHES_TOTAL.labels(
                endpoint_id=endpoint.id, partner_id=endpoint.owner_id
            ).inc()
    else:
        next_retry = _next_retry(delivery.attempt)
        if next_retry is None:
            delivery.status = WebhookDeliveryStatus.DEAD.value
        else:
            delivery.status = WebhookDeliveryStatus.FAILED.value
            delivery.next_retry_at = next_retry

    db.add(delivery)
    db.commit()
    db.refresh(delivery)
    return delivery


def pending_deliveries(db: Session) -> Iterable[WebhookDelivery]:
    now = datetime.now(timezone.utc)
    return (
        db.query(WebhookDelivery)
        .join(WebhookEndpoint, WebhookEndpoint.id == WebhookDelivery.endpoint_id)
        .filter(WebhookEndpoint.delivery_paused.is_(False))
        .filter(WebhookDelivery.next_retry_at.isnot(None))
        .filter(WebhookDelivery.next_retry_at <= now)
        .filter(
            WebhookDelivery.status.in_(
                [WebhookDeliveryStatus.PENDING.value, WebhookDeliveryStatus.FAILED.value]
            )
        )
        .all()
    )


def pause_endpoint(db: Session, endpoint: WebhookEndpoint, reason: str | None = None) -> WebhookEndpoint:
    endpoint.delivery_paused = True
    endpoint.paused_at = datetime.now(timezone.utc)
    endpoint.paused_reason = reason
    db.add(endpoint)
    db.query(WebhookDelivery).filter(WebhookDelivery.endpoint_id == endpoint.id).filter(
        WebhookDelivery.status.in_([WebhookDeliveryStatus.PENDING.value, WebhookDeliveryStatus.FAILED.value])
    ).update(
        {
            WebhookDelivery.status: WebhookDeliveryStatus.PAUSED.value,
            WebhookDelivery.next_retry_at: None,
        },
        synchronize_session=False,
    )
    db.commit()
    db.refresh(endpoint)
    return endpoint


def resume_endpoint(db: Session, endpoint: WebhookEndpoint) -> WebhookEndpoint:
    endpoint.delivery_paused = False
    endpoint.paused_at = None
    endpoint.paused_reason = None
    db.add(endpoint)
    db.query(WebhookDelivery).filter(WebhookDelivery.endpoint_id == endpoint.id).filter(
        WebhookDelivery.status == WebhookDeliveryStatus.PAUSED.value
    ).update(
        {
            WebhookDelivery.status: WebhookDeliveryStatus.PENDING.value,
            WebhookDelivery.next_retry_at: datetime.now(timezone.utc),
        },
        synchronize_session=False,
    )
    db.commit()
    db.refresh(endpoint)
    return endpoint


def schedule_replay(
    db: Session,
    *,
    endpoint: WebhookEndpoint,
    from_at: datetime,
    to_at: datetime,
    event_types: list[str] | None = None,
    only_failed: bool = False,
    created_by: str | None = None,
) -> tuple[WebhookReplay, int]:
    replay = WebhookReplay(
        endpoint_id=endpoint.id,
        from_at=from_at,
        to_at=to_at,
        event_types=event_types,
        scheduled_count=0,
        created_by=created_by,
    )
    query = db.query(WebhookDelivery).filter(WebhookDelivery.endpoint_id == endpoint.id)
    query = query.filter(WebhookDelivery.occurred_at >= from_at).filter(WebhookDelivery.occurred_at <= to_at)
    if event_types:
        query = query.filter(WebhookDelivery.event_type.in_(event_types))
    if only_failed:
        query = query.filter(WebhookDelivery.status.in_([WebhookDeliveryStatus.FAILED.value, WebhookDeliveryStatus.DEAD.value]))
    deliveries = query.all()
    db.add(replay)
    db.commit()
    db.refresh(replay)

    scheduled = 0
    for delivery in deliveries:
        status = WebhookDeliveryStatus.PAUSED.value if endpoint.delivery_paused else WebhookDeliveryStatus.PENDING.value
        new_delivery = WebhookDelivery(
            endpoint_id=endpoint.id,
            event_id=delivery.event_id,
            event_type=delivery.event_type,
            payload=delivery.payload,
            attempt=0,
            status=status,
            next_retry_at=None if endpoint.delivery_paused else datetime.now(timezone.utc),
            replay_id=replay.id,
            occurred_at=delivery.occurred_at,
        )
        db.add(new_delivery)
        scheduled += 1
    replay.scheduled_count = scheduled
    db.add(replay)
    db.commit()
    logger.info(
        "webhook.replay.scheduled",
        extra={
            "endpoint_id": endpoint.id,
            "partner_id": endpoint.owner_id,
            "replay_id": replay.id,
            "correlation_id": replay.id,
            "scheduled_count": scheduled,
        },
    )
    return replay, scheduled


def compute_sla(
    db: Session,
    *,
    endpoint: WebhookEndpoint,
    window: str,
) -> tuple[float, int | None, int, int]:
    window_seconds = _SLA_WINDOW_SECONDS.get(window)
    if window_seconds is None:
        raise ValueError("invalid_window")
    since = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
    query = (
        db.query(WebhookDelivery)
        .filter(WebhookDelivery.endpoint_id == endpoint.id)
        .filter(WebhookDelivery.occurred_at >= since)
    )
    deliveries = query.all()
    if not deliveries:
        return 1.0, None, 0, 0

    total = len(deliveries)
    delivered = [item for item in deliveries if item.status == WebhookDeliveryStatus.DELIVERED.value]
    sla_seconds = settings.webhook_sla_seconds
    breaches = 0
    success = 0
    latencies = []
    for item in delivered:
        if item.latency_ms is not None:
            latencies.append(item.latency_ms)
            if item.latency_ms / 1000 <= sla_seconds:
                success += 1
            else:
                breaches += 1
        else:
            breaches += 1
    success_ratio = success / total if total else 1.0
    avg_latency_ms = int(sum(latencies) / len(latencies)) if latencies else None
    return success_ratio, avg_latency_ms, breaches, total


def evaluate_alerts(db: Session, *, endpoint: WebhookEndpoint) -> list[WebhookAlert]:
    now = datetime.now(timezone.utc)
    success_ratio, _avg, _breaches, _total = compute_sla(db, endpoint=endpoint, window=_ALERT_WINDOW)
    failed_count = (
        db.query(WebhookDelivery)
        .filter(WebhookDelivery.endpoint_id == endpoint.id)
        .filter(WebhookDelivery.status.in_([WebhookDeliveryStatus.FAILED.value, WebhookDeliveryStatus.DEAD.value]))
        .count()
    )
    paused_too_long = (
        endpoint.delivery_paused
        and endpoint.paused_at is not None
        and (now - endpoint.paused_at).total_seconds() > _PAUSE_ALERT_SECONDS
    )
    conditions = {
        WebhookAlertType.SLA_BREACH.value: success_ratio < 0.8,
        WebhookAlertType.DELIVERY_FAILURE.value: failed_count > settings.webhook_alert_failure_threshold,
        WebhookAlertType.PAUSED_TOO_LONG.value: paused_too_long,
    }
    active_alerts: list[WebhookAlert] = []
    for alert_type, should_trigger in conditions.items():
        existing = (
            db.query(WebhookAlert)
            .filter(WebhookAlert.endpoint_id == endpoint.id)
            .filter(WebhookAlert.type == alert_type)
            .filter(WebhookAlert.window == _ALERT_WINDOW)
            .filter(WebhookAlert.resolved_at.is_(None))
            .first()
        )
        if should_trigger:
            if existing is None:
                alert = WebhookAlert(
                    endpoint_id=endpoint.id,
                    partner_id=endpoint.owner_id,
                    type=alert_type,
                    window=_ALERT_WINDOW,
                )
                db.add(alert)
                db.commit()
                db.refresh(alert)
                event = build_event(
                    event_type="WEBHOOK_ALERT_TRIGGERED",
                    payload={
                        "alert_id": alert.id,
                        "endpoint_id": endpoint.id,
                        "partner_id": endpoint.owner_id,
                        "type": alert.type,
                        "window": alert.window,
                    },
                    correlation_id=alert.id,
                )
                publish_event(event)
                existing = alert
            active_alerts.append(existing)
        else:
            if existing is not None:
                existing.resolved_at = now
                db.add(existing)
                db.commit()
                event = build_event(
                    event_type="WEBHOOK_ALERT_RESOLVED",
                    payload={
                        "alert_id": existing.id,
                        "endpoint_id": endpoint.id,
                        "partner_id": endpoint.owner_id,
                        "type": existing.type,
                        "window": existing.window,
                    },
                    correlation_id=existing.id,
                )
                publish_event(event)

    return active_alerts


__all__ = [
    "build_event_envelope",
    "create_endpoint",
    "create_subscription",
    "decrypt_secret",
    "deliver_webhook",
    "encrypt_secret",
    "enqueue_delivery",
    "evaluate_alerts",
    "generate_secret",
    "list_deliveries",
    "list_endpoints",
    "pending_deliveries",
    "pause_endpoint",
    "resume_endpoint",
    "rotate_secret",
    "schedule_replay",
    "compute_sla",
]
