from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from redis import Redis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies.redis import get_redis
from app.db import get_db
from app.models.helpdesk import HelpdeskInboundEvent, HelpdeskInboundEventStatus, HelpdeskProvider, HelpdeskTicketLink
from app.services.helpdesk_service import (
    apply_helpdesk_inbound_event,
    normalize_zendesk_payload,
)
from neft_shared.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/helpdesk", tags=["helpdesk-webhooks"])

RATE_LIMIT_PER_MINUTE = 60
IN_PROGRESS_MARKER = "in_progress"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _require_json(request: Request) -> None:
    content_type = request.headers.get("content-type", "")
    if content_type:
        content_type = content_type.split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="json_required")


def _verify_signature(*, timestamp: str, signature: str, body: bytes) -> None:
    settings = get_settings()
    secret = settings.NEFT_HELPDESK_WEBHOOK_SECRET
    if not secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="secret_missing")
    try:
        timestamp_value = int(timestamp)
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="timestamp_invalid")
    tolerance = settings.NEFT_HELPDESK_WEBHOOK_TOLERANCE_SEC
    now = int(time.time())
    if abs(now - timestamp_value) > tolerance:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="timestamp_expired")

    payload = f"{timestamp}.".encode("utf-8") + body
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    expected = f"v1={digest}"
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="signature_invalid")


def _rate_limit(redis: Redis | None, *, key: str, limit: int) -> int | None:
    if not redis:
        return None
    try:
        count = redis.incr(key)
        if count == 1:
            redis.expire(key, 60)
        if count > limit:
            ttl = redis.ttl(key)
            return ttl if ttl and ttl > 0 else 60
    except Exception:  # noqa: BLE001
        logger.warning("Helpdesk webhook rate limit check failed", exc_info=True)
    return None


def _existing_event(db: Session, *, provider: HelpdeskProvider, event_id: str) -> HelpdeskInboundEvent | None:
    return (
        db.query(HelpdeskInboundEvent)
        .filter(HelpdeskInboundEvent.provider == provider)
        .filter(HelpdeskInboundEvent.event_id == event_id)
        .one_or_none()
    )


def _finalize_event(
    db: Session,
    *,
    record: HelpdeskInboundEvent | None,
    provider: HelpdeskProvider,
    event_id: str,
    status: HelpdeskInboundEventStatus,
    error: str | None = None,
) -> None:
    now = _now()
    if record is None:
        record = HelpdeskInboundEvent(
            provider=provider,
            event_id=event_id,
            received_at=now,
            processed_at=now,
            status=status,
            last_error=error,
        )
        db.add(record)
    else:
        record.status = status
        record.last_error = error
        record.processed_at = now
        db.add(record)
    db.commit()


def _reserve_event(
    db: Session,
    *,
    provider: HelpdeskProvider,
    event_id: str,
    tolerance: int,
) -> HelpdeskInboundEvent | None:
    now = _now()
    record = _existing_event(db, provider=provider, event_id=event_id)
    if record:
        if record.status != HelpdeskInboundEventStatus.FAILED:
            return None
        if (
            record.last_error == IN_PROGRESS_MARKER
            and record.received_at
            and (now - record.received_at).total_seconds() < tolerance
        ):
            return None
        record.last_error = IN_PROGRESS_MARKER
        record.received_at = now
        record.processed_at = None
        db.add(record)
        db.commit()
        return record

    record = HelpdeskInboundEvent(
        provider=provider,
        event_id=event_id,
        received_at=now,
        status=HelpdeskInboundEventStatus.FAILED,
        last_error=IN_PROGRESS_MARKER,
    )
    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return None
    return record


@router.post("/zendesk")
async def zendesk_webhook(
    request: Request,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> dict[str, Any]:
    _require_json(request)
    body = await request.body()
    timestamp = request.headers.get("X-Neft-Timestamp")
    signature = request.headers.get("X-Neft-Signature")
    event_id = request.headers.get("X-Neft-Event-Id")
    if not timestamp or not signature:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="signature_missing")
    if not event_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="event_id_required")

    _verify_signature(timestamp=timestamp, signature=signature, body=body)

    provider = HelpdeskProvider.ZENDESK
    existing = _existing_event(db, provider=provider, event_id=event_id)
    if existing and existing.status != HelpdeskInboundEventStatus.FAILED:
        return {"ok": True}
    if existing and existing.status == HelpdeskInboundEventStatus.FAILED:
        settings = get_settings()
        if (
            existing.last_error == IN_PROGRESS_MARKER
            and existing.received_at
            and (_now() - existing.received_at).total_seconds() < settings.NEFT_HELPDESK_WEBHOOK_TOLERANCE_SEC
        ):
            return {"ok": True}

    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        _finalize_event(
            db,
            record=existing,
            provider=provider,
            event_id=event_id,
            status=HelpdeskInboundEventStatus.IGNORED,
            error="invalid_json",
        )
        return {"ok": True}

    normalized = normalize_zendesk_payload(payload, event_id=event_id)
    if not normalized:
        _finalize_event(
            db,
            record=existing,
            provider=provider,
            event_id=event_id,
            status=HelpdeskInboundEventStatus.IGNORED,
            error="unsupported_payload",
        )
        return {"ok": True}

    link = (
        db.query(HelpdeskTicketLink)
        .filter(HelpdeskTicketLink.provider == provider)
        .filter(HelpdeskTicketLink.external_ticket_id == normalized.external_ticket_id)
        .one_or_none()
    )
    if not link:
        _finalize_event(
            db,
            record=existing,
            provider=provider,
            event_id=event_id,
            status=HelpdeskInboundEventStatus.IGNORED,
            error="unknown_external_ticket",
        )
        return {"ok": True}

    rate_key = f"helpdesk:inbound:{provider.value}:{link.org_id}:{int(time.time() // 60)}"
    retry_after = _rate_limit(redis, key=rate_key, limit=RATE_LIMIT_PER_MINUTE)
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate_limited",
            headers={"Retry-After": str(retry_after)},
        )

    settings = get_settings()
    record = _reserve_event(
        db,
        provider=provider,
        event_id=event_id,
        tolerance=settings.NEFT_HELPDESK_WEBHOOK_TOLERANCE_SEC,
    )
    if record is None:
        return {"ok": True}

    try:
        status_result, error, _ = apply_helpdesk_inbound_event(db, event=normalized, provider=provider)
        _finalize_event(
            db,
            record=record,
            provider=provider,
            event_id=event_id,
            status=status_result,
            error=error,
        )
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Helpdesk inbound webhook processing failed")
        db.rollback()
        _finalize_event(
            db,
            record=record,
            provider=provider,
            event_id=event_id,
            status=HelpdeskInboundEventStatus.FAILED,
            error=str(exc),
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="internal_error") from exc
