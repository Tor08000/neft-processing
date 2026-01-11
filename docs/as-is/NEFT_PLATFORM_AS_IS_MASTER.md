# NEFT Platform — AS-IS Master Documentation (Full System Map + Current Status Snapshot)

> **Scope:** This document describes what is **actually implemented** in `/workspace/neft-processing` as of now. Any missing components are explicitly marked **NOT IMPLEMENTED**. No future work or assumptions are included.

---

## 4.1 Overview

**Назначение платформы (AS-IS):**
- Мультисервисная платформа для финансовой обработки (billing, settlement), флота/топлива, маркетплейса, документов и аудита.
- Основной API — `core-api` (`platform/processing-core/`) + вспомогательные сервисы `auth-host`, `integration-hub`, `ai-service`, `document-service`, `logistics-service`.

**Основные контуры (по факту кода):**
- Core/Trust & Audit
- Billing & Finance
- Fleet/Fuel
- Marketplace & Partner Services
- Documents & Exports
- Decision Memory & What-If
- Reconciliation/Internal Ledger
- Integrations (Integration Hub + webhooks)
- Observability (Prometheus/Grafana/Jaeger/Loki)

**Карта ключевых директорий (AS-IS):**

```
platform/
  processing-core/        # Core API (billing, fleet, marketplace, audit)
  auth-host/              # JWT/auth service
  integration-hub/        # webhooks + EDO stub
  ai-services/risk-scorer # AI scoring stub
  billing-clearing/       # Celery workers/beat
  document-service/       # PDF render/sign/verify
  logistics-service/      # logistics ETA/deviation service
  crm-service/            # CRM stub
frontends/
  admin-ui/
  client-portal/
  partner-portal/
  shared/
gateway/
services/
  flower/
  ai-risk/                # auxiliary assets
infra/
  prometheus.yml, grafana/, otel-collector-config.yaml, loki/, promtail/
shared/
  python/                 # shared settings/logging
  contracts/
docs/
  as-is/                  # текущий AS-IS пакет
```

**Краткая карта сервисов (AS-IS):**
- Gateway (nginx) → core-api, auth-host, ai-service, integration-hub, crm-service, logistics-service, document-service + SPA frontends. (`gateway/nginx.conf`)
- Core API + Celery workers → Postgres, Redis, MinIO, optional ClickHouse. (`docker-compose.yml`, `shared/python/neft_shared/settings.py`)

---

## 4.2 Runtime Architecture (AS-IS)

**Сервисы (по docker-compose):**
- API: `core-api`, `auth-host`, `ai-service`, `integration-hub`, `crm-service`, `logistics-service`, `document-service`.
- Frontends: `admin-web`, `client-web`, `partner-web`.
- Infra: `postgres`, `redis`, `minio`, `clickhouse` (optional), `otel-collector`, `jaeger`, `prometheus`, `grafana`, `loki`, `promtail`.
- Async: `workers`, `beat`, `flower`, `celery-exporter`.

**Основные связи (AS-IS):**
- `gateway` → `/api/core/*` → `core-api` (`platform/processing-core/app/main.py`).
- `gateway` → `/api/auth/*` → `auth-host` (`platform/auth-host/app/main.py`).
- `gateway` → `/api/ai/*` → `ai-service` (`platform/ai-services/risk-scorer/app/main.py`).
- `gateway` → `/api/int/*` или `/api/integrations/*` → `integration-hub` (`platform/integration-hub/neft_integration_hub/main.py`).
- `gateway` → `/api/crm/*`, `/api/logistics/*`, `/api/docs/*` → `crm-service`, `logistics-service`, `document-service`.
- `core-api` + `workers` + `beat` → `redis` (broker/backend), `postgres` (DB), `minio` (S3).
- `core-api` (опционально) → `clickhouse` (BI), `document-service`, `logistics-service` (через флаги включения).

**Базы/кэши/очереди:**
- Postgres (основной storage) — `postgres:16`.
- Redis (cache + Celery broker/backend) — `redis:7.4-alpine`.
- MinIO (S3) — `quay.io/minio/minio`.
- ClickHouse (BI) — `clickhouse/clickhouse-server:24.6` (по флагу `BI_CLICKHOUSE_ENABLED`).

**Observability:**
- OTel Collector (OTLP 4317) + Jaeger UI 16686.
- Prometheus + Grafana.
- Loki + Promtail (лог-агрегация). (`infra/loki/`, `infra/promtail/`)

---

## 4.3 Service Catalog (кратко)

Подробный каталог: **[docs/as-is/SERVICE_CATALOG.md](SERVICE_CATALOG.md)**

| Service | Purpose | Port(s) | Health | Metrics |
|---|---|---|---|---|
| gateway | API + SPA routing | `80` | `/health` | `/metrics` |
| core-api | Core domain API | `8001` | `/api/core/health` | `/metrics` |
| auth-host | Auth/JWT | `8002` | `/api/auth/health` | `/api/v1/metrics` |
| ai-service | Risk scoring API | `8003` | `/api/v1/health` | `/metrics` |
| integration-hub | Webhooks + EDO | `8010` | `/health` | `/metrics` |
| admin-web | Admin SPA | `4173` | `/health` | n/a |
| client-web | Client SPA | `4174` | `/health` | n/a |
| partner-web | Partner SPA | `4175` | `/health` | n/a |
| workers/beat | Celery worker + scheduler | internal | compose healthchecks | n/a |
| flower | Celery monitoring UI | `5555` | `/api/workers` | n/a |

---

## 4.4 Data Layer (AS-IS)

Подробная карта: **[docs/as-is/DB_SCHEMA_MAP.md](DB_SCHEMA_MAP.md)**

**Схемы БД:**
- `processing_core` — доменные данные core-api. (`platform/processing-core/app/db/schema.py`)
- `public` (или `AUTH_DB_SCHEMA`) — auth-host. (`platform/auth-host/app/alembic/versions/20251001_0001_auth_bootstrap.py`)
- Integration Hub DB — SQLite по умолчанию, или Postgres по `INTEGRATION_HUB_DATABASE_URL`.

**Alembic:**
- Core API heads: `20261201_0017_accounts_and_ledger`, `20297100_0115_merge_heads`. (`platform/processing-core/app/alembic/versions/`)
- Auth-host head: `20251001_0001_auth_bootstrap`. (`platform/auth-host/app/alembic/versions/`)
- `alembic current` **NOT VERIFIED** (требует запущенной БД).

---

## 4.5 Eventing & Audit (AS-IS)

Подробный каталог: **[docs/as-is/EVENT_CATALOG.md](EVENT_CATALOG.md)**

**Audit log и hash-chain:**
- `audit_log` хранит хэш-цепочку и метаданные запросов. (`platform/processing-core/app/models/audit_log.py`)
- `case_events` также содержит `prev_hash/hash/signature` поля. (`platform/processing-core/app/models/cases.py`)

**Signing mode (local) и варианты:**
- `AUDIT_SIGNING_MODE` по умолчанию `local`. (`shared/python/neft_shared/settings.py`)
- Поддерживаются `local`, `aws_kms`, `vault_transit` (реализации в `app/services/audit_signing.py`).

**WORM / Object Lock:**
- Конфигурация через `S3_OBJECT_LOCK_*` env. (`shared/python/neft_shared/settings.py`)
- Требует поддержки object-lock на S3/MinIO — **NOT VERIFIED**.

**Метрики:**
- `core-api` экспортирует Prometheus метрики (`/metrics`). (`platform/processing-core/app/main.py`)
- Gateway метрика `gateway_up` на `/metrics`. (`gateway/nginx.conf`)

---

### Security (Service Identities + ABAC) — **READY**

- **Service identities (M2M):** таблицы `service_identities`, `service_tokens`, `service_token_audit`; выпуск/ротация/ревокация через admin API. (`platform/processing-core/app/models/service_identity.py`, `platform/processing-core/app/routers/admin/security.py`)
- **Token rotation flow:** issue → rotate (grace period) → revoke; токены только в виде хэша + префикс, plaintext выдаётся однократно. (`platform/processing-core/app/services/service_identities.py`)
- **ABAC policies:** версии `abac_policy_versions` + правила `abac_policies` с JSON conditions и приоритетами. (`platform/processing-core/app/models/abac.py`, `platform/processing-core/app/services/abac/engine.py`)
- **ABAC enforcement:** подключено к Documents download, EDO send, CRM client read, Payout export, BI scope. (`platform/processing-core/app/routers/client_documents.py`, `platform/processing-core/app/routers/admin/edo.py`, `platform/processing-core/app/routers/admin/crm.py`, `platform/processing-core/app/api/v1/endpoints/payouts.py`, `platform/processing-core/app/api/v1/endpoints/bi.py`)

---

## 4.6 Core Business Modules (AS-IS)

> Статусы: **READY / PARTIAL / NOT IMPLEMENTED**.

### Billing & Finance — **READY**
- **Модели/таблицы:** `billing_invoices`, `billing_payments`, `billing_refunds`, `invoices`, `invoice_lines`, `internal_ledger_*`, `posting_batches`, `settlements`, `payout_*`. (`platform/processing-core/app/models/*`)
- **Сервисы/эндпоинты:** `app/services/billing_service.py`, `app/services/payouts_service.py`, `app/routers/admin/billing.py`, `app/api/v1/endpoints/billing_invoices.py`.
- **Инварианты/стейт-машины:** invoice transitions + billing flow state в `invoice_transition_logs`, `billing_flow`. (`platform/processing-core/app/models/invoice.py`, `platform/processing-core/app/models/billing_flow.py`)

### Fleet / Fuel — **REAL**
- **Модели/таблицы:** `fuel_cards`, `fuel_transactions`, `fuel_provider_batches`, `fleet_offline_profiles`, `fleet_offline_reconciliation_runs`. (`platform/processing-core/app/models/fuel.py`, `platform/processing-core/app/integrations/fuel/models.py`)
- **Сервисы/эндпоинты:** `app/services/fleet_service.py`, `app/services/fleet_ingestion_service.py`, `app/routers/client_fleet.py`, `app/routers/internal/fuel_providers.py`.
- **Инварианты:** блокировки/эскалации в `fleet_policy_engine.py`, `fleet_anomaly_service.py`; batch replay idempotency через `content_hash` и `provider_batch_key`.
- **Fleet Providers: REAL** — эталонный адаптер `provider_ref` с протоколами ingestion/authorize/settlement, CSV ingest и replay. (`platform/processing-core/app/integrations/fuel/providers/provider_ref/`)

### Marketplace — **PARTIAL**
- **Модели/таблицы:** `marketplace_products`, `marketplace_orders`, `marketplace_promotions`, `marketplace_events`, `sponsored_events`, `service_bookings`. (`platform/processing-core/app/models/marketplace_*.py`, `platform/processing-core/app/models/service_bookings.py`)
- **Сервисы/эндпоинты:** `app/routers/client_marketplace*.py`, `app/routers/partner/marketplace_*.py`, `app/services/marketplace_order_service.py`.
- **Инварианты:** immutable event tables via ORM hooks. (`platform/processing-core/app/models/marketplace_orders.py`)
- **Почему PARTIAL:** алгоритмы рекомендаций и спонсоринга реализованы как data-модели + API без внешнего ML сервиса. Отдельного рекомендационного сервиса **NOT IMPLEMENTED**.

### Decision Memory + What-If — **PARTIAL**
- **Модели/таблицы:** `decision_memory`, `decision_results`, `risk_*`. (`platform/processing-core/app/models/decision_memory.py`, `platform/processing-core/app/models/decision_result.py`)
- **Сервисы/эндпоинты:** `app/services/what_if/simulator.py`, `app/routers/admin/what_if.py`.
- **Инварианты:** deterministic what-if scoring tests. (`platform/processing-core/app/tests/test_what_if_simulator_*`)

### Reconciliation / Internal Ledger — **READY**
- **Модели/таблицы:** `reconciliation_*`, `billing_reconciliation_*`, `internal_ledger_*`. (`platform/processing-core/app/models/reconciliation.py`, `platform/processing-core/app/models/internal_ledger.py`)
- **Сервисы/эндпоинты:** `app/services/reconciliation_service.py`, `app/services/settlement_service.py`.

### Documents / Exports — **PARTIAL**
- **Модели/таблицы:** `documents`, `document_files`, `closing_packages`, `accounting_export_batches`, `erp_exports`. (`platform/processing-core/app/models/documents.py`, `platform/processing-core/app/models/accounting_export_batch.py`, `platform/processing-core/app/models/erp_exports.py`)
- **Сервисы/эндпоинты:** `platform/document-service/app/main.py`, `app/services/documents_generator.py`, `app/routers/client_documents.py`.
- **Шаблоны документов:** репозиторий `platform/document-service/templates/` + схемы `platform/document-service/templates/schemas/`, эндпоинты `GET /v1/templates` и `GET /v1/templates/{code}` в document-service, прокси `GET /api/core/documents/templates` в core-api.
- **Почему PARTIAL:** EDO интеграции и внешние провайдеры — stub/мок режим (`platform/integration-hub/neft_integration_hub/services/edo_stub.py`).

### Legal Gate / Compliance — **PARTIAL**
- **Граф доверия (legal graph):** `app/services/legal_graph/*`, admin endpoints `/api/core/admin/legal-graph/*`.
- **Trust gates:** интеграционные проверки в `platform/processing-core/app/tests/test_trust_gates.py`.
- **Проверка legal gate (Windows CMD):** `scripts\\test_core_stack.cmd` (unit tests) и `scripts\\smoke_legal_gate.cmd` (smoke через gateway).
- **Почему PARTIAL:** юридические блокировки/гейты для бизнес-операций описаны, но API-обвязка под конкретные сценарии требует настройки.

---

## 4.7 Frontends / Portals

- **Admin Web:** `frontends/admin-ui/`, контейнер `admin-web`, gateway путь `/admin/`.
- **Client Web:** `frontends/client-portal/`, контейнер `client-web`, gateway путь `/client/`.
- **Partner Web:** `frontends/partner-portal/`, контейнер `partner-web`, gateway путь `/partner/`.

**Gateway routing:** `gateway/nginx.conf` (upstreams `admin_web`, `client_web`, `partner_web`).

**Статус сборки/запуска (AS-IS):**
- Все три контейнера определены в `docker-compose.yml`.
- Факт запуска **NOT VERIFIED** (см. snapshot).

---

## 4.8 Operations

Подробный runbook: **[docs/as-is/RUNBOOK_LOCAL.md](RUNBOOK_LOCAL.md)**

**Запуск (Windows CMD):**
```cmd
docker compose up -d --build
```

**Проверка:**
```cmd
curl http://localhost/health
curl http://localhost/api/core/health
curl http://localhost/api/auth/health
curl http://localhost/api/ai/health
curl http://localhost/api/int/health
```

**Логи:**
```cmd
docker compose logs -f core-api
docker compose logs -f auth-host
docker compose logs -f gateway
```

**How to run core tests (processing-core):**
```cmd
scripts\test_processing_core_docker.cmd
```

All processing-core tests:
```cmd
scripts\test_processing_core_docker.cmd all
```

**Типовые ошибки (минимум 5):**
1) **MinIO init не проходит** → проверьте `MINIO_ROOT_USER/PASSWORD` и `minio-init` логи. (`infra/minio-init.sh`)
2) **Auth-host не стартует** → проверьте ключи и `AUTH_KEY_DIR` volume. (`docker-compose.yml`, `.env.example`)
3) **502 от gateway** → убедитесь в `service_healthy` upstream. (`gateway/nginx.conf`, `docker-compose.yml`)
4) **Celery workers unhealthy** → проверьте `CELERY_BROKER_URL` и Redis. (`docker-compose.yml`)
5) **Нет метрик в Prometheus** → проверьте target в `infra/prometheus.yml`.

---

## 4.9 Flags / Configuration Matrix

> Только реальные env vars из compose и `.env.example`.

### core-api
- `NEFT_DB_SCHEMA` (schema), `NEFT_S3_*` (S3), `NEFT_PDF_AUTO_GENERATE`.
- `BI_CLICKHOUSE_ENABLED`, `CLICKHOUSE_URL`.
- `DOCUMENT_SERVICE_ENABLED`, `DOCUMENT_SERVICE_URL`.
- `LOGISTICS_SERVICE_ENABLED`, `LOGISTICS_SERVICE_URL`.
- `NEFT_AUTH_ISSUER`, `NEFT_AUTH_AUDIENCE`.

### auth-host
- `AUTH_KEY_DIR`, `AUTH_PRIVATE_KEY_PATH`, `AUTH_PUBLIC_KEY_PATH`.
- `NEFT_BOOTSTRAP_ADMIN_*` (bootstrap admin).
- `NEFT_AUTH_ISSUER`, `NEFT_AUTH_AUDIENCE`.

### integration-hub
- `INTEGRATION_HUB_DATABASE_URL`, `WEBHOOK_INTAKE_SECRET`, `WEBHOOK_ALLOW_UNSIGNED`.
- `DIADOK_MODE`, `DIADOK_BASE_URL`, `DIADOK_API_TOKEN` (stub/real). (`platform/integration-hub/neft_integration_hub/settings.py`)

### Integrations Hub (core-api)
- 1C export + bank statements + reconciliation implemented in `platform/processing-core/app/integrations/` and `/api/v1/admin/integrations/*`.

### workers/beat
- `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `CELERY_DEFAULT_QUEUE`.
- S3 + ClickHouse envs (same as core-api).

### Observability
- OTel collector config in `infra/otel-collector-config.yaml`.
- Prometheus targets in `infra/prometheus.yml`.

### Audit signing / security
- `AUDIT_SIGNING_MODE`, `AUDIT_SIGNING_REQUIRED`, `AUDIT_SIGNING_ALG`.
- `AUDIT_SIGNING_PRIVATE_KEY_B64`, `AUDIT_SIGNING_PUBLIC_KEYS_JSON`.
- `S3_OBJECT_LOCK_*` for WORM/retention. (`shared/python/neft_shared/settings.py`, `.env.example`)

### Feature flags
- `FEATURE_FLAGS` присутствует в `.env.example`, но прямых ссылок в коде не найдено. **NOT IMPLEMENTED (runtime parsing)**.

---

## 4.10 Known Limitations

- Kafka/RabbitMQ-based event bus **NOT IMPLEMENTED** (нет в compose/коде).
- Schema registry **NOT IMPLEMENTED**.
- Реальные провайдеры топлива — **stub/template** (см. `platform/processing-core/app/integrations/fuel/providers/*`).
- SMS/Voice провайдеры уведомлений — **stub only** (`sms_stub`, `voice_stub` в `app/services/fleet_notification_dispatcher.py`).
- Рекомендательный сервис как отдельный сервис **NOT IMPLEMENTED** (только модели/эндпоинты).
- BI ClickHouse выключен по умолчанию (`BI_CLICKHOUSE_ENABLED=0`).
- Object Lock/WORM требует внешней поддержки S3 — **NOT VERIFIED**.

---

## 4.11 Status Snapshot 2026-01-03

Снимок статуса: **[docs/as-is/STATUS_SNAPSHOT_2026-01-03.md](STATUS_SNAPSHOT_2026-01-03.md)**
