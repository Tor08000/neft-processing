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
- Auth-host: `http://localhost:8002/api/v1/metrics`
- AI service: `http://localhost:8003/metrics`
- Integration Hub: `http://localhost:8010/metrics`

---

## 4) Smoke scripts (business flows)

> Все smoke-скрипты в `scripts/smoke_*.cmd` перечислены ниже. Команды выполняются на запущенном стеке (`docker compose up -d --build`).
> PASS criteria: script exits `0`; steps may emit `[SKIP]` with a documented reason (например отсутствие данных) without failing the script.

- `scripts\smoke_invoice_state_machine.cmd` корректно проходит в пустом окружении: при отсутствии инвойсов возвращает `[SKIP]` и exit `0`.

| Smoke check | Command | Prerequisites | PASS criteria |
| --- | --- | --- | --- |
| All smoke scripts | `scripts\smoke_all.cmd` | full stack running | Script exits `0` |
| Billing smoke | `scripts\billing_smoke.cmd` | core-api, auth-host, postgres, redis, minio | Script exits `0` (SKIP when no invoices) |
| Billing finance | `scripts\smoke_billing_finance.cmd` | core-api, auth-host, postgres, redis, minio | Script exits `0` |
| Billing run | `scripts\smoke_billing_run.cmd` | same as above | Script exits `0` |
| Billing v14 | `scripts\smoke_billing_v14.cmd` | same as above | Script exits `0` |
| Invoice state machine (conditional) | `scripts\smoke_invoice_state_machine.cmd` | same as above | Script exits `0` (SKIP when no invoices) |
| Legal gate | `scripts\smoke_legal_gate.cmd` | core-api, auth-host | Script exits `0` |
| Onboarding E2E | `scripts\smoke_onboarding_e2e.cmd` | core-api, auth-host | Script exits `0` |
| 1C export | `scripts\smoke_onec_export.cmd` | core-api, auth-host, postgres | Script exits `0` |
| Bank statement import | `scripts\smoke_bank_statement_import.cmd` | core-api, auth-host, postgres | Script exits `0` |
| Reconciliation after bank | `scripts\smoke_reconciliation_after_bank.cmd` | core-api, auth-host, postgres | Script exits `0` |
| Finance negative scenarios | `scripts\smoke_finance_negative_scenarios.cmd` | core-api, auth-host, postgres | Script exits `0` |
| Fleet ingest batch | `scripts\smoke_fuel_ingest_batch.cmd` | core-api, auth-host, postgres | Script exits `0` |
| Fleet offline reconcile | `scripts\smoke_fuel_offline_reconcile.cmd` | core-api, auth-host, postgres | Script exits `0` |
| Fleet replay batch | `scripts\smoke_fuel_replay_batch.cmd` | core-api, auth-host, postgres | Script exits `0` |
| EDO SBIS send | `scripts\smoke_edo_sbis_send.cmd` | core-api, integration-hub, SBIS env vars | Script exits `0` |
| EDO SBIS wait signed | `scripts\smoke_edo_sbis_wait_signed.cmd` | core-api, integration-hub, SBIS env vars | Script exits `0` |
| EDO SBIS revoke | `scripts\smoke_edo_sbis_revoke.cmd` | core-api, integration-hub, SBIS env vars | Script exits `0` |
| BI ops dashboard | `scripts\smoke_bi_ops_dashboard.cmd` | core-api, auth-host, clickhouse, `BI_CLICKHOUSE_ENABLED=1` | Script exits `0` |
| BI partner dashboard | `scripts\smoke_bi_partner_dashboard.cmd` | core-api, auth-host, clickhouse, `BI_CLICKHOUSE_ENABLED=1` | Script exits `0` |
| BI client spend dashboard | `scripts\smoke_bi_client_spend_dashboard.cmd` | core-api, auth-host, clickhouse, `BI_CLICKHOUSE_ENABLED=1` | Script exits `0` |
| BI CFO dashboard | `scripts\smoke_bi_cfo_dashboard.cmd` | core-api, auth-host, clickhouse, `BI_CLICKHOUSE_ENABLED=1` | Script exits `0` |
| Notifications invoice email | `scripts\smoke_notifications_invoice_email.cmd` | core-api, auth-host, mailpit | Script exits `0` |
| Notifications webhook | `scripts\smoke_notifications_webhook.cmd` | core-api, auth-host | Script exits `0` |
| Restart smoke | `scripts\smoke_restart.cmd` | full stack running | Script exits `0` |
| Client users & roles | `scripts\smoke_client_users_roles.cmd` | core-api, auth-host | **N/A (script is stub and exits 1)** |
| Limits apply/enforce | `scripts\smoke_limits_apply_and_enforce.cmd` | core-api, auth-host | **N/A (script is stub and exits 1)** |
| Cards issue | `scripts\smoke_cards_issue.cmd` | core-api, auth-host | **N/A (script is stub and exits 1)** |
| Operations explain | `scripts\smoke_operations_explain.cmd` | core-api, auth-host | **N/A (script is stub and exits 1)** |
| Closing package | `scripts\smoke_closing_package.cmd` | core-api, auth-host | **N/A (script is stub and exits 1)** |
| Reconciliation request/sign | `scripts\smoke_reconciliation_request_sign.cmd` | core-api, auth-host | **N/A (script is stub and exits 1)** |
| Support ticket | `scripts\smoke_support_ticket.cmd` | core-api, auth-host | **N/A (script is stub and exits 1)** |
| Partner onboarding | `scripts\smoke_partner_onboarding.cmd` | core-api, auth-host | **N/A (script is stub and exits 1)** |
| Partner webhooks | `scripts\smoke_partner_webhooks.cmd` | integration-hub | **N/A (script is stub and exits 1)** |
| Partner documents | `scripts\smoke_partner_documents.cmd` | core-api, auth-host | **N/A (script is stub and exits 1)** |
| Payouts batch export | `scripts\smoke_payouts_batch_export.cmd` | core-api, auth-host | **N/A (script is stub and exits 1)** |
| Clearing batch | `scripts\smoke_clearing_batch.cmd` | core-api, auth-host | **N/A (script is stub and exits 1)** |
| Reconciliation run | `scripts\smoke_reconciliation_run.cmd` | core-api, auth-host | **N/A (script is stub and exits 1)** |
| Dispute/refund | `scripts\smoke_dispute_refund.cmd` | core-api, auth-host | **N/A (script is stub and exits 1)** |

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

---

## 8) Known limitations

- Smoke scripts that are explicit placeholders (currently return `NOT IMPLEMENTED`):
  - `scripts\smoke_client_users_roles.cmd`
  - `scripts\smoke_limits_apply_and_enforce.cmd`
  - `scripts\smoke_cards_issue.cmd`
  - `scripts\smoke_operations_explain.cmd`
  - `scripts\smoke_closing_package.cmd`
  - `scripts\smoke_reconciliation_request_sign.cmd`
  - `scripts\smoke_support_ticket.cmd`
  - `scripts\smoke_partner_onboarding.cmd`
  - `scripts\smoke_partner_webhooks.cmd`
  - `scripts\smoke_partner_documents.cmd`
  - `scripts\smoke_payouts_batch_export.cmd`
  - `scripts\smoke_clearing_batch.cmd`
  - `scripts\smoke_reconciliation_run.cmd`
  - `scripts\smoke_dispute_refund.cmd`
