# STATUS SNAPSHOT — RUNTIME LATEST

**Runtime status:** verify_all PASS.
**Generated:** 2026-01-13

## Steps (verify_all)

| Step | Status | Details |
| --- | --- | --- |
| 1. Stack up | OK | docker compose up -d --build |
| 2.1 Migrations | OK | scripts\migrate.cmd |
| 2.2 Alembic core-api current | OK | alembic -c app/alembic.ini current |
| 2.3 Alembic auth-host current | OK | alembic -c alembic.ini current |
| 2.9 Wait core-api via gateway | OK | core-api ready |
| 3. Health checks | OK | /health, /api/core/health, /api/auth/health, /api/ai/health, /api/int/health |
| 4. Metrics checks | OK | /metrics, /api/core/metrics, http://localhost:8010/metrics |
| 5.1 auth-host tests subset | OK | pytest app/tests/test_health.py app/tests/test_metrics.py -q |
| 5.x scripts\billing_smoke.cmd | SKIP_OK | [SKIP] no billing data present |
| 5.x scripts\smoke_billing_finance.cmd | OK | PASS |
| 5.x scripts\smoke_invoice_state_machine.cmd | SKIP_OK | [SKIP] no invoices present |
| 5. Smoke scripts | OK | All smoke scripts OK (SKIP_OK accepted) |
| 6.1 core tests subset | OK | pytest app/tests/test_transactions_pipeline.py ... test_documents_lifecycle.py |
| 6.2 integration-hub webhooks | OK | pytest neft_integration_hub/tests/test_webhooks.py |
| 6. Pytest smoke subset | OK | All pytest checks OK |
| verify_all.cmd | OK | Completed with SKIP_OK in smoke subset |

## Smoke outcomes (explicit)

| Smoke script | Status | Notes |
| --- | --- | --- |
| scripts\billing_smoke.cmd | SKIP_OK | Нет данных для сценария (SKIP считается PASS). |
| scripts\smoke_billing_finance.cmd | PASS | Базовый billing/finance smoke завершён. |
| scripts\smoke_invoice_state_machine.cmd | SKIP_OK | Нет инвойсов (SKIP считается PASS). |

## Errors

- None
