# NEFT Platform — FULL READINESS MAP (AS-IS, доказуемо)

> Источники фактов: код и конфиги в репозитории + текущий AS-IS пакет.
> Любые пункты без подтверждения запуском помечаются **NOT VERIFIED**.
>
> Обязательная шкала статусов:
> - READY (VERIFIED)
> - READY (CODED)
> - PARTIAL
> - NOT IMPLEMENTED
> - NOT VERIFIED

---

## 4.1 Executive Summary (1–2 экрана)

**Где мы сейчас (AS-IS по коду):**
- Платформа содержит ядро `core-api`, сервисы `auth-host`, `integration-hub`, `ai-service`, `document-service`, `logistics-service`, `crm-service`, Celery-воркеры, фронтенды Admin/Client/Partner и наблюдаемость (Prometheus/Grafana/Jaeger/Loki). (`docker-compose.yml`, `gateway/nginx.conf`, `infra/prometheus.yml`, `platform/*/app/main.py`, `frontends/*/src/App.tsx`)
- В `processing-core` есть модели, сервисы, роутеры и тесты по большинству доменов (billing, settlement, fleet, marketplace, audit, cases, reconciliation, documents, limits/rules). (`platform/processing-core/app/models`, `platform/processing-core/app/services`, `platform/processing-core/app/routers`, `platform/processing-core/app/tests`)

**Что уже готово “для продажи/пилота” (только по коду):**
- Базовый runtime-стек (compose + gateway + health/metrics endpoints) — **READY (CODED)**.
- Core domain API с большим покрытием моделей и тестов — **READY (CODED)**.
- Integration Hub для webhooks/EDO stub — **READY (CODED)**.
- Документный сервис (PDF render/sign/verify) — **READY (CODED)**.
- Фронтенды Admin/Client/Partner с маршрутизацией и API-клиентами — **READY (CODED)**.

**Что блокирует следующий шаг:**
- Нет подтверждённого запуска и smoke-результатов; все runtime-проверки отмечены **NOT VERIFIED**. (`docs/as-is/STATUS_SNAPSHOT_2026-01-03.md`, `docs/as-is/RUNBOOK_LOCAL.md`)

**Главные риски (по факту реализации):**
- Интеграции EDO и внешние провайдеры топлива/рекомендаций — stub/мок, без продовых интеграций. (`platform/integration-hub/neft_integration_hub/services/edo_stub.py`, `platform/processing-core/app/integrations/fuel/providers/stub_provider.py`)
- Не подтверждена миграция БД и актуальные головы alembic на живой БД. (`docs/as-is/DB_SCHEMA_MAP.md`)
- End-to-end сценарии не прогонялись в этом окружении. (`docs/as-is/STATUS_SNAPSHOT_2026-01-03.md`)

---

## 4.2 Readiness Matrix (главная таблица)

> **Важно:** статус READY (VERIFIED) не используется, потому что команды из Runbook не запускались (см. STATUS_SNAPSHOT).

| Domain / Module | Status | What’s implemented | What’s missing | Proof (paths + endpoints + tests + migrations) | How to verify (exact commands) |
|---|---|---|---|---|---|
| **Identity/Auth** | **READY (CODED)** | Auth API, bootstrap demo users, JWT, admin users routes | Runtime verification, production auth flows | `platform/auth-host/app/main.py`, `platform/auth-host/app/api/routes/*`, migrations `platform/auth-host/app/alembic/versions/20251001_0001_auth_bootstrap.py`, tests `platform/auth-host/app/tests/*` | `docker compose up -d --build`; `curl http://localhost/api/auth/health`; `docker compose exec -T auth-host sh -lc "alembic -c alembic.ini heads"` — **NOT VERIFIED** |
| **Processing / Transactions lifecycle** | **READY (CODED)** | Terminal auth/capture/refund/reversal, operations log, limits checks | Runtime verification | `platform/processing-core/app/api/routes/transactions.py`, `platform/processing-core/app/api/routes/transactions_log.py`, `platform/processing-core/app/services/transactions.py`, tests `platform/processing-core/app/tests/test_transactions_*` | `curl http://localhost/api/core/health`; run `scripts\test_core_api.cmd` — **NOT VERIFIED** |
| **Pricing** | **PARTIAL** | Price lookup endpoint (`/prices/active`) | Pricing engine, publishing workflows | `platform/processing-core/app/api/routes/prices.py`, tests `platform/processing-core/app/tests/test_pricing_service.py` | `curl http://localhost/api/v1/prices/active?azs_name=...` — **NOT VERIFIED** |
| **Rules / Limits** | **READY (CODED)** | Limits engine + rules endpoints and services | Runtime verification | `platform/processing-core/app/api/routes/limits.py`, `platform/processing-core/app/api/routes/rules.py`, `platform/processing-core/app/services/limits.py`, tests `platform/processing-core/app/tests/test_limits_v2.py` | `scripts\test_core_api.cmd` — **NOT VERIFIED** |
| **Billing** | **READY (CODED)** | Billing invoices/payments/refunds, billing flows, invoice state machine | Runtime verification | `platform/processing-core/app/models/billing_flow.py`, `platform/processing-core/app/routers/admin/billing.py`, `platform/processing-core/app/services/billing_service.py`, tests `platform/processing-core/app/tests/test_billing_*` | `scripts\billing_smoke.cmd` — **NOT VERIFIED** |
| **Clearing / Settlement / Payouts** | **READY (CODED)** | Settlement models, payouts, clearing services | Runtime verification | `platform/processing-core/app/models/settlement.py`, `platform/processing-core/app/services/settlement_service.py`, `platform/processing-core/app/services/payouts_service.py`, tests `platform/processing-core/app/tests/test_settlement_*`, `test_payouts_*` | `scripts\smoke_billing_finance.cmd` — **NOT VERIFIED** |
| **Reconciliation** | **READY (CODED)** | Reconciliation models, services, admin pages | Runtime verification | `platform/processing-core/app/models/reconciliation.py`, `platform/processing-core/app/services/reconciliation_service.py`, tests `platform/processing-core/app/tests/test_reconciliation_v1.py` | `scripts\smoke_billing_finance.cmd` — **NOT VERIFIED** |
| **Documents / PDF / EDO** | **PARTIAL** | Document models, PDF render/sign/verify service, EDO stub | Реальные EDO провайдеры | `platform/document-service/app/main.py`, `platform/processing-core/app/models/documents.py`, `platform/integration-hub/neft_integration_hub/services/edo_stub.py`, tests `platform/processing-core/app/tests/test_document_service_integration.py` | `curl http://localhost/api/docs/health`; `curl http://localhost:8000/metrics` — **NOT VERIFIED** |
| **Audit / Trust layer** | **READY (CODED)** | Audit log + signing + hash-chain | KMS/Vault integration not verified | `platform/processing-core/app/models/audit_log.py`, `platform/processing-core/app/services/audit_signing.py`, tests `platform/processing-core/app/tests/test_audit_*` | `scripts\test_core_api.cmd` — **NOT VERIFIED** |
| **Integrations / Webhooks / Integration Hub** | **READY (CODED)** | Webhook endpoints, intake, delivery, replay, EDO stub | Runtime verification | `platform/integration-hub/neft_integration_hub/main.py`, `platform/integration-hub/neft_integration_hub/services/webhooks.py`, tests `platform/integration-hub/neft_integration_hub/tests/test_webhooks.py` | `curl http://localhost/api/int/health`; `curl http://localhost:8010/metrics` — **NOT VERIFIED** |
| **Fleet/Fuel** | **PARTIAL** | Fleet/fuel models, policies, ingestion, anomalies, notifications | Реальные топливные провайдеры (stub) | `platform/processing-core/app/models/fuel.py`, `platform/processing-core/app/services/fleet_service.py`, `platform/processing-core/app/integrations/fuel/providers/stub_provider.py`, tests `platform/processing-core/app/tests/test_fleet_*` | `scripts\test_core_api.cmd` — **NOT VERIFIED** |
| **Marketplace** | **PARTIAL** | Products/orders/promotions/events/models + partner/client routes | Нет внешнего recommendation ML сервиса | `platform/processing-core/app/models/marketplace_*.py`, `platform/processing-core/app/routers/client_marketplace*.py`, `platform/processing-core/app/routers/partner/marketplace_*`, tests `platform/processing-core/app/tests/test_marketplace_*` | `scripts\test_core_api.cmd` — **NOT VERIFIED** |
| **CRM** | **PARTIAL** | CRM models in core + stub CRM service | Реальная CRM интеграция отсутствует | `platform/processing-core/app/models/crm.py`, `platform/crm-service/app/main.py`, tests `platform/processing-core/app/tests/test_crm_*` | `curl http://localhost/api/crm/health` — **NOT VERIFIED** |
| **Logistics** | **READY (CODED)** | Logistics service API (ETA/deviation/explain) + core models | Runtime verification | `platform/logistics-service/neft_logistics_service/main.py`, `platform/processing-core/app/models/logistics.py`, tests `platform/processing-core/app/tests/test_logistics_*` | `curl http://localhost/api/logistics/health` — **NOT VERIFIED** |
| **Analytics/BI** | **PARTIAL** | BI models + metrics hooks, optional ClickHouse | ClickHouse runtime not verified | `platform/processing-core/app/models/bi.py`, `platform/processing-core/app/services/bi/metrics.py`, `docker-compose.yml` (clickhouse), tests `platform/processing-core/app/tests/test_bi_exports_v1_1.py` | `curl http://localhost:8123` (если включен) — **NOT VERIFIED** |
| **Notifications** | **PARTIAL** | Fleet notification outbox + dispatcher (email/telegram/webpush/stub) | Реальные внешние провайдеры не подтверждены | `platform/processing-core/app/models/fuel.py`, `platform/processing-core/app/services/fleet_notification_dispatcher.py`, tests `platform/processing-core/app/tests/test_fleet_notifications_*` | `scripts\test_core_api.cmd` — **NOT VERIFIED** |
| **Frontends: Admin** | **READY (CODED)** | Маршруты + API клиенты + страницы | Runtime/UI verification | `frontends/admin-ui/src/App.tsx`, `frontends/admin-ui/src/api/*` | `curl http://localhost:4173/health` — **NOT VERIFIED** |
| **Frontends: Client** | **READY (CODED)** | Маршруты + API клиенты + страницы | Runtime/UI verification | `frontends/client-portal/src/App.tsx`, `frontends/client-portal/src/api/*` | `curl http://localhost:4174/health` — **NOT VERIFIED** |
| **Frontends: Partner** | **READY (CODED)** | Маршруты + API клиенты + страницы | Runtime/UI verification | `frontends/partner-portal/src/App.tsx`, `frontends/partner-portal/src/api/*` | `curl http://localhost:4175/health` — **NOT VERIFIED** |
| **Observability stack** | **READY (CODED)** | Prometheus/Grafana/Jaeger/Loki/OTel | Runtime verification | `infra/prometheus.yml`, `infra/grafana/`, `infra/loki/`, `infra/promtail/`, `docker-compose.yml` | `curl http://localhost:9090/-/healthy`; `curl http://localhost:3000/health` — **NOT VERIFIED** |

---

## 4.3 Service-by-service map (по docker-compose.yml)

> **Источник:** `docker-compose.yml`, `gateway/nginx.conf`, `docs/as-is/SERVICE_CATALOG.md`.

| Service | Ports | Health | Metrics | Depends on | Реально используется / подключение | Проверка |
|---|---|---|---|---|---|---|
| **gateway** | 80 | `/health` | `/metrics` | core-api, auth-host, ai-service | Входная точка + роутинг `/api/*` и SPA | `curl http://localhost/health` — **NOT VERIFIED** |
| **core-api** | 8001:8000 | `/api/core/health` | `/metrics` | postgres, redis, minio-init | Основной API | `curl http://localhost/api/core/health` — **NOT VERIFIED** |
| **auth-host** | 8002:8000 | `/api/auth/health` | `/api/v1/metrics` | postgres, redis | JWT/auth | `curl http://localhost/api/auth/health` — **NOT VERIFIED** |
| **ai-service** | 8003:8000 | `/api/v1/health` | `/metrics` | redis | AI scoring stub | `curl http://localhost/api/ai/health` — **NOT VERIFIED** |
| **integration-hub** | 8010:8000 | `/health` | `/metrics` | postgres, redis, minio-init | Webhooks + EDO stub | `curl http://localhost/api/int/health` — **NOT VERIFIED** |
| **document-service** | internal | `/health` | `/metrics` | none | PDF render/sign/verify | `curl http://localhost/api/docs/health` — **NOT VERIFIED** |
| **logistics-service** | internal | `/health` | `/metrics` | none | ETA/Deviation/Explain | `curl http://localhost/api/logistics/health` — **NOT VERIFIED** |
| **crm-service** | internal | `/health` | `/metrics` | none | Stub CRM | `curl http://localhost/api/crm/health` — **NOT VERIFIED** |
| **workers** | internal | compose healthcheck | n/a | core-api, redis | Celery workers (billing/pdf/clearing) | `docker compose ps` — **NOT VERIFIED** |
| **beat** | internal | compose healthcheck | n/a | core-api, redis | Celery scheduler | `docker compose ps` — **NOT VERIFIED** |
| **flower** | 5555 | `/api/workers` | same | redis, workers | Celery UI | `curl http://localhost:5555/api/workers` — **NOT VERIFIED** |
| **celery-exporter** | internal | `/metrics` | `/metrics` | redis | Prometheus exporter | `curl http://localhost:9808/metrics` — **NOT VERIFIED** |
| **admin-web** | 4173:80 | `/health` | n/a | none | Admin SPA | `curl http://localhost:4173/health` — **NOT VERIFIED** |
| **client-web** | 4174:80 | `/health` | n/a | none | Client SPA | `curl http://localhost:4174/health` — **NOT VERIFIED** |
| **partner-web** | 4175:80 | `/health` | n/a | gateway | Partner SPA | `curl http://localhost:4175/health` — **NOT VERIFIED** |
| **postgres** | 5432 | `pg_isready` | n/a | none | Primary DB | `docker compose exec -T postgres pg_isready` — **NOT VERIFIED** |
| **redis** | 6379 | `redis-cli ping` | n/a | none | Cache/broker | `docker compose exec -T redis redis-cli ping` — **NOT VERIFIED** |
| **minio** | 9000/9001 | `/minio/health/ready` | n/a | none | S3 storage | `curl http://localhost:9000/minio/health/ready` — **NOT VERIFIED** |
| **clickhouse** | 8123/9002 | n/a | n/a | none | Optional BI | `curl http://localhost:8123` — **NOT VERIFIED** |
| **otel-collector** | 4317 | `/` (13133) | n/a | none | OTLP ingest | `curl http://localhost:13133/` — **NOT VERIFIED** |
| **jaeger** | 16686 | `/` | n/a | otel-collector | Traces UI | `curl http://localhost:16686/` — **NOT VERIFIED** |
| **prometheus** | 9090 | `/-/healthy` | `/metrics` | gateway | Metrics | `curl http://localhost:9090/-/healthy` — **NOT VERIFIED** |
| **grafana** | 3000 | `/health` | n/a | prometheus | Dashboards | `curl http://localhost:3000/health` — **NOT VERIFIED** |
| **loki** | 3100 | n/a | n/a | none | Logs backend | `curl http://localhost:3100/ready` — **NOT VERIFIED** |
| **promtail** | 9080 | n/a | n/a | loki | Log shipper | `docker compose logs -f promtail` — **NOT VERIFIED** |

---

## 4.4 API Coverage Map

> **Статусы эндпоинтов:**
> - **есть**: есть роутер/обработчик в коде
> - **используется**: есть связь через gateway/SPA/клиенты
> - **покрыт тестом/смоуком**: есть тесты/скрипты в репо
> - **требует ручной проверки**: все runtime проверки НЕ запускались

### core-api (FastAPI)
- **Группа `/api/v1` (core API routes)** — `platform/processing-core/app/api/routes/__init__.py` (health/auth/clients/prices/rules/transactions/limits/merchants/terminals/cards/internal_ledger).
  - **Статус:** есть; используется (gateway `/api/v1` и `/api/core`); покрыт тестами; требует ручной проверки.
- **Admin + client + partner routers** — `platform/processing-core/app/routers/*` (admin, client, marketplace, service bookings, cases, explain, portal, etc.).
  - **Статус:** есть; используется (frontends Admin/Client/Partner); покрыт тестами; требует ручной проверки.
- **Дополнительные API v1 endpoints** — `platform/processing-core/app/api/v1/endpoints/*` (operations, reports, intake, partners, billing invoices, payouts, fuel transactions, logistics, EDO, BI, pricing intelligence, support).
  - **Статус:** есть (подключаются через `main.py`); требует ручной проверки.

### auth-host
- **Routes** — `platform/auth-host/app/api/routes/auth.py`, `admin_users.py`, `processing.py`, `health.py`.
  - **Статус:** есть; используется (gateway `/api/auth/*`); покрыт тестами в `platform/auth-host/app/tests/*`; требует ручной проверки.

### ai-service
- **Routes** — `platform/ai-services/risk-scorer/app/api/v1/health.py`, `score.py`, `risk_score.py`, admin models router.
  - **Статус:** есть; используется (gateway `/api/ai/*`); покрыт тестами `platform/processing-core/app/tests/test_ai_risk_endpoint.py`; требует ручной проверки.

### integration-hub
- **Webhook intake + endpoints + deliveries + replay + SLA** — `platform/integration-hub/neft_integration_hub/main.py` and `services/webhooks.py`.
  - **Статус:** есть; используется (gateway `/api/int/*`); покрыт тестами в `platform/integration-hub/neft_integration_hub/tests/*`; требует ручной проверки.
- **EDO stub** — `services/edo_stub.py`, `services/edo_service.py`.
  - **Статус:** есть; stub; покрыт тестами; требует ручной проверки.

### document-service
- **Routes** — `/v1/render`, `/v1/sign`, `/v1/verify`, `/v1/presign` в `platform/document-service/app/main.py`.
  - **Статус:** есть; используется (gateway `/api/docs/*`); покрыт тестами в core `test_document_service_integration.py`; требует ручной проверки.

### logistics-service
- **Routes** — `/v1/eta`, `/v1/deviation`, `/v1/explain` в `platform/logistics-service/neft_logistics_service/main.py`.
  - **Статус:** есть; используется (gateway `/api/logistics/*`); покрыт тестами `platform/processing-core/app/tests/test_logistics_*`; требует ручной проверки.

### crm-service
- **Routes** — только `/health`, `/metrics` (stub) в `platform/crm-service/app/main.py`.
  - **Статус:** есть; используется (gateway `/api/crm/*`); требует ручной проверки.

---

## 4.5 DB + Migrations Reality Check

**Alembic heads / merge heads (по коду):**
- **processing-core:** heads `20261201_0017_accounts_and_ledger`, `20297100_0115_merge_heads`. (`platform/processing-core/app/alembic/versions/*`)
- **auth-host:** head `20251001_0001_auth_bootstrap`. (`platform/auth-host/app/alembic/versions/20251001_0001_auth_bootstrap.py`)
- **integration-hub:** миграций нет, схема создаётся ORM. (`platform/integration-hub/neft_integration_hub/db.py`)

**Что реально мигрируется при `scripts\migrate.cmd`:**
- Команда внутри скрипта — `alembic -c app/alembic.ini upgrade head` в контейнере `core-api`. (`scripts/migrate.cmd`)

**Key tables by domain (из моделей):**
- Billing/Finance: `billing_invoices`, `billing_payments`, `invoices`, `ledger_entries`, `posting_batches`, `settlements`, `payouts`.
- Reconciliation: `reconciliation_runs`, `billing_reconciliation_runs`, `reconciliation_discrepancies`.
- Fleet/Fuel: `fuel_cards`, `fuel_transactions`, `fleet_notification_*`, `fleet_vehicles`.
- Marketplace: `marketplace_products`, `marketplace_orders`, `marketplace_order_events`, `promotions`.
- Documents: `documents`, `document_files`, `closing_packages`, `erp_exports`.
- Audit/Trust: `audit_log`, `case_events`.

**NOT VERIFIED:**
- `alembic current` не запускался. (`docs/as-is/STATUS_SNAPSHOT_2026-01-03.md`)

---

## 4.6 Eventing Reality Check

**Что реально пишется (таблицы событий):**
- `case_events`, `marketplace_order_events`, `service_booking_events`, `service_proof_events`, `money_flow_events`, `payout_events`, `logistics_*_events`, `fuel_*_events` — см. `docs/as-is/EVENT_CATALOG.md`.
- Integration Hub: `webhook_intake_events`, `webhook_deliveries`, `webhook_alerts`, `edo_documents`, `edo_stub_messages` — см. `docs/as-is/EVENT_CATALOG.md`.

**Кто потребляет:**
- Core API сервисы и порталы (admin/client/partner) — по роутерам `platform/processing-core/app/routers/*`.
- Integration Hub worker / SLA logic — `platform/integration-hub/neft_integration_hub/services/webhooks.py`.

**Что заявлено, но не реализовано:**
- Kafka/RabbitMQ event bus — **NOT IMPLEMENTED** (в compose и коде отсутствует). (`docs/as-is/EVENT_CATALOG.md`)

---

## 4.7 UI Reality Check (самая важная часть)

> **Шкала UX readiness:**
> 0 — каркас; 1 — данные показываются (по коду есть API-клиенты/запросы); 2 — CRUD работает; 3 — сценарии end-to-end; 4 — продуктово готово.
> 
> **Важно:** запуск UI не проверялся, поэтому даже при наличии кода все оценки ниже помечены как **NOT VERIFIED**.

### Admin Portal (`/admin`)
- **Routes (by code):** `/login`, `/dashboard`, `/billing/*`, `/finance/*`, `/operations/*`, `/risk/*`, `/crm/*`, `/reconciliation/*`, `/fleet/*`, `/support/*`, `/explain`, `/users/*`. (`frontends/admin-ui/src/App.tsx`)
- **API usage (by code):** `frontends/admin-ui/src/api/*` (billing, clearing, payouts, reconciliation, CRM, risk rules, operations, users, cases, marketplace, etc.).
- **UX readiness:** **1 (NOT VERIFIED)** — код API-клиентов и страниц есть, но не подтверждено отображение данных/CRUD.

### Client Portal (`/client`)
- **Routes (by code):** `/dashboard`, `/cards`, `/fleet/*`, `/analytics/*`, `/marketplace/*`, `/billing/*`, `/documents/*`, `/operations/*`, `/support/*`, `/reconciliation`, `/settings/*`. (`frontends/client-portal/src/App.tsx`)
- **API usage (by code):** `frontends/client-portal/src/api/*` (fleet, analytics, invoices, documents, marketplace, support, notifications).
- **UX readiness:** **1 (NOT VERIFIED)** — маршруты и API-клиенты есть, runtime не проверен.

### Partner Portal (`/partner`)
- **Routes (by code):** `/dashboard`, `/products`, `/orders/*`, `/prices/*`, `/payouts/*`, `/documents/*`, `/integrations`, `/support/*`, `/services/*`. (`frontends/partner-portal/src/App.tsx`)
- **API usage (by code):** `frontends/partner-portal/src/api/*` (orders, prices, refunds, webhooks, marketplace catalog).
- **UX readiness:** **1 (NOT VERIFIED)** — маршруты и API-клиенты есть, runtime не проверен.

**Страницы “есть, но пустая/без данных”:**
- **NOT VERIFIED** (требует запуск и ручную проверку).

---

## 4.8 End-to-End Scenarios Catalog (>=15)

> Все сценарии ниже имеют кодовые точки входа, но **NOT VERIFIED** по факту запуска.

1) **Регистрация/логин → токен → доступ в Admin Portal**
   - **Сервисы:** auth-host, admin-web
   - **Endpoints:** `/api/auth/login`, `/api/auth/me`, `/admin/*`
   - **Таблицы:** `users`, `user_roles` (auth-host)
   - **Proof:** `platform/auth-host/app/api/routes/auth.py`, `frontends/admin-ui/src/App.tsx`, `platform/auth-host/app/alembic/versions/20251001_0001_auth_bootstrap.py`
   - **Verify:** `scripts\test_auth_host.cmd` — **NOT VERIFIED**

2) **Terminal auth → authorize → capture → refund → reversal**
   - **Сервисы:** core-api
   - **Endpoints:** `/api/v1/processing/terminal-auth`, `/api/v1/transactions/{auth_operation_id}/capture`, `/api/v1/transactions/{capture_operation_id}/refund`, `/api/v1/transactions/{operation_id}/reversal`
   - **Таблицы:** `operations` (core), `internal_ledger_*`
   - **Proof:** `platform/processing-core/app/api/routes/transactions.py`, `platform/processing-core/app/models/operation.py`
   - **Verify:** `scripts\test_core_api.cmd` — **NOT VERIFIED**

3) **Лимиты → проверка → approve/decline**
   - **Сервисы:** core-api
   - **Endpoints:** `/api/v1/limits/recalc/{client_id}`, limits check in `transactions`
   - **Таблицы:** `limits`, `limit_configs`
   - **Proof:** `platform/processing-core/app/api/routes/limits.py`, `platform/processing-core/app/services/limits.py`
   - **Verify:** `scripts\test_core_api.cmd` — **NOT VERIFIED**

4) **Создание invoice → state machine transitions → PDF**
   - **Сервисы:** core-api, document-service
   - **Endpoints:** `/api/core/.../billing`, `/api/docs/v1/render`
   - **Таблицы:** `invoices`, `invoice_transition_logs`, `document_files`
   - **Proof:** `platform/processing-core/app/models/invoice.py`, `platform/document-service/app/main.py`, tests `test_billing_invoice_pdf_e2e.py`
   - **Verify:** `scripts\billing_smoke.cmd` — **NOT VERIFIED**

5) **Billing job run → posting batches → ledger**
   - **Сервисы:** core-api, workers
   - **Endpoints:** admin billing endpoints
   - **Таблицы:** `billing_job_runs`, `posting_batches`, `ledger_entries`
   - **Proof:** `platform/processing-core/app/models/billing_job_run.py`, `platform/processing-core/app/services/billing_service.py`
   - **Verify:** `scripts\smoke_billing_v14.cmd` — **NOT VERIFIED**

6) **Settlement → payout batch → payout export**
   - **Сервисы:** core-api
   - **Endpoints:** `/api/core/.../payouts`, `/api/core/.../settlements`
   - **Таблицы:** `settlements`, `payout_batches`, `payout_export_files`
   - **Proof:** `platform/processing-core/app/models/settlement.py`, `platform/processing-core/app/services/payouts_service.py`, tests `test_payout_exports_e2e.py`
   - **Verify:** `scripts\smoke_billing_finance.cmd` — **NOT VERIFIED**

7) **Reconciliation run → discrepancies → report**
   - **Сервисы:** core-api
   - **Endpoints:** reconciliation admin routes
   - **Таблицы:** `reconciliation_runs`, `reconciliation_discrepancies`
   - **Proof:** `platform/processing-core/app/services/reconciliation_service.py`, `platform/processing-core/app/tests/test_reconciliation_v1.py`
   - **Verify:** `scripts\smoke_billing_finance.cmd` — **NOT VERIFIED**

8) **Webhook intake → delivery → retry/replay (Integration Hub)**
   - **Сервисы:** integration-hub
   - **Endpoints:** `/v1/webhooks/*`, `/v1/webhooks/replay`
   - **Таблицы:** `webhook_intake_events`, `webhook_deliveries`, `webhook_replays`
   - **Proof:** `platform/integration-hub/neft_integration_hub/main.py`, tests `test_webhooks.py`
   - **Verify:** `curl http://localhost:8010/health` — **NOT VERIFIED**

9) **EDO dispatch → status simulation (stub)**
   - **Сервисы:** integration-hub
   - **Endpoints:** `/v1/edo/dispatch`, `/v1/edo/stub/*`
   - **Таблицы:** `edo_documents`, `edo_stub_messages`
   - **Proof:** `platform/integration-hub/neft_integration_hub/services/edo_stub.py`, tests `test_edo_stub.py`
   - **Verify:** `curl http://localhost:8010/health` — **NOT VERIFIED**

10) **Decision memory write → what-if simulator → explain**
    - **Сервисы:** core-api
    - **Endpoints:** `/api/core/.../what-if`, `/api/core/.../explain`
    - **Таблицы:** `decision_memory`, `decision_results`
    - **Proof:** `platform/processing-core/app/services/what_if/simulator.py`, tests `test_what_if_simulator_*`
    - **Verify:** `scripts\test_core_api.cmd` — **NOT VERIFIED**

11) **Audit log write + hash-chain enforcement**
    - **Сервисы:** core-api
    - **Endpoints:** internal hooks on requests
    - **Таблицы:** `audit_log`, `case_events`
    - **Proof:** `platform/processing-core/app/models/audit_log.py`, `platform/processing-core/app/tests/test_audit_log.py`
    - **Verify:** `scripts\test_core_api.cmd` — **NOT VERIFIED**

12) **Fleet fuel ingestion → anomalies → notification outbox**
    - **Сервисы:** core-api
    - **Endpoints:** fleet ingestion APIs
    - **Таблицы:** `fuel_ingest_jobs`, `fuel_anomaly_events`, `fleet_notification_outbox`
    - **Proof:** `platform/processing-core/app/services/fleet_ingestion_service.py`, `platform/processing-core/app/services/fleet_notification_dispatcher.py`, tests `test_fleet_ingestion_v1.py`
    - **Verify:** `scripts\test_core_api.cmd` — **NOT VERIFIED**

13) **Marketplace order → order events → partner portal list**
    - **Сервисы:** core-api, partner-web
    - **Endpoints:** `/api/core/.../marketplace/orders`, partner portal routes `/orders`
    - **Таблицы:** `marketplace_orders`, `marketplace_order_events`
    - **Proof:** `platform/processing-core/app/services/marketplace_order_service.py`, `frontends/partner-portal/src/App.tsx`
    - **Verify:** `scripts\test_core_api.cmd` — **NOT VERIFIED**

14) **Logistics ETA/deviation → explain**
    - **Сервисы:** logistics-service
    - **Endpoints:** `/v1/eta`, `/v1/deviation`, `/v1/explain`
    - **Таблицы:** `logistics_tracking_events` (core)
    - **Proof:** `platform/logistics-service/neft_logistics_service/main.py`, `platform/processing-core/app/models/logistics.py`
    - **Verify:** `curl http://localhost/api/logistics/health` — **NOT VERIFIED**

15) **Client portal: invoices list → invoice details**
    - **Сервисы:** core-api, client-web
    - **Endpoints:** `/api/core/.../invoices`, client portal routes `/billing` and `/billing/:id`
    - **Таблицы:** `invoices`, `invoice_lines`
    - **Proof:** `frontends/client-portal/src/App.tsx`, `frontends/client-portal/src/api/invoices.ts`, `platform/processing-core/app/models/invoice.py`
    - **Verify:** `curl http://localhost:4174/health` — **NOT VERIFIED**

16) **Partner portal: webhooks management**
    - **Сервисы:** integration-hub, partner-web
    - **Endpoints:** `/v1/webhooks/*`, partner portal `/integrations`
    - **Таблицы:** `webhook_endpoints`, `webhook_subscriptions`
    - **Proof:** `platform/integration-hub/neft_integration_hub/models/webhooks.py`, `frontends/partner-portal/src/pages/IntegrationsPage.tsx`
    - **Verify:** `curl http://localhost:8010/health` — **NOT VERIFIED**

---

## 4.9 Граница “Итогового проекта” vs “Сделано”

### DONE (AS-IS факты)
- Core API: billing/finance, settlement/payouts, reconciliation, cases, limits/rules, marketplace, fleet/fuel, audit/decision memory, documents. (`platform/processing-core/app/models`, `platform/processing-core/app/services`)
- Auth host (JWT, demo bootstrap). (`platform/auth-host/app/main.py`)
- Integration Hub (webhooks + EDO stub). (`platform/integration-hub/neft_integration_hub/main.py`)
- Document service (render/sign/verify). (`platform/document-service/app/main.py`)
- Logistics service (ETA/deviation/explain). (`platform/logistics-service/neft_logistics_service/main.py`)
- Frontends (Admin/Client/Partner) with routing + API clients. (`frontends/*/src/App.tsx`, `frontends/*/src/api/*`)
- Observability stack configs. (`infra/*`, `docker-compose.yml`)

### FINAL VISION (UPAS / итоговая цель)
> Основано на перечне доменов из ТЗ (без предположений о реализации).
- Identity/Auth
- Processing/Transactions lifecycle
- Pricing
- Rules/Limits
- Billing
- Clearing/Settlement/Payouts
- Reconciliation
- Documents/PDF/EDO
- Audit/Trust layer
- Integrations/Webhooks/Integration Hub
- Fleet/Fuel
- Marketplace
- CRM
- Logistics
- Analytics/BI
- Notifications
- Frontends (Admin/Client/Partner)
- Observability stack

### GAP (разница между FINAL VISION и DONE)
- Все runtime-проверки, включая health/metrics, миграции, smoke/e2e — **NOT VERIFIED**.
- Реальные внешние интеграции (EDO провайдеры, топливные провайдеры, ML-recommendations) — **NOT IMPLEMENTED** (stub).
- ClickHouse BI runtime — **NOT VERIFIED**.

---

## 5) Минимальные команды проверки (обязательные)

> **Статус:** все ниже **NOT VERIFIED** (не запускались в этом окружении).

```cmd
# Stack
 docker compose up -d --build

# Health
 curl http://localhost/health
 curl http://localhost/api/core/health
 curl http://localhost/api/auth/health
 curl http://localhost/api/ai/health
 curl http://localhost/api/int/health

# Metrics
 curl http://localhost/metrics
 curl http://localhost:8001/metrics
 curl http://localhost:8010/metrics

# Alembic heads/current
 docker compose exec -T core-api sh -lc "alembic -c app/alembic.ini heads"
 docker compose exec -T core-api sh -lc "alembic -c app/alembic.ini current"
 docker compose exec -T auth-host sh -lc "alembic -c alembic.ini heads"
 docker compose exec -T auth-host sh -lc "alembic -c alembic.ini current"

# Smoke scripts
 scripts\get_admin_token.cmd
 scripts\test_core_api.cmd
 scripts\test_auth_host.cmd
 scripts\billing_smoke.cmd
 scripts\smoke_billing_v14.cmd
 scripts\smoke_invoice_state_machine.cmd
```

---

## 6) Расхождения AS-IS docs vs код (если найдены)

- **Не обнаружено расхождений, требующих исправлений**, кроме отсутствия runtime-подтверждений (см. STATUS_SNAPSHOT). (`docs/as-is/STATUS_SNAPSHOT_2026-01-03.md`)
