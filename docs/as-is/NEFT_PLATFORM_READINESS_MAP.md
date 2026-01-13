# NEFT Platform — Readiness Map (AS-IS vs FINAL_VISION_BASELINE)

> **Эталон:** `docs/as-is/FINAL_VISION_BASELINE.md` (единственный baseline).
> **Правила:**
> - Статус домена: **DONE / PARTIAL / NOT IMPLEMENTED** (по факту кода).
> - Верификация: **VERIFIED / VERIFIED (SKIP_OK) / NOT VERIFIED** (только при наличии runtime/test evidence).
> - Источник истины — репозиторий; без runtime-логов статус = **NOT VERIFIED**.

---

## Readiness Matrix (по доменам baseline)

| Domain (baseline) | Status | Verification | AS-IS coverage (факт) | GAP vs baseline | Proof (code/tests/scripts) |
|---|---|---|---|---|---|
| Identity & Access (RBAC/ABAC, tenants, service identities) | PARTIAL | NOT VERIFIED | auth-host JWT + RBAC/ABAC + service identities в core | нет подтверждения полного tenant enforcement и сквозного RBAC для всех доменов | `platform/auth-host/app/main.py`, `platform/processing-core/app/security/rbac/`, `platform/processing-core/app/services/abac/`, `platform/processing-core/app/models/service_identity.py` |
| Processing & Transactions lifecycle (authorize/capture/reverse/refund, idempotency) | DONE | NOT VERIFIED | операции/транзакции + lifecycle сервисы | runtime PASS отсутствует | `platform/processing-core/app/services/transactions.py`, `platform/processing-core/app/api/routes/transactions.py`, `platform/processing-core/app/tests/test_transactions_pipeline.py` |
| Pricing (versions, schedules, client/partner pricing) | PARTIAL | NOT VERIFIED | модели pricing + endpoints + marketplace pricing | нет полного coverage по версиям/графикам/партнёрским прайсам в runtime | `platform/processing-core/app/models/pricing.py`, `platform/processing-core/app/api/routes/prices.py`, `platform/processing-core/app/services/marketplace_pricing_service.py` |
| Rules/Limits (DSL, priorities, sandbox, audits) | PARTIAL | NOT VERIFIED | limit/rules модели + routes | нет отдельной DSL/sandbox среды и runtime подтверждения | `platform/processing-core/app/models/limit_rule.py`, `platform/processing-core/app/api/routes/limits.py`, `platform/processing-core/app/tests/test_limits_v2.py` |
| Billing (invoices, payments, refunds, state machine) | DONE | NOT VERIFIED | billing flows + invoice state machine | runtime PASS отсутствует (invoice smoke возможен SKIP) | `platform/processing-core/app/models/invoice.py`, `platform/processing-core/app/services/billing_service.py`, `platform/processing-core/app/tests/test_invoice_state_machine.py`, `scripts/billing_smoke.cmd` |
| Clearing / Settlement / Payouts | DONE | NOT VERIFIED | clearing/settlement/payouts модели и сервисы | runtime PASS отсутствует | `platform/processing-core/app/models/clearing.py`, `platform/processing-core/app/services/settlement_service.py`, `platform/processing-core/app/tests/test_settlement_v1.py` |
| Reconciliation (runs, discrepancies, exports) | DONE | NOT VERIFIED | reconciliation runs + discrepancies | runtime PASS отсутствует | `platform/processing-core/app/models/reconciliation.py`, `platform/processing-core/app/services/reconciliation_service.py`, `scripts/smoke_reconciliation_run.cmd` |
| Documents (templates, render PDF, sign, verify, closing packages) | DONE | NOT VERIFIED | core registry + document-service PDF/sign/verify | runtime PASS отсутствует | `platform/processing-core/app/models/documents.py`, `platform/document-service/app/main.py`, `platform/document-service/app/tests/test_templates.py` |
| EDO (integration реально, не stub) | PARTIAL | NOT VERIFIED | EDO модели + интеграционный stub | внешние провайдеры отсутствуют (stub/mock) | `platform/processing-core/app/models/edo.py`, `platform/integration-hub/neft_integration_hub/models/edo_stub.py`, `scripts/smoke_edo_sbis_send.cmd` |
| Audit / Trust layer (hash-chain, signing, retention) | DONE | NOT VERIFIED | audit log + signing/retention модели | runtime PASS отсутствует | `platform/processing-core/app/models/audit_log.py`, `platform/processing-core/app/models/audit_retention.py`, `platform/processing-core/app/services/audit_signing.py` |
| Integrations hub (webhooks: intake/delivery/retry/replay, connectors) | PARTIAL | NOT VERIFIED | webhooks intake/delivery/retry/replay | внешние коннекторы отсутствуют | `platform/integration-hub/neft_integration_hub/services/webhooks.py`, `platform/integration-hub/neft_integration_hub/tests/test_webhooks.py` |
| Fleet/Fuel (cards, ingestion, anomalies, policies) | PARTIAL | NOT VERIFIED | fuel/fleet модели + ingestion providers | реальные провайдеры отсутствуют | `platform/processing-core/app/models/fuel.py`, `platform/processing-core/app/integrations/fuel/`, `scripts/smoke_fuel_ingest_batch.cmd` |
| Marketplace (catalog, orders, SLA, promotions, recommendations) | PARTIAL | NOT VERIFIED | marketplace модели + SLA + promotions | внешние recommendation/ads сервисы отсутствуют | `platform/processing-core/app/models/marketplace_orders.py`, `platform/processing-core/app/models/marketplace_promotions.py`, `platform/processing-core/app/tests/test_marketplace_orders_v1.py` |
| Logistics (routes, tracking, deviation, ETA, explain) | PARTIAL | NOT VERIFIED | logistics-service compute + core models | runtime PASS отсутствует | `platform/logistics-service/neft_logistics_service/main.py`, `platform/processing-core/app/models/logistics.py`, `platform/processing-core/app/tests/test_logistics_eta.py` |
| CRM (clients, deals, tickets/tasks, contracts linkage) | PARTIAL | NOT VERIFIED | CRM модели + stub сервис | полноценная CRM интеграция отсутствует | `platform/processing-core/app/models/crm.py`, `platform/crm-service/app/main.py`, `platform/processing-core/app/tests/test_crm_clients.py` |
| Analytics/BI (exports, dashboards, optional ClickHouse) | PARTIAL | NOT VERIFIED | BI endpoints + optional marts | runtime ClickHouse не подтверждён | `platform/processing-core/app/api/v1/endpoints/bi.py`, `platform/processing-core/app/alembic/versions/20297240_0129_bi_runtime_marts_v1.py`, `scripts/smoke_bi_ops_dashboard.cmd` |
| Notifications (channels, outbox, delivery logs) | PARTIAL | NOT VERIFIED | email/webhook notifications в core | каналы ограничены, runtime PASS отсутствует | `platform/processing-core/app/services/notifications_v1.py`, `platform/processing-core/app/tests/test_notifications_webhook.py`, `scripts/smoke_notifications_webhook.cmd` |
| Frontends: Admin / Client / Partner | PARTIAL | NOT VERIFIED | SPA проекты + gateway маршруты | runtime e2e подтверждения нет | `frontends/admin-ui/`, `frontends/client-portal/`, `frontends/partner-portal/`, `gateway/nginx.conf` |
| Observability (metrics/logs/traces dashboards/targets) | PARTIAL | NOT VERIFIED | Prometheus/Grafana/OTel/Loki configs | runtime dashboards/targets не подтверждены | `infra/prometheus.yml`, `infra/otel-collector-config.yaml`, `infra/loki/loki-config.yml`, `docker-compose.yml` |

---

## Примечание по верификации

- Runtime-verify (`scripts/verify_all.cmd`) в репозитории не выполнялся; см. `docs/as-is/STATUS_SNAPSHOT_RUNTIME_LATEST.md`.
- Smoke/pytest скрипты и наборы перечислены в `docs/as-is/VERIFY_EVIDENCE_INDEX.md` и `docs/as-is/STATUS_SNAPSHOT_LATEST.md` как артефакты, без статуса PASS.
