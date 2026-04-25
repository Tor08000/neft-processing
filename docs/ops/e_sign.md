# E-sign v1 (document signing)

## Overview

The E-sign flow is handled by **processing-core** (request orchestration + audit chain) and **document-service** (artifact signing + verification). The core system remains the owner of lifecycle, permissions, and audit log truth.

## Configuration

### Document-service

Set provider configuration via environment variables:

- `PROVIDER_X_MODE` (default: `real`)
- `PROVIDER_X_BASE_URL` (for real provider calls)
- `PROVIDER_X_API_KEY` (required for `real` / `prod` / `sandbox`)
- `PROVIDER_X_API_SECRET` (required for `real` / `prod` / `sandbox`)
- `PROVIDER_X_TIMEOUT_SECONDS`

Supported `PROVIDER_X_MODE` values:

- `real` / `prod` - live Provider X transport; startup fails fast if the URL or non-placeholder credentials are missing.
- `sandbox` - sandbox Provider X transport; requires `PROVIDER_X_SANDBOX_BASE_URL` plus non-placeholder credentials.
- `mock` - explicit local mock only.
- `degraded` / `disabled` - explicit degraded mode; `/v1/sign` and `/v1/verify` surface structured `503` responses instead of pretending signing succeeded.

Mock is never inferred from an empty base URL. Placeholder credentials such as `dev-key`, `dev-secret`, or `change-me` are treated as unconfigured.

### Processing-core

Ensure the document service URL is configured:

- `DOCUMENT_SERVICE_URL` (default: `http://document-service:8000`)

## Operations

### Request a signature

```
POST /api/v1/admin/documents/{document_id}/sign/request
{
  "provider": "provider_x",
  "meta": {"reason": "closing_package"}
}
```

Core behavior:
- Creates a `document_signatures` record with status `REQUESTED` -> `SIGNING`.
- Calls document-service to sign the PDF from S3.
- Updates status to `SIGNED` or `FAILED`.
- Writes audit events:
  - `DOCUMENT_SIGNING_REQUESTED`
  - `DOCUMENT_SIGNED` / `DOCUMENT_SIGN_FAILED`

### Verify a signature

```
POST /api/v1/admin/documents/{document_id}/signatures/{signature_id}/verify
```

Core behavior:
- Calls document-service `/v1/verify`.
- Updates status to `VERIFIED` or `REJECTED`.
- Writes audit events:
  - `DOCUMENT_SIGNATURE_VERIFIED`
  - `DOCUMENT_SIGNATURE_REJECTED`

### List signatures

```
GET /api/v1/admin/documents/{document_id}/signatures
```

### Storage conventions (S3)

Input:

```
.../vN.pdf
```

Output:

```
.../vN.signed.pdf
.../vN.sig.p7s
```

Each artifact stores its SHA-256 hash in S3 object metadata and is recorded in `document_signatures`.

## Monitoring & Metrics

### Document-service metrics

- `document_service_sign_total{status}`
- `document_service_sign_duration_seconds_bucket`
- `document_service_sign_errors_total{code}`
- `document_service_verify_total{status}`

## Retry & Fail-safe

- Signature failures leave the document lifecycle unchanged.
- Each request creates a new `document_signatures` version; previous artifacts are kept (WORM-style).
- Retry by re-issuing the sign request and tracking the next version.

## Alerts

Recommended alerts:

- High ratio of `document_service_sign_total{status="fail"}`.
- Sustained `DOCUMENT_SIGN_FAILED` audit events.

## Runbook: Provider Down

1. Confirm provider availability and API credentials.
2. Check `document_service_sign_errors_total{code}` for error spikes.
3. Retry signing requests once provider is healthy.
4. Validate `document_signatures` statuses and audit log entries.
