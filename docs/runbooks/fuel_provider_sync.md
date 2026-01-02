# Fuel provider sync

## Overview
This runbook covers polling sync runs for fuel provider integrations, including how to trigger a sync, diagnose failures, and perform a replay of raw events.

## Signals
- `provider_sync_runs_total{provider,status}`
- `provider_sync_latency_seconds{provider}`
- `provider_tx_inserted_total{provider}`
- `provider_tx_deduped_total{provider}`
- `provider_errors_total{provider,kind}`

## Triggers
- Scheduled polling job per provider (every N minutes).
- Manual admin trigger: `POST /api/admin/fleet/providers/{id}/sync-now`.

## Common checks
1. **Connection status**
   - `GET /api/admin/fleet/providers/connections?client_id=...`
   - Ensure status is `ACTIVE` and `last_sync_at` advances.

2. **Raw ingestion**
   - `GET /api/admin/fleet/providers/raw?client_id=...&provider_code=...`
   - Confirm raw events are created and payload hashes are populated.

3. **Transactions**
   - Inspect `fuel_transactions` for newly inserted rows with matching `provider_code`.

## Replay
1. Pick raw event ID from `fuel_provider_raw_events`.
2. Call `POST /api/admin/fleet/providers/raw/{id}/replay`.
3. Check the new ingest job in `/api/admin/fleet/providers/jobs`.

## Failure handling
- If the sync fails, verify:
  - Secret reference validity in `fuel_provider_connections.secret_ref`.
  - Provider endpoint configuration in `config`.
  - Provider API error responses in logs.

## Escalation
- If sync lag exceeds threshold or repeated failures occur, escalate to the integrations on-call and attach:
  - Connection ID
  - Provider code
  - Latest ingest job ID and error
