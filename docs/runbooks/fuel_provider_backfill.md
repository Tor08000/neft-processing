# Fuel provider backfill

## Overview
Historical backfill allows fetching data in batches for a specified period and replaying it through the same normalization and deduplication pipeline.

## Trigger
`POST /api/admin/fleet/providers/{id}/backfill`

Payload:
```json
{
  "period_start": "2024-01-01T00:00:00Z",
  "period_end": "2024-01-31T23:59:59Z",
  "batch_hours": 24
}
```

## Monitoring
- Check jobs: `GET /api/admin/fleet/providers/jobs`
- Look for `mode=BACKFILL` and validate `window_start/end`.

## Dedupe
- Backfill uses at-least-once ingestion. Monitor `deduped_count` vs `inserted_count` in jobs.

## Reconciliation
- Ensure `external_statements` contain statements for the same period.
- Run reconciliation workflows once the backfill completes.

## Failure handling
- Validate provider credentials and date window size.
- Retry with smaller `batch_hours` if timeouts occur.
