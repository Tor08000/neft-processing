# NEFT Platform — Verified Evidence Index

> Индекс артефактов проверки, которые **реально существуют в repo**.
> Все элементы ниже — фактические файлы/скрипты в репозитории.

| Item | Evidence type | Path | What it proves |
|---|---|---|---|
| Full verification gate (compose + migrations + health/metrics + smoke + pytest subset) | VERIFIED_BY_SMOKE | `scripts/verify_all.cmd` | Единая точка правды: поднимает stack, применяет миграции, проверяет health/metrics, запускает smoke subset и pytest subset (core + integration-hub). |
| Runtime snapshot (latest) | VERIFIED_BY_RUNTIME (status only) | `docs/as-is/STATUS_SNAPSHOT_RUNTIME_LATEST.md` | Фиксирует текущий runtime-статус (в т.ч. факт, что verify_all не выполнялся). |
| Auth health + metrics tests | VERIFIED_BY_TESTS | `platform/auth-host/app/tests/test_health.py`, `platform/auth-host/app/tests/test_metrics.py` | Health/metrics endpoints auth-host. |
| Core transactions pipeline | VERIFIED_BY_TESTS | `platform/processing-core/app/tests/test_transactions_pipeline.py` | authorize/capture/refund/reverse pipeline. |
| Billing invoice state machine | VERIFIED_BY_TESTS | `platform/processing-core/app/tests/test_invoice_state_machine.py` | переходы/инварианты invoice state machine. |
| Settlement flows | VERIFIED_BY_TESTS | `platform/processing-core/app/tests/test_settlement_v1.py` | settlement модели/сервисы. |
| Reconciliation runs | VERIFIED_BY_TESTS | `platform/processing-core/app/tests/test_reconciliation_v1.py` | reconciliation runs + discrepancies. |
| Documents lifecycle | VERIFIED_BY_TESTS | `platform/processing-core/app/tests/test_documents_lifecycle.py` | registry документов и жизненный цикл. |
| Integration-hub webhooks | VERIFIED_BY_TESTS | `platform/integration-hub/neft_integration_hub/tests/test_webhooks.py` | intake/delivery/retry/replay basics. |
| EDO stub | VERIFIED_BY_TESTS | `platform/integration-hub/neft_integration_hub/tests/test_edo_stub.py` | EDO stub workflow. |
| Document service render/sign | VERIFIED_BY_TESTS | `platform/document-service/app/tests/test_service.py`, `platform/document-service/app/tests/test_sign_service.py` | PDF render/verify + signing service. |
| RBAC roles wiring | VERIFIED_BY_TESTS | `platform/processing-core/app/security/rbac/test_rbac_roles_import.py` | наличие roles/permissions mapping. |
| ABAC policy engine | VERIFIED_BY_TESTS | `platform/processing-core/app/tests/test_abac_policies.py`, `platform/processing-core/app/tests/test_abac_explain.py` | policies CRUD + explain. |
| Admin token helper | VERIFIED_BY_SMOKE | `scripts/get_admin_token.cmd` | token-only stdout для admin token (используется smokes). |
| Billing smoke (PASS or SKIP_OK by script logic) | VERIFIED_BY_SMOKE | `scripts/billing_smoke.cmd` | billing smoke: PASS или SKIP_OK при отсутствии инвойсов. |
| Billing finance smoke | VERIFIED_BY_SMOKE | `scripts/smoke_billing_finance.cmd` | billing finance smoke. |
| Invoice state machine smoke (conditional) | VERIFIED_BY_SMOKE | `scripts/smoke_invoice_state_machine.cmd` | invoice state transitions via smoke script (SKIP_OK when no invoices). |
| Core API healthcheck | VERIFIED_BY_SMOKE | `docker-compose.yml` (`core-api.healthcheck`) | health gate for core-api. |
| Auth-host healthcheck | VERIFIED_BY_SMOKE | `docker-compose.yml` (`auth-host.healthcheck`) | auth service health gate. |
| Integration-hub healthcheck | VERIFIED_BY_SMOKE | `docker-compose.yml` (`integration-hub.healthcheck`) | integration hub health gate. |
| Gateway healthcheck | VERIFIED_BY_SMOKE | `docker-compose.yml` (`gateway.healthcheck`) | gateway health endpoint. |
| Frontend healthchecks | VERIFIED_BY_SMOKE | `docker-compose.yml` (`admin-web/client-web/partner-web.healthcheck`) | SPA readiness gates. |
| Infra/observability healthchecks | VERIFIED_BY_SMOKE | `docker-compose.yml` (`postgres/redis/minio-health/otel-collector/jaeger/prometheus/grafana` healthchecks) | infra & observability service gates. |
