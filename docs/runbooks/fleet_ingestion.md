# Fleet ingestion runbook

## Overview
This runbook describes the ingestion pipeline for external fuel transactions, including idempotency, normalization, and audit events.

## Signals & metrics
- `core_api_fleet_ingest_jobs_total{status,provider}`
- `core_api_fleet_ingest_items_total{result}`
- `core_api_fleet_transactions_total`

## Common failure modes
- **Idempotency conflicts**: reuse of `idempotency_key` returns the existing job result.
- **Card resolution failures**: `card_alias`/`masked_pan` does not match any `fuel_cards` entry.
- **Provider misconfiguration**: missing `fuel_providers` entry (auto-created in v1).

## Operational checks
1. Query `fuel_ingest_jobs` for recent failures:
   ```sql
   SELECT id, provider_code, status, error, received_at
   FROM fuel_ingest_jobs
   WHERE status = 'FAILED'
   ORDER BY received_at DESC
   LIMIT 20;
   ```
2. Inspect dedupe counts:
   ```sql
   SELECT provider_code, sum(inserted_count) AS inserted, sum(deduped_count) AS deduped
   FROM fuel_ingest_jobs
   WHERE received_at > now() - interval '24 hours'
   GROUP BY provider_code;
   ```

## Escalation
- Re-ingest with a new `idempotency_key` only after confirming the batch was not partially ingested.
- For persistent provider failures, disable provider in `fuel_providers` and notify integrations team.
