# NEFT Platform — Evidence Index (facts only)

> Индекс артефактов, **реально присутствующих в репозитории**. Статус PASS не ставится без runtime-лога.

| Item | Evidence type | Path | What it proves |
|---|---|---|---|
| Runtime verification gate | VERIFIED_BY_RUNTIME | `scripts/verify_all.cmd` | Единая точка запуска: поднимает stack, миграции, health/metrics, smoke subset, pytest subset и пишет runtime snapshot. |
| Runtime snapshot (latest pointer) | VERIFIED_BY_RUNTIME | `docs/as-is/STATUS_SNAPSHOT_RUNTIME_LATEST.md` | Фиксирует текущий runtime-статус (сейчас verify_all = SKIP). |
| Admin token helper | VERIFIED_BY_SMOKE | `scripts/get_admin_token.cmd` | Получение admin token для smoke-скриптов (stdout-only). |
| Billing smoke | VERIFIED_BY_SMOKE | `scripts/billing_smoke.cmd` | Billing smoke flow; при отсутствии данных выдаёт `[SKIP]` и exit `0`. |
| Billing finance smoke | VERIFIED_BY_SMOKE | `scripts/smoke_billing_finance.cmd` | Billing/finance smoke flow; `[SKIP]` возможен по ответам API. |
| Invoice state machine smoke | VERIFIED_BY_SMOKE | `scripts/smoke_invoice_state_machine.cmd` | State machine smoke; `[SKIP]` при отсутствии инвойсов. |
| Smoke suite aggregator | VERIFIED_BY_SMOKE | `scripts/smoke_all.cmd` | Проверяет health/metrics/infra endpoints и базовые команды через docker exec. |
| Local smoke (bash) | VERIFIED_BY_SMOKE | `scripts/smoke_local.sh` | Быстрый smoke локального стенда (gateway + SPA). |
| Bank statement import smoke | VERIFIED_BY_SMOKE | `scripts/smoke_bank_statement_import.cmd` | Smoke сценарий импорта выписок (см. шаги в скрипте). |
| BI dashboards smoke (ops/partner/client/cfo) | VERIFIED_BY_SMOKE | `scripts/smoke_bi_ops_dashboard.cmd`, `scripts/smoke_bi_partner_dashboard.cmd`, `scripts/smoke_bi_client_spend_dashboard.cmd`, `scripts/smoke_bi_cfo_dashboard.cmd` | Smoke вызовы BI endpoints/дашбордов (см. шаги в скриптах). |
| Billing run smoke | VERIFIED_BY_SMOKE | `scripts/smoke_billing_run.cmd` | Smoke сценарий запуска биллинга (см. шаги в скрипте). |
| Billing v14 smoke | VERIFIED_BY_SMOKE | `scripts/smoke_billing_v14.cmd` | Smoke сценарий биллинга v14 (см. шаги в скрипте). |
| Cards issue smoke | VERIFIED_BY_SMOKE | `scripts/smoke_cards_issue.cmd` | Smoke сценарий выдачи карт (см. шаги в скрипте). |
| Clearing batch smoke | VERIFIED_BY_SMOKE | `scripts/smoke_clearing_batch.cmd` | Smoke сценарий clearing batch (см. шаги в скрипте). |
| Client users/roles smoke | VERIFIED_BY_SMOKE | `scripts/smoke_client_users_roles.cmd` | Smoke сценарий ролей/пользователей клиента (см. шаги в скрипте). |
| Closing package smoke | VERIFIED_BY_SMOKE | `scripts/smoke_closing_package.cmd` | Smoke сценарий закрывающих пакетов (см. шаги в скрипте). |
| Dispute refund smoke | VERIFIED_BY_SMOKE | `scripts/smoke_dispute_refund.cmd` | Smoke сценарий dispute/refund (см. шаги в скрипте). |
| EDO SBIS smokes | VERIFIED_BY_SMOKE | `scripts/smoke_edo_sbis_send.cmd`, `scripts/smoke_edo_sbis_wait_signed.cmd`, `scripts/smoke_edo_sbis_revoke.cmd` | Smoke шаги EDO SBIS интеграции (см. шаги в скриптах). |
| Finance negative scenarios smoke | VERIFIED_BY_SMOKE | `scripts/smoke_finance_negative_scenarios.cmd` | Negative smoke сценарии финансовых операций (см. шаги в скрипте). |
| Fuel ingest/offline/replay smokes | VERIFIED_BY_SMOKE | `scripts/smoke_fuel_ingest_batch.cmd`, `scripts/smoke_fuel_offline_reconcile.cmd`, `scripts/smoke_fuel_replay_batch.cmd` | Smoke сценарии топливной интеграции (см. шаги в скриптах). |
| Legal gate smoke | VERIFIED_BY_SMOKE | `scripts/smoke_legal_gate.cmd` | Smoke сценарий legal gate (см. шаги в скрипте). |
| Limits apply/enforce smoke | VERIFIED_BY_SMOKE | `scripts/smoke_limits_apply_and_enforce.cmd` | Smoke сценарий лимитов (см. шаги в скрипте). |
| Notifications smokes | VERIFIED_BY_SMOKE | `scripts/smoke_notifications_invoice_email.cmd`, `scripts/smoke_notifications_webhook.cmd` | Smoke сценарии уведомлений (см. шаги в скриптах). |
| Onboarding smoke | VERIFIED_BY_SMOKE | `scripts/smoke_onboarding_e2e.cmd` | Smoke сценарий onboarding (см. шаги в скрипте). |
| 1C export smoke | VERIFIED_BY_SMOKE | `scripts/smoke_onec_export.cmd` | Smoke сценарий выгрузки 1C (см. шаги в скрипте). |
| Operations explain smoke | VERIFIED_BY_SMOKE | `scripts/smoke_operations_explain.cmd` | Smoke сценарий explain/operations (см. шаги в скрипте). |
| Partner documents/onboarding/webhooks smokes | VERIFIED_BY_SMOKE | `scripts/smoke_partner_documents.cmd`, `scripts/smoke_partner_onboarding.cmd`, `scripts/smoke_partner_webhooks.cmd` | Smoke сценарии партнёрского контура (см. шаги в скриптах). |
| Payouts export smoke | VERIFIED_BY_SMOKE | `scripts/smoke_payouts_batch_export.cmd` | Smoke сценарий payout export (см. шаги в скрипте). |
| Reconciliation smokes | VERIFIED_BY_SMOKE | `scripts/smoke_reconciliation_after_bank.cmd`, `scripts/smoke_reconciliation_request_sign.cmd`, `scripts/smoke_reconciliation_run.cmd` | Smoke сценарии reconciliation (см. шаги в скриптах). |
| Restart smoke | VERIFIED_BY_SMOKE | `scripts/smoke_restart.cmd` | Smoke сценарий рестарта (см. шаги в скрипте). |
| Support ticket smoke | VERIFIED_BY_SMOKE | `scripts/smoke_support_ticket.cmd` | Smoke сценарий support ticket (см. шаги в скрипте). |
| Core API pytest entry | VERIFIED_BY_TESTS | `scripts/test_core_api.cmd` | Запуск pytest внутри core-api контейнера. |
| Auth-host pytest entry | VERIFIED_BY_TESTS | `scripts/test_auth_host.cmd` | Запуск pytest внутри auth-host контейнера. |
| Core stack pytest (subset/full) | VERIFIED_BY_TESTS | `scripts/test_core_stack.cmd` | Запуск pytest subset или full core suite через docker compose. |
| Core full suite (system/smoke/contracts/integration) | VERIFIED_BY_TESTS | `scripts/test_core_full.cmd` | Запуск core-api pytest в поднаборах `app/tests/system`, `smoke`, `contracts`, `integration`. |
| Processing-core docker runner | VERIFIED_BY_TESTS | `scripts/test_processing_core_docker.cmd` | Запуск pytest в контейнере core-api (по умолчанию `test_entitlements_pricing_versions.py`). |
| Processing-core legacy wrapper | VERIFIED_BY_TESTS | `scripts/test_processing_core.cmd` | Redirect на `scripts/test_core_stack.cmd`. |
| Integration-hub pytest subset (verify_all) | VERIFIED_BY_TESTS | `scripts/verify_all.cmd` | Запуск `pytest neft_integration_hub/tests/test_webhooks.py` как часть verify_all. |
| Auth-host pytest subset (verify_all) | VERIFIED_BY_TESTS | `scripts/verify_all.cmd` | Запуск `pytest app/tests/test_health.py app/tests/test_metrics.py` как часть verify_all. |
| Core pytest subset (verify_all) | VERIFIED_BY_TESTS | `scripts/verify_all.cmd` | Запуск `pytest app/tests/test_transactions_pipeline.py ... test_documents_lifecycle.py` как часть verify_all. |
