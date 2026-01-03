from __future__ import annotations

import hashlib
import hmac

from app.services.notifications.webhook_signature import (
    ERROR_NONCE_REPLAYED,
    ERROR_SIG_INVALID,
    ERROR_TIMESTAMP_EXPIRED,
    build_signature_headers,
    sign_webhook_v1,
    verify_webhook_signature,
)


class _MemoryNonceStore:
    def __init__(self) -> None:
        self._nonces: set[str] = set()

    def check_and_store(self, nonce: str, ttl_seconds: int) -> bool:  # noqa: ARG002 - parity with interface
        if nonce in self._nonces:
            return False
        self._nonces.add(nonce)
        return True


def test_signature_generation_is_deterministic() -> None:
    secret = "secret"
    timestamp = "1700000000"
    nonce = "11111111-1111-1111-1111-111111111111"
    event_id = "22222222-2222-2222-2222-222222222222"
    body = b"{\"hello\":\"world\"}"
    signature = sign_webhook_v1(
        secret=secret,
        timestamp=timestamp,
        nonce=nonce,
        event_id=event_id,
        body=body,
    )
    payload_hash = hashlib.sha256(body).hexdigest()
    canonical = f"v1\n{timestamp}\n{nonce}\n{event_id}\n{payload_hash}"
    expected = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
    assert signature == expected


def test_verify_ok_for_correct_signature() -> None:
    secret = "secret"
    timestamp = "1700000000"
    nonce = "11111111-1111-1111-1111-111111111111"
    event_id = "22222222-2222-2222-2222-222222222222"
    body = b"{\"hello\":\"world\"}"
    signature = sign_webhook_v1(
        secret=secret,
        timestamp=timestamp,
        nonce=nonce,
        event_id=event_id,
        body=body,
    )
    headers = build_signature_headers(event_id=event_id, timestamp=timestamp, nonce=nonce, signature=signature)
    ok, error = verify_webhook_signature(headers, body, secret, now=1700000000)
    assert ok
    assert error is None


def test_verify_fails_for_modified_body() -> None:
    secret = "secret"
    timestamp = "1700000000"
    nonce = "11111111-1111-1111-1111-111111111111"
    event_id = "22222222-2222-2222-2222-222222222222"
    body = b"{\"hello\":\"world\"}"
    signature = sign_webhook_v1(
        secret=secret,
        timestamp=timestamp,
        nonce=nonce,
        event_id=event_id,
        body=body,
    )
    headers = build_signature_headers(event_id=event_id, timestamp=timestamp, nonce=nonce, signature=signature)
    ok, error = verify_webhook_signature(headers, b"{\"hello\":\"tampered\"}", secret, now=1700000000)
    assert not ok
    assert error == ERROR_SIG_INVALID


def test_verify_rejects_expired_timestamp() -> None:
    secret = "secret"
    timestamp = "1600000000"
    nonce = "11111111-1111-1111-1111-111111111111"
    event_id = "22222222-2222-2222-2222-222222222222"
    body = b"{\"hello\":\"world\"}"
    signature = sign_webhook_v1(
        secret=secret,
        timestamp=timestamp,
        nonce=nonce,
        event_id=event_id,
        body=body,
    )
    headers = build_signature_headers(event_id=event_id, timestamp=timestamp, nonce=nonce, signature=signature)
    ok, error = verify_webhook_signature(headers, body, secret, now=1700000000)
    assert not ok
    assert error == ERROR_TIMESTAMP_EXPIRED


def test_verify_rejects_nonce_replay() -> None:
    secret = "secret"
    timestamp = "1700000000"
    nonce = "11111111-1111-1111-1111-111111111111"
    event_id = "22222222-2222-2222-2222-222222222222"
    body = b"{\"hello\":\"world\"}"
    signature = sign_webhook_v1(
        secret=secret,
        timestamp=timestamp,
        nonce=nonce,
        event_id=event_id,
        body=body,
    )
    headers = build_signature_headers(event_id=event_id, timestamp=timestamp, nonce=nonce, signature=signature)
    store = _MemoryNonceStore()
    ok, error = verify_webhook_signature(headers, body, secret, now=1700000000, replay_store=store)
    assert ok
    ok, error = verify_webhook_signature(headers, body, secret, now=1700000000, replay_store=store)
    assert not ok
    assert error == ERROR_NONCE_REPLAYED
