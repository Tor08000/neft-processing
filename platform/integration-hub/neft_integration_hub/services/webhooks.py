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

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from neft_integration_hub.models import (
    WebhookDelivery,
    WebhookDeliveryStatus,
    WebhookEndpoint,
    WebhookEndpointStatus,
    WebhookSigningAlgo,
    WebhookSubscription,
)
from neft_integration_hub.schemas import WebhookEventEnvelope, WebhookOwner
from neft_integration_hub.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


_BACKOFF_MINUTES = [1, 2, 5, 10, 30, 60, 180]


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
    delivery = WebhookDelivery(
        endpoint_id=endpoint.id,
        event_id=envelope.event_id,
        event_type=envelope.event_type,
        payload=envelope.model_dump(),
        status=WebhookDeliveryStatus.PENDING.value,
        attempt=0,
        next_retry_at=datetime.now(timezone.utc),
    )
    db.add(delivery)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        delivery = (
            db.query(WebhookDelivery)
            .filter(WebhookDelivery.endpoint_id == endpoint.id)
            .filter(WebhookDelivery.event_id == envelope.event_id)
            .first()
        )
        if delivery is None:
            raise
    else:
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
        .filter(WebhookDelivery.next_retry_at.isnot(None))
        .filter(WebhookDelivery.next_retry_at <= now)
        .filter(WebhookDelivery.status.in_([WebhookDeliveryStatus.PENDING.value, WebhookDeliveryStatus.FAILED.value]))
        .all()
    )


__all__ = [
    "build_event_envelope",
    "create_endpoint",
    "create_subscription",
    "decrypt_secret",
    "deliver_webhook",
    "encrypt_secret",
    "enqueue_delivery",
    "generate_secret",
    "list_deliveries",
    "list_endpoints",
    "pending_deliveries",
    "rotate_secret",
]
