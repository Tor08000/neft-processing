# NEFT Platform — Evidence Index (facts only)

> Индекс артефактов, **реально присутствующих в репозитории**.
> Runtime-статус фиксируется в `docs/as-is/STATUS_SNAPSHOT_RUNTIME_LATEST.md`.

| Item | Evidence type | Path | What it proves |
|---|---|---|---|
| Runtime verification gate | VERIFIED_BY_RUNTIME | `scripts/verify_all.cmd` | Единая точка запуска: поднимает stack, миграции, health/metrics, smoke subset и pytest subset, пишет runtime snapshot. |
| Runtime snapshot (latest) | VERIFIED_BY_RUNTIME | `docs/as-is/STATUS_SNAPSHOT_RUNTIME_LATEST.md` | Фиксирует последний PASS `verify_all` и статусы smoke (PASS / SKIP_OK). |
| Admin token helper | VERIFIED_BY_SMOKE | `scripts/get_admin_token.cmd` | Получение admin token для smoke-скриптов (stdout-only). |
| Billing smoke | VERIFIED_BY_SMOKE | `scripts/billing_smoke.cmd` | Billing smoke flow; при отсутствии данных возвращает `[SKIP]` (SKIP_OK). |
| Billing finance smoke | VERIFIED_BY_SMOKE | `scripts/smoke_billing_finance.cmd` | Billing/finance smoke flow; подтверждает базовые финансовые операции. |
| Invoice state machine smoke | VERIFIED_BY_SMOKE | `scripts/smoke_invoice_state_machine.cmd` | Smoke state machine инвойсов; `[SKIP]` при отсутствии инвойсов (SKIP_OK). |
| Smoke suite aggregator | VERIFIED_BY_SMOKE | `scripts/smoke_all.cmd` | Health/metrics и базовые команды через docker exec. |
| Reconciliation smoke | VERIFIED_BY_SMOKE | `scripts/smoke_reconciliation_run.cmd` | Smoke сценарий reconciliation run. |
| EDO SBIS smoke | VERIFIED_BY_SMOKE | `scripts/smoke_edo_sbis_send.cmd` | Smoke сценарий отправки EDO SBIS (stub). |
| Fuel ingest smoke | VERIFIED_BY_SMOKE | `scripts/smoke_fuel_ingest_batch.cmd` | Smoke сценарий batch ingest топлива. |
| Notifications webhook smoke | VERIFIED_BY_SMOKE | `scripts/smoke_notifications_webhook.cmd` | Smoke сценарий webhook notifications. |
| Core API pytest entry | VERIFIED_BY_TESTS | `scripts/test_core_api.cmd` | Запуск pytest внутри core-api контейнера. |
| Auth-host pytest entry | VERIFIED_BY_TESTS | `scripts/test_auth_host.cmd` | Запуск pytest внутри auth-host контейнера. |
| Core stack pytest (subset/full) | VERIFIED_BY_TESTS | `scripts/test_core_stack.cmd` | Запуск pytest subset или full core suite через docker compose. |
| Core full suite | VERIFIED_BY_TESTS | `scripts/test_core_full.cmd` | Запуск core-api pytest по наборам system/smoke/contracts/integration. |
| Processing-core docker runner | VERIFIED_BY_TESTS | `scripts/test_processing_core_docker.cmd` | Запуск pytest в контейнере core-api. |
