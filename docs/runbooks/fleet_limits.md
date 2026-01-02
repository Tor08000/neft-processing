# Fleet limits runbook

## Overview
Fuel limit checks are evaluated deterministically at ingestion. Breaches create immutable `fuel_limit_breaches` records and emit signed audit events.

## Signals & metrics
- `core_api_fleet_limit_breaches_total{type,scope}`

## Operational checks
1. Inspect open breaches:
   ```sql
   SELECT id, client_id, breach_type, threshold, observed, delta, occurred_at
   FROM fuel_limit_breaches
   WHERE status = 'OPEN'
   ORDER BY occurred_at DESC
   LIMIT 20;
   ```
2. Confirm limit coverage:
   ```sql
   SELECT scope_type, scope_id, period, amount_limit, volume_limit_liters
   FROM fuel_limits
   WHERE active = true;
   ```

## Alert handling
- `ACKED` indicates a human acknowledged the breach.
- `IGNORED` requires a reason in the audit trail.

## Escalation
Escalate repeated `HARD_BREACH` events to the operations team for follow-up and policy tuning.
