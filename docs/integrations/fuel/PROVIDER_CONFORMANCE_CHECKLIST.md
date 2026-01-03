# NEFT Fuel Provider Conformance Checklist

Use this checklist to validate a provider integration before enabling it in production.

## C1. Functional

- [ ] `health()` returns `HealthResult` and does not time out.
- [ ] `list_cards()` returns provider cards with `provider_card_id`.
- [ ] `fetch_transactions()` returns transactions with `occurred_at`, `amount`, `currency`.
- [ ] `provider_tx_id` is unique per provider (preferred); dedupe works when duplicates are sent.
- [ ] `fetch_statements()` returns statements for a period (if supported by provider).
- [ ] Pagination/cursor via `TxPage.next_cursor` is supported.
- [ ] Backfill for 7 days works via `backfill_provider()` windows.
- [ ] Replay does not create duplicates (`replay_raw_event()` + dedupe).

## C2. Reliability

- [ ] `health()` completes ≤ 1s (provider SLA target).
- [ ] `fetch_transactions()` completes ≤ 30s for a 24h window (provider SLA target).
- [ ] Retry behavior for transient errors is implemented in provider adapter.
- [ ] Rate-limit handling is implemented (HTTP 429 or provider-specific).
- [ ] Out-of-order transactions are documented and supported.

## C3. Security

- [ ] Secrets stored via `secret_ref` (not hardcoded).
- [ ] TLS is used for all provider API calls.
- [ ] Payload minimization: no unnecessary PII in `raw_payload`.
- [ ] Payload redaction verified via `payload_redacted` in `FuelProviderRawEvent`.

## C4. Ops

- [ ] Runbook includes enable/disable steps (connection status in `FuelProviderConnection`).
- [ ] Metrics/monitoring cover ingestion lag and provider errors.
- [ ] Manual replay path validated using `list_raw_events()` + `replay_raw_event()`.
