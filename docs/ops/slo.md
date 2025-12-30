# SLO/SLA v1

## Core API (admin/client)
- **p95 latency:** 300–500 ms
- **Error rate:** < 0.1%
- **Notes:** измеряется по основным endpoint-ам (dashboard, transactions, documents).

## Auth / authorize
- **p95 latency:** 60–80 ms
- **Error rate:** < 0.1%

## Background jobs
- **Billing/Clearing SLA:** завершение в пределах заданного окна выполнения.
- **Метрика:** доля jobs, завершенных в SLA-окне (не latency).

## SLO measurement
- Метрики снимаются из Prometheus/Grafana по p50/p95/p99.
- Ошибки считаются по 5xx + бизнес-ошибкам с кодами FAIL.
