# NEFT Platform — AS-IS Master Documentation (фактическое состояние репозитория)

> **Источник истины:** код, конфигурации и скрипты в репозитории `/workspace/neft-processing`.
> **Runtime-верификация:** последний `verify_all` завершён **PASS**, детали — в `docs/as-is/STATUS_SNAPSHOT_RUNTIME_LATEST.md`.

---

## 1) Общее описание (AS-IS)

**Фактически реализованный стек:**
- Мультисервисная платформа с основным API `core-api` (`platform/processing-core`) и вспомогательными сервисами: `auth-host`, `integration-hub`, `ai-service`, `document-service`, `logistics-service`, `crm-service` (compatibility/shadow CRM surface). Состав и параметры определены в `docker-compose.yml`.
- Gateway (nginx) маршрутизирует API и SPA фронтенды. (`gateway/nginx.conf`)
- Асинхронная обработка: Celery worker/beat (`platform/billing-clearing`).
- Инфраструктура: Postgres, Redis, MinIO, observability stack (OTel/Jaeger/Prometheus/Grafana/Loki/Promtail).

**Карта ключевых директорий:**
```
platform/
  processing-core/        # Core API + доменные модели/сервисы
  auth-host/              # JWT/auth сервис
  integration-hub/        # webhooks + EDO transport owner (stub only in explicit mode)
  ai-services/risk-scorer # эвристический risk scorer
  billing-clearing/       # Celery worker/beat
  document-service/       # PDF render/sign/verify
  logistics-service/      # ETA/Deviation/Explain
  crm-service/            # Compatibility/shadow CRM service
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

## 2) Сервисы (AS-IS по docker-compose)

| Service | Назначение | БД / схема | Ключевые API/интерфейсы | Статус |
|---|---|---|---|---|
| gateway | API + SPA routing | — | `/health`, `/metrics`, прокси `/api/*`, `/admin/`, `/client/`, `/partner/` | DONE |
| core-api | Core domain API | Postgres, schema `processing_core` | `/api/core/*`, `/api/v1/*` | DONE |
| auth-host | Auth/JWT | Postgres, schema `AUTH_DB_SCHEMA` (default `public`) | `/api/auth/*` | DONE |
| integration-hub | Webhooks + explicit EDO transport owner | Postgres/SQLite (configurable) | `/api/int/*`, `/api/integrations/*` | PARTIAL |
| ai-service | Risk scoring API (heuristics) | — | `/api/ai/*` | PARTIAL |
| document-service | PDF render/sign/verify | — | `/api/docs/*` | DONE |
| logistics-service | ETA/Deviation/Explain | — | `/api/logistics/*` | PARTIAL |
| crm-service | Compatibility/shadow CRM surface | — | `/api/crm/*`, `/api/v1/crm/*` | COMPATIBILITY |
| billing-clearing worker/beat | Асинхронные billing/settlement задачи | Postgres `processing_core`, Redis | Celery queues (internal) | DONE |
| flower | UI мониторинга Celery | — | `/api/workers` | DONE |
| admin-web | Admin SPA | — | `/admin/` | PARTIAL |
| client-web | Client SPA | — | `/client/` | PARTIAL |
| partner-web | Partner SPA | — | `/partner/` | PARTIAL |
| observability (otel/jaeger/prometheus/grafana/loki/promtail) | Метрики/трейсы/логи | — | сервисные endpoints в `docker-compose.yml` | PARTIAL |

---

## 3) Data layer (AS-IS)

- **Postgres** — основной storage для `processing-core` и `auth-host`.
- **Schema `processing_core`** определяется `NEFT_DB_SCHEMA` (default `processing_core`). (`platform/processing-core/app/db/schema.py`)
- **Auth-host schema** определяется `AUTH_DB_SCHEMA` (default `public`). (`platform/auth-host/app/db.py`, `platform/auth-host/app/alembic/env.py`)
- **Integration-hub DB** — URL из `INTEGRATION_HUB_DATABASE_URL` (fallback `DATABASE_URL` или SQLite). (`platform/integration-hub/neft_integration_hub/settings.py`)
- **Подробная карта схем и таблиц:** `docs/as-is/DB_SCHEMA_MAP.md`.

---

## 4) Домены и модули (AS-IS по коду)

> Статусы отражают **наличие кода** и не эквивалентны полноте baseline.

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
| CRM | PARTIAL | canonical admin CRM в `processing-core` + compatibility/shadow `crm-service` | `platform/processing-core/app/routers/admin/crm.py`, `platform/crm-service/app/main.py` |
| Analytics/BI | PARTIAL | BI endpoints + optional ClickHouse marts | `platform/processing-core/app/api/v1/endpoints/bi.py`, `platform/processing-core/app/alembic/versions/20297240_0129_bi_runtime_marts_v1.py` |
| Notifications | PARTIAL | email/webhook notifications | `platform/processing-core/app/services/notifications_v1.py`, `platform/processing-core/app/tests/test_notifications_webhook.py` |
| Frontends | PARTIAL | Admin/Client/Partner SPA | `frontends/admin-ui/`, `frontends/client-portal/`, `frontends/partner-portal/` |
| Observability | PARTIAL | OTel/Prometheus/Grafana/Loki configs | `infra/otel-collector-config.yaml`, `infra/prometheus.yml`, `infra/loki/` |

---

## 5) Верификация (runtime status)

- **verify_all** выполнен и завершён **PASS**; подробности — `docs/as-is/STATUS_SNAPSHOT_RUNTIME_LATEST.md`.
- **Smoke/pytest** фиксируются как шаги runtime-снимка (PASS или SKIP_OK).
- **SKIP_OK логика:** `scripts/billing_smoke.cmd` и `scripts/smoke_invoice_state_machine.cmd` при отсутствии данных возвращают `[SKIP]`, что считается PASS по логике verify_all.

---

## 6) Известные ограничения (AS-IS)

- **CRM service** — compatibility/shadow CRM service with its own `/api/v1/crm/*` runtime, but not the canonical CRM control plane owner. (`platform/crm-service/app/main.py`)
- **EDO провайдеры** — stub/mocked, реальных внешних коннекторов нет. (`platform/integration-hub/neft_integration_hub/settings.py`, `platform/integration-hub/neft_integration_hub/models/edo_stub.py`)
- **AI scoring** — эвристическая модель без внешних ML моделей. (`platform/ai-services/risk-scorer/app/model_provider.py`)
- **Logistics provider** — по умолчанию transport=`integration_hub`, compute=`osrm`; explicit `mock` remains dev/test-only override. (`platform/logistics-service/neft_logistics_service/settings.py`)
- **ClickHouse/BI** — опционально и не обязателен для verify_all. (`docker-compose.yml`, `platform/processing-core/app/alembic/versions/20297240_0129_bi_runtime_marts_v1.py`)

---

## 7) Актуальные ссылки

- Readiness map: `docs/as-is/NEFT_PLATFORM_READINESS_MAP.md`
- Текущий выверенный статус готовности: `docs/as-is/NEFT_ASIS_Readiness_Current.md`
- Evidence index: `docs/as-is/VERIFY_EVIDENCE_INDEX.md`
- Latest checks snapshot: `docs/as-is/STATUS_SNAPSHOT_LATEST.md`
- Runtime snapshot: `docs/as-is/STATUS_SNAPSHOT_RUNTIME_LATEST.md`
