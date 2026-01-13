# STATUS SNAPSHOT — LATEST (Static checklist)

> Этот snapshot фиксирует **актуальные проверки и артефакты**, которые реально есть в репозитории.
> Runtime-результаты фиксируются отдельно в `docs/as-is/STATUS_SNAPSHOT_RUNTIME_LATEST.md`.

---

## 1) verify_all gate (актуальные шаги из scripts/verify_all.cmd)

| Step | Command (Windows CMD) | Expected result |
| --- | --- | --- |
| Stack up | `docker compose up -d --build` | PASS |
| Core migrations | `scripts\migrate.cmd` | PASS |
| Alembic current (core-api) | `docker compose exec -T core-api sh -lc "alembic -c app/alembic.ini current"` | PASS |
| Alembic current (auth-host) | `docker compose exec -T auth-host sh -lc "alembic -c alembic.ini current"` | PASS |
| Health checks | `curl http://localhost/health` + `/api/core/health` + `/api/auth/health` + `/api/ai/health` + `/api/int/health` | PASS |
| Metrics checks | `curl http://localhost/metrics` + `/api/core/metrics` + `http://localhost:8010/metrics` | PASS |
| Smoke subset | `scripts\billing_smoke.cmd`, `scripts\smoke_billing_finance.cmd`, `scripts\smoke_invoice_state_machine.cmd` | PASS / SKIP_OK |
| Pytest subset (auth-host) | `docker compose exec -T auth-host pytest app/tests/test_health.py app/tests/test_metrics.py -q` | PASS |
| Pytest subset (core-api) | `docker compose exec -T core-api sh -lc "pytest app/tests/test_transactions_pipeline.py app/tests/test_invoice_state_machine.py app/tests/test_settlement_v1.py app/tests/test_reconciliation_v1.py app/tests/test_documents_lifecycle.py"` | PASS |
| Pytest subset (integration-hub) | `docker compose exec -T integration-hub sh -lc "pytest neft_integration_hub/tests/test_webhooks.py"` | PASS |

**SKIP_OK правило:** если smoke-скрипт пишет `[SKIP]`, verify_all помечает шаг как SKIP_OK и не падает.

---

## 2) Дополнительные smoke scripts (standalone)

| Smoke script | Command | Expected result |
| --- | --- | --- |
| Smoke aggregator | `scripts\smoke_all.cmd` | PASS |
| Bank statement import | `scripts\smoke_bank_statement_import.cmd` | PASS / SKIP_OK |
| BI dashboards (ops/partner/client/cfo) | `scripts\smoke_bi_ops_dashboard.cmd`, `scripts\smoke_bi_partner_dashboard.cmd`, `scripts\smoke_bi_client_spend_dashboard.cmd`, `scripts\smoke_bi_cfo_dashboard.cmd` | PASS / SKIP_OK |
| Billing run | `scripts\smoke_billing_run.cmd` | PASS / SKIP_OK |
| Billing v14 | `scripts\smoke_billing_v14.cmd` | PASS / SKIP_OK |
| Cards issue | `scripts\smoke_cards_issue.cmd` | PASS / SKIP_OK |
| Clearing batch | `scripts\smoke_clearing_batch.cmd` | PASS / SKIP_OK |
| Client users/roles | `scripts\smoke_client_users_roles.cmd` | PASS / SKIP_OK |
| Closing package | `scripts\smoke_closing_package.cmd` | PASS / SKIP_OK |
| Dispute refund | `scripts\smoke_dispute_refund.cmd` | PASS / SKIP_OK |
| EDO SBIS (send/wait/revoke) | `scripts\smoke_edo_sbis_send.cmd`, `scripts\smoke_edo_sbis_wait_signed.cmd`, `scripts\smoke_edo_sbis_revoke.cmd` | PASS / SKIP_OK |
| Finance negative scenarios | `scripts\smoke_finance_negative_scenarios.cmd` | PASS / SKIP_OK |
| Fuel ingest/offline/replay | `scripts\smoke_fuel_ingest_batch.cmd`, `scripts\smoke_fuel_offline_reconcile.cmd`, `scripts\smoke_fuel_replay_batch.cmd` | PASS / SKIP_OK |
| Legal gate | `scripts\smoke_legal_gate.cmd` | PASS / SKIP_OK |
| Limits apply/enforce | `scripts\smoke_limits_apply_and_enforce.cmd` | PASS / SKIP_OK |
| Notifications | `scripts\smoke_notifications_invoice_email.cmd`, `scripts\smoke_notifications_webhook.cmd` | PASS / SKIP_OK |
| Onboarding | `scripts\smoke_onboarding_e2e.cmd` | PASS / SKIP_OK |
| 1C export | `scripts\smoke_onec_export.cmd` | PASS / SKIP_OK |
| Operations explain | `scripts\smoke_operations_explain.cmd` | PASS / SKIP_OK |
| Partner docs/onboarding/webhooks | `scripts\smoke_partner_documents.cmd`, `scripts\smoke_partner_onboarding.cmd`, `scripts\smoke_partner_webhooks.cmd` | PASS / SKIP_OK |
| Payout export | `scripts\smoke_payouts_batch_export.cmd` | PASS / SKIP_OK |
| Reconciliation | `scripts\smoke_reconciliation_after_bank.cmd`, `scripts\smoke_reconciliation_request_sign.cmd`, `scripts\smoke_reconciliation_run.cmd` | PASS / SKIP_OK |
| Restart | `scripts\smoke_restart.cmd` | PASS / SKIP_OK |
| Support ticket | `scripts\smoke_support_ticket.cmd` | PASS / SKIP_OK |

---

## 3) Pytest entrypoints (standalone)

| Check | Command | Expected result |
| --- | --- | --- |
| Core API pytest | `scripts\test_core_api.cmd -q` | PASS |
| Auth-host pytest | `scripts\test_auth_host.cmd -q` | PASS |
| Core stack subset/full | `scripts\test_core_stack.cmd` / `scripts\test_core_stack.cmd --full` | PASS |
| Core full suite | `scripts\test_core_full.cmd` | PASS |
| Processing-core docker runner | `scripts\test_processing_core_docker.cmd` / `scripts\test_processing_core_docker.cmd all` | PASS |

---

## 4) UI smoke (Playwright)

| Check | Command | Expected result |
| --- | --- | --- |
| Playwright UI smoke | `cd frontends\e2e && npm install && npx playwright install && npx playwright test` | PASS |
