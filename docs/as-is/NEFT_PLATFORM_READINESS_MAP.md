# NEFT Platform — Readiness Map (AS-IS vs FINAL_VISION_BASELINE)

> **Эталон:** `docs/as-is/FINAL_VISION_BASELINE.md` (единственный baseline).
> **Правила:**
> - Статус домена: **DONE / PARTIAL / NOT IMPLEMENTED** (по факту кода).
> - Верификация: **VERIFIED_RUNTIME / VERIFIED (SKIP_OK) / NOT VERIFIED** (только при наличии runtime/test evidence).
> - Источник истины — репозиторий + `docs/as-is/STATUS_SNAPSHOT_RUNTIME_LATEST.md`.

---

## Readiness Matrix (по доменам baseline)

| Domain (baseline) | Status | Verification | AS-IS coverage (факт) | GAP vs baseline | Proof (code/tests/scripts) |
|---|---|---|---|---|---|
| Identity & Access (RBAC/ABAC, tenants, service identities) | PARTIAL | NOT VERIFIED | auth-host JWT + RBAC/ABAC + service identities в core | нет подтверждения полного tenant enforcement и сквозного RBAC для всех доменов | `platform/auth-host/app/main.py`, `platform/processing-core/app/security/rbac/`, `platform/processing-core/app/services/abac/`, `platform/processing-core/app/models/service_identity.py` |
| Processing & Transactions lifecycle (authorize/capture/reverse/refund, idempotency) | DONE | VERIFIED_RUNTIME | операции/транзакции + lifecycle сервисы | runtime подтверждение ограничено subset-тестами | `platform/processing-core/app/services/transactions.py`, `platform/processing-core/app/api/routes/transactions.py`, `scripts/verify_all.cmd`, `docs/as-is/STATUS_SNAPSHOT_RUNTIME_LATEST.md` |
| Pricing (versions, schedules, client/partner pricing) | PARTIAL | NOT VERIFIED | модели pricing + endpoints + marketplace pricing | нет полного coverage по версиям/графикам/партнёрским прайсам в runtime | `platform/processing-core/app/models/pricing.py`, `platform/processing-core/app/api/routes/prices.py`, `platform/processing-core/app/services/marketplace_pricing_service.py` |
| Rules/Limits (DSL, priorities, sandbox, audits) | PARTIAL | NOT VERIFIED | limit/rules модели + routes | нет отдельной DSL/sandbox среды и runtime подтверждения | `platform/processing-core/app/models/limit_rule.py`, `platform/processing-core/app/api/routes/limits.py` |
| Billing (invoices, payments, refunds, state machine) | DONE | VERIFIED (SKIP_OK) | billing flows + invoice state machine | runtime PASS со smoke SKIP_OK при отсутствии данных | `platform/processing-core/app/models/invoice.py`, `platform/processing-core/app/services/billing_service.py`, `scripts/billing_smoke.cmd`, `scripts/smoke_billing_finance.cmd`, `scripts/smoke_invoice_state_machine.cmd`, `docs/as-is/STATUS_SNAPSHOT_RUNTIME_LATEST.md` |
| Clearing / Settlement / Payouts | DONE | VERIFIED_RUNTIME | clearing/settlement/payouts модели и сервисы | runtime подтверждение ограничено subset-тестами | `platform/processing-core/app/models/clearing.py`, `platform/processing-core/app/services/settlement_service.py`, `scripts/verify_all.cmd`, `docs/as-is/STATUS_SNAPSHOT_RUNTIME_LATEST.md` |
| Reconciliation (runs, discrepancies, exports) | DONE | VERIFIED_RUNTIME | reconciliation runs + discrepancies | runtime подтверждение ограничено subset-тестами | `platform/processing-core/app/models/reconciliation.py`, `platform/processing-core/app/services/reconciliation_service.py`, `scripts/verify_all.cmd`, `docs/as-is/STATUS_SNAPSHOT_RUNTIME_LATEST.md` |
| Documents (templates, render PDF, sign, verify, closing packages) | DONE | VERIFIED_RUNTIME | core registry + document-service PDF/sign/verify | runtime подтверждение ограничено subset-тестами | `platform/processing-core/app/models/documents.py`, `platform/document-service/app/main.py`, `scripts/verify_all.cmd`, `docs/as-is/STATUS_SNAPSHOT_RUNTIME_LATEST.md` |
| EDO (integration реально, не stub) | PARTIAL | NOT VERIFIED | EDO модели + интеграционный stub | внешние провайдеры отсутствуют (stub/mock) | `platform/processing-core/app/models/edo.py`, `platform/integration-hub/neft_integration_hub/models/edo_stub.py` |
| Audit / Trust layer (hash-chain, signing, retention) | DONE | NOT VERIFIED | audit log + signing/retention модели | runtime PASS отсутствует | `platform/processing-core/app/models/audit_log.py`, `platform/processing-core/app/models/audit_retention.py`, `platform/processing-core/app/services/audit_signing.py` |
| Integrations hub (webhooks: intake/delivery/retry/replay, connectors) | PARTIAL | VERIFIED_RUNTIME | webhooks intake/delivery/retry/replay | внешние коннекторы отсутствуют | `platform/integration-hub/neft_integration_hub/services/webhooks.py`, `scripts/verify_all.cmd`, `docs/as-is/STATUS_SNAPSHOT_RUNTIME_LATEST.md` |
| Fleet/Fuel (cards, ingestion, anomalies, policies) | PARTIAL | NOT VERIFIED | fuel/fleet модели + ingestion providers | реальные провайдеры отсутствуют | `platform/processing-core/app/models/fuel.py`, `platform/processing-core/app/integrations/fuel/` |
| Marketplace (catalog, orders, SLA, promotions, recommendations) | PARTIAL | NOT VERIFIED | marketplace модели + SLA + promotions | внешние recommendation/ads сервисы отсутствуют | `platform/processing-core/app/models/marketplace_orders.py`, `platform/processing-core/app/models/marketplace_promotions.py` |
| Logistics (routes, tracking, deviation, ETA, explain) | PARTIAL | NOT VERIFIED | logistics-service compute + core модели | runtime PASS отсутствует | `platform/logistics-service/neft_logistics_service/main.py`, `platform/processing-core/app/models/logistics.py` |
| CRM (clients, deals, tickets/tasks, contracts linkage) | PARTIAL | NOT VERIFIED | CRM модели + stub сервис | полноценная CRM интеграция отсутствует | `platform/processing-core/app/models/crm.py`, `platform/crm-service/app/main.py` |
| Analytics/BI (exports, dashboards, optional ClickHouse) | PARTIAL | NOT VERIFIED | BI endpoints + optional marts | runtime ClickHouse не подтверждён | `platform/processing-core/app/api/v1/endpoints/bi.py`, `platform/processing-core/app/alembic/versions/20297240_0129_bi_runtime_marts_v1.py` |
| Notifications (channels, outbox, delivery logs) | PARTIAL | NOT VERIFIED | email/webhook notifications в core | каналы ограничены, runtime PASS отсутствует | `platform/processing-core/app/services/notifications_v1.py` |
| Frontends: Admin / Client / Partner | PARTIAL | NOT VERIFIED | SPA проекты + gateway маршруты | runtime e2e подтверждения нет | `frontends/admin-ui/`, `frontends/client-portal/`, `frontends/partner-portal/`, `gateway/nginx.conf` |
| Observability (metrics/logs/traces dashboards/targets) | PARTIAL | NOT VERIFIED | Prometheus/Grafana/OTel/Loki configs | runtime dashboards/targets не подтверждены | `infra/prometheus.yml`, `infra/otel-collector-config.yaml`, `infra/loki/loki-config.yml`, `docker-compose.yml` |

---

## Stage 0 — Verification Discipline

Status: **CLOSED**
Proof: `docs/as-is/STATUS_SNAPSHOT_RUNTIME_LATEST.md`
