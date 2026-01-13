# NEFT Platform — AS-IS Master Documentation (фактическое состояние репозитория)

> **Источник истины:** код, конфигурации и скрипты в репозитории `/workspace/neft-processing`.
> **Верификация:** runtime-verify не выполнен; доступные скрипты/тесты перечислены как артефакты, без статуса PASS. См. `docs/as-is/STATUS_SNAPSHOT_RUNTIME_LATEST.md`.

---

## 1) Общее описание (AS-IS)

**Фактически реализованный стек:**
- Мультисервисная платформа с основным API `core-api` (`platform/processing-core`) и вспомогательными сервисами: `auth-host`, `integration-hub`, `ai-service`, `document-service`, `logistics-service`, `crm-service` (stub). Состав и параметры определены в `docker-compose.yml`.
- Gateway (nginx) маршрутизирует API и SPA фронтенды. (`gateway/nginx.conf`)
- Асинхронная обработка: Celery worker/beat (`platform/billing-clearing`).
- Инфраструктура: Postgres, Redis, MinIO, ClickHouse (опционально), observability (OTel, Jaeger, Prometheus, Grafana, Loki/Promtail).

**Карта ключевых директорий:**
```
platform/
  processing-core/        # Core API + доменные модели/сервисы
  auth-host/              # JWT/auth сервис
  integration-hub/        # webhooks + EDO stub
  ai-services/risk-scorer # эвристический risk scorer
  billing-clearing/       # Celery worker/beat
  document-service/       # PDF render/sign/verify
  logistics-service/      # ETA/Deviation/Explain
  crm-service/            # CRM stub (health/metrics)
frontends/
  admin-ui/
  client-portal/
  partner-portal/
  shared/
gateway/
infra/
shared/
```

---

## 2) Runtime architecture (из docker-compose + gateway)

### 2.1 Сервисы (docker-compose)

| Service | Назначение | Код | Health endpoint |
|---|---|---|---|
| gateway | API + SPA routing | `gateway/` | `/health` |
| core-api | Core domain API | `platform/processing-core/` | `/api/core/health` (через gateway) |
| auth-host | Auth/JWT | `platform/auth-host/` | `/api/auth/health` (через gateway) |
| ai-service | Risk scoring API | `platform/ai-services/risk-scorer/` | `/api/ai/health` (через gateway) |
| integration-hub | Webhooks + EDO stub | `platform/integration-hub/` | `/api/int/health` (через gateway) |
| crm-service | CRM stub | `platform/crm-service/` | `/api/crm/health` (через gateway) |
| logistics-service | ETA/Deviation/Explain | `platform/logistics-service/` | `/api/logistics/health` (через gateway) |
| document-service | PDF render/sign/verify | `platform/document-service/` | `/api/docs/health` (через gateway) |
| admin-web | Admin SPA | `frontends/admin-ui/` | `/health` |
| client-web | Client SPA | `frontends/client-portal/` | `/health` |
| partner-web | Partner SPA | `frontends/partner-portal/` | `/health` |
| workers/beat | Celery worker/scheduler | `platform/billing-clearing/` | compose healthchecks |
| flower | Celery monitoring UI | `services/flower/` | `/api/workers` |
| observability | OTel/Jaeger/Prometheus/Grafana/Loki/Promtail | `infra/` | compose healthchecks |

### 2.2 Gateway routing (nginx)

Фактические маршруты (из `gateway/nginx.conf`):
- `/api/core/*` → `core-api`
- `/api/auth/*` → `auth-host`
- `/api/ai/*` → `ai-service`
- `/api/int/*` и `/api/integrations/*` → `integration-hub`
- `/api/crm/*` → `crm-service`
- `/api/logistics/*` → `logistics-service`
- `/api/docs/*` → `document-service`
- `/api/v1/*` → legacy passthrough to `core-api`
- `/admin/`, `/client/`, `/partner/` → SPA фронтенды

---

## 3) Data layer (AS-IS)

- **Postgres** — основной storage для `processing-core` и `auth-host`.
- **Schema `processing_core`** определяется `NEFT_DB_SCHEMA` (default `processing_core`). (`platform/processing-core/app/db/schema.py`)
- **Auth-host schema** определяется `AUTH_DB_SCHEMA` (default `public`). (`platform/auth-host/app/db.py`, `platform/auth-host/app/alembic/env.py`)
- **Integration-hub DB** — URL из `INTEGRATION_HUB_DATABASE_URL` (fallback `DATABASE_URL` или SQLite). (`platform/integration-hub/neft_integration_hub/settings.py`)
- **Подробная карта схем и таблиц:** `docs/as-is/DB_SCHEMA_MAP.md`.

---

## 4) Домены и модули (AS-IS по коду)

> Статусы здесь отражают **наличие кода**. Верификация по runtime отсутствует (см. `STATUS_SNAPSHOT_RUNTIME_LATEST.md`).

| Domain (baseline) | Status | AS-IS coverage (факт) | Key code evidence |
|---|---|---|---|
| Identity & Access | PARTIAL | auth-host JWT + RBAC/ABAC + service identities в core | `platform/auth-host/app/main.py`, `platform/processing-core/app/security/rbac/`, `platform/processing-core/app/services/abac/`, `platform/processing-core/app/models/service_identity.py` |
| Processing & Transactions lifecycle | DONE | операции/транзакции + lifecycle в core | `platform/processing-core/app/services/transactions.py`, `platform/processing-core/app/api/routes/transactions.py` |
| Pricing | PARTIAL | базовые прайсы/версии/marketplace pricing | `platform/processing-core/app/models/pricing.py`, `platform/processing-core/app/api/routes/prices.py`, `platform/processing-core/app/services/marketplace_pricing_service.py` |
| Rules/Limits | PARTIAL | лимиты/правила/политики в core | `platform/processing-core/app/api/routes/limits.py`, `platform/processing-core/app/models/limit_rule.py` |
| Billing | DONE | биллинг/инвойсы/платежи/рефанды | `platform/processing-core/app/services/billing_service.py`, `platform/processing-core/app/models/invoice.py` |
| Clearing/Settlement/Payouts | DONE | clearing + settlement + payouts | `platform/processing-core/app/models/clearing.py`, `platform/processing-core/app/services/settlement_service.py` |
| Reconciliation | DONE | reconciliation runs/discrepancies | `platform/processing-core/app/models/reconciliation.py`, `platform/processing-core/app/services/reconciliation_service.py` |
| Documents | DONE | реестр документов + PDF render/sign/verify | `platform/processing-core/app/models/documents.py`, `platform/document-service/app/main.py` |
| EDO | PARTIAL | EDO модель/роутеры + stub/интеграционный хаб | `platform/processing-core/app/models/edo.py`, `platform/integration-hub/neft_integration_hub/models/edo_stub.py` |
| Audit / Trust | DONE | audit log + signing/retention | `platform/processing-core/app/models/audit_log.py`, `platform/processing-core/app/services/audit_signing.py` |
| Integrations hub | PARTIAL | webhooks intake/delivery/retry/replay | `platform/integration-hub/neft_integration_hub/services/webhooks.py` |
| Fleet/Fuel | PARTIAL | fleet ingestion + fuel models/providers | `platform/processing-core/app/models/fuel.py`, `platform/processing-core/app/integrations/fuel/` |
| Marketplace | PARTIAL | marketplace orders/SLA/promotions | `platform/processing-core/app/models/marketplace_orders.py`, `platform/processing-core/app/services/marketplace_order_service.py` |
| Logistics | PARTIAL | ETA/Deviation/Explain сервис + core модели | `platform/logistics-service/neft_logistics_service/main.py`, `platform/processing-core/app/models/logistics.py` |
| CRM | PARTIAL | CRM модели/роутеры + отдельный stub сервис | `platform/processing-core/app/models/crm.py`, `platform/crm-service/app/main.py` |
| Analytics/BI | PARTIAL | BI endpoints + optional ClickHouse marts | `platform/processing-core/app/api/v1/endpoints/bi.py`, `platform/processing-core/app/alembic/versions/20297240_0129_bi_runtime_marts_v1.py` |
| Notifications | PARTIAL | email/webhook notifications | `platform/processing-core/app/services/notifications_v1.py`, `platform/processing-core/app/tests/test_notifications_webhook.py` |
| Frontends | PARTIAL | Admin/Client/Partner SPA | `frontends/admin-ui/`, `frontends/client-portal/`, `frontends/partner-portal/` |
| Observability | PARTIAL | OTel/Prometheus/Grafana/Loki configs | `infra/otel-collector-config.yaml`, `infra/prometheus.yml`, `infra/loki/` |

---

## 5) Верификация (runtime status)

- **verify_all** существует, но не выполнялся в текущем репозитории. (`scripts/verify_all.cmd`, `docs/as-is/STATUS_SNAPSHOT_RUNTIME_LATEST.md`)
- **Smoke/pytest** перечислены в `docs/as-is/STATUS_SNAPSHOT_LATEST.md` и `docs/as-is/VERIFY_EVIDENCE_INDEX.md` как артефакты, без статуса PASS.
- **SKIP_OK логика:** `scripts/billing_smoke.cmd` и `scripts/smoke_invoice_state_machine.cmd` помечают отсутствие данных как `[SKIP]` и возвращают exit `0`. Эти SKIP учитываются как PASS **только при фактическом выполнении**.

---

## 6) Известные ограничения (AS-IS)

- **CRM service** — stub (health/metrics, без бизнес-логики). (`platform/crm-service/app/main.py`)
- **EDO провайдеры** — stub/mocked, реальных внешних коннекторов нет. (`platform/integration-hub/neft_integration_hub/settings.py`, `platform/integration-hub/neft_integration_hub/models/edo_stub.py`)
- **AI scoring** — эвристическая модель без внешних ML моделей. (`platform/ai-services/risk-scorer/app/model_provider.py`)
- **Logistics provider** — по умолчанию `mock` через `LOGISTICS_PROVIDER`. (`platform/logistics-service/neft_logistics_service/settings.py`)
- **ClickHouse/BI** — опционально, runtime не подтверждён. (`docker-compose.yml`, `platform/processing-core/app/alembic/versions/20297240_0129_bi_runtime_marts_v1.py`)

---

## 7) Актуальные ссылки

- Readiness map: `docs/as-is/NEFT_PLATFORM_READINESS_MAP.md`
- Evidence index: `docs/as-is/VERIFY_EVIDENCE_INDEX.md`
- Latest checks snapshot: `docs/as-is/STATUS_SNAPSHOT_LATEST.md`
- Runtime snapshot: `docs/as-is/STATUS_SNAPSHOT_RUNTIME_LATEST.md`
