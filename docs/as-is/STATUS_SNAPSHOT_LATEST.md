# STATUS SNAPSHOT — LATEST (Evidence-based)

> Этот snapshot фиксирует **актуальные проверки и артефакты** в репозитории: docker harness, smoke/chaos/backup/restore, UI smoke (Playwright), BI/notifications smoke. Все команды — Windows CMD.

---

## 1) Core docker harness tests

| Check | Command (Windows CMD) | Prerequisites | PASS criteria |
| --- | --- | --- | --- |
| Processing-core default suite | `scripts\test_processing_core_docker.cmd` | `docker compose up` dependencies (`postgres`, `redis`, `minio`) | Script exits `0` and pytest passes |
| Processing-core full suite | `scripts\test_processing_core_docker.cmd all` | same as above | Script exits `0` and pytest passes |
| Core stack smoke + optional full | `scripts\test_core_stack.cmd` / `scripts\test_core_stack.cmd --full` | `postgres`, `redis`, `minio` running | Script exits `0` |
| Core full (system/smoke/contracts/integration) | `scripts\test_core_full.cmd` | `postgres`, `redis`, `minio`, `minio-health`, `minio-init` | Script exits `0` |
| Core API pytest (inside container) | `scripts\test_core_api.cmd -q` | `core-api` container running | pytest exits `0` |
| Auth-host pytest (inside container) | `scripts\test_auth_host.cmd -q` | `auth-host` container running | pytest exits `0` |

---

## 2) Migration Stabilization Pack

| Check | Command (Windows CMD) | Prerequisites | PASS criteria |
| --- | --- | --- | --- |
| Frontend docker builds | `docker compose build admin-web client-web partner-web` | Docker available | Build exits `0` |
| Alembic heads (core-api) | `docker compose run --rm --entrypoint "" core-api alembic -c app/alembic.ini heads` | Postgres running | Output contains exactly 1 head |
| Alembic upgrade (clean DB) | `docker compose down -v` + `docker compose up -d postgres` + `docker compose run --rm --entrypoint "" core-api alembic -c app/alembic.ini upgrade head` | Docker available | Upgrade exits `0` |
| Alembic upgrade (repeat) | `docker compose run --rm --entrypoint "" core-api alembic -c app/alembic.ini upgrade head` | Previous upgrade succeeded | Upgrade exits `0` |
| Orphan composite cleanup | `scripts\db\fix_orphan_composite_types.cmd` | core-api container running | Script exits `0` |

---

## 3) Health & metrics endpoints (source-of-truth paths)

> Актуальные пути из `gateway/nginx.conf` и сервисных `main.py`. Эти URL используются в verify_all/runtime.

### Health (HTTP 200)
- Gateway: `http://localhost/health`
- Core API via gateway: `http://localhost/api/core/health`
- Auth via gateway: `http://localhost/api/auth/health`
- AI via gateway: `http://localhost/api/ai/health`
- Integration Hub via gateway: `http://localhost/api/int/health`

### Metrics (HTTP 200)
- Gateway: `http://localhost/metrics`
- Core API via gateway: `http://localhost/api/core/metrics`
- Integration Hub: `http://localhost:8010/metrics`

---

## 4) Smoke scripts (business flows)

> Актуальный runtime-набор smoke-скриптов — это список, который запускается `scripts\verify_all.cmd`.
> PASS criteria: script exits `0`; steps may emit `[SKIP]` with a documented reason (например отсутствие данных) without failing the script.

- `scripts\smoke_invoice_state_machine.cmd` корректно проходит в пустом окружении: при отсутствии инвойсов возвращает `[SKIP]` и exit `0`.

| Smoke check (verify_all) | Command | Prerequisites | PASS criteria |
| --- | --- | --- | --- |
| Billing smoke | `scripts\billing_smoke.cmd` | core-api, auth-host, postgres, redis, minio | Script exits `0` (SKIP when no invoices) |
| Billing finance | `scripts\smoke_billing_finance.cmd` | core-api, auth-host, postgres, redis, minio | Script exits `0` |
| Invoice state machine (conditional) | `scripts\smoke_invoice_state_machine.cmd` | same as above | Script exits `0` (SKIP when no invoices) |

---

## 5) Pytest subset (verify_all gate)

| Check | Command | Prerequisites | PASS criteria |
| --- | --- | --- | --- |
| Auth-host health/metrics tests | `docker compose exec -T auth-host pytest app/tests/test_health.py app/tests/test_metrics.py -q` | auth-host running | pytest exits `0` |
| Core API tests subset | `docker compose exec -T core-api sh -lc "pytest app/tests/test_transactions_pipeline.py app/tests/test_invoice_state_machine.py app/tests/test_settlement_v1.py app/tests/test_reconciliation_v1.py app/tests/test_documents_lifecycle.py"` | core-api running | pytest exits `0` |
| Integration-hub webhooks | `docker compose exec -T integration-hub sh -lc "pytest neft_integration_hub/tests/test_webhooks.py"` | integration-hub running | pytest exits `0` |

---

## 6) Chaos / Backup / Restore / Release

| Check | Command | Prerequisites | PASS criteria |
| --- | --- | --- | --- |
| Chaos: Postgres restart | `scripts\chaos\chaos_postgres_restart.cmd` | full stack running | Script exits `0` |
| Chaos: Redis flush | `scripts\chaos\chaos_redis_flush.cmd` | full stack running | Script exits `0` |
| Chaos: MinIO down | `scripts\chaos\chaos_minio_down.cmd` | full stack running | Script exits `0` |
| Chaos: full smoke | `scripts\chaos\chaos_smoke_all.cmd` | full stack running | Script exits `0` |
| Backup Postgres | `scripts\backup\backup_postgres.cmd` | postgres running | Script exits `0` |
| Backup MinIO | `scripts\backup\backup_minio.cmd` | minio running | Script exits `0` |
| Backup ClickHouse | `scripts\backup\backup_clickhouse.cmd` | clickhouse running | Script exits `0` |
| Verify backups | `scripts\backup\verify_backup.cmd` | backups created | Script exits `0` |
| Backup+restore smoke | `scripts\backup\backup_restore_smoke.cmd` | postgres/minio/clickhouse | Script exits `0` |
| Restore Postgres | `scripts\restore\restore_postgres.cmd` | postgres running | Script exits `0` |
| Restore MinIO | `scripts\restore\restore_minio.cmd` | minio running | Script exits `0` |
| Restore ClickHouse | `scripts\restore\restore_clickhouse.cmd` | clickhouse running | Script exits `0` |
| Release notes generator | `scripts\release\generate_release_notes.cmd vYYYY.MM.PATCH` | git history available | Script exits `0` |

---

## 7) UI smoke (Playwright)

| Check | Command | Prerequisites | PASS criteria |
| --- | --- | --- | --- |
| Playwright UI smoke | `cd frontends\e2e && npm install && npx playwright install && npx playwright test` | UI services running (`admin-web`, `client-web`, `partner-web`) | `playwright test` exits `0` |
