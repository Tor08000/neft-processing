# On-demand integrations status

## Definitions

- **NOT CONNECTED**: no external provider connection is active in runtime, but the integration surface is prepared.
- **READY TO CONNECT**: contracts exist, endpoints are implemented, and a local stub is available for testing.

## Integration status table

| Integration | Status | Where | How to enable | Contracts | Notes |
| --- | --- | --- | --- | --- | --- |
| Bank API | NOT CONNECTED | processing-core explicit bank stub contour | `BANK_STUB_ENABLED=true` for local/test stub only | Admin bank-stub API + payout export formats | No real bank API adapter is wired. Stub payment/statement paths are disabled by default and idempotent by stable keys/checksums. |
| ERP/1C | NOT CONNECTED | processing-core explicit ERP stub/export contour | `ERP_STUB_ENABLED=true` for local/test stub only | Export format v1 / XML_1C payload generation | No real 1C delivery adapter is wired. Stub exports produce persisted payload evidence and ack state only. |
| EDO (Diadok) | NOT CONNECTED | integration-hub transport owner | `DIADOK_MODE=real|prod` + non-placeholder `DIADOK_BASE_URL` + `DIADOK_API_TOKEN` | EDO API v1 | Explicit mock only in `DIADOK_MODE=mock|stub`; unsupported providers fail degraded instead of silently succeeding. |
| EDO (SBIS) | UNSUPPORTED | integration-hub health/rejection map | none until adapter/contracts are supplied | EDO API v1 event contracts reserve provider value | Requests fail explicitly as `edo_provider_not_supported`; no fallback to Diadok/mock is allowed. |
| Fuel Networks | NOT CONNECTED | processing-core provider framework + virtual network | local virtual provider only | Provider Standard v1 | External fuel card/transaction APIs remain vendor-gated. |
| OTP/SMS | NOT CONNECTED | integration-hub OTP send surface | `OTP_PROVIDER_MODE=mock` for explicit local mock only | OTP send API | Default is degraded. Non-mock modes return structured degraded/unimplemented errors until a concrete vendor adapter is wired; send is idempotent by `idempotency_key`. |
| Email | READY TO CONFIGURE | integration-hub SMTP email transport | `EMAIL_PROVIDER_MODE=smtp` + `SMTP_HOST` and sender/credentials as needed | Notify email API | Default is disabled. SMTP errors map to auth/timeout/provider errors; mock is explicit local mode only. |
| Voice | NOT CONNECTED | processing-core fleet notification stub | `VOICE_PROVIDER=voice_stub` or `VOICE_PROVIDER=stub` for local tests | Fleet notification dispatch | Disabled by default; no real voice transport is wired in processing-core. |
| Webhooks | READY TO CONNECT | integration-hub endpoints + HMAC spec | enable endpoints + secrets | Webhook Signature v1 | Intake + registry + test delivery. |

## Contracts, secrets, and networks

- **Contracts**: follow the per-integration contract listed above (OpenAPI v1, Export v1, EDO API v1, Webhook Signature v1).
- **Secrets**: provide HMAC secrets for webhooks (`WEBHOOK_INTAKE_SECRET`) and per-provider credentials as needed. Placeholder values such as `change-me`, `dev-key`, or `dev-secret` are degraded evidence, not configured external-provider proof.
- **Networks**: allow outbound access from the integration hub to partner endpoints when enabling real providers.

## Mock/stub and degraded modes

- **EDO stub**: `/api/int/v1/edo/send`, `/api/int/v1/edo/{edo_doc_id}/status`, `/api/int/v1/edo/{edo_doc_id}/simulate` remain available only when `USE_STUB_EDO=true`.
- **EDO degraded/unsupported**: live `/api/int/v1/edo/*` routes return structured degraded errors when the requested provider is not wired or not configured.
- **Provider health**: `GET /api/int/v1/providers/health` lists Diadok readiness, explicit SBIS unsupported state, OTP/SMS, SMTP email, notification transport, and webhook signature policy.
- **Webhook intake stub**: `/api/int/v1/webhooks/client/events`, `/api/int/v1/webhooks/partner/events` with optional unsigned mode (`WEBHOOK_ALLOW_UNSIGNED=true`).
- **Webhook registry/test delivery**: `/api/int/v1/webhooks/endpoints`, `/api/int/v1/webhooks/endpoints/{id}/test`.
- **Webhook schema bootstrap**: local/dev compose should run with `INTEGRATION_HUB_AUTO_CREATE_SCHEMA=true`; otherwise `/api/int/health` must fail when webhook/EDO tables are absent instead of reporting a false-green service.

## Run instructions

1. **Start the stack**:
   ```bash
   docker compose up -d integration-hub gateway postgres redis minio
   ```
2. **Check health via gateway**:
   ```bash
   curl -fsS http://localhost/api/int/health
   ```
3. **Send an EDO stub document**:
   ```bash
   curl -fsS http://localhost/api/int/v1/edo/send \
     -H "Content-Type: application/json" \
     -d '{"doc_id":"doc-1","counterparty":{"inn":"7700000000"},"payload_ref":"s3://stub/doc-1"}'
   ```
4. **Check EDO status / simulate signed**:
   ```bash
   curl -fsS http://localhost/api/int/v1/edo/<edo_doc_id>/status
   curl -fsS http://localhost/api/int/v1/edo/<edo_doc_id>/simulate \
     -H "Content-Type: application/json" \
     -d '{"status":"SIGNED"}'
   ```
5. **Send a webhook intake event**:
   ```bash
   curl -fsS http://localhost/api/int/v1/webhooks/client/events \
     -H "Content-Type: application/json" \
     -d '{"event_type":"test.event","payload":{"id":"evt-1"}}'
   ```
