# Verification Catalog (Scripts + Tests)

> Полный индекс verification артефактов (Windows CMD). Таблица покрывает все `scripts/test_*.cmd`, `scripts/smoke_*.cmd`, `scripts/chaos/*.cmd`, `scripts/backup/*.cmd`, `scripts/restore/*.cmd`, `scripts/release/*.cmd`, а также seed-скрипты.

| Script/Test | Purpose | Prerequisites | Command | PASS criteria | Module coverage |
| --- | --- | --- | --- | --- | --- |
| `scripts\test_processing_core_docker.cmd` | Core pytest (default target) | `postgres`, `redis`, `minio` | `scripts\test_processing_core_docker.cmd` | exit `0` | Core API regression |
| `scripts\test_processing_core_docker.cmd all` | Core pytest (full) | `postgres`, `redis`, `minio` | `scripts\test_processing_core_docker.cmd all` | exit `0` | Full processing-core |
| `scripts\test_processing_core.cmd` | Alias to core stack tests | `postgres`, `redis`, `minio` | `scripts\test_processing_core.cmd` | exit `0` | Core API regression |
| `scripts\test_core_stack.cmd` | Core stack sanity tests | `postgres`, `redis`, `minio` | `scripts\test_core_stack.cmd` | exit `0` | Legal gate + pricing + optional full |
| `scripts\test_core_full.cmd` | System/smoke/contracts/integration suite | `postgres`, `redis`, `minio` | `scripts\test_core_full.cmd` | exit `0` | System + contracts |
| `scripts\test_core_api.cmd` | Run pytest inside core-api container | `core-api` running | `scripts\test_core_api.cmd -q` | exit `0` | Core API targeted |
| `scripts\test_auth_host.cmd` | Run pytest inside auth-host container | `auth-host` running | `scripts\test_auth_host.cmd -q` | exit `0` | Auth host |
| `scripts\smoke_all.cmd` | All smoke scripts | Core stack running | `scripts\smoke_all.cmd` | exit `0` | Smoke coverage |
| `scripts\smoke_billing_finance.cmd` | Billing + finance smoke | Core stack running | `scripts\smoke_billing_finance.cmd` | exit `0` | Billing & finance |
| `scripts\smoke_billing_v14.cmd` | Billing v14 flow | Core stack running | `scripts\smoke_billing_v14.cmd` | exit `0` | Billing |
| `scripts\smoke_billing_run.cmd` | Billing run smoke | Core stack running | `scripts\smoke_billing_run.cmd` | exit `0` | Billing |
| `scripts\smoke_invoice_state_machine.cmd` | Invoice transitions | Core stack running | `scripts\smoke_invoice_state_machine.cmd` | exit `0` | Billing |
| `scripts\smoke_legal_gate.cmd` | Legal gate enforcement | Core stack running | `scripts\smoke_legal_gate.cmd` | exit `0` | Legal gate |
| `scripts\smoke_onboarding_e2e.cmd` | Client onboarding flow | Core stack running | `scripts\smoke_onboarding_e2e.cmd` | exit `0` | CRM onboarding |
| `scripts\smoke_onec_export.cmd` | 1C export | Core stack running | `scripts\smoke_onec_export.cmd` | exit `0` | Integrations (1C) |
| `scripts\smoke_bank_statement_import.cmd` | Bank statement import | Core stack running | `scripts\smoke_bank_statement_import.cmd` | exit `0` | Integrations (bank) |
| `scripts\smoke_reconciliation_after_bank.cmd` | Bank reconciliation | Core stack running | `scripts\smoke_reconciliation_after_bank.cmd` | exit `0` | Reconciliation |
| `scripts\smoke_finance_negative_scenarios.cmd` | Negative finance flows | Core stack running | `scripts\smoke_finance_negative_scenarios.cmd` | exit `0` | Finance invariants |
| `scripts\smoke_fuel_ingest_batch.cmd` | Fleet ingest batch | Core stack running | `scripts\smoke_fuel_ingest_batch.cmd` | exit `0` | Fleet ingest |
| `scripts\smoke_fuel_offline_reconcile.cmd` | Fleet offline reconcile | Core stack running | `scripts\smoke_fuel_offline_reconcile.cmd` | exit `0` | Fleet offline |
| `scripts\smoke_fuel_replay_batch.cmd` | Fleet batch replay | Core stack running | `scripts\smoke_fuel_replay_batch.cmd` | exit `0` | Fleet replay |
| `scripts\smoke_edo_sbis_send.cmd` | EDO SBIS send | Core stack + SBIS env | `scripts\smoke_edo_sbis_send.cmd` | exit `0` | EDO SBIS |
| `scripts\smoke_edo_sbis_wait_signed.cmd` | EDO SBIS poll | Core stack + SBIS env | `scripts\smoke_edo_sbis_wait_signed.cmd` | exit `0` | EDO SBIS |
| `scripts\smoke_edo_sbis_revoke.cmd` | EDO SBIS revoke | Core stack + SBIS env | `scripts\smoke_edo_sbis_revoke.cmd` | exit `0` | EDO SBIS |
| `scripts\smoke_bi_ops_dashboard.cmd` | BI Ops dashboard | ClickHouse + BI enabled | `scripts\smoke_bi_ops_dashboard.cmd` | exit `0` | BI ops |
| `scripts\smoke_bi_partner_dashboard.cmd` | BI Partner dashboard | ClickHouse + BI enabled | `scripts\smoke_bi_partner_dashboard.cmd` | exit `0` | BI partner |
| `scripts\smoke_bi_client_spend_dashboard.cmd` | BI Client spend dashboard | ClickHouse + BI enabled | `scripts\smoke_bi_client_spend_dashboard.cmd` | exit `0` | BI client |
| `scripts\smoke_bi_cfo_dashboard.cmd` | BI CFO dashboard | ClickHouse + BI enabled | `scripts\smoke_bi_cfo_dashboard.cmd` | exit `0` | BI CFO |
| `scripts\smoke_notifications_invoice_email.cmd` | Email notification flow | Mailpit running | `scripts\smoke_notifications_invoice_email.cmd` | exit `0` | Notifications |
| `scripts\smoke_notifications_webhook.cmd` | Webhook notification flow | Core stack running | `scripts\smoke_notifications_webhook.cmd` | exit `0` | Notifications |
| `scripts\smoke_restart.cmd` | Stack restart smoke | Core stack running | `scripts\smoke_restart.cmd` | exit `0` | Ops reliability |
| `scripts\smoke_client_users_roles.cmd` | Client users/roles smoke | Core stack running | `scripts\smoke_client_users_roles.cmd` | stub (exit `1`) | Client users |
| `scripts\smoke_limits_apply_and_enforce.cmd` | Limits smoke | Core stack running | `scripts\smoke_limits_apply_and_enforce.cmd` | stub (exit `1`) | Fleet limits |
| `scripts\smoke_cards_issue.cmd` | Cards smoke | Core stack running | `scripts\smoke_cards_issue.cmd` | stub (exit `1`) | Fleet cards |
| `scripts\smoke_operations_explain.cmd` | Explain smoke | Core stack running | `scripts\smoke_operations_explain.cmd` | stub (exit `1`) | Explain |
| `scripts\smoke_closing_package.cmd` | Closing package smoke | Core stack running | `scripts\smoke_closing_package.cmd` | stub (exit `1`) | Documents |
| `scripts\smoke_reconciliation_request_sign.cmd` | Reconciliation request smoke | Core stack running | `scripts\smoke_reconciliation_request_sign.cmd` | stub (exit `1`) | Reconciliation requests |
| `scripts\smoke_support_ticket.cmd` | Support ticket smoke | Core stack running | `scripts\smoke_support_ticket.cmd` | stub (exit `1`) | Support cases |
| `scripts\smoke_partner_onboarding.cmd` | Partner onboarding smoke | Core stack running | `scripts\smoke_partner_onboarding.cmd` | stub (exit `1`) | Partner onboarding |
| `scripts\smoke_partner_webhooks.cmd` | Partner webhooks smoke | Integration-hub running | `scripts\smoke_partner_webhooks.cmd` | stub (exit `1`) | Webhooks |
| `scripts\smoke_partner_documents.cmd` | Partner documents smoke | Core stack running | `scripts\smoke_partner_documents.cmd` | stub (exit `1`) | EDO partner docs |
| `scripts\smoke_payouts_batch_export.cmd` | Payout export smoke | Core stack running | `scripts\smoke_payouts_batch_export.cmd` | stub (exit `1`) | Payout exports |
| `scripts\smoke_clearing_batch.cmd` | Clearing batch smoke | Core stack running | `scripts\smoke_clearing_batch.cmd` | stub (exit `1`) | Clearing |
| `scripts\smoke_reconciliation_run.cmd` | Reconciliation run smoke | Core stack running | `scripts\smoke_reconciliation_run.cmd` | stub (exit `1`) | Reconciliation |
| `scripts\smoke_dispute_refund.cmd` | Dispute/refund smoke | Core stack running | `scripts\smoke_dispute_refund.cmd` | stub (exit `1`) | Disputes/refunds |
| `scripts\chaos\chaos_postgres_restart.cmd` | Chaos: restart Postgres | Full stack running | `scripts\chaos\chaos_postgres_restart.cmd` | exit `0` | Ops reliability |
| `scripts\chaos\chaos_redis_flush.cmd` | Chaos: flush Redis | Full stack running | `scripts\chaos\chaos_redis_flush.cmd` | exit `0` | Ops reliability |
| `scripts\chaos\chaos_minio_down.cmd` | Chaos: MinIO down | Full stack running | `scripts\chaos\chaos_minio_down.cmd` | exit `0` | Ops reliability |
| `scripts\chaos\chaos_smoke_all.cmd` | Chaos suite | Full stack running | `scripts\chaos\chaos_smoke_all.cmd` | exit `0` | Ops reliability |
| `scripts\backup\backup_postgres.cmd` | Backup Postgres | Postgres running | `scripts\backup\backup_postgres.cmd` | exit `0` | Ops backup |
| `scripts\backup\backup_minio.cmd` | Backup MinIO | MinIO running | `scripts\backup\backup_minio.cmd` | exit `0` | Ops backup |
| `scripts\backup\backup_clickhouse.cmd` | Backup ClickHouse | ClickHouse running | `scripts\backup\backup_clickhouse.cmd` | exit `0` | Ops backup |
| `scripts\backup\verify_backup.cmd` | Verify backups | Backups present | `scripts\backup\verify_backup.cmd` | exit `0` | Ops backup |
| `scripts\backup\backup_restore_smoke.cmd` | Backup + restore smoke | Postgres/MinIO/ClickHouse | `scripts\backup\backup_restore_smoke.cmd` | exit `0` | Ops backup |
| `scripts\restore\restore_postgres.cmd` | Restore Postgres | Postgres running | `scripts\restore\restore_postgres.cmd` | exit `0` | Ops restore |
| `scripts\restore\restore_minio.cmd` | Restore MinIO | MinIO running | `scripts\restore\restore_minio.cmd` | exit `0` | Ops restore |
| `scripts\restore\restore_clickhouse.cmd` | Restore ClickHouse | ClickHouse running | `scripts\restore\restore_clickhouse.cmd` | exit `0` | Ops restore |
| `scripts\release\generate_release_notes.cmd` | Generate release notes | Git history | `scripts\release\generate_release_notes.cmd vYYYY.MM.PATCH` | exit `0` | Release |
| `scripts\seed_e2e.cmd` | Seed E2E demo data | Core stack + auth | `scripts\seed_e2e.cmd` | exit `0` | Seeds |
| `scripts\seed_billing.py` | Seed billing demo data | Core DB reachable | `python scripts\seed_billing.py` | exit `0` | Seeds |
| `scripts\seed_legal.py` | Seed legal docs | Core DB reachable | `python scripts\seed_legal.py` | exit `0` | Seeds |
