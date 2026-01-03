from __future__ import annotations

import hashlib
import hmac
import time
from typing import Mapping

from app.services.notifications.webhook_replay_store import WebhookNonceStore

DEFAULT_REPLAY_WINDOW_SECONDS = 300

HEADER_EVENT_ID = "x-neft-event-id"
HEADER_TIMESTAMP = "x-neft-timestamp"
HEADER_NONCE = "x-neft-nonce"
HEADER_SIGNATURE = "x-neft-signature"
HEADER_SIGNATURE_ALG = "x-neft-signature-alg"
HEADER_SIGNATURE_VERSION = "x-neft-signature-version"

SIGNATURE_VERSION = "v1"
SIGNATURE_ALG = "HMAC-SHA256"

ERROR_SIG_MISSING = "WEBHOOK_SIG_MISSING"
ERROR_SIG_INVALID = "WEBHOOK_SIG_INVALID"
ERROR_TIMESTAMP_EXPIRED = "WEBHOOK_TIMESTAMP_EXPIRED"
ERROR_NONCE_REPLAYED = "WEBHOOK_NONCE_REPLAYED"


# NEFT Webhook Signature v1 canonical string (strict):
# v1\n<timestamp>\n<nonce>\n<event_id>\n<sha256_hex(body_json_bytes)>


def _normalize_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {key.lower(): value for key, value in headers.items()}


def body_sha256_hex(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def canonical_string(*, timestamp: str, nonce: str, event_id: str, body_hash: str) -> str:
    return "\n".join([SIGNATURE_VERSION, timestamp, nonce, event_id, body_hash])


def sign_webhook_v1(*, secret: str, timestamp: str, nonce: str, event_id: str, body: bytes) -> str:
    payload_hash = body_sha256_hex(body)
    canonical = canonical_string(timestamp=timestamp, nonce=nonce, event_id=event_id, body_hash=payload_hash)
    signature = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
    return signature


def build_signature_headers(*, event_id: str, timestamp: str, nonce: str, signature: str) -> dict[str, str]:
    return {
        "X-NEFT-Event-Id": event_id,
        "X-NEFT-Timestamp": timestamp,
        "X-NEFT-Nonce": nonce,
        "X-NEFT-Signature": f"{SIGNATURE_VERSION}={signature}",
        "X-NEFT-Signature-Alg": SIGNATURE_ALG,
        "X-NEFT-Signature-Version": SIGNATURE_VERSION,
    }


def verify_webhook_signature(
    headers: Mapping[str, str],
    body: bytes,
    secret: str,
    *,
    replay_store: WebhookNonceStore | None = None,
    replay_window_seconds: int = DEFAULT_REPLAY_WINDOW_SECONDS,
    now: float | None = None,
) -> tuple[bool, str | None]:
    normalized = _normalize_headers(headers)
    signature_header = normalized.get(HEADER_SIGNATURE)
    timestamp = normalized.get(HEADER_TIMESTAMP)
    nonce = normalized.get(HEADER_NONCE)
    event_id = normalized.get(HEADER_EVENT_ID)
    signature_version = normalized.get(HEADER_SIGNATURE_VERSION)
    signature_alg = normalized.get(HEADER_SIGNATURE_ALG)

    if not signature_header or not timestamp or not nonce or not event_id or not signature_version or not signature_alg:
        return False, ERROR_SIG_MISSING

    if signature_alg != SIGNATURE_ALG:
        return False, ERROR_SIG_INVALID
    if signature_version != SIGNATURE_VERSION:
        return False, ERROR_SIG_INVALID

    if not signature_header.startswith(f"{SIGNATURE_VERSION}="):
        return False, ERROR_SIG_INVALID

    provided_signature = signature_header.split("=", 1)[-1]
    try:
        timestamp_value = int(timestamp)
    except ValueError:
        return False, ERROR_SIG_INVALID

    now_ts = int(now if now is not None else time.time())
    if abs(now_ts - timestamp_value) > replay_window_seconds:
        return False, ERROR_TIMESTAMP_EXPIRED

    expected_signature = sign_webhook_v1(
        secret=secret,
        timestamp=timestamp,
        nonce=nonce,
        event_id=event_id,
        body=body,
    )
    if not hmac.compare_digest(expected_signature, provided_signature):
        return False, ERROR_SIG_INVALID

    if replay_store:
        if not replay_store.check_and_store(nonce, replay_window_seconds):
            return False, ERROR_NONCE_REPLAYED

    return True, None


__all__ = [
    "DEFAULT_REPLAY_WINDOW_SECONDS",
    "ERROR_NONCE_REPLAYED",
    "ERROR_SIG_INVALID",
    "ERROR_SIG_MISSING",
    "ERROR_TIMESTAMP_EXPIRED",
    "SIGNATURE_ALG",
    "SIGNATURE_VERSION",
    "build_signature_headers",
    "body_sha256_hex",
    "canonical_string",
    "sign_webhook_v1",
    "verify_webhook_signature",
]
