# NEFT Platform — Readiness Map v3 (AS-IS facts + Baseline coverage + Verified evidence)

> **Источники фактов (обязательные):**
> - `docs/as-is/NEFT_PLATFORM_AS_IS_MASTER.md`
> - `docs/as-is/FINAL_VISION_BASELINE.md`
> - `docs/as-is/SERVICE_CATALOG.md`
> - `docs/as-is/DB_SCHEMA_MAP.md`
> - `docs/as-is/EVENT_CATALOG.md`
> - `docs/as-is/RUNBOOK_LOCAL.md`
> - `docs/as-is/STATUS_SNAPSHOT_2026-01-03.md` (исторический, не источник истины)
> - код репозитория (compose, routers, services, models, tests, scripts)

**Запрещено:** писать «планируется/в будущем», ссылаться на внешние диалоги/логи, ставить VERIFIED без артефактов в repo.

---

## 1) Шкалы статусов (две независимые оси)

### 1.1 CODE STATUS (кодовая готовность)
- **CODED_FULL** — реализовано полностью как подсистема (модели + сервисы + роутеры)
- **CODED_PARTIAL** — реализовано частично (в таблице перечислено что именно)
- **NOT_IMPLEMENTED** — отсутствует

### 1.2 VERIFY STATUS (проверенность)
- **VERIFIED_BY_TESTS** — есть тесты в repo (pytest/npm) и указан файл теста
- **VERIFIED_BY_SMOKE_SCRIPT** — есть `scripts/*.cmd` и указан скрипт
- **VERIFIED_BY_COMPOSE_HEALTHCHECK** — есть healthcheck в compose и указан путь
- **NOT_VERIFIED** — нет артефактов проверки в repo

**Важно:** VERIFIED определяется **только** артефактами в repo (tests/scripts/healthchecks), а не тем, выполнялись ли команды в этом чате.

---

## 2) Executive Summary (AS-IS факты + baseline coverage + evidence)

**AS-IS CODED (факты из repo):**
- Есть core API (`platform/processing-core`), auth-host, integration-hub, ai-service, document-service, logistics-service, crm-service, Celery workers/beat, gateway, фронтенды Admin/Client/Partner. (`docker-compose.yml`, `platform/*/app/main.py`, `frontends/*/src/App.tsx`)
- В `processing-core` реализованы модели/сервисы/роутеры для billing, settlement, reconciliation, documents, audit, fleet, marketplace, pricing, limits/rules и т.д. (`platform/processing-core/app/models`, `.../services`, `.../routers`)

**FINAL VISION COVERAGE (сравнение с baseline):**
- Полностью покрыто по коду: processing lifecycle, billing, settlement/payouts, reconciliation, audit/trust, logistics, базовые webhooks в integration-hub.
- Частично покрыто: pricing (только часть контуров), rules/limits (без полноценного DSL/sandbox), documents+EDO (EDO stub), fleet/fuel (stub провайдер), marketplace (без внешнего ML), CRM (stub), analytics/BI (без проверенного ClickHouse), notifications (stub провайдеры), фронтенды (нет доказательств end-to-end UX).
- Не покрыто: service identities и ABAC-политики как отдельные подсистемы.

**VERIFIED EVIDENCE (по артефактам в repo):**
- Тесты: `platform/processing-core/app/tests/*`, `platform/auth-host/app/tests/*`, `platform/integration-hub/neft_integration_hub/tests/*`, `platform/document-service/app/tests/*`.
- Smoke scripts: `scripts/*.cmd` (например `billing_smoke.cmd`, `smoke_billing_finance.cmd`).
- Compose healthchecks: `docker-compose.yml` (core-api, auth-host, integration-hub, ai-service, frontends, gateway, observability и др.).

---

## 3) Readiness Matrix (Domain → CODE STATUS + VERIFY STATUS + Coverage)

**Формат статуса:** `<CODE STATUS> + <VERIFY STATUS>`

| Domain / Module | Status | FINAL VISION Coverage | AS-IS evidence (code paths) | Missing vs baseline | Verify artifacts (repo paths) |
|---|---|---|---|---|---|
| **Identity & Access — RBAC (roles + permission guard)** | **CODED_PARTIAL + VERIFIED_BY_TESTS** | PARTIAL | `platform/processing-core/app/security/rbac/*`, `platform/auth-host/app/alembic/versions/20251001_0001_auth_bootstrap.py` | RBAC есть, но покрытие ролей/разрешений не подтверждено для всех доменов | `platform/processing-core/app/security/rbac/test_rbac_roles_import.py`, `platform/auth-host/app/tests/test_auth.py` |
| **Identity & Access — Tenant isolation** | **CODED_PARTIAL + NOT_VERIFIED** | PARTIAL | `tenant_id` в моделях/миграциях (`platform/processing-core/app/alembic/versions/*`), фильтрация в отдельных роутерах (`platform/processing-core/app/routers/client_marketplace.py`) | Нет системной гарантии tenant enforcement для всех доменов | нет явных тестов/скриптов |
| **Identity & Access — Service identities** | **NOT_IMPLEMENTED + NOT_VERIFIED** | NONE | Только env `SERVICE_TOKEN` в `platform/auth-host/app/settings.py` | Нет сервисных ролей/токенов/идентификаторов и enforcement | нет |
| **Identity & Access — ABAC/policy engine** | **CODED_PARTIAL + VERIFIED_BY_TESTS** | PARTIAL | `platform/processing-core/app/services/policy/*` используется в billing/documents | Нет полноценного ABAC (атрибутные политики вне role-based) | `platform/processing-core/app/tests/test_policy_engine.py` |
| **Processing & Transactions lifecycle** | **CODED_FULL + VERIFIED_BY_TESTS** | FULL | `platform/processing-core/app/api/routes/transactions.py`, `.../services/transactions.py` | — | `platform/processing-core/app/tests/test_transactions_*` |
| **Pricing — Fuel pricing (prices)** | **CODED_PARTIAL + VERIFIED_BY_TESTS** | PARTIAL | `platform/processing-core/app/api/routes/prices.py`, `/internal/pricing/resolve` в `platform/processing-core/app/api/routes/auth.py` | Нет полного контура клиентских/партнёрских прайсингов | `platform/processing-core/app/tests/test_pricing_service.py` |
| **Pricing — Marketplace offers/promotions/sponsored** | **CODED_PARTIAL + VERIFIED_BY_TESTS** | PARTIAL | модели `platform/processing-core/app/models/marketplace_*.py`, роутеры `platform/processing-core/app/routers/*marketplace*` | Нет внешнего ML/recommendations сервиса | `platform/processing-core/app/tests/test_marketplace_pricing_v1.py`, `test_marketplace_recommendations_v1.py` |
| **Pricing — Versioning/schedules** | **CODED_PARTIAL + NOT_VERIFIED** | PARTIAL | таблицы `price_list`/versioning в `docs/as-is/DB_SCHEMA_MAP.md`, SQL с `version`, `start_at`, `end_at` в `platform/processing-core/app/api/routes/auth.py` | Нет явных API/воркфлоу для управления версиями/расписаниями | нет явных тестов/скриптов |
| **Rules/Limits — Operational limits & rules** | **CODED_FULL + VERIFIED_BY_TESTS** | PARTIAL | `platform/processing-core/app/api/routes/limits.py`, `.../services/limits.py`, `.../api/routes/rules.py` | Нет DSL/sandbox среды | `platform/processing-core/app/tests/test_limits_v2.py`, `test_admin_limits_api.py` |
| **Rules/Limits — Risk rules/policies (risk_*)** | **CODED_FULL + VERIFIED_BY_TESTS** | PARTIAL | `risk_*` таблицы в `docs/as-is/DB_SCHEMA_MAP.md`, модели `platform/processing-core/app/models/risk_*.py`, `.../routers/admin/risk_rules.py` | Нет sandbox среды / версии правил не подтверждены тестами энд-то-энд | `platform/processing-core/app/tests/test_risk_rules_repository.py`, `test_admin_risk_rules_api.py` |
| **Rules/Limits — Sandbox/evaluate** | **CODED_PARTIAL + NOT_VERIFIED** | PARTIAL | `POST /internal/rules/evaluate` (`platform/processing-core/app/api/routes/auth.py`), what-if (`platform/processing-core/app/routers/admin/what_if.py`) | Нет выделенной sandbox подсистемы | нет явных тестов/скриптов |
| **Billing** | **CODED_FULL + VERIFIED_BY_TESTS** | FULL | `platform/processing-core/app/models/billing_flow.py`, `.../services/billing_service.py`, `.../routers/admin/billing.py` | — | `platform/processing-core/app/tests/test_invoice_state_machine.py`, `test_billing_*` |
| **Clearing / Settlement / Payouts** | **CODED_FULL + VERIFIED_BY_TESTS** | FULL | `platform/processing-core/app/models/settlement.py`, `.../services/settlement_service.py`, `.../services/payouts_service.py` | — | `platform/processing-core/app/tests/test_settlement_v1.py`, `test_settlements.py` |
| **Reconciliation** | **CODED_FULL + VERIFIED_BY_TESTS** | FULL | `platform/processing-core/app/models/reconciliation.py`, `.../services/reconciliation_service.py` | — | `platform/processing-core/app/tests/test_reconciliation_v1.py` |
| **Documents — PDF render/sign/verify** | **CODED_FULL + VERIFIED_BY_TESTS** | FULL | `platform/document-service/app/main.py` | — | `platform/document-service/app/tests/test_service.py`, `test_sign_service.py` |
| **Documents — Core registry (documents/closing packages/exports)** | **CODED_FULL + VERIFIED_BY_TESTS** | FULL | `platform/processing-core/app/models/documents.py`, `.../routers/client_documents.py` | — | `platform/processing-core/app/tests/test_documents_lifecycle.py` |
| **EDO integration (real vs stub)** | **CODED_PARTIAL + VERIFIED_BY_TESTS** | PARTIAL | `platform/integration-hub/neft_integration_hub/services/edo_stub.py` | Реальные EDO провайдеры отсутствуют | `platform/integration-hub/neft_integration_hub/tests/test_edo_stub.py` |
| **Audit / Trust layer** | **CODED_FULL + VERIFIED_BY_TESTS** | FULL | `platform/processing-core/app/models/audit_log.py`, `.../services/audit_signing.py` | — | `platform/processing-core/app/tests/test_audit_log.py`, `test_audit_signing_*` |
| **Integrations Hub — Webhooks** | **CODED_FULL + VERIFIED_BY_TESTS** | PARTIAL | `platform/integration-hub/neft_integration_hub/services/webhooks.py` | Нет внешних коннекторов (кроме stub) | `platform/integration-hub/neft_integration_hub/tests/test_webhooks.py`, `test_webhook_intake.py` |
| **Fleet/Fuel** | **CODED_PARTIAL + VERIFIED_BY_TESTS** | PARTIAL | `platform/processing-core/app/models/fuel.py`, `.../services/fleet_service.py`, `.../integrations/fuel/providers/stub_provider.py` | Реальные топливные провайдеры отсутствуют | `platform/processing-core/app/tests/test_fleet_*`, `test_fuel_limits_engine.py` |
| **Marketplace** | **CODED_PARTIAL + VERIFIED_BY_TESTS** | PARTIAL | `platform/processing-core/app/models/marketplace_*.py`, `.../routers/client_marketplace*.py` | Нет внешнего recommendation/ads сервиса | `platform/processing-core/app/tests/test_marketplace_*` |
| **CRM** | **CODED_PARTIAL + VERIFIED_BY_TESTS** | PARTIAL | модели `platform/processing-core/app/models/crm.py`, stub `platform/crm-service/app/main.py` | Реальная CRM интеграция отсутствует | `platform/processing-core/app/tests/test_crm_*` |
| **Logistics** | **CODED_FULL + VERIFIED_BY_TESTS** | FULL | `platform/logistics-service/neft_logistics_service/main.py`, `platform/processing-core/app/models/logistics.py` | — | `platform/processing-core/app/tests/test_logistics_*` |
| **Analytics/BI** | **CODED_PARTIAL + VERIFIED_BY_TESTS** | PARTIAL | `platform/processing-core/app/models/bi.py`, `.../services/bi/metrics.py`, `docker-compose.yml` (clickhouse) | Runtime ClickHouse не подтвержден | `platform/processing-core/app/tests/test_bi_exports_v1_1.py` |
| **Notifications** | **CODED_PARTIAL + VERIFIED_BY_TESTS** | PARTIAL | `platform/processing-core/app/services/fleet_notification_dispatcher.py` | Реальные каналы в основном stub | `platform/processing-core/app/tests/test_fleet_notifications_*`, `test_notification_stub_providers.py` |
| **Frontends — Admin/Client/Partner** | **CODED_PARTIAL + VERIFIED_BY_COMPOSE_HEALTHCHECK** | PARTIAL | `frontends/*/src/App.tsx`, `docker-compose.yml` | Нет доказательств end-to-end UX сценариев | compose healthchecks в `docker-compose.yml` (admin-web/client-web/partner-web) |
| **Observability (metrics/logs/traces)** | **CODED_FULL + VERIFIED_BY_COMPOSE_HEALTHCHECK** | FULL | `infra/prometheus.yml`, `infra/grafana/`, `infra/otel-collector-config.yaml` | Loki/Promtail без healthchecks | compose healthchecks в `docker-compose.yml` (gateway/prometheus/grafana/otel-collector/jaeger) |

---

## 4) Scenarios Coverage (FINAL_VISION_BASELINE)

**Формат карточки:**
- Scenario
- Coverage: **FULL / PARTIAL / NONE**
- What exists in code
- Missing links
- Verify artifacts

### 4.1 Onboarding: клиент → роли → подписки/лимиты → карты → первые операции
- **Coverage:** PARTIAL
- **What exists in code:** auth-host bootstrap + роли (`platform/auth-host/app/alembic/versions/20251001_0001_auth_bootstrap.py`), limits/rules (`platform/processing-core/app/api/routes/limits.py`), cards/transactions (`platform/processing-core/app/api/routes/cards.py`, `transactions.py`).
- **Missing links:** единый onboarding flow и гарантированная tenant isolation across domains.
- **Verify artifacts:** `platform/auth-host/app/tests/test_bootstrap.py`, `platform/processing-core/app/tests/test_limits_v2.py`, `test_transactions_*`.

### 4.2 Partner onboarding: партнёр/АЗС → цены → POS/терминалы → операции
- **Coverage:** PARTIAL
- **What exists in code:** terminals/routes (`platform/processing-core/app/api/routes/terminals.py`), pricing (`platform/processing-core/app/api/routes/prices.py`), partner portal routes (`platform/processing-core/app/routers/partner/*`).
- **Missing links:** end-to-end POS/terminal integration + полноценный партнёрский pricing workflow.
- **Verify artifacts:** `platform/processing-core/app/tests/test_pricing_service.py`, `test_transactions_*`.

### 4.3 Processing E2E: authorize → capture → reverse/refund + логирование + аудит
- **Coverage:** FULL
- **What exists in code:** transactions сервисы и лог (`platform/processing-core/app/services/transactions.py`, `.../api/routes/transactions.py`), audit (`platform/processing-core/app/models/audit_log.py`).
- **Missing links:** —
- **Verify artifacts:** `platform/processing-core/app/tests/test_transactions_*`, `test_audit_log.py`.

### 4.4 Billing cycle: период → инвойсы/акты → PDF → хранение → выдача клиенту
- **Coverage:** PARTIAL
- **What exists in code:** billing periods/invoices (`platform/processing-core/app/services/billing_periods.py`, `.../models/invoice.py`), PDF render (`platform/document-service/app/main.py`).
- **Missing links:** EDO integration (реальная) и полное end-to-end подтверждение выдачи.
- **Verify artifacts:** `platform/processing-core/app/tests/test_billing_*`, `platform/document-service/app/tests/test_service.py`.

### 4.5 Settlement: расчёт → payout batches → exports
- **Coverage:** FULL
- **What exists in code:** settlement/payouts (`platform/processing-core/app/services/settlement_service.py`, `.../services/payouts_service.py`).
- **Missing links:** —
- **Verify artifacts:** `platform/processing-core/app/tests/test_settlement_v1.py`, `test_settlements.py`.

### 4.6 Reconciliation: импорт/сверка → discrepancies → отчёт
- **Coverage:** FULL
- **What exists in code:** reconciliation сервисы (`platform/processing-core/app/services/reconciliation_service.py`).
- **Missing links:** —
- **Verify artifacts:** `platform/processing-core/app/tests/test_reconciliation_v1.py`.

### 4.7 Documents: генерация/подпись/верификация + связи с периодом/инвойсом
- **Coverage:** FULL
- **What exists in code:** documents registry (`platform/processing-core/app/models/documents.py`), document-service render/sign (`platform/document-service/app/main.py`).
- **Missing links:** —
- **Verify artifacts:** `platform/processing-core/app/tests/test_documents_lifecycle.py`, `platform/document-service/app/tests/test_sign_service.py`.

### 4.8 Webhooks: intake → delivery → retry/replay + SLA/alerts
- **Coverage:** PARTIAL
- **What exists in code:** integration-hub webhooks (`platform/integration-hub/neft_integration_hub/services/webhooks.py`).
- **Missing links:** внешние коннекторы/провайдеры и SLA-алерты вне stub.
- **Verify artifacts:** `platform/integration-hub/neft_integration_hub/tests/test_webhooks.py`, `test_webhook_intake.py`.

### 4.9 Fleet: ingest топлива → anomalies → policies → notifications
- **Coverage:** PARTIAL
- **What exists in code:** fleet ingestion/policies (`platform/processing-core/app/services/fleet_ingestion_service.py`, `fleet_policy_engine.py`).
- **Missing links:** реальные провайдеры топлива.
- **Verify artifacts:** `platform/processing-core/app/tests/test_fleet_ingestion_v1.py`, `test_fuel_limits_engine.py`, `test_fleet_notifications_*`.

### 4.10 Marketplace: product → order → SLA evaluation → billing coupling
- **Coverage:** PARTIAL
- **What exists in code:** marketplace models/routers (`platform/processing-core/app/models/marketplace_*.py`, `.../routers/*marketplace*`), SLA (`platform/processing-core/app/routers/admin/marketplace_contracts.py`).
- **Missing links:** внешние рекомендации/спонсоринг сервисы.
- **Verify artifacts:** `platform/processing-core/app/tests/test_marketplace_orders_v1.py`, `test_marketplace_sla_billing_v1.py`.

### 4.11 Logistics: trip → tracking events → deviation → explain
- **Coverage:** FULL
- **What exists in code:** logistics service (`platform/logistics-service/neft_logistics_service/main.py`), logistics models (`platform/processing-core/app/models/logistics.py`).
- **Missing links:** —
- **Verify artifacts:** `platform/processing-core/app/tests/test_logistics_*`.

### 4.12 BI: отчёты/экспорт, витрины, (опционально ClickHouse)
- **Coverage:** PARTIAL
- **What exists in code:** BI exports (`platform/processing-core/app/services/bi/metrics.py`).
- **Missing links:** runtime ClickHouse не подтвержден.
- **Verify artifacts:** `platform/processing-core/app/tests/test_bi_exports_v1_1.py`.

---

## 5) Verified evidence index

Отдельный индекс доказательств: **`docs/as-is/VERIFY_EVIDENCE_INDEX.md`**.

---

## 6) Evidence snapshot (без запуска)

Текущий слепок артефактов проверки (services/health/scripts/tests): **`docs/as-is/STATUS_SNAPSHOT_LATEST.md`**.

---

## 7) Definition of Done — что значит «готово» в NEFT

- **Готово как код:** статус **CODED_FULL**.
- **Готово как проверено:** статус **VERIFIED_BY_TESTS** или **VERIFIED_BY_SMOKE_SCRIPT**.
- **Готово как end-to-end продукт:** все сценарии **Coverage = FULL** + verify artifacts + UI wired (маршруты и API-клиенты подтверждены тестами/смоуком).
