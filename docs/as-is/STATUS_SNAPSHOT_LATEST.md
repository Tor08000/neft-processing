# STATUS SNAPSHOT — LATEST (Evidence-based, no runtime)

> Этот snapshot **не** про запуск. Он фиксирует, какие **артефакты проверки существуют в repo**: compose services, health endpoints, smoke scripts, tests.

---

## 1) Services in docker-compose.yml

| Service | Found in compose | Path |
|---|---|---|
| postgres | YES | `docker-compose.yml` |
| redis | YES | `docker-compose.yml` |
| clickhouse | YES | `docker-compose.yml` |
| minio | YES | `docker-compose.yml` |
| minio-health | YES | `docker-compose.yml` |
| minio-init | YES | `docker-compose.yml` |
| admin-web | YES | `docker-compose.yml` |
| client-web | YES | `docker-compose.yml` |
| partner-web | YES | `docker-compose.yml` |
| auth-host | YES | `docker-compose.yml` |
| core-api | YES | `docker-compose.yml` |
| integration-hub | YES | `docker-compose.yml` |
| ai-service | YES | `docker-compose.yml` |
| crm-service | YES | `docker-compose.yml` |
| logistics-service | YES | `docker-compose.yml` |
| document-service | YES | `docker-compose.yml` |
| workers | YES | `docker-compose.yml` |
| celery-exporter | YES | `docker-compose.yml` |
| beat | YES | `docker-compose.yml` |
| flower | YES | `docker-compose.yml` |
| gateway | YES | `docker-compose.yml` |
| otel-collector | YES | `docker-compose.yml` |
| jaeger | YES | `docker-compose.yml` |
| loki | YES | `docker-compose.yml` |
| promtail | YES | `docker-compose.yml` |
| prometheus | YES | `docker-compose.yml` |
| grafana | YES | `docker-compose.yml` |

---

## 2) Health endpoints (from RUNBOOK_LOCAL.md)

| Health endpoint | Listed in runbook | Path |
|---|---|---|
| `http://localhost/health` | YES | `docs/as-is/RUNBOOK_LOCAL.md` |
| `http://localhost/api/core/health` | YES | `docs/as-is/RUNBOOK_LOCAL.md` |
| `http://localhost/api/auth/health` | YES | `docs/as-is/RUNBOOK_LOCAL.md` |
| `http://localhost/api/ai/health` | YES | `docs/as-is/RUNBOOK_LOCAL.md` |
| `http://localhost/api/int/health` | YES | `docs/as-is/RUNBOOK_LOCAL.md` |
| `http://localhost:8001/api/core/health` | YES | `docs/as-is/RUNBOOK_LOCAL.md` |
| `http://localhost:8002/api/auth/health` | YES | `docs/as-is/RUNBOOK_LOCAL.md` |
| `http://localhost:8003/api/v1/health` | YES | `docs/as-is/RUNBOOK_LOCAL.md` |
| `http://localhost:8010/health` | YES | `docs/as-is/RUNBOOK_LOCAL.md` |
| `http://localhost:4173/health` | YES | `docs/as-is/RUNBOOK_LOCAL.md` |
| `http://localhost:4174/health` | YES | `docs/as-is/RUNBOOK_LOCAL.md` |
| `http://localhost:4175/health` | YES | `docs/as-is/RUNBOOK_LOCAL.md` |
| `http://localhost:9090/-/healthy` | YES | `docs/as-is/RUNBOOK_LOCAL.md` |
| `http://localhost:3000/health` | YES | `docs/as-is/RUNBOOK_LOCAL.md` |
| `http://localhost:16686/` | YES | `docs/as-is/RUNBOOK_LOCAL.md` |

---

## 3) Smoke scripts (scripts/)

| Script | Found | Path |
|---|---|---|
| `billing_smoke.cmd` | YES | `scripts/billing_smoke.cmd` |
| `smoke_billing_finance.cmd` | YES | `scripts/smoke_billing_finance.cmd` |
| `smoke_billing_v14.cmd` | YES | `scripts/smoke_billing_v14.cmd` |
| `smoke_finance_negative_scenarios.cmd` | YES | `scripts/smoke_finance_negative_scenarios.cmd` |
| `smoke_invoice_state_machine.cmd` | YES | `scripts/smoke_invoice_state_machine.cmd` |
| `smoke_local.sh` | YES | `scripts/smoke_local.sh` |
| `smoke_restart.cmd` | YES | `scripts/smoke_restart.cmd` |
| `smoke_legal_gate.cmd` | YES | `scripts/smoke_legal_gate.cmd` |
| `test_processing_core.cmd` | YES | `scripts/test_processing_core.cmd` |
| `test_core_stack.cmd` | YES | `scripts/test_core_stack.cmd` |
| `test_core_api.cmd` | YES | `scripts/test_core_api.cmd` |
| `test_core_full.cmd` | YES | `scripts/test_core_full.cmd` |
| `test_auth_host.cmd` | YES | `scripts/test_auth_host.cmd` |
| `verify_all.cmd` | YES | `scripts/verify_all.cmd` |

---

## 4) Key tests (tests/)

| Area | Found | Path |
|---|---|---|
| Auth | YES | `platform/auth-host/app/tests/test_auth.py` |
| Transactions | YES | `platform/processing-core/app/tests/test_transactions_pipeline.py` |
| Billing | YES | `platform/processing-core/app/tests/test_invoice_state_machine.py` |
| Settlement | YES | `platform/processing-core/app/tests/test_settlement_v1.py` |
| Reconciliation | YES | `platform/processing-core/app/tests/test_reconciliation_v1.py` |
| Documents | YES | `platform/processing-core/app/tests/test_documents_lifecycle.py` |
| Document service | YES | `platform/document-service/app/tests/test_service.py` |
| Document templates | YES | `platform/document-service/app/tests/test_templates.py` |
| Legal gate | YES | `platform/processing-core/app/tests/test_legal_gate.py` |
| Trust gates | YES | `platform/processing-core/app/tests/test_trust_gates.py` |
| Webhooks | YES | `platform/integration-hub/neft_integration_hub/tests/test_webhooks.py` |
| EDO stub | YES | `platform/integration-hub/neft_integration_hub/tests/test_edo_stub.py` |
| Logistics | YES | `platform/processing-core/app/tests/test_logistics_eta.py` |
| Marketplace | YES | `platform/processing-core/app/tests/test_marketplace_orders_v1.py` |
| Fleet/Fuel | YES | `platform/processing-core/app/tests/test_fleet_ingestion_v1.py` |
| Pricing | YES | `platform/processing-core/app/tests/test_pricing_service.py` |

---

## 5) Verification runs (this workspace)

| Check | Command | Result | Evidence |
|---|---|---|---|
| Document-service tests (root) | `pytest platform/document-service/app/tests -q` | **PASS** | Completed locally (11 passed). |
| Document-service tests (service cwd) | `cd platform/document-service && pytest -q` | **PASS** | Completed locally (11 passed). |
| Processing-core legal gate tests (docker) | `scripts\\test_core_stack.cmd` | **FAIL** | Docker not available in this environment. |
| Pricing entitlements tests (docker) | `scripts\\test_core_stack.cmd` | **FAIL** | Docker not available in this environment. |
| Processing-core full tests (docker) | `scripts\\test_core_stack.cmd --full` | **NOT RUN** | Requires docker compose stack. |
| Smoke legal gate (Windows CMD) | `scripts\\smoke_legal_gate.cmd` | **FAIL** | Docker not available in this environment. |
