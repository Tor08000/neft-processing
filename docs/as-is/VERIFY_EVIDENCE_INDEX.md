# NEFT Platform — Verified Evidence Index

> Индекс артефактов проверки, которые **реально существуют в repo**.

| Item | Evidence type | Path | What it proves |
|---|---|---|---|
| Auth health + JWT basics | VERIFIED_BY_TESTS | `platform/auth-host/app/tests/test_auth.py` | базовые auth flows и JWT обработка |
| RBAC roles wiring | VERIFIED_BY_TESTS | `platform/processing-core/app/security/rbac/test_rbac_roles_import.py` | наличие roles/permissions mapping |
| Transactions pipeline | VERIFIED_BY_TESTS | `platform/processing-core/app/tests/test_transactions_pipeline.py` | authorize/capture/refund/reverse pipeline |
| Billing invoice state machine | VERIFIED_BY_TESTS | `platform/processing-core/app/tests/test_invoice_state_machine.py` | переходы/инварианты invoice state machine |
| Settlement flows | VERIFIED_BY_TESTS | `platform/processing-core/app/tests/test_settlement_v1.py` | расчёт и settlement модели/сервисы |
| Reconciliation runs | VERIFIED_BY_TESTS | `platform/processing-core/app/tests/test_reconciliation_v1.py` | reconciliation runs + discrepancies |
| Document render/sign | VERIFIED_BY_TESTS | `platform/document-service/app/tests/test_service.py` | PDF render/verify and health/metrics |
| Documents lifecycle | VERIFIED_BY_TESTS | `platform/processing-core/app/tests/test_documents_lifecycle.py` | registry документов и жизненный цикл |
| EDO stub | VERIFIED_BY_TESTS | `platform/integration-hub/neft_integration_hub/tests/test_edo_stub.py` | EDO stub workflow |
| Webhooks intake/delivery | VERIFIED_BY_TESTS | `platform/integration-hub/neft_integration_hub/tests/test_webhooks.py` | intake/delivery/retry/replay basics |
| Core API smoke | VERIFIED_BY_SMOKE | `scripts/test_core_api.cmd` | smoke по core API |
| Token contract: stdout token-only | VERIFIED_BY_SMOKE | `scripts/get_admin_token.cmd` | token-only stdout для admin token (используется smokes) |
| Full verification gate | VERIFIED_BY_SMOKE | `scripts/verify_all.cmd` | full verification gate (health/metrics/smoke/pytest subset) |
| Billing smoke (PASS or SKIP_OK) | VERIFIED_BY_SMOKE | `scripts/billing_smoke.cmd` | billing smoke: PASS или SKIP_OK при отсутствии инвойсов |
| Billing finance smoke | VERIFIED_BY_SMOKE | `scripts/smoke_billing_finance.cmd` | billing finance smoke |
| Invoice state machine smoke (conditional) | VERIFIED_BY_SMOKE | `scripts/smoke_invoice_state_machine.cmd` | invoice state transitions via smoke script (SKIP_OK when no invoices) |
| Core API healthcheck | VERIFIED_BY_SMOKE | `docker-compose.yml` (`core-api.healthcheck`) | health gate for core-api |
| Auth-host healthcheck | VERIFIED_BY_SMOKE | `docker-compose.yml` (`auth-host.healthcheck`) | auth service health gate |
| Integration-hub healthcheck | VERIFIED_BY_SMOKE | `docker-compose.yml` (`integration-hub.healthcheck`) | integration hub health gate |
| Gateway healthcheck | VERIFIED_BY_SMOKE | `docker-compose.yml` (`gateway.healthcheck`) | gateway health endpoint |
| Frontend healthchecks | VERIFIED_BY_SMOKE | `docker-compose.yml` (`admin-web/client-web/partner-web.healthcheck`) | SPA readiness gates |
| Infra healthchecks | VERIFIED_BY_SMOKE | `docker-compose.yml` (`postgres/redis/minio-health/otel-collector/jaeger/prometheus/grafana` healthchecks) | infra & observability service gates |
