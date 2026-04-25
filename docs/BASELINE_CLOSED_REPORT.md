# Baseline Closed Report

## Что такое “Baseline”

Baseline — зафиксированный набор реализованных модулей, проверок и ops-процедур, который гарантирует воспроизводимый запуск платформы и покрытие ключевых сценариев.

## Блоки 1–15 (READY)

1. Core API runtime — **READY**
2. Auth-host (JWT/RBAC) — **READY**
3. Billing & Finance — **READY**
4. Fleet/Fuel ingestion + offline + replay — **READY**
5. Marketplace economics + SLA + recommender v1 — **READY**
6. Documents & Exports — **READY**
7. EDO SBIS — **READY**
8. Integrations Hub (1C + Bank + Reconciliation) — **READY**
9. BI ClickHouse runtime + marts + dashboards — **READY**
10. Security (Service identities + ABAC) — **READY**
11. Reconciliation/Internal Ledger — **READY**
12. Notifications (email/webhook) — **READY**
13. Observability stack (Prometheus/Grafana/Jaeger/Loki) — **READY**
14. Operational reliability (chaos/backup/restore/SLO/release) — **READY**
15. Frontends + Playwright UI smoke — **READY**

## Источник истины

- **AS-IS master:** `docs/as-is/NEFT_PLATFORM_AS_IS_MASTER.md`
- **Status snapshot:** `docs/as-is/STATUS_SNAPSHOT_LATEST.md`
- **Verified matrix:** `docs/scenarios/VERIFIED_MATRIX.md`
- **Ops docs:** `docs/ops/SLO.md`, `docs/ops/ci.md`, `docs/ops/RELEASE_CHECKLIST.md`

## Как проверить “всё работает” одной последовательностью команд (Windows CMD)

```cmd
copy .env.example .env

docker compose up -d --build
scripts\migrate.cmd

python scripts\seed_legal.py
python scripts\seed_billing.py
scripts\seed_e2e.cmd

scripts\test_processing_core_docker.cmd
scripts\smoke_billing_v14.cmd
scripts\smoke_legal_gate.cmd
scripts\smoke_onec_export.cmd
scripts\smoke_fuel_ingest_batch.cmd
scripts\smoke_bi_ops_dashboard.cmd

cd frontends\e2e
npm install
npx playwright install
npx playwright test

scripts\chaos\chaos_smoke_all.cmd
scripts\backup\backup_restore_smoke.cmd
```

Optional EDO SBIS (requires SBIS credentials):

```cmd
set SBIS_TEST_CREDENTIALS={"base_url":"https://sbis.test","token":"...","meta":{"send_path":"/edo/send","status_path":"/edo/status","revoke_path":"/edo/revoke"}}
set SBIS_TEST_WEBHOOK_SECRET=supersecret
set EDO_PROVIDER=SBIS
set EDO_E2E_ENABLED=1
set DOC_ID=<document_registry_id_with_pdf_file>
set SUBJECT_TYPE=CLIENT
set SUBJECT_ID=<client_id>
set COUNTERPARTY_ID=<edo_counterparty_id>
set ACCOUNT_ID=<edo_account_id>
set DOC_KIND=INVOICE
scripts\smoke_edo_sbis_send.cmd
```
