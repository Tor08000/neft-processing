# NEFT Webhook Signature v1

NEFT uses a unified HMAC signature scheme for **all outbound webhooks** and provides a helper for inbound verification.

## Required headers

```
X-NEFT-Event-Id: <uuid>
X-NEFT-Timestamp: <unix_seconds>
X-NEFT-Nonce: <uuid>
X-NEFT-Signature: v1=<hex_hmac_sha256>
X-NEFT-Signature-Alg: HMAC-SHA256
X-NEFT-Signature-Version: v1
Content-Type: application/json
```

## Canonical string (strict)

The payload is signed using **exactly** the following canonical string:

```
v1
<timestamp>
<nonce>
<event_id>
<sha256_hex(body_json_bytes)>
```

Notes:

- `timestamp` is UNIX seconds (UTC).
- `nonce` is a UUID generated per request.
- `event_id` is the webhook event UUID.
- `body_json_bytes` is the raw JSON request body (UTF-8 bytes).

Signature:

```
signature = hex(hmac_sha256(secret, canonical_string))
```

## Replay protection

Default replay window is **300 seconds** (5 minutes).

Clients should reject webhooks when:

- Timestamp is outside the window.
- Nonce has already been seen in the window.

Nonce storage (recommended order):

1. Redis `SETNX` + TTL (`webhook:nonce:<nonce>`)
2. Postgres `webhook_nonce_store` (fallback)

## Verification pseudocode

```python
canonical = "\n".join([
    "v1",
    timestamp,
    nonce,
    event_id,
    sha256_hex(body_bytes),
])

expected = hmac_sha256_hex(secret, canonical)

if not constant_time_equal(expected, provided_signature):
    return WEBHOOK_SIG_INVALID

if abs(now - int(timestamp)) > replay_window_seconds:
    return WEBHOOK_TIMESTAMP_EXPIRED

if nonce_already_seen(nonce):
    return WEBHOOK_NONCE_REPLAYED

return OK
```

## Example

```
POST /webhook
X-NEFT-Event-Id: 6f8bb9c8-1a60-4a6f-9a7b-1e7b7d5c3c1f
X-NEFT-Timestamp: 1700000000
X-NEFT-Nonce: 88a94b50-0cbe-4d59-8e86-70b46b92a8db
X-NEFT-Signature: v1=3e9d7f0b2b4a...
X-NEFT-Signature-Alg: HMAC-SHA256
X-NEFT-Signature-Version: v1
Content-Type: application/json

{"event":"test","payload":{"hello":"world"}}
```
