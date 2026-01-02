# Fleet notifications runbook

## Overview
Fleet notifications use a durable outbox (`fleet_notification_outbox`) with dedupe keys, backoff retries, and per-client policies for webhook/email delivery.

## Signals & metrics
- `core_api_fleet_notifications_outbox_total{status,event_type}`
- `core_api_fleet_notifications_delivery_seconds{channel}`
- `core_api_fleet_anomalies_total{type,severity}`
- `core_api_fleet_auto_actions_total{action,status}`
- `core_api_fleet_alerts_open_gauge`

## Operational checks
1. Inspect pending outbox items:
   ```sql
   SELECT id, client_id, event_type, severity, attempts, next_attempt_at, status
   FROM fleet_notification_outbox
   WHERE status = 'PENDING'
   ORDER BY next_attempt_at ASC
   LIMIT 50;
   ```
2. Inspect failures:
   ```sql
   SELECT id, client_id, event_type, attempts, last_error
   FROM fleet_notification_outbox
   WHERE status IN ('FAILED', 'DEAD')
   ORDER BY created_at DESC
   LIMIT 50;
   ```
3. Validate channel configuration:
   ```sql
   SELECT id, client_id, channel_type, target, status
   FROM fleet_notification_channels
   WHERE status = 'ACTIVE';
   ```

## Alert handling
- Each outbox entry is deduped by `{client_id}:{event_type}:{event_ref_id}:{severity}`.
- `FAILED` entries retry with exponential backoff; `DEAD` entries require manual investigation.

## Escalation
- If `FAILED` or `DEAD` counts spike, check downstream webhook/email dependencies.
- For repeated auto-action failures, inspect `fuel_limit_escalations` for error details.
