# Service Level Objectives (SLO)

> Минимальный набор SLO для baseline. Используется для контроля SLA и аудитного следа.

## SLO targets

| SLO | Target | Measurement source |
| --- | --- | --- |
| API availability | 99.9% | `http_requests_total` + error codes |
| Authorize latency | p95 < 200ms | `http_request_duration_seconds` for authorize endpoints |
| Billing run success | 100% per period | `billing_run_status` |
| EDO send success | ≥ 99% | `edo_send_status` |
| BI sync freshness | < 15 min lag | `bi_sync_duration` + scheduler offsets |

## Metrics baseline

Ensure `/metrics` is available on gateway and core services, and that the following metrics are exported:

- `http_requests_total`
- `http_request_duration_seconds`
- `billing_run_status`
- `edo_send_status`
- `bi_sync_duration`
- `fuel_ingest_errors`

## Verification checklist

1. `curl http://localhost/metrics` returns data.
2. PromQL samples in `docs/ops/dashboards/` return non-empty results.
3. Alert thresholds mapped to SLO targets above.
