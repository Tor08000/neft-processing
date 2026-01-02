# Fleet notifications runbook

## Overview
Fleet notifications use a durable outbox (`fleet_notification_outbox`) with dedupe keys, backoff retries, and per-client policies for webhook/email/push delivery.

## Signals & metrics
- `core_api_fleet_notifications_outbox_total{status,event_type}`
- `core_api_fleet_notifications_delivery_seconds{channel}`
- `core_api_fleet_webhook_responses_total{status_bucket}`
- `core_api_fleet_push_subscriptions_gauge`
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
4. Inspect push subscriptions:
   ```sql
   SELECT client_id, employee_id, endpoint, active, last_sent_at
   FROM fleet_push_subscriptions
   WHERE active = true
   ORDER BY created_at DESC
   LIMIT 50;
   ```

## Alert handling
- Each outbox entry is deduped by `{client_id}:{event_type}:{event_ref_id}:{severity}`.
- `FAILED` entries retry with exponential backoff; `DEAD` entries require manual investigation.

## Escalation
- If `FAILED` or `DEAD` counts spike, check downstream webhook/email dependencies.
- For repeated auto-action failures, inspect `fuel_limit_escalations` for error details.

## SMTP failures
- Verify `SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASS/SMTP_FROM`.
- Check `fleet_notification_outbox.last_error` for `smtp_host_missing` or auth errors.
- Use `/api/admin/fleet/notifications/outbox/{id}/replay` after fixing SMTP.

## Webhook signature mismatch
- Ensure the receiver validates the canonical JSON payload (`sort_keys`, no extra whitespace).
- Confirm timestamp header `X-NEFT-Signature-Timestamp` is included in signature input as `{timestamp}.{body}`.
- Validate `X-NEFT-Event-Id` and `X-NEFT-Event-Type` headers in logs.

## Push permission denied
- Confirm browser permission state (`Notification.permission`).
- If denied, the client must reset permissions in browser settings and re-subscribe.
- Check `fleet_push_subscriptions.active` to ensure the device has an active subscription.

## Replay procedure
1. Identify outbox entry in `FAILED`/`DEAD`.
2. Trigger replay via `POST /api/admin/fleet/notifications/outbox/{id}/replay`.
3. Verify `last_status` and `last_response_status` updates in `fleet_notification_outbox`.
