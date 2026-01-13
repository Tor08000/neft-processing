# NEFT Platform — Local Runbook (AS-IS, Windows CMD)

> **Scope:** local compose stack defined in `docker-compose.yml` (+ optional `docker-compose.smoke.yml`).

## 1) Prerequisites

- Docker Desktop / Docker Engine installed.
- Python 3.11+ available on PATH.
- Node.js 18+ available on PATH (for Playwright UI smoke).
- Ports available: `80`, `3000`, `4173`, `4174`, `4175`, `5432`, `6379`, `8001`, `8002`, `8003`, `8010`, `5555`, `9000`, `9001`, `9090`, `16686`, `3100`, `9080`, `4317`.

## 2) Configure environment

```cmd
copy .env.example .env
```

Edit `.env` and set at least:
- `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`
- `NEFT_S3_ACCESS_KEY`, `NEFT_S3_SECRET_KEY`
- `POSTGRES_PASSWORD`

(See `.env.example` for full list.)

## 3) Start the stack

```cmd
docker compose up -d --build
```

Optional smoke profile (adds smoke helpers):

```cmd
docker compose -f docker-compose.yml -f docker-compose.smoke.yml --profile smoke up -d
```

## 4) Apply DB migrations (core-api)

```cmd
scripts\migrate.cmd
```

Auth-host migrations are handled by its own service start; if needed:

```cmd
docker compose exec -T auth-host sh -lc "alembic -c alembic.ini upgrade head"
```

If `alembic -c app/alembic.ini heads` shows more than one head for processing-core, you must create a merge revision and commit it before starting the stack (entrypoint enforces a single head as a gate).
Use:

```cmd
docker compose run --rm --entrypoint "" core-api sh -lc "alembic -c app/alembic.ini merge -m \"merge heads (baseline)\" <head_ids...>"
```

### 4.1) Fix orphan composite types (when migrations failed)

Use the universal cleanup (drops orphan composite types without tables):

```cmd
scripts\db\fix_orphan_composite_types.cmd
```

Optional: target a different service name:

```cmd
scripts\db\fix_orphan_composite_types.cmd core-api
```

### 4.2) Frontend build verification (Docker + local)

Docker builds:

```cmd
docker compose build admin-web client-web partner-web
```

Local portal builds:

```cmd
cd frontends\admin-ui && npm run build
cd frontends\client-portal && npm run build
cd frontends\partner-portal && npm run build
```

## 5) Seed data (e2e + business seeds)

Legal documents:

```cmd
python scripts\seed_legal.py
```

Billing demo seed:

```cmd
python scripts\seed_billing.py
```

End-to-end seed (auth + billing + support ticket):

```cmd
scripts\seed_e2e.cmd
```

## 6) Health checks (HTTP)

Gateway + APIs:

```cmd
curl http://localhost/health
curl http://localhost/api/core/health
curl http://localhost/api/auth/health
curl http://localhost/api/ai/health
curl http://localhost/api/int/health
```

Direct service ports:

```cmd
curl http://localhost:8001/api/core/health
curl http://localhost:8002/api/auth/health
curl http://localhost:8003/api/v1/health
curl http://localhost:8010/health
```

Frontends:

```cmd
curl http://localhost:4173/health
curl http://localhost:4174/health
curl http://localhost:4175/health
```

Observability:

```cmd
curl http://localhost:9090/-/healthy
curl http://localhost:3000/health
curl http://localhost:16686/
```

## 7) Core tests

Recommended core harness:

```cmd
scripts\test_processing_core_docker.cmd
```

Full suite:

```cmd
scripts\test_processing_core_docker.cmd all
```

Alternative (subset + optional full):

```cmd
scripts\test_core_stack.cmd
scripts\test_core_stack.cmd --full
```

## 8) Единая проверка системы

```cmd
scripts\verify_all.cmd
```

> Проверка включает docker compose stack, миграции, health/metrics и smoke subset. SKIP в smoke из-за пустых данных считается PASS.

## 9) Как получить admin token

```cmd
scripts\get_admin_token.cmd
```

> Скрипт печатает токен **только в stdout** (для подстановки в smoke).

## 10) Smoke suite

```cmd
scripts\billing_smoke.cmd
scripts\smoke_billing_finance.cmd
scripts\smoke_invoice_state_machine.cmd
```

> Если smoke-скрипт возвращает `[SKIP]` из-за отсутствия данных (например invoices=0), это считается PASS.

## 11) Smoke tests (business flows)

```cmd
scripts\smoke_billing_v14.cmd
scripts\smoke_invoice_state_machine.cmd
scripts\smoke_legal_gate.cmd
scripts\smoke_onboarding_e2e.cmd
scripts\smoke_onec_export.cmd
scripts\smoke_bank_statement_import.cmd
scripts\smoke_reconciliation_after_bank.cmd
scripts\smoke_fuel_ingest_batch.cmd
scripts\smoke_fuel_offline_reconcile.cmd
scripts\smoke_fuel_replay_batch.cmd
```

## 12) Playwright UI smoke

```cmd
cd frontends\e2e
npm install
npx playwright install
npx playwright test
```

## 13) BI (ClickHouse runtime + marts + dashboards)

Enable in `.env`:
- `BI_CLICKHOUSE_ENABLED=1`
- `CLICKHOUSE_URL=http://clickhouse:8123`

Run BI sync + dashboard smokes:

```cmd
scripts\smoke_bi_ops_dashboard.cmd
scripts\smoke_bi_partner_dashboard.cmd
scripts\smoke_bi_client_spend_dashboard.cmd
scripts\smoke_bi_cfo_dashboard.cmd
```

Dashboards JSON: `docs\ops\dashboards\*.json`.

## 14) EDO SBIS

Set SBIS credentials and webhook secret in CMD before running EDO smokes:

```cmd
set SBIS_TEST_CREDENTIALS={"base_url":"https://sbis.test","token":"...","meta":{"send_path":"/edo/send","status_path":"/edo/status","revoke_path":"/edo/revoke"}}
set SBIS_TEST_WEBHOOK_SECRET=supersecret
set EDO_PROVIDER=SBIS
set EDO_E2E_ENABLED=1
```

Create EDO account with `credentials_ref=env:SBIS_TEST_CREDENTIALS` and
`webhook_secret_ref=env:SBIS_TEST_WEBHOOK_SECRET` via admin API. Then run:

```cmd
scripts\smoke_edo_sbis_send.cmd
scripts\smoke_edo_sbis_wait_signed.cmd
scripts\smoke_edo_sbis_revoke.cmd
```

## 15) Notifications (Mailpit) smoke

Mailpit is in the base compose (`SMTP_HOST=mailpit`).

```cmd
scripts\smoke_notifications_invoice_email.cmd
scripts\smoke_notifications_webhook.cmd
```

## 16) Backup / Restore

Postgres:

```cmd
scripts\backup\backup_postgres.cmd
scripts\restore\restore_postgres.cmd
scripts\backup\verify_backup.cmd
```

MinIO:

```cmd
scripts\backup\backup_minio.cmd
scripts\restore\restore_minio.cmd
```

ClickHouse (optional):

```cmd
scripts\backup\backup_clickhouse.cmd
scripts\restore\restore_clickhouse.cmd
```

## 14) Chaos checks (minimal)

```cmd
scripts\chaos\chaos_postgres_restart.cmd
scripts\chaos\chaos_redis_flush.cmd
scripts\chaos\chaos_minio_down.cmd
scripts\chaos\chaos_smoke_all.cmd
```

## 15) Release discipline

```cmd
scripts\release\generate_release_notes.cmd vYYYY.MM.PATCH
```

## 16) Known failure points

1) **MinIO not initialized** → check `minio-health` and `minio-init` logs. (`infra/minio-init.sh`)
2) **Auth-host fails to start** → verify key paths and `AUTH_KEY_DIR` volume. (`docker-compose.yml`, `.env.example`)
3) **Gateway returns 502** → ensure upstream services are healthy (`docker compose ps`). (`gateway/nginx.conf`)
4) **Celery workers unhealthy** → confirm Redis is healthy and `CELERY_BROKER_URL`. (`docker-compose.yml`)
5) **Metrics missing** → confirm `/metrics` endpoints and Prometheus targets. (`infra/prometheus.yml`)
