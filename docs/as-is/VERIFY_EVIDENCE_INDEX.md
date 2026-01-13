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
| Core API smoke | VERIFIED_BY_SMOKE_SCRIPT | `scripts/test_core_api.cmd` | smoke по core API |
| Billing smoke | VERIFIED_BY_SMOKE_SCRIPT | `scripts/billing_smoke.cmd` | billing e2e smoke |
| Invoice state machine smoke | VERIFIED_BY_SMOKE_SCRIPT | `scripts/smoke_invoice_state_machine.cmd` | invoice state transitions via smoke script |
| Full verification gate | VERIFIED_BY_SMOKE_SCRIPT | `scripts/verify_all.cmd` | единая точка проверки: compose, миграции, health, metrics, smoke, pytest subset |
| Core API health | VERIFIED_BY_COMPOSE_HEALTHCHECK | `docker-compose.yml` (`core-api.healthcheck`) | health gate for core-api |
| Gateway health | VERIFIED_BY_COMPOSE_HEALTHCHECK | `docker-compose.yml` (`gateway.healthcheck`) | gateway health endpoint |
| Observability health | VERIFIED_BY_COMPOSE_HEALTHCHECK | `docker-compose.yml` (`prometheus/grafana/otel-collector/jaeger` healthchecks) | monitoring services health gates |
