# PARTNER 10 — Webhooks Self-Service

## Goal
Partner creates webhook endpoints, rotates secrets, sends test deliveries, and replays deliveries.

## Actors & Roles
- Partner Admin

## Prerequisites
- Integration hub API (`platform/integration-hub`).

## UI Flow
**Partner portal**
- Webhooks page → create endpoint → rotate secret → send test → replay delivery.

**NOT IMPLEMENTED**
- Partner portal UI is not present.

## API Flow
1. `POST /v1/webhooks/endpoints` — create endpoint (returns secret).
2. `POST /v1/webhooks/endpoints/{endpoint_id}/rotate-secret` — rotate secret.
3. `POST /v1/webhooks/endpoints/{endpoint_id}/test` — send test delivery.
4. `POST /v1/webhooks/endpoints/{endpoint_id}/replay` — schedule replay.
5. `GET /v1/webhooks/deliveries?endpoint_id=...` — list deliveries.

## DB Touchpoints
- `webhook_endpoints` — endpoint configuration.
- `webhook_deliveries` — delivery attempts.
- `webhook_replays` — replay records.
- `webhook_alerts` — SLA/delivery alerts.

**NOT IMPLEMENTED**
- `webhook_secrets` history table (secret rotation stored inline on endpoint).

## Events & Audit
- `WEBHOOK_ALERT_TRIGGERED`, `WEBHOOK_ALERT_RESOLVED` — emitted during SLA alert evaluation.
- **NOT IMPLEMENTED**: `WEBHOOK_CREATED`, `WEBHOOK_SECRET_ROTATED`, `WEBHOOK_TEST_SENT`, `WEBHOOK_DELIVERY_REPLAYED` as explicit event codes.

## Security / Gates
- Integration hub endpoints currently lack explicit partner auth (assumed internal/service usage).

## Failure modes
- Endpoint not found → `404 endpoint_not_found`.
- Delivery replay without deliveries → `200` with `scheduled_deliveries=0`.

## VERIFIED
- pytest: `platform/integration-hub/neft_integration_hub/tests/test_webhooks.py`.
- smoke cmd: `scripts/smoke_partner_webhooks.cmd` (fails with NOT IMPLEMENTED).
- PASS: webhook endpoint created, test delivery recorded, replay scheduled.
