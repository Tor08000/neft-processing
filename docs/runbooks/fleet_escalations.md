# Fleet escalations runbook

## Overview
This runbook covers policy-driven fleet escalations, auto-blocks, and incident handling.

## Signals
- **Auto-block failed** (policy action failed notification/outbox event)
- **High escalation volume** (multiple escalation cases for same client)

## Immediate checks
1. Verify policy executions for the client:
   - `GET /api/admin/fleet/executions?client_id=<client_id>`
2. Check active action policies:
   - `GET /api/admin/fleet/policies?client_id=<client_id>`
3. Inspect fleet cases for escalation details in the case timeline.

## Auto-block failure response
1. Confirm card status and status history.
2. Review the failure case (case source `policy_action_failure`).
3. If needed, manually unblock with a reason:
   - `POST /api/admin/fleet/cards/{id}/unblock`

## Escalation volume response
1. Confirm anomalies/breaches causing escalations.
2. Validate policy thresholds and cooldowns for the client.
3. Coordinate with fraud/ops for investigation and resolution.

## Audit artifacts
- `FLEET_POLICY_ACTION_APPLIED` and `FLEET_POLICY_ACTION_FAILED` case events
- `FLEET_ESCALATION_CASE_CREATED` case event
- `FUEL_CARD_AUTO_BLOCKED` and `FUEL_CARD_UNBLOCKED` case events
- `fleet_policy_executions` and `fuel_card_status_events` tables
