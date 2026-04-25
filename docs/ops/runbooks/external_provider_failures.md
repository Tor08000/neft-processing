# External Provider Failure Runbook

This runbook covers the external API phase provider layer. It does not change money, auth/JWT, or public route semantics.

## Provider Status Taxonomy

Runtime owner health and provider health are separate. Provider health uses:

- `DISABLED`: provider intentionally off in this environment.
- `CONFIGURED`: adapter is configured, but no live success has been recorded in the health snapshot.
- `HEALTHY`: provider is configured and accepted by the runtime owner as usable.
- `DEGRADED`: provider is reachable only as a blocked/degraded contour, or required config is incomplete.
- `AUTH_FAILED`: provider credentials/certificate/signature were rejected.
- `TIMEOUT`: provider request exceeded its timeout budget.
- `UNSUPPORTED`: vendor is not selected or adapter is not wired.
- `RATE_LIMITED`: provider throttled the call.

## First Checks

1. Open Admin Runtime Center and inspect External Provider Diagnostics.
2. Check service health:
   - `integration-hub`: `GET /health`
   - `document-service`: `GET /health`
   - `logistics-service`: `GET /health`
   - `processing-core`: `/api/core/v1/admin/runtime/summary`
3. Confirm the provider mode: `disabled`, `degraded`, `sandbox`, `production`, or dev/test-only `mock`.
4. If `APP_ENV=prod|production`, verify no provider depends on `mock` unless `ALLOW_MOCK_PROVIDERS_IN_PROD=1` was intentionally set for break-glass and audited.

## Webhook Signature Failure

Symptoms:

- intake returns `401 signature_required` or `401 invalid_signature`
- provider diagnostics show `webhook_intake` as `DEGRADED`

Actions:

- Confirm `WEBHOOK_ALLOW_UNSIGNED=false` in production.
- Confirm sender signs with `WEBHOOK_INTAKE_SECRET` or, during rotation, `WEBHOOK_INTAKE_NEXT_SECRET`.
- Replace local placeholder secrets before production smoke; `change-me` keeps provider health degraded.
- Re-send with a fresh timestamp/correlation id if the sender supports replay protection.
- Do not allow unsigned production intake to pass silently.

## E-sign Down

Symptoms:

- document signing returns structured provider errors such as `esign_provider_timeout`, `esign_provider_auth_failed`, `esign_provider_rate_limited`, or `esign_provider_not_configured`
- document surfaces must show business states such as provider degraded/pending provider, not raw provider payloads

Actions:

- Check `ESIGN_PROVIDER_MODE` / `PROVIDER_X_MODE`.
- For sandbox, check `PROVIDER_X_SANDBOX_BASE_URL`; for production, check `PROVIDER_X_BASE_URL`.
- Validate API key/secret and callback secret outside the repo secret store. Empty values and placeholders such as `dev-key`, `dev-secret`, or `change-me` are degraded configuration, not provider-ready proof.
- Retry only idempotent requests or provider-documented retryable states.

## Diadok Down

Symptoms:

- integration-hub EDO calls return degraded/auth/timeout mappings
- provider diagnostics show `diadok` as `DEGRADED`, `AUTH_FAILED`, `TIMEOUT`, or `UNSUPPORTED`

Actions:

- Check `DIADOK_MODE`, `DIADOK_BASE_URL`, `DIADOK_API_TOKEN`, and timeout.
- Empty or placeholder base URL/token values are treated as degraded before network calls; do not use `diadok.example.com` or `change-me` as launch evidence.
- `SBIS` remains `UNSUPPORTED` until credentials/docs are supplied.
- Keep business/legal document lifecycle in `processing-core`; do not mark the legal contour green from transport-only proof.

## SMTP Down

Symptoms:

- email provider diagnostics show `smtp_email` as `DEGRADED`
- notification email returns provider-degraded errors

Actions:

- Check `EMAIL_PROVIDER_MODE=smtp`, `SMTP_HOST`, `SMTP_PORT`, TLS, sender and credentials.
- Mailpit is dev/test only and must not be used as production evidence.
- Webhook delivery readiness does not imply SMTP readiness.

## OTP/SMS Down

Symptoms:

- `otp_sms` is `DEGRADED` or `UNSUPPORTED`
- OTP send returns an explicit blocker instead of success

Actions:

- Confirm no local fake OTP is enabled for production.
- Select a concrete SMS provider and wire credentials/docs before moving from `UNSUPPORTED` to sandbox/production proof.
- Do not change auth/JWT/session semantics while adding OTP provider delivery.

## Bank API Down

Symptoms:

- `bank_api_statements` is `UNSUPPORTED` or `DEGRADED`

Actions:

- Keep file/import reconciliation path as canonical fallback evidence.
- Select bank vendor, configure account mapping, statement window, idempotency key, and checksum/WORM preservation before calling it provider-ready.
- Duplicate pulls must stay idempotent; malformed statements must be rejected before money posting.

## ERP / 1C Delivery Down

Symptoms:

- `erp_1c_delivery` is `file_only`, `DEGRADED`, or lacks external import id/ack

Actions:

- Treat generated export payload and delivered export as separate states.
- Keep `file_only` as configured payload generation, not API-delivery proof.
- Configure concrete 1C endpoint/protocol before `api_sandbox` or `api_production`.

## Fuel / Logistics Provider Down

Symptoms:

- `fuel_provider` is `UNSUPPORTED` or `DEGRADED`
- route compute provider diagnostics show OSRM not configured/degraded

Actions:

- OSRM is the concrete route compute provider; check `OSRM_BASE_URL`.
- Fuel card/transaction APIs remain vendor-gated until a concrete provider is selected.
- Client trip create stays mounted through processing-core; provider-backed fuel-consumption writes stay unmounted/frozen until external fuel proof exists.
