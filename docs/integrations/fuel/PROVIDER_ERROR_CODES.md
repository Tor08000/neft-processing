# NEFT Fuel Provider Error Codes

This document defines standard error codes used for provider integrations. These are used by provider adapters, ingestion jobs, and operational runbooks.

Source references:

- Provider interface: `platform/processing-core/app/integrations/fuel/base.py`
- Ingestion jobs: `platform/processing-core/app/integrations/fuel/jobs.py`
- Ingest dedupe: `platform/processing-core/app/services/fleet_ingestion_service.py`

| Code | Retry | Severity | Description | Alerts / Cases |
| --- | --- | --- | --- | --- |
| `PROVIDER_UNAVAILABLE` | YES | HIGH | Provider service unavailable (5xx / network). | Alert `provider_unavailable`; create ops case if >15m. |
| `PROVIDER_TIMEOUT` | YES | HIGH | Provider did not respond within configured timeout. | Alert `provider_timeout`; case if sustained. |
| `PROVIDER_RATE_LIMITED` | YES | MEDIUM | Provider rate limit hit. | Alert `provider_rate_limited`; backoff required. |
| `PROVIDER_AUTH_FAILED` | NO | HIGH | Authentication/authorization failed (invalid API key/OAuth). | Alert `provider_auth_failed`; case immediately. |
| `PROVIDER_SCHEMA_INVALID` | NO | HIGH | Provider payload does not map to required fields. | Alert `provider_schema_invalid`; case with payload sample. |
| `PROVIDER_DATA_GAP` | NO | MEDIUM | Missing data in a requested window. | Case `provider_data_gap`; backfill request. |
| `PROVIDER_DUPLICATE_TXN` | NO | LOW | Duplicate transaction ingested (deduped). | No alert; metrics only. |
| `PROVIDER_CURSOR_INVALID` | YES | MEDIUM | Cursor rejected/expired. | Alert `provider_cursor_invalid`; restart cursor. |
| `PROVIDER_REPLAY_FAILED` | YES | MEDIUM | Replay mapping failed for raw event. | Alert `provider_replay_failed`; manual review. |
| `PROVIDER_STATEMENT_UNAVAILABLE` | YES | LOW | Statement unavailable for period. | Warning; retry later. |

Notes:

- Retry behavior is handled by the caller/job runner (core does not implement a retry loop for providers).
- Deduped transactions are expected behavior under at-least-once delivery.
