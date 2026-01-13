# NEFT Platform — Local Runbook (AS-IS, Windows CMD)

> **Scope:** локальный docker-compose стенд из `docker-compose.yml`.
> **Единая точка запуска проверки:** `scripts\verify_all.cmd`.

---

## 1) Prerequisites

- Docker Desktop / Docker Engine.
- Python 3.11+.
- Node.js 18+ (если запускать Playwright UI smoke).
- Доступные порты из `docker-compose.yml` (gateway 80, сервисные порты 8001/8002/8003/8010, infra).

---

## 2) Configure environment

```cmd
copy .env.example .env
```

Минимальные переменные для локального запуска:
- `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`
- `NEFT_S3_ACCESS_KEY`, `NEFT_S3_SECRET_KEY`
- `POSTGRES_PASSWORD`

---

## 3) Единая проверка системы (runtime gate)

```cmd
scripts\verify_all.cmd
```

**Что делает verify_all:**
- поднимает stack и применяет миграции;
- проверяет health/metrics endpoints через gateway;
- запускает smoke subset и pytest subset;
- пишет runtime snapshot в `docs\as-is\STATUS_SNAPSHOT_RUNTIME_<timestamp>.md`.

**PASS/FAIL правила:**
- Любой шаг с exit code ≠ 0 → **FAIL**.
- Если скрипт выводит строку с `[SKIP]`, verify_all помечает шаг как **SKIP_OK** и не падает.
- **SKIP_OK:** `scripts\billing_smoke.cmd` и `scripts\smoke_invoice_state_machine.cmd` возвращают `[SKIP]` при отсутствии инвойсов (это допустимый PASS по логике скрипта).

---

## 4) Health & metrics endpoints (gateway)

Актуальные URL из `gateway/nginx.conf` и `scripts/verify_all.cmd`:

```cmd
curl http://localhost/health
curl http://localhost/api/core/health
curl http://localhost/api/auth/health
curl http://localhost/api/ai/health
curl http://localhost/api/int/health
curl http://localhost/metrics
curl http://localhost/api/core/metrics
curl http://localhost:8010/metrics
```

Дополнительно доступны (если сервисы подняты):

```cmd
curl http://localhost/api/crm/health
curl http://localhost/api/logistics/health
curl http://localhost/api/docs/health
```

---

## 5) Admin token helper

```cmd
scripts\get_admin_token.cmd
```

> Скрипт печатает токен **только в stdout** и используется другими smoke-скриптами.

---

## 6) Pytest entrypoints (по необходимости)

```cmd
scripts\test_core_api.cmd -q
scripts\test_auth_host.cmd -q
scripts\test_core_stack.cmd
scripts\test_core_stack.cmd --full
scripts\test_core_full.cmd
scripts\test_processing_core_docker.cmd
scripts\test_processing_core_docker.cmd all
```

---

## 7) Smoke scripts (standalone)

> Все smoke-скрипты находятся в `scripts\smoke_*.cmd` и `scripts\billing_smoke.cmd`.
> Некоторые сценарии могут вернуть `[SKIP]` при отсутствии данных — это **SKIP_OK**.

Примеры:
```cmd
scripts\billing_smoke.cmd
scripts\smoke_billing_finance.cmd
scripts\smoke_invoice_state_machine.cmd
scripts\smoke_legal_gate.cmd
scripts\smoke_onec_export.cmd
scripts\smoke_bank_statement_import.cmd
scripts\smoke_reconciliation_run.cmd
scripts\smoke_fuel_ingest_batch.cmd
scripts\smoke_notifications_webhook.cmd
```

---

## 8) UI smoke (Playwright)

```cmd
cd frontends\e2e
npm install
npx playwright install
npx playwright test
```

---

## 9) Runtime snapshots

- **Latest pointer:** `docs/as-is/STATUS_SNAPSHOT_RUNTIME_LATEST.md`
- **Generated snapshots:** `docs/as-is/STATUS_SNAPSHOT_RUNTIME_<timestamp>.md`
