# PARTNER 10 — Webhooks Self-Service

## Goal
Partner registers webhooks, rotates secrets, and replays deliveries.

## Actors & Roles
- Partner Admin

## Prerequisites
- Integration-hub running with DB.

## UI Flow
**Partner portal**
- Webhooks list → add endpoint → rotate secret → replay delivery.

## API Flow
1. `POST /v1/webhooks/endpoints` — create endpoint.
2. `GET /v1/webhooks/endpoints` — list endpoints.
3. `POST /v1/webhooks/endpoints/{id}/rotate-secret` — rotate secret.
4. `POST /v1/webhooks/endpoints/{id}/replay` — replay deliveries.

## DB Touchpoints
- `webhook_endpoints`, `webhook_deliveries`, `webhook_replays`.

## Events & Audit
- Delivery/replay records stored in webhook tables; retries recorded as `webhook_replays` rows.

## Security / Gates
- Webhook signatures verified via HMAC; replay protection enforced.

## Failure modes
- Invalid secret or signature → `401` / `422`.

## VERIFIED
- pytest: `platform/integration-hub/neft_integration_hub/tests/test_webhooks.py`.
- smoke cmd: `scripts/smoke_partner_webhooks.cmd` (placeholder).
- PASS: endpoint created and delivery stored.
