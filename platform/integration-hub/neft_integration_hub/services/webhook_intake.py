from __future__ import annotations

import hashlib
import hmac
from typing import Tuple

from sqlalchemy.orm import Session

from neft_integration_hub.models import WebhookIntakeEvent
from neft_integration_hub.settings import get_settings

settings = get_settings()


def compute_signature(payload: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def verify_signature(payload: bytes, signature_header: str | None, secret: str) -> Tuple[bool, str | None]:
    if not signature_header:
        return False, None
    signature = signature_header.strip()
    if signature.startswith("sha256="):
        signature = signature.split("=", 1)[1]
    expected = compute_signature(payload, secret)
    return hmac.compare_digest(signature, expected), signature_header


def record_intake_event(
    db: Session,
    *,
    source: str,
    event_type: str,
    payload: dict,
    event_id: str | None,
    signature: str | None,
    verified: bool,
    request_id: str | None,
    trace_id: str | None,
) -> WebhookIntakeEvent:
    record = WebhookIntakeEvent(
        source=source,
        event_type=event_type,
        event_id=event_id,
        payload=payload,
        signature=signature,
        verified=verified,
        request_id=request_id,
        trace_id=trace_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


__all__ = ["compute_signature", "record_intake_event", "verify_signature"]
