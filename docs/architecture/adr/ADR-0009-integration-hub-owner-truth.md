# ADR-0009: Integration Hub Transport Owner Truth

## Status
Accepted

## Context
- `platform/integration-hub` is the canonical transport-owner for external EDO/webhook-style integrations in NEFT.
- Runtime drift had accumulated around that contour:
  - mock-by-default notification/email modes,
  - OTP fake-success in non-mock modes,
  - webhook intake allowing unsigned payloads by default,
  - implicit provider support assumptions,
  - processing-core legal integrations auto-registering `noop` transport behavior.
- This made `integration-hub` look transport-owned while still returning synthetic success for several real-looking paths.

## Decision
- `integration-hub` remains the only canonical transport-owner for external EDO-style calls and webhook delivery/replay.
- `integration-hub` must not perform business compute or template/render orchestration.
- Provider truth is explicit:
  - `DIADOK`:
    - explicit mock only when `DIADOK_MODE=mock|stub`
    - otherwise real HTTP adapter with structured provider/auth/timeout errors
    - production/sandbox readiness requires a non-placeholder `DIADOK_BASE_URL` and `DIADOK_API_TOKEN`; placeholder values are degraded, not configured
  - `SBIS`:
    - not wired; requests and provider health must fail explicitly as unsupported/degraded
  - OTP:
    - explicit mock only when `OTP_PROVIDER_MODE=mock`
    - send requests are idempotent by `idempotency_key`
    - otherwise degraded/unimplemented until a real transport adapter exists
  - notifications:
    - explicit mock only when `NOTIFICATIONS_MODE=mock`
    - otherwise degraded/unimplemented until a real notification transport exists
  - email:
    - explicit mock only when `EMAIL_PROVIDER_MODE=mock`
    - canonical live transport is SMTP
    - default mode is disabled, not mock
- `document-service` remains the signing artifact transport owner. `PROVIDER_X_MODE=real|prod|sandbox` requires a provider URL plus non-placeholder API key/secret; default empty credentials must not count as configured.
- Webhook intake must require signature by default and report duplicates explicitly instead of silently dropping them.
- Webhook health must not treat `change-me` as a production-grade configured secret.
- Integration-hub health must be schema-aware:
  - local/dev compose may auto-create service tables with `INTEGRATION_HUB_AUTO_CREATE_SCHEMA=true`
  - when mounted webhook/EDO tables are missing and auto-create is disabled, `/health` must fail explicitly instead of reporting a false-green service
- Processing-core legal integrations must not auto-register `noop` adapters at runtime.

## Consequences
- Default runtime no longer pretends external transport succeeded when no real provider exists.
- Mock remains available, but only in explicit mode.
- Degraded paths are visible and reproducible through structured HTTP errors.
- Some adjacent direct-provider contours still exist outside this ADR:
  - document-service `provider_x`
  - logistics-service transport/compute split
  These are not re-owned here; they stay explicit adjacent contours until a separate transport handoff plan exists.

## Files
- `platform/integration-hub/neft_integration_hub/main.py`
- `platform/integration-hub/neft_integration_hub/settings.py`
- `platform/integration-hub/neft_integration_hub/providers/*`
- `platform/integration-hub/neft_integration_hub/services/*`
- `platform/processing-core/app/services/legal_integrations/*`
