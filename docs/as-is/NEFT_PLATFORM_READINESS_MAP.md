# NEFT Platform — Readiness Map v3 (AS-IS facts + Baseline coverage + Verified evidence)

> **Источники фактов (обязательные):**
> - `docs/as-is/NEFT_PLATFORM_AS_IS_MASTER.md`
> - `docs/as-is/FINAL_VISION_BASELINE.md`
> - `docs/as-is/SERVICE_CATALOG.md`
> - `docs/as-is/DB_SCHEMA_MAP.md`
> - `docs/as-is/EVENT_CATALOG.md`
> - `docs/as-is/RUNBOOK_LOCAL.md`
> - `docs/as-is/STATUS_SNAPSHOT_LATEST.md`
> - `docs/as-is/STATUS_SNAPSHOT_RUNTIME_LATEST.md`
> - код репозитория (compose, routers, services, models, tests, scripts)

**Запрещено:** писать «планируется/в будущем», ссылаться на внешние диалоги/логи, ставить VERIFIED без артефактов в repo.

---

## 1) Шкалы статусов (две независимые оси)

### 1.1 CODE STATUS (кодовая готовность)
- **CODED_FULL** — реализовано полностью как подсистема (модели + сервисы + роутеры)
- **CODED_PARTIAL** — реализовано частично (в таблице перечислено что именно)
- **NOT IMPLEMENTED** — кода/моделей/роутов нет

### 1.2 READINESS STATUS (DoD по факту)
- **VERIFIED** — есть runtime snapshot с PASS (см. `STATUS_SNAPSHOT_RUNTIME_LATEST.md`)
- **SKIP_OK** — runtime snapshot фиксирует SKIP как PASS (скрипт допускает SKIP)
- **CODED_ONLY** — код/тесты/скрипты есть, но runtime snapshot отсутствует или показывает `verify_all` SKIP
- **NOT IMPLEMENTED** — реализация отсутствует

**Важно:** текущий runtime snapshot (`STATUS_SNAPSHOT_RUNTIME_LATEST.md`) фиксирует `verify_all` как **SKIP**, поэтому все домены с кодом имеют статус **CODED_ONLY** до появления PASS-рантайма.

---

## 2) Executive Summary (AS-IS факты + baseline coverage + evidence)

**AS-IS CODED (факты из repo):**
- Есть core API (`platform/processing-core`), auth-host, integration-hub, ai-service, document-service, logistics-service, crm-service (stub), Celery workers/beat, gateway, фронтенды Admin/Client/Partner. (`docker-compose.yml`, `platform/*/app/main.py`, `frontends/*/src/App.tsx`)
- В `processing-core` реализованы модели/сервисы/роутеры для billing, settlement, reconciliation, documents, audit, fleet, marketplace, pricing, limits/rules и др. (`platform/processing-core/app/models`, `.../services`, `.../routers`)

**FINAL VISION COVERAGE (сравнение с baseline):**
- Полностью покрыто по коду: processing lifecycle, billing, settlement/payouts, reconciliation, audit/trust, logistics, базовые webhooks (integration-hub).
- Частично покрыто: pricing (часть контуров), rules/limits (без отдельной DSL/sandbox среды), documents+EDO (stub провайдеры), fleet/fuel (stub провайдер), marketplace (без внешнего ML), CRM (stub), analytics/BI (ClickHouse runtime опционален), notifications (часть каналов stub), фронтенды (нет runtime доказательств e2e UX).

**Runtime verification:**
- `STATUS_SNAPSHOT_RUNTIME_LATEST.md` фиксирует `verify_all` как **SKIP**, поэтому статус DoD = **CODED_ONLY** до появления PASS-рантайма.

---

## 2.1 Stage status (verification readiness)

| Stage | Status | Evidence |
| --- | --- | --- |
| Stage 0 — Verification Discipline | **OPEN (CODED_ONLY)** | `scripts/verify_all.cmd`, `docs/as-is/STATUS_SNAPSHOT_RUNTIME_LATEST.md` |

### 2.1.1 Stage 0 — Verification Discipline

- **Status:** **OPEN (CODED_ONLY)**
- **Причина:** runtime snapshot фиксирует `verify_all` как **SKIP** (не выполнялся).
- **Proof:** `docs/as-is/STATUS_SNAPSHOT_RUNTIME_LATEST.md`

### 2.2 Stage 0 verification controls (runtime-verified)

| Check | Status | Evidence |
| --- | --- | --- |
| Docker compose stack (up + health gates) | **CODED_ONLY** | `scripts/verify_all.cmd`, `docker-compose.yml` |
| Core API migrations (alembic current) | **CODED_ONLY** | `scripts/verify_all.cmd` |
| Auth-host migrations + `users` table | **CODED_ONLY** | `platform/auth-host/app/alembic/versions/20251002_0001_create_auth_tables.py` |
| Health/metrics endpoints | **CODED_ONLY** | `scripts/verify_all.cmd`, `gateway/nginx.conf` |
| Smoke suite: `billing_smoke`, `smoke_billing_finance`, `smoke_invoice_state_machine` | **CODED_ONLY** | `scripts/verify_all.cmd`, `scripts/*.cmd` |

---

## 3) Readiness Matrix (Domain → CODE STATUS + READINESS STATUS + Coverage)

**Формат статуса:** `<CODE STATUS> + <READINESS STATUS>`

| Domain / Module | Status | FINAL VISION Coverage | AS-IS evidence (code paths / tests) | Missing vs baseline |
|---|---|---|---|---|
| **Identity & Access — RBAC (roles + permission guard)** | **CODED_PARTIAL + CODED_ONLY** | PARTIAL | `platform/processing-core/app/security/rbac/*`, `platform/processing-core/app/security/rbac/test_rbac_roles_import.py` | Нет подтверждённого покрытия всех доменов ролями/разрешениями |
| **Identity & Access — Tenant isolation** | **CODED_PARTIAL + CODED_ONLY** | PARTIAL | `tenant_id` в моделях/миграциях (`platform/processing-core/app/alembic/versions/*`), частичная фильтрация в роутерах | Нет системной гарантии tenant enforcement для всех доменов |
| **Identity & Access — Service identities** | **CODED_FULL + CODED_ONLY** | PARTIAL | `platform/processing-core/app/models/service_identity.py`, `platform/processing-core/app/tests/test_service_tokens.py` | Нет отдельного внешнего M2M управления вне core-api |
| **Identity & Access — ABAC/policy engine** | **CODED_PARTIAL + CODED_ONLY** | PARTIAL | `platform/processing-core/app/services/abac/*`, `platform/processing-core/app/tests/test_abac_policies.py` | Enforcement ограничен указанными доменами |
| **Processing & Transactions lifecycle** | **CODED_FULL + CODED_ONLY** | FULL | `platform/processing-core/app/api/routes/transactions.py`, `platform/processing-core/app/tests/test_transactions_pipeline.py` | — |
| **Pricing — Fuel pricing (prices)** | **CODED_PARTIAL + CODED_ONLY** | PARTIAL | `platform/processing-core/app/api/routes/prices.py`, `platform/processing-core/app/tests/test_pricing_service.py` | Нет полного контура клиентских/партнёрских прайсингов |
| **Pricing — Marketplace offers/promotions/sponsored** | **CODED_PARTIAL + CODED_ONLY** | PARTIAL | `platform/processing-core/app/models/marketplace_*.py`, `platform/processing-core/app/tests/test_marketplace_pricing_v1.py` | Нет внешнего ML/recommendations сервиса |
| **Pricing — Versioning/schedules** | **CODED_PARTIAL + CODED_ONLY** | PARTIAL | `platform/processing-core/app/tests/test_entitlements_pricing_versions.py` | Нет отдельного UI/воркфлоу для управления версиями |
| **Rules/Limits — Operational limits & rules** | **CODED_FULL + CODED_ONLY** | PARTIAL | `platform/processing-core/app/api/routes/limits.py`, `platform/processing-core/app/tests/test_limits_v2.py` | Нет DSL/sandbox среды |
| **Rules/Limits — Risk rules/policies (risk_*)** | **CODED_FULL + CODED_ONLY** | PARTIAL | `platform/processing-core/app/models/risk_*.py`, `platform/processing-core/app/tests/test_risk_rules_repository.py` | Нет sandbox среды / отдельного rule studio |
| **Rules/Limits — Sandbox/evaluate** | **CODED_PARTIAL + CODED_ONLY** | PARTIAL | `platform/processing-core/app/tests/test_rules_sandbox.py`, `platform/processing-core/app/tests/test_what_if_simulator_v1.py` | Нет выделенной sandbox подсистемы |
| **Billing** | **CODED_FULL + CODED_ONLY** | FULL | `platform/processing-core/app/services/billing_service.py`, `platform/processing-core/app/tests/test_invoice_state_machine.py` | — |
| **Clearing / Settlement / Payouts** | **CODED_FULL + CODED_ONLY** | FULL | `platform/processing-core/app/services/settlement_service.py`, `platform/processing-core/app/tests/test_settlement_v1.py` | — |
| **Reconciliation** | **CODED_FULL + CODED_ONLY** | FULL | `platform/processing-core/app/services/reconciliation_service.py`, `platform/processing-core/app/tests/test_reconciliation_v1.py` | — |
| **Documents — PDF render/sign/verify** | **CODED_FULL + CODED_ONLY** | FULL | `platform/document-service/app/main.py`, `platform/document-service/app/tests/test_service.py` | — |
| **Documents — Core registry (documents/closing packages/exports)** | **CODED_FULL + CODED_ONLY** | FULL | `platform/processing-core/app/models/documents.py`, `platform/processing-core/app/tests/test_documents_lifecycle.py` | — |
| **EDO integration (real vs stub)** | **CODED_PARTIAL + CODED_ONLY** | PARTIAL | `platform/processing-core/app/models/edo.py`, `platform/integration-hub/neft_integration_hub/tests/test_edo_stub.py` | Реальные EDO провайдеры отсутствуют |
| **Audit / Trust layer** | **CODED_FULL + CODED_ONLY** | FULL | `platform/processing-core/app/models/audit_log.py`, `platform/processing-core/app/tests/test_audit_log.py` | — |
| **Integrations Hub — Webhooks** | **CODED_FULL + CODED_ONLY** | PARTIAL | `platform/integration-hub/neft_integration_hub/services/webhooks.py`, `platform/integration-hub/neft_integration_hub/tests/test_webhooks.py` | Нет внешних коннекторов (кроме stub) |
| **Fleet/Fuel** | **CODED_PARTIAL + CODED_ONLY** | PARTIAL | `platform/processing-core/app/models/fuel.py`, `platform/processing-core/app/tests/test_fleet_ingestion_v1.py` | Реальные топливные провайдеры отсутствуют |
| **Marketplace** | **CODED_PARTIAL + CODED_ONLY** | PARTIAL | `platform/processing-core/app/models/marketplace_*.py`, `platform/processing-core/app/tests/test_marketplace_orders_v1.py` | Нет внешнего recommendation/ads сервиса |
| **CRM** | **CODED_PARTIAL + CODED_ONLY** | PARTIAL | `platform/processing-core/app/models/crm.py`, `platform/processing-core/app/tests/test_crm_clients.py` | Сервис `crm-service` — stub, внешняя CRM интеграция отсутствует |
| **Logistics** | **CODED_FULL + CODED_ONLY** | FULL | `platform/logistics-service/neft_logistics_service/main.py`, `platform/processing-core/app/tests/test_logistics_eta.py` | — |
| **Analytics/BI** | **CODED_PARTIAL + CODED_ONLY** | PARTIAL | `platform/processing-core/app/models/bi.py`, `platform/processing-core/app/tests/test_bi_exports_v1_1.py` | Runtime ClickHouse не подтверждён |
| **Notifications** | **CODED_PARTIAL + CODED_ONLY** | PARTIAL | `platform/processing-core/app/services/notifications_v1.py`, `platform/processing-core/app/tests/test_notifications_webhook.py` | Реальные каналы частично stub |
| **Frontends — Admin/Client/Partner** | **CODED_PARTIAL + CODED_ONLY** | PARTIAL | `frontends/*/src/App.tsx`, `docker-compose.yml` (healthchecks) | Нет runtime доказательств end-to-end UX сценариев |
| **Observability (metrics/logs/traces)** | **CODED_FULL + CODED_ONLY** | FULL | `infra/prometheus.yml`, `infra/otel-collector-config.yaml`, healthchecks в `docker-compose.yml` | Loki/Promtail без healthchecks |

---

## 4) Scenarios Coverage (FINAL_VISION_BASELINE)

**Формат карточки:**
- Scenario
- Coverage: **FULL / PARTIAL / NONE**
- What exists in code
- Missing links
- Verify artifacts
- Readiness status (DoD)

### 4.1 Onboarding: клиент → роли → подписки/лимиты → карты → первые операции
- **Coverage:** PARTIAL
- **What exists in code:** auth-host bootstrap + роли (`platform/auth-host/app/alembic/versions/20251001_0001_auth_bootstrap.py`), limits/rules (`platform/processing-core/app/api/routes/limits.py`), cards/transactions (`platform/processing-core/app/api/routes/cards.py`, `transactions.py`).
- **Missing links:** единый onboarding flow и гарантированная tenant isolation across domains.
- **Verify artifacts:** `platform/auth-host/app/tests/test_auth.py`, `platform/processing-core/app/tests/test_limits_v2.py`, `platform/processing-core/app/tests/test_transactions_pipeline.py`.
- **Readiness status:** **CODED_ONLY** (runtime snapshot отсутствует).

### 4.2 Partner onboarding: партнёр/АЗС → цены → POS/терминалы → операции
- **Coverage:** PARTIAL
- **What exists in code:** terminals/routes (`platform/processing-core/app/api/routes/terminals.py`), pricing (`platform/processing-core/app/api/routes/prices.py`), partner portal routes (`platform/processing-core/app/routers/partner/*`).
- **Missing links:** end-to-end POS/terminal integration + полноценный партнёрский pricing workflow.
- **Verify artifacts:** `platform/processing-core/app/tests/test_pricing_service.py`, `platform/processing-core/app/tests/test_transactions_pipeline.py`.
- **Readiness status:** **CODED_ONLY** (runtime snapshot отсутствует).

### 4.3 Processing E2E: authorize → capture → reverse/refund + логирование + аудит
- **Coverage:** FULL
- **What exists in code:** transactions сервисы и лог (`platform/processing-core/app/services/transactions.py`, `.../api/routes/transactions.py`), audit (`platform/processing-core/app/models/audit_log.py`).
- **Missing links:** —
- **Verify artifacts:** `platform/processing-core/app/tests/test_transactions_pipeline.py`, `platform/processing-core/app/tests/test_audit_log.py`.
- **Readiness status:** **CODED_ONLY** (runtime snapshot отсутствует).

### 4.4 Billing cycle: период → инвойсы/акты → PDF → хранение → выдача клиенту
- **Coverage:** PARTIAL
- **What exists in code:** billing periods/invoices (`platform/processing-core/app/services/billing_periods.py`, `.../models/invoice.py`), PDF render (`platform/document-service/app/main.py`).
- **Missing links:** EDO integration (реальная) и runtime подтверждение выдачи.
- **Verify artifacts:** `platform/processing-core/app/tests/test_billing_periods.py`, `platform/document-service/app/tests/test_service.py`.
- **Readiness status:** **CODED_ONLY** (runtime snapshot отсутствует).

### 4.5 Settlement: расчёт → payout batches → exports
- **Coverage:** FULL
- **What exists in code:** settlement/payouts (`platform/processing-core/app/services/settlement_service.py`, `.../services/payouts_service.py`).
- **Missing links:** —
- **Verify artifacts:** `platform/processing-core/app/tests/test_settlement_v1.py`, `platform/processing-core/app/tests/test_payouts_e2e.py`.
- **Readiness status:** **CODED_ONLY** (runtime snapshot отсутствует).

### 4.6 Reconciliation: импорт/сверка → discrepancies → отчёт
- **Coverage:** FULL
- **What exists in code:** reconciliation сервисы (`platform/processing-core/app/services/reconciliation_service.py`).
- **Missing links:** —
- **Verify artifacts:** `platform/processing-core/app/tests/test_reconciliation_v1.py`.
- **Readiness status:** **CODED_ONLY** (runtime snapshot отсутствует).

### 4.7 Documents: генерация/подпись/верификация + связи с периодом/инвойсом
- **Coverage:** FULL
- **What exists in code:** documents registry (`platform/processing-core/app/models/documents.py`), document-service render/sign (`platform/document-service/app/main.py`).
- **Missing links:** —
- **Verify artifacts:** `platform/processing-core/app/tests/test_documents_lifecycle.py`, `platform/document-service/app/tests/test_sign_service.py`.
- **Readiness status:** **CODED_ONLY** (runtime snapshot отсутствует).

### 4.8 Webhooks: intake → delivery → retry/replay + SLA/alerts
- **Coverage:** PARTIAL
- **What exists in code:** integration-hub webhooks (`platform/integration-hub/neft_integration_hub/services/webhooks.py`).
- **Missing links:** внешние коннекторы/провайдеры и SLA-алерты вне stub.
- **Verify artifacts:** `platform/integration-hub/neft_integration_hub/tests/test_webhooks.py`, `platform/integration-hub/neft_integration_hub/tests/test_webhook_intake.py`.
- **Readiness status:** **CODED_ONLY** (runtime snapshot отсутствует).

### 4.9 Fleet: ingest топлива → anomalies → policies → notifications
- **Coverage:** PARTIAL
- **What exists in code:** fleet ingestion/policies (`platform/processing-core/app/services/fleet_ingestion_service.py`, `fleet_policy_engine.py`).
- **Missing links:** реальные провайдеры топлива.
- **Verify artifacts:** `platform/processing-core/app/tests/test_fleet_ingestion_v1.py`, `platform/processing-core/app/tests/test_fuel_provider_framework_v1.py`.
- **Readiness status:** **CODED_ONLY** (runtime snapshot отсутствует).

### 4.10 Marketplace: product → order → SLA evaluation → billing coupling
- **Coverage:** PARTIAL
- **What exists in code:** marketplace модели/роутеры (`platform/processing-core/app/models/marketplace_*.py`, `.../routers/*marketplace*`), SLA (`platform/processing-core/app/routers/admin/marketplace_contracts.py`).
- **Missing links:** внешние рекомендации/спонсоринг сервисы.
- **Verify artifacts:** `platform/processing-core/app/tests/test_marketplace_orders_v1.py`, `platform/processing-core/app/tests/test_marketplace_sla_billing_v1.py`.
- **Readiness status:** **CODED_ONLY** (runtime snapshot отсутствует).

### 4.11 Logistics: trip → tracking events → deviation → explain
- **Coverage:** FULL
- **What exists in code:** logistics service (`platform/logistics-service/neft_logistics_service/main.py`), logistics модели (`platform/processing-core/app/models/logistics.py`).
- **Missing links:** —
- **Verify artifacts:** `platform/processing-core/app/tests/test_logistics_eta.py`, `platform/processing-core/app/tests/test_logistics_deviation_v2.py`.
- **Readiness status:** **CODED_ONLY** (runtime snapshot отсутствует).

### 4.12 BI: отчёты/экспорт, витрины, (опционально ClickHouse)
- **Coverage:** PARTIAL
- **What exists in code:** BI exports (`platform/processing-core/app/services/bi/metrics.py`).
- **Missing links:** runtime ClickHouse не подтверждён.
- **Verify artifacts:** `platform/processing-core/app/tests/test_bi_exports_v1_1.py`.
- **Readiness status:** **CODED_ONLY** (runtime snapshot отсутствует).

---

## 5) Verified evidence index

Отдельный индекс доказательств: **`docs/as-is/VERIFY_EVIDENCE_INDEX.md`**.

---

## 6) Evidence snapshot (без запуска)

Текущий слепок артефактов проверки (services/health/scripts/tests): **`docs/as-is/STATUS_SNAPSHOT_LATEST.md`**.

---

## 7) Definition of Done — что значит «готово» в NEFT

- **Готово как код:** статус **CODED_FULL**.
- **Готово как проверено:** статус **VERIFIED** или **SKIP_OK** в runtime snapshot.
- **Готово как end-to-end продукт:** все сценарии **Coverage = FULL** + runtime PASS + UI wired (маршруты и API-клиенты подтверждены тестами/смоуком).

### 7.1 Формальное правило DoD (обязательное)

Этап считается **ЗАКРЫТЫМ**, только если выполнены все условия:

1. **CODED** — в репозитории есть код, миграции, модели, роуты и сервисы, соответствующие этапу.
2. **VERIFIED** — есть runtime snapshot (`STATUS_SNAPSHOT_RUNTIME_<DATE>.md`) с PASS или SKIP_OK.
3. **DOC** — состояние этапа зафиксировано в:
   - `docs/as-is/NEFT_PLATFORM_READINESS_MAP.md`
   - `docs/as-is/VERIFY_EVIDENCE_INDEX.md`
   - `docs/as-is/STATUS_SNAPSHOT_LATEST.md`
   - `docs/as-is/STATUS_SNAPSHOT_RUNTIME_<DATE>.md`

Если хотя бы один пункт отсутствует — этап **НЕ ЗАКРЫТ**.

---

## 8) 🚫 Правило необратимости

Если отсутствует файл `STATUS_SNAPSHOT_RUNTIME_<DATE>.md`, или он содержит `verify_all` со статусом **SKIP/FAIL**, то этап считается **НЕ ЗАКРЫТЫМ**, независимо от количества кода, тестов и диалогов.

Диалоги, обсуждения и устные договорённости **НЕ ЯВЛЯЮТСЯ** доказательством готовности.

---

## Итог AS-IS на 2026-01-13

- **Закрыто (VERIFIED/SKIP_OK):** нет (runtime snapshot фиксирует `verify_all` как SKIP).
- **Осознанно не сделано (NOT IMPLEMENTED/STUB):** внешние провайдеры EDO, реальные топливные провайдеры, внешние ML/recommendations, полноценная CRM-интеграция; указано в матрице как PARTIAL/Stub.
- **Следующий этап, но не AS-IS:** получить PASS runtime snapshot через `scripts/verify_all.cmd` и зафиксировать `STATUS_SNAPSHOT_RUNTIME_<DATE>.md`.
