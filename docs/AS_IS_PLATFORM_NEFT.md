# NEFT Platform — AS-IS (текущее состояние)

> Источники: структура репозитория, docker-compose/infra конфиги, код сервисов, Alembic миграции, модели SQLAlchemy, тесты, entrypoint скрипты.

## 3.1 Executive Summary

**Что это:**

NEFT Platform в текущем виде — набор сервисов вокруг процессинга операций и биллинга, собранный в `docker-compose.yml`: 
* core-api (FastAPI) с бизнес-логикой операций, биллинга, клиринга, payout/export, лимитов, risk rules, клиентского портала, админки.
* auth-host (FastAPI) для авторизации/админ-пользователей, с минимальной схемой БД на прямом SQL.
* ai-service (FastAPI) — простой risk scoring (stub) с локальной моделью.
* Celery workers/beat + Flower для фоновых задач.
* инфраструктура: Postgres, Redis, MinIO, Nginx gateway, Prometheus/Grafana, OTel collector + Jaeger.

**Для чего пригодна (фактически):**

* CRUD/операции процессинга (operations, merchants, terminals, cards, clients) и риск-правила в core-api.
* Биллинг/инвойсинг: генерация периодов, сводок, инвойсов, PDF, финоперации по инвойсам (payments/credit notes/refunds), аудит переходов, job runs.
* Клиринг: дневные batch + привязка операций, статусы, запуск через API.
* Payouts/settlements: создание batch, экспорт, mark-sent/settled, S3 storage экспорта.
* Клиентский портал и админские endpoints (основные CRUD/отчёты/статусы).
* Метрики в Prometheus-формате (core-api и ai-service), gateway /metrics.

**Статус платформы (по факту в репозитории):**

* core-api стартует, проверяет Alembic heads и применяет миграции (`platform/processing-core/entrypoint.sh`).
* Сервисы в compose поднимаются без блокирующих ошибок, критичные health/metrics endpoints объявлены.
* Критичные домены подтверждены: core-api ✅, documents ✅, risk v3 ✅, accounting_export_batch ✅.

**Критичные этапы, которые есть в коде:**

* Billing hardening + инварианты (state machine + immutability guards).
* Cross-period settlement_allocation для платежей/credit notes/возвратов.
* accounting_export_batch с детерминированным сериализатором и S3 storage.
* RBAC/policy engine для финансовых действий (finalize/lock/payment/credit/export).
* Legal finalization для documents/closing_package (ISSUED → ACKNOWLEDGED → FINALIZED).
* Decision engine + risk scoring v2 endpoints (ai-service).

**Ядро (core):**

* `platform/processing-core/app` — ядро бизнес-логики и схемы БД (через Alembic). 
* `platform/billing-clearing/app` — Celery задачи (limits, billing summaries, clearing batches, AI scoring вызов).

**Готовые бизнес-потоки (по коду):**

* Транзакции: authorize/capture/refund/reversal через core-api, запись операций в БД.
* Лимиты: check-and-reserve + пересчёт лимитов (частично через Celery/локальную логику).
* Биллинг: daily summary, close period, генерация инвойсов, PDF генерация (с MinIO).
* Финансы: платежи и credit notes по инвойсам с идемпотентностью и state machine.
* Клиринг: daily batch (связка операций → clearing_batch) + reconciliation/mark.
* Payouts/exports: batch exports, storage, download.

**End-to-end потоки (по коду):**

* billing period finalize/lock → invoices → payments/credits → settlement_allocation.
* accounting export (charges/settlement) → S3 upload → download → confirm.
* documents issue/acknowledgement/finalize → immutable chain (hash) → audit.
* decision engine gating → fail-closed (отказ при DECLINE/MANUAL_REVIEW).

**Ключевые блокеры готовности (по факту):**

* В auth-host нет миграций: таблицы создаются при старте (простая схема, потенциально для prod недостаточно).
* В beat конфигурация расписания лежит в `platform/billing-clearing/app/beat.py`, но `entrypoint` запускает `-A ...celery_app` без загрузки `beat.py` → расписания могут не применяться.
* В Prometheus config заложен /api/v1/metrics для auth-host, но такого endpoint в коде нет (metrics отсутствуют).
* В docker-compose есть crm-service/logistics-service/document-service как заглушки (alpine + sleep).
* AI scoring: core-api использует legacy `/api/v1/score`, ai-service имеет `/v1/risk-score` v2 и admin train/update, но это пока не подключено в core-api (scoring heuristic/stub).

**Known limitations (current):**

* auth-host не имеет Alembic миграций (bootstrap SQL при старте).
* Планировщик beat не гарантирует загрузку расписания без явного импорта `app/beat.py`.
* metrics для auth-host отсутствуют (endpoint объявлен только в Prometheus config).
* Заглушки сервисов остаются без доменной функциональности (crm/logistics/document-service).
* Внешний документооборот/подписание не реализован (только document lifecycle и audit chain).

---

## 3.1.1 Current runtime status (docker compose)

**Текущее состояние стенда (по последнему поднятому docker compose):**

* **core-api** — healthy (`8001 → 8000` в контейнере).
* **gateway** — up (`80`).
* **admin-web** — up/healthy (`4173`).
* **client-web** — up/healthy (`4174`).
* **auth-host** — up (`8002 → 8000`).
* **ai-service** — up (`8003 → 8000`).
* **workers / beat / flower** — up (Flower `5555`).
* **postgres** — up (`5432`), **redis** — up (`6379`).
* **grafana** — up (`3000`), **prometheus** — up (`9090`), **jaeger** — up (`16686`), **otel-collector** — up.
* **minio** — up (`9000/9001`), **minio-init** — `exited=0` (инициализация бакетов).
* **crm-service / document-service / logistics-service** — заглушки (`alpine + sleep`), доменной функциональности нет.
* **orphan/smoke контейнеры** — если присутствуют, считаются мусором и подлежат cleanup (см. раздел Tech debt).

**Факты по проверкам (на поднятом стенде):**

* `GET http://localhost:8001/api/core/health` → `{"status":"ok"}`.
* `GET http://localhost:8001/metrics` → Prometheus-метрики, `core_api_up 1`.
* `GET http://localhost/api/core/health` через gateway → `{"status":"ok"}`.

---

## 3.1.2 Migrations stabilization: what was fixed

**Цель:** убрать ошибки парсинга/создания типов/конфликтов head, сделать повторный прогон миграций безопасным.

### Syntax/parse errors in migrations
* **Проблема:** `SyntaxError` из-за экранированных кавычек в f-string (`f\"{SCHEMA}...\"`).
* **Причина:** некорректный синтаксис в миграции CRM.
* **Решение:** нормализованы строки до обычных f-strings.
* **Текущее состояние:** миграция `20291405_0066_crm_subscriptions_v1.py` корректно парсится.

### Multiple heads
* **Проблема:** в репозитории было **2 head** (`20290510_0046...` и `20291410_0067...`).
* **Причина:** параллельные ветки миграций (CRM/логистика).
* **Решение:** добавлен merge revision `20291415_0068_merge_heads_0046_0067`.
* **Текущее состояние:** единый head — `20291415_0068_merge_heads_0046_0067`.

### ENUM idempotency (DuplicateObject)
* **Проблема:** `DuplicateObject` при повторном прогоне миграций (fuel/logistics/crm).
* **Причина:** `CREATE TYPE` без проверки существования и использование `sa.Enum(name=...)` без `create_type=False`.
* **Решение:** единый паттерн:
  * функции `ensure_pg_enum(...)` и `ensure_pg_enum_value(...)` (см. `platform/processing-core/app/alembic/helpers.py`, `app/alembic/utils.py`);
  * в колонках только `postgresql.ENUM(..., create_type=False, schema=SCHEMA)`;
  * запрет на “голые” `sa.Enum(name=...)` без `create_type=False`.
* **Текущее состояние:** миграции fuel/logistics/crm повторно применимы без ошибок `DuplicateObject`.

### FK datatype mismatch (varchar vs uuid)
* **Проблема:** `DatatypeMismatch` при создании FK (например, PK = `UUID`, FK = `VARCHAR`).
* **Причина:** несогласованные типы ключей в CRM/fuel доменах.
* **Решение:** приведены поля к `UUID`, в т.ч. `billing_period_id` и связанные FK в миграциях fuel/CRM.
* **Текущее состояние:** правило зафиксировано — **тип FK = тип PK целевой таблицы**.

### Entrypoint migration validation
* **Проблема:** риск старта `uvicorn` на неконсистентной БД.
* **Решение:** entrypoint проверяет heads/таблицы/regclass и только потом стартует API.
* **Текущее состояние:** head — `20291415_0068_merge_heads_0046_0067`, checks выполняются до `uvicorn`.

---

## 3.1.3 App boot fixes

**Проблемы старта core-api (uvicorn):**

* **SyntaxError:** `non-default argument follows default argument` в CRM admin router.
  * **Причина:** параметр без дефолта располагался после параметра с дефолтом.
  * **Решение:** исправлен порядок аргументов.
* **Импортные конфликты моделей (FuelRouteLink и связанные модели fuel/logistics):**
  * **Причина:** несогласованность экспортов/импортов между доменами.
  * **Решение:** поправлены импорты и определения моделей.

**Текущее состояние:** лог старта `core-api` доходит до `startup complete`, healthchecks проходят.

---

## 3.1.4 Frontends status and fixes

### client-portal
* **Проблема:** `TS2339` (`slice` на `{}`) в `DocumentDetails`.
* **Причина:** `risk_explain` типизировался как `{}` без guards.
* **Решение:** добавлена типизация + guards для nullable risk state.
* **Текущее состояние:** сборка проходит, контейнер healthy.

### admin-web
* **Проблема:** пачка TS ошибок в payouts (types/api/helpers/pages).
* **Причина:** рассинхрон типов payouts и API.
* **Решение:** выровнены типы, хелперы и страницы списка/детали; добавлен payout access в layout через role helper.
* **Текущее состояние:** docker build проходит, контейнер healthy.

---

## 3.1.5 Observability

**Порты и endpoints (локально):**

* **Prometheus:** `9090`
* **Grafana:** `3000`
* **Jaeger UI:** `16686`
* **OTel collector:** `4317`
* **core-api metrics:** `http://localhost:8001/metrics` (также доступно через gateway `/metrics`)

---

## 3.1.6 Warnings & tech debt

**Pydantic warnings**
* **Проблема:** `model_version` конфликтует с `protected_namespaces` (`model_`).
* **Решение (рекомендовано):** точечный `ConfigDict(protected_namespaces=())` для `RiskV5*` моделей.

**Отсутствующие автопроверки**
* Нет CI smoke, который гоняет `alembic upgrade head` на чистой БД + второй прогон (идемпотентность).

**Политика по enum**
* Нужен линтер/проверка “no `sa.Enum(name=...)` in Alembic” без `create_type=False` и без `ensure_pg_enum`.

**Cleanup**
* Orphan/smoke контейнеры (если есть) — в cleanup после проверок.

---

## 3.1.7 Local verification checklist

Команды (копипаст, 10–15 шагов):

```bash
docker compose up -d --build
docker compose ps

curl http://localhost:8001/api/core/health
curl http://localhost:8001/metrics
curl http://localhost/api/core/health
curl http://localhost/api/auth/health
curl http://localhost/api/ai/api/v1/health

docker compose logs -n 200 core-api
docker compose exec -T core-api sh -lc "alembic -c app/alembic.ini heads"
docker compose exec -T core-api sh -lc "alembic -c app/alembic.ini current"
docker compose exec -T postgres psql -U neft -d neft -c "select * from public.alembic_version;"
docker compose exec -T postgres psql -U neft -d neft -c "select 1;"

docker compose exec -T redis redis-cli ping
docker compose exec -T minio mc ls local
```

---

## 3.2 Карта сервисов

| name | path | type | port(s) | dependencies | entrypoint/command | status | что делает (по факту) | основные модули |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| postgres | docker-compose.yml | infra | 5432 | volume postgres-data | postgres:16 | ✅ | Основная БД. Используется core-api и auth-host. | — |
| redis | docker-compose.yml | infra | 6379 | — | redis-server --appendonly yes --databases 4 | ✅ | Брокер/результаты Celery. | — |
| minio | docker-compose.yml / infra/minio-init.sh | infra | 9000, 9001 | minio-init | minio server /data | ✅ | S3 совместимое хранилище (invoice pdf, payout exports). | infra/minio-init.sh |
| minio-init | infra/minio-init.sh | infra | — | minio | /infra/minio-init.sh | ✅ | Создаёт бакеты, включает versioning, ставит private policy. | infra/minio-init.sh |
| gateway | gateway/ | infra/api gateway | 80 | core-api, auth-host, ai-service, admin-web, client-web | nginx | ✅ | Роутинг /api/core, /api/auth, /api/ai, /admin, /client + /metrics. | gateway/nginx.conf |
| auth-host | platform/auth-host | api | 8002->8000 | postgres, redis | uvicorn app.main:app | 🟡 | Авторизация/админ-пользователи. Прямые SQL таблицы users/user_roles, bootstrap admin. | app/main.py, app/db.py, app/api/routes |
| core-api | platform/processing-core | api | 8001->8000 | postgres, redis, minio | uvicorn app.main:app | ✅ | Основная бизнес-логика: operations, billing, clearing, payout, risk, admin, client portal + /metrics. | app/main.py, app/services, app/routers, app/models |
| ai-service | platform/ai-services/risk-scorer | api | 8003->8000 | redis (по compose) | uvicorn app.main:app | 🟡 | Риск скоринг (stub), /v1/risk-score v2 + admin train/update + /metrics. | app/main.py, app/api/v1 |
| workers | platform/billing-clearing | worker | — | redis, core-api, minio | celery worker | 🟡 | Celery задачи: limits, billing summary, clearing batch, AI scoring proxy. | app/tasks, app/celery_app.py |
| beat | platform/billing-clearing | worker | — | redis, core-api, minio | celery beat | 🟡 | Запускает beat, но расписание в app/beat.py может не быть подхвачено. | app/beat.py, entrypoint.sh |
| flower | services/flower | infra | 5555 | redis, workers | celery flower | ✅ | UI для мониторинга Celery. | services/flower/Dockerfile |
| admin-web | frontends/admin-ui | frontend | 4173->80 | gateway | nginx static | 🟡 | Админ UI (Vite build). | frontends/admin-ui |
| client-web | frontends/client-portal | frontend | 4174->80 | gateway | nginx static | 🟡 | Клиентский портал (Vite build). | frontends/client-portal |
| otel-collector | infra/otel-collector-config.yaml | infra | 4317 | jaeger | otel collector | 🟡 | Принимает OTLP traces, экспортит в Jaeger. | infra/otel-collector-config.yaml |
| jaeger | docker-compose.yml | infra | 16686, 14250 | otel-collector | all-in-one | 🟡 | UI и backend для трассировок. | docker-compose.yml |
| prometheus | infra/prometheus.yml | infra | 9090 | gateway | prometheus | 🟡 | Скрейпит /metrics (core-api, ai-service, workers, gateway). | infra/prometheus.yml |
| grafana | infra/grafana | infra | 3000 | prometheus | grafana | 🟡 | Dashboard для метрик. | infra/grafana |
| crm-service | docker-compose.yml | placeholder | — | — | sleep infinity | ❌ | Заглушка. | docker-compose.yml |
| logistics-service | docker-compose.yml | placeholder | — | — | sleep infinity | ❌ | Заглушка. | docker-compose.yml |
| document-service | docker-compose.yml | placeholder | — | — | sleep infinity | ❌ | Заглушка. | docker-compose.yml |

---

## 3.3 Взаимодействия (кто с кем и как)

**HTTP**

* gateway → core-api: `/api/core/*`, `/api/v1/*` (legacy)
* gateway → auth-host: `/api/auth/*`
* gateway → ai-service: `/api/ai/*`
* core-api → ai-service: HTTP POST в `AI_SCORE_URL` (по умолчанию `/api/v1/score`, `app/services/risk_adapter.py`)
* core-api/clients → ai-service: `/api/v1/risk-score` (v2 endpoint, доступен в ai-service)
* admin → ai-service: `/admin/ai/train-model`, `/admin/ai/update-model` (train/update модели)
* workers → ai-service: HTTP POST `/api/v1/score` (`app/tasks/ai.py`)

**Очереди/фоновые задачи (Celery)**

* core-api → Redis → workers: `billing.generate_monthly_invoices`, `billing.generate_invoice_pdf`, `limits.check_and_reserve`, `limits.recalc_all`, `workers.ping`.
* beat (celery beat) — расписание объявлено в `platform/billing-clearing/app/beat.py` (periodic.ping, limits.apply_daily_limits), но `entrypoint` запускает celery_app напрямую.

**База данных (Postgres)**

* core-api использует схемы и таблицы из Alembic миграций (`platform/processing-core/app/alembic`).
* Decision engine пишет `decision_results` и audit_log (см. `app/services/decision/engine.py`).
* Settlement allocations связывают payments/credit notes/refunds с `settlement_period_id`.
* auth-host использует таблицы users/user_roles, создаваемые при старте (`platform/auth-host/app/db.py`).

**Хранилища (MinIO/S3)**

* core-api: Invoice PDF (`app/services/invoice_pdf.py`, `app/services/s3_storage.py`).
* core-api: payout exports (см. `app/services/payouts_service.py` и `payout_export_files`).

**Observability**

* Prometheus scrapes: gateway `/metrics`, core-api `/metrics`, ai-service `/metrics`, workers `/metrics`, auth-host `/api/v1/metrics` (не реализовано).
* OTel collector → Jaeger (traces). Инструментация сервисов в коде явно не указана.

**Mermaid диаграмма (факт взаимодействий)**

```mermaid
flowchart LR
  gateway[Nginx Gateway] --> core[core-api]
  gateway --> auth[auth-host]
  gateway --> ai[ai-service]
  gateway --> admin_ui[admin-web]
  gateway --> client_ui[client-web]

  core -->|HTTP| ai
  core -->|Celery tasks| redis
  workers -->|HTTP| ai

  core --> postgres
  auth --> postgres
  core --> minio

  redis --> workers
  redis --> beat

  prom[Prometheus] --> gateway
  prom --> core
  prom --> ai
  prom --> workers

  otel[otel-collector] --> jaeger
```

---

## 3.4 Домены и модули (реализованные)

### Auth / users / roles

* **Назначение:** учётные записи админ/клиентских пользователей с ролями.
* **Код:** `platform/auth-host/app`.
* **Сущности:** users, user_roles (таблицы создаются в `app/db.py`).
* **API:** `/api/v1/auth/*`, `/api/v1/admin/users/*` (см. section 3.8)
* **Фоновые процессы:** отсутствуют.
* **БД:** `users`, `user_roles` (Postgres, прямой SQL).
* **Статус:** 🟡 — базовая auth + bootstrap admin, нет полноценной миграционной стратегии.

### Accounts / balances / ledger

* **Назначение:** бухгалтерский учет и балансы.
* **Сущности:** `accounts`, `account_balances`, `ledger_entries`, `posting_batches`.
* **Код:** `platform/processing-core/app/models/account.py`, `ledger_entry.py`, `posting_batch.py`.
* **API:** `/v1/admin/accounts/*`, `/v1/admin/accounts/{client_id}/balances`.
* **Фоновые процессы:** posting engine (в core-api services). Celery задачи отдельно не описаны.
* **БД:** таблицы перечислены в секции 3.6.
* **Статус:** 🟡 — есть модели, posting engine и API, но домен зависит от операций и биллинга.

### Cards / card groups

* **Назначение:** карточки и группировка карточек/клиентов.
* **Сущности:** `cards`, `card_groups`, `card_group_members`, `client_groups`, `client_group_members`.
* **Код:** `app/models/card.py`, `app/models/groups.py`, `app/routers/admin/limits.py`.
* **API:** `/v1/admin/limits/*`, `/v1/admin/card-groups/*` и legacy `/v1/admin/groups_legacy.py`.
* **Фоновые процессы:** отсутствуют.
* **Статус:** 🟡 — CRUD и группирование, но есть дублирующиеся legacy endpoints.

### Billing (summary/periods)

* **Назначение:** агрегации по операциям и периоды биллинга.
* **Сущности:** `billing_summary`, `billing_periods`, `billing_job_runs`, `billing_task_links`.
* **Код:** `app/services/billing_*`, `app/services/billing/daily.py`, `app/models/billing_*`.
* **API:** `/v1/admin/billing/*`, `/api/v1/billing/*`.
* **Фоновые процессы:** Celery `billing.build_daily_summaries`, `clearing.finalize_billing`.
* **Статус:** ✅ — lifecycle finalize/lock защищён policy engine, billing hardening и инварианты реализованы.

### Invoices

* **Назначение:** инвойсы и их lifecycle.
* **Сущности:** `invoices`, `invoice_lines`, `invoice_transition_logs`.
* **Код:** `app/models/invoice.py`, `app/services/invoice_state_machine.py`, `app/services/billing_invoice_service.py`.
* **API:** `/api/v1/invoices/*`, `/v1/admin/billing/invoices/*`, `/v1/client/invoices/*`.
* **Фоновые процессы:** `billing.generate_invoice_pdf`, `billing.generate_monthly_invoices`.
* **Статус:** ✅ ядро lifecycle + PDF + финоперации есть, charges immutable после finalize/lock.

### Finance / payments / credit notes / refunds

* **Назначение:** учёт платежей, credit notes и возвратов по инвойсам.
* **Сущности:** `invoice_payments`, `credit_notes`, `refund_requests`.
* **Код:** `app/services/finance.py`, `app/models/finance.py`.
* **API:** `/api/v1/invoices/{id}/payments`, `/api/v1/invoices/{id}/refunds`, `/v1/admin/finance/*`.
* **Фоновые процессы:** нет (всё синхронно в core-api).
* **Статус:** ✅ — есть идемпотентность, state machine, settlement_allocation и аудит.

### Accounting export (accounting_export_batch)

* **Назначение:** выгрузки charges/settlement по периодам.
* **Сущности:** `accounting_export_batches` (accounting_export_batch).
* **Код:** `app/services/accounting_export_service.py`, `app/services/accounting_export/serializer.py`.
* **API:** `/v1/admin/accounting/exports/*`.
* **Фоновые процессы:** нет (синхронно, в core-api).
* **Статус:** ✅ — deterministic serializer, sha256, S3 upload/download, confirm + RBAC gating.

### Clearing / settlement / payouts

* **Назначение:** клиринг и выплаты партнёрам.
* **Сущности:** `clearing`, `clearing_batch`, `clearing_batch_operation`, `settlements`, `payout_batches`, `payout_orders`, `payout_items`, `payout_export_files`, `payout_events`.
* **Код:** `app/services/clearing_*`, `app/services/payouts_service.py`, `app/models/clearing.py`, `app/models/payout_*`.
* **API:** `/v1/admin/clearing/*`, `/api/v1/payouts/*`, `/v1/admin/settlements/*`.
* **Фоновые процессы:** Celery `clearing.build_daily_batch`.
* **Статус:** 🟡 — основные сущности и API реализованы, но часть инфраструктуры и интеграций отсутствует.

### Merchants / clients / documents

* **Назначение:** клиенты, мерчанты, терминалы, документы и клиентские действия.
* **Сущности:** `clients`, `merchants`, `terminals`, `documents`, `document_files`, closing_package, `client_actions`, `reconciliation_requests`.
* **Код:** `app/models/client.py`, `app/models/merchant.py`, `app/models/terminal.py`, `app/models/documents.py`, `app/models/client_actions.py`.
* **API:** `/api/v1/clients`, `/api/v1/merchants`, `/v1/admin/documents`, `/api/v1/client/*`.
* **Фоновые процессы:** отсутствуют.
* **Статус:** ✅ — legal finalization lifecycle, hash/document chain, immutable guards, policy checks для acknowledgement/finalize.

### Risk rules / limits

* **Назначение:** антифрод + лимиты по клиентам/картам.
* **Сущности:** `risk_rules`, `risk_rule_versions`, `risk_rule_audits`, `limit_rules`, `limit_configs`.
* **Код:** `app/services/risk_rules.py`, `app/services/limits.py`, `app/models/risk_rule.py`, `app/models/limits.py`.
* **API:** `/v1/admin/risk/*`, `/v1/admin/limits/*`, `/api/v1/limits`.
* **Фоновые процессы:** Celery `limits.check_and_reserve`, `limits.recalc_*`.
* **Статус:** 🟡 — правила и лимиты реализованы, ML/AI остаётся heuristic/stub.

### Decision engine / risk scoring

* **Назначение:** детерминированные решения по критичным операциям (fail-closed).
* **Сущности:** `decision_results` (audit), `risk_scores` (таблица под риск события; write-path пока не найден).
* **Код:** `app/services/decision/*`, `app/services/transactions_service.py`.
* **API:** decision engine встроен в core-api (вызовы при authorize, payout export, accounting export, billing finalize).
* **Версия:** `DECISION_ENGINE_VERSION = v1`.
* **AI сервис:** `/api/v1/score` (legacy), `/api/v1/risk-score` v2 + `/admin/ai/train-model`, `/admin/ai/update-model`.
* **Статус:** ✅ — decision engine пишет audit/decision_results; v2 endpoints есть (heuristic/stub).

---

## 3.5 Billing & Finance — подробный раздел

### Что реализовано

**Генерация инвойсов**

* Генерация по clearing batch: `generate_invoice_for_batch` (`app/services/billing_invoice_service.py`).
* Месячная генерация (monthly run): `run_invoice_monthly` (`app/services/invoicing/monthly.py`).
* Запуск из API:
  * `/api/v1/invoices/generate?batch_id=...` (billing_invoices endpoint)
  * `/v1/admin/billing/invoices/generate`
  * `/v1/admin/billing/invoices/run-monthly`

**Модель инвойса**

* Таблицы: `invoices`, `invoice_lines`, `invoice_transition_logs`.
* Ключевые поля: `client_id`, `period_from`, `period_to`, `currency`, `total_amount`, `tax_amount`, `total_with_tax`, `amount_paid`, `amount_due`, `status`, `pdf_status`.
* Инвойс связан с `billing_periods` и `clearing_batch`.

**Статусы и переходы (state machine)**

* `InvoiceStatus`: DRAFT → ISSUED → SENT → PARTIALLY_PAID → PAID.
* Дополнительно: CANCELLED, OVERDUE, CREDITED (terminal состояния).
* Реализовано в `app/services/invoice_state_machine.py`.
* Инварианты: суммы paid/credited/refunded должны держать баланс `total`; запрещены переходы при отсутствии PDF, при некорректных суммах.
* Логи переходов: `invoice_transition_logs` + аудит в `audit_log`.

**Частичная/полная оплата**

* `FinanceService.apply_payment` — создаёт запись `invoice_payments`, проверяет idempotency, статус invoice, сумму, запускает переход через state machine.
* Частичная оплата переводит в PARTIALLY_PAID, полная — в PAID (по сумме outstanding).

**Платежи / credit notes / возвраты**

* `invoice_payments` — запись платежей, idempotency по `idempotency_key`/external_ref.
* `credit_notes` — credit note по инвойсу (`FinanceService.create_credit_note`).
* `refund_requests` — отдельный домен возвратов по операциям, но для инвойсов есть `FinanceService.create_refund`.

**Периодизация**

* `billing_periods` — типы: DAILY/MONTHLY/ADHOC. 
* `billing_summary` — дневные/периодические агрегации.

**PDF и хранение**

* `InvoicePdfService` генерирует PDF (ReportLab) и сохраняет в MinIO/S3.
* Статусы PDF: NONE → QUEUED → GENERATING → READY / FAILED.
* Автогенерация при `NEFT_PDF_AUTO_GENERATE=1`.

### Cross-period settlement_allocation

* Таблица `invoice_settlement_allocations` хранит settlement_allocation привязку payments/credit notes/refunds к `settlement_period_id`.
* Правило: charges immutable после finalize/lock, settlement остаётся mutable (allocations создаются по дате события).
* Отчётность settlement: `GET /v1/admin/billing/settlement-summary` (summary по периодам/валюте).

### Accounting export (accounting_export_batch)

* Таблица `accounting_export_batches` фиксирует accounting_export_batch: type/format/state, idempotency_key, checksum_sha256.
* Типы: `CHARGES` / `SETTLEMENT`, форматы: `CSV` / `JSON`.
* Детерминированный сериализатор: canonical JSON/CSV + sha256.
* S3 storage: upload (bucket `NEFT_S3_BUCKET_ACCOUNTING_EXPORTS`) + download/confirm.
* Идемпотентность: повторный create/export возвращает существующий accounting_export_batch.

### RBAC / Policies

* Policy engine защищает финальные действия: finalize/lock, invoice issue/adjust, payment/credit, payout export, accounting export, document finalize.

### Endpoints (billing/finance)

> Ниже перечислены **реально существующие** endpoints. Префиксы зависят от router wiring:
> * `/api/v1/...`
> * `/api/core/api/v1/...`
> * `/api/v1/admin/...` (через `/api` + `/v1/admin`)
> * `/api/core/v1/admin/...`

**Billing + invoices**

* `POST /billing/close-period` — закрыть период (payload: `ClosePeriodRequest`).
* `POST /invoices/generate?batch_id=...` — сгенерировать инвойс по batch.
* `GET /invoices/{invoice_id}` — получить инвойс.
* `POST /invoices/{invoice_id}/payments` — создать оплату (payload: `InvoicePaymentRequest`).
* `POST /invoices/{invoice_id}/refunds` — создать возврат (payload: `InvoiceRefundRequest`).
* `GET /invoices/{invoice_id}/refunds` — список возвратов.
* `GET /invoices/{invoice_id}/pdf` — получить PDF ссылку/файл.

**Admin billing (пример)**

* `GET /periods` — список периодов.
* `POST /periods/lock` / `POST /periods/finalize` — управление периодами.
* `POST /seed`, `POST /run`, `POST /run-daily`, `POST /finalize-day` — запуск пайплайна биллинга.
* `GET /summary`, `GET /summary/{summary_id}`, `POST /summary/{summary_id}/finalize`.
* `GET /settlement-summary` — settlement_allocation summary.
* `GET /invoices`, `GET /invoices/{invoice_id}`, `POST /invoices/{invoice_id}/transition`, `POST /invoices/{invoice_id}/pdf`.
* `GET /jobs` — billing job runs.

**Finance endpoints**

* `POST /payments` — создать payment (admin).
* `POST /credit-notes` — создать credit note (admin).

**Accounting export endpoints**

* `POST /accounting/exports` — создать batch (admin).
* `POST /accounting/exports/{batch_id}/generate` — сгенерировать и загрузить.
* `GET /accounting/exports/{batch_id}/download` — скачать export.
* `POST /accounting/exports/{batch_id}/confirm` — подтвердить выгрузку.

### Таблицы БД для биллинга/финансов

* `billing_summary`, `billing_periods`, `billing_job_runs`, `billing_task_links`.
* `invoices`, `invoice_lines`, `invoice_transition_logs`.
* `invoice_payments`, `credit_notes`, `refund_requests`.
* `billing_reconciliation_runs`, `billing_reconciliation_items`.

### Ключевые миграции (billing/finance)

* `20260101_0008_billing_summary.py`, `20260110_0009_billing_summary_extend.py`, `20261101_0014_billing_summary_alignment.py`.
* `20270115_0020_invoices.py`, `0042_invoice_state_machine_v15.py`, `0041_invoice_lifecycle_hardening.py`.
* `20271120_0036_billing_job_runs_and_invoice_fields.py`, `20271205_0037_billing_pdf_and_tasks.py`.
* `20271220_0038_finance_invoice_extensions.py`.
* `20280401_0043_invoice_settlement_allocations.py`, `20280415_0044_accounting_export_batches.py`.

### Тесты по биллингу/финансам

* `platform/processing-core/app/tests/test_billing_*` (summary, periods, jobs, pipeline, invoice pdf, payments, refunds).
* `test_invoice_state_machine.py`, `test_admin_invoice_status_transitions.py`.
* `test_billing_pdf_task.py`, `test_billing_invoice_pdf_e2e.py`.

### Что не сделано (по факту)

* Уведомления (email/webhooks) о счетах/оплатах — не найдено.
* Внешние интеграции для документооборота (подписание/архив/CRM) отсутствуют, хотя lifecycle/immutability реализованы.
* Reconciliation с внешними системами — только внутренняя модель и API, без внешних интеграций.
* Провайдеры платежей/банковские интеграции — отсутствуют.

### Граница ответственности

* Billing/Finance отвечает за формирование инвойсов, статусы, платежи/credit notes/ refunds и их аудит.
* За внешние списания/банковские операции и юридические документы отвечает внешний контур (в репо не реализовано).

---

## 3.6 База данных (реальная схема)

### Схемы

* По умолчанию: `public` (`NEFT_DB_SCHEMA` в env может переопределить).
* Alembic использует `search_path` и включает `include_schemas=True`.

### 3.6.1 Alembic stability notes (2029-06)

* Были multiple heads → исправлено merge migration (`20290615_0048_merge_heads.py`).
* Добавлен documents bootstrap migration (`20290601_0046a_documents_bootstrap.py`).
* Исправлены несовместимые типы FK:
  * `invoice_settlement_allocations.settlement_period_id` (UUID vs varchar) → `20290620_0049_fix_settlement_period_id_type.py`.
  * `invoices.reconciliation_request_id` (uuid vs varchar) → `20290625_0050_fix_invoices_reconciliation_request_id_type.py`.
* Миграции остаются idempotent и schema-aware (create_table_if_not_exists, safe enum, guards для отсутствующих таблиц/колонок).
* Protected revisions (do not rewrite history): `20290615_0048_merge_heads`, `20290601_0046a_documents_bootstrap`, `20290601_0047_document_chain_reconciliation`, `20290620_0049_fix_settlement_period_id_type`, `20290625_0050_fix_invoices_reconciliation_request_id_type`.

### Новые таблицы/enum (recent)

**Таблицы:** `documents`, `document_files`, `document_acknowledgements`, `closing_packages`, `invoice_settlement_allocations`, `accounting_export_batches`, `risk_decisions`, `risk_policies`, `risk_threshold_sets`, `risk_thresholds`.

**Enum:** `document_status`, `closing_package_status`, `accounting_export_state`, `accounting_export_type`, `riskdecision`, `riskdecisionactor`, `risksubjecttype`.

### Список таблиц (core-api)

- `account_balances`
- `accounts`
- `accounting_export_batches`
- `audit_log`
- `billing_job_runs`
- `billing_periods`
- `billing_reconciliation_items`
- `billing_reconciliation_runs`
- `billing_summary`
- `billing_task_links`
- `card_group_members`
- `card_groups`
- `cards`
- `clearing`
- `clearing_batch`
- `clearing_batch_operation`
- `client_cards`
- `client_group_members`
- `client_groups`
- `client_limits`
- `client_operations`
- `client_tariffs`
- `clients`
- `closing_packages`
- `commission_rules`
- `credit_notes`
- `decision_results`
- `dispute_events`
- `disputes`
- `document_acknowledgements`
- `document_files`
- `documents`
- `external_request_logs`
- `financial_adjustments`
- `invoice_lines`
- `invoice_messages`
- `invoice_payments`
- `invoice_threads`
- `invoice_transition_logs`
- `invoices`
- `invoice_settlement_allocations`
- `ledger_entries`
- `limit_configs`
- `limits_rules`
- `merchants`
- `operations`
- `partners`
- `payout_batches`
- `payout_events`
- `payout_export_files`
- `payout_items`
- `payout_orders`
- `posting_batches`
- `reconciliation_requests`
- `refund_requests`
- `reversals`
- `risk_decisions`
- `risk_policies`
- `risk_rule_audits`
- `risk_rule_versions`
- `risk_rules`
- `risk_scores`
- `risk_threshold_sets`
- `risk_thresholds`
- `settlements`
- `tariff_plans`
- `tariff_prices`
- `terminals`


### Enum типы (core-api)

- `audit_actor_type`: USER, SERVICE, SYSTEM
- `audit_visibility`: PUBLIC, INTERNAL
- `billing_job_status`: STARTED, SUCCESS, FAILED
- `billing_job_type`: BILLING_DAILY, BILLING_FINALIZE, INVOICE_MONTHLY, RECONCILIATION, MANUAL_RUN, PDF_GENERATE, INVOICE_SEND, CREDIT_NOTE_PDF, FINANCE_EXPORT, BALANCE_REBUILD, CLEARING
- `billing_period_status`: OPEN, FINALIZED, LOCKED
- `billing_period_type`: DAILY, MONTHLY, ADHOC
- `billing_task_status`: QUEUED, RUNNING, SUCCESS, FAILED
- `billing_task_type`: MONTHLY_RUN, PDF_GENERATE, INVOICE_SEND
- `closing_package_status`: DRAFT, ISSUED, ACKNOWLEDGED, FINALIZED, VOID
- `accounting_export_format`: CSV, JSON
- `accounting_export_state`: CREATED, GENERATED, UPLOADED, DOWNLOADED, CONFIRMED, FAILED
- `accounting_export_type`: CHARGES, SETTLEMENT
- `credit_note_status`: POSTED, FAILED, REVERSED
- `document_file_type`: PDF, XLSX
- `document_status`: DRAFT, ISSUED, ACKNOWLEDGED, FINALIZED, VOID
- `document_type`: INVOICE, ACT, RECONCILIATION_ACT, CLOSING_PACKAGE
- `invoice_message_sender_type`: CLIENT, SUPPORT, SYSTEM
- `invoice_payment_status`: POSTED, FAILED
- `invoice_pdf_status`: NONE, QUEUED, GENERATING, READY, FAILED
- `invoice_thread_status`: OPEN, WAITING_SUPPORT, WAITING_CLIENT, RESOLVED, CLOSED
- `invoicestatus`: DRAFT, ISSUED, SENT, PARTIALLY_PAID, PAID, OVERDUE, CANCELLED, CREDITED
- `reconciliation_request_status`: REQUESTED, IN_PROGRESS, GENERATED, SENT, ACKNOWLEDGED, REJECTED, CANCELLED
- `riskdecision`: ALLOW, ALLOW_WITH_REVIEW, BLOCK, ESCALATE
- `riskdecisionactor`: SYSTEM, ADMIN
- `risk_level`: LOW, MEDIUM, HIGH, VERY_HIGH
- `risk_score_action`: PAYMENT, INVOICE, PAYOUT
- `risksubjecttype`: PAYMENT, INVOICE, PAYOUT, DOCUMENT, EXPORT
- `settlement_source_type`: PAYMENT, CREDIT_NOTE, REFUND


### Детализация по таблицам (core-api)

### `account_balances`
**Назначение:** Current and available balances for an account.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| account_id | BIGINT | False | True |  |  | accounts.id |  |
| current_balance | NUMERIC(18, 4) | False | False | 0 |  |  |  |
| available_balance | NUMERIC(18, 4) | False | False | 0 |  |  |  |
| hold_balance | NUMERIC(18, 4) | False | False | 0 |  |  |  |
| updated_at | DATETIME | False | False |  | now() |  |  |

**Foreign Keys**
| Columns | References |
| --- | --- |
| account_id | accounts.id |

### `accounts`
**Назначение:** Customer or technical account used for posting ledger entries.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | BIGINT | False | True |  |  |  |  |
| client_id | VARCHAR(64) | False | False |  |  |  |  |
| owner_type | VARCHAR(8) | False | False | AccountOwnerType.CLIENT |  |  |  |
| owner_id | VARCHAR(36) | True | False |  |  |  |  |
| card_id | VARCHAR(64) | True | False |  |  | cards.id |  |
| tariff_id | VARCHAR(64) | True | False |  |  |  |  |
| currency | VARCHAR(8) | False | False |  |  |  |  |
| type | VARCHAR(13) | False | False |  |  |  |  |
| status | VARCHAR(6) | False | False | AccountStatus.ACTIVE |  |  |  |
| created_at | DATETIME | False | False |  | now() |  |  |
| updated_at | DATETIME | False | False |  | now() |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_accounts_card_id | card_id | False |
| ix_accounts_client_id | client_id | False |
| ix_accounts_owner_id | owner_id | False |
| ix_accounts_owner_type | owner_type | False |
| ix_accounts_status | status | False |
| ix_accounts_type | type | False |

**Foreign Keys**
| Columns | References |
| --- | --- |
| card_id | cards.id |

### `audit_log`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | VARCHAR(36) | False | True | <function new_uuid_str at 0x7f15518a7b00> |  |  |  |
| ts | DATETIME | False | False | <function AuditLog.<lambda> at 0x7f15518a7c40> |  |  |  |
| tenant_id | INTEGER | True | False |  |  |  |  |
| actor_type | VARCHAR(7) | False | False |  |  |  | audit_actor_type |
| actor_id | TEXT | True | False |  |  |  |  |
| actor_email | TEXT | True | False |  |  |  |  |
| actor_roles | ARRAY | True | False |  |  |  |  |
| ip | INET | True | False |  |  |  |  |
| user_agent | TEXT | True | False |  |  |  |  |
| request_id | TEXT | True | False |  |  |  |  |
| trace_id | TEXT | True | False |  |  |  |  |
| event_type | TEXT | False | False |  |  |  |  |
| entity_type | TEXT | False | False |  |  |  |  |
| entity_id | TEXT | False | False |  |  |  |  |
| action | TEXT | False | False |  |  |  |  |
| visibility | VARCHAR(8) | False | False |  | INTERNAL |  | audit_visibility |
| before | JSON | True | False |  |  |  |  |
| after | JSON | True | False |  |  |  |  |
| diff | JSON | True | False |  |  |  |  |
| external_refs | JSON | True | False |  |  |  |  |
| reason | TEXT | True | False |  |  |  |  |
| attachment_key | TEXT | True | False |  |  |  |  |
| prev_hash | TEXT | False | False |  |  |  |  |
| hash | TEXT | False | False |  |  |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_audit_log_entity | entity_type, entity_id | False |
| ix_audit_log_entity_id | entity_id | False |
| ix_audit_log_entity_type | entity_type | False |
| ix_audit_log_event_ts | event_type, ts | False |
| ix_audit_log_event_type | event_type | False |
| ix_audit_log_external_refs_gin | external_refs | False |
| ix_audit_log_tenant_id | tenant_id | False |
| ix_audit_log_ts | ts | False |
| ix_audit_log_ts_desc | ts | False |
| ix_audit_log_visibility | visibility | False |

**Уникальные ограничения**
| Name | Columns |
| --- | --- |
|  | hash |

### `billing_job_runs`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | VARCHAR(36) | False | True | <function BillingJobRun.<lambda> at 0x7f1551c5c040> |  |  |  |
| job_type | VARCHAR(16) | False | False |  |  |  | billing_job_type |
| params | JSON | True | False |  |  |  |  |
| status | VARCHAR(7) | False | False |  |  |  | billing_job_status |
| started_at | DATETIME | False | False |  | now() |  |  |
| finished_at | DATETIME | True | False |  |  |  |  |
| error | TEXT | True | False |  |  |  |  |
| metrics | JSON | True | False |  |  |  |  |
| duration_ms | INTEGER | True | False |  |  |  |  |
| celery_task_id | VARCHAR(128) | True | False |  |  |  |  |
| correlation_id | VARCHAR(128) | True | False |  |  |  |  |
| invoice_id | VARCHAR(36) | True | False |  |  |  |  |
| billing_period_id | VARCHAR(36) | True | False |  |  |  |  |
| updated_at | DATETIME | True | False |  | now() |  |  |
| attempts | INTEGER | True | False | 0 |  |  |  |
| last_heartbeat_at | DATETIME | True | False |  |  |  |  |
| result_ref | JSON | True | False |  |  |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_billing_job_runs_billing_period_id | billing_period_id | False |
| ix_billing_job_runs_celery_task_id | celery_task_id | False |
| ix_billing_job_runs_correlation_id | correlation_id | False |
| ix_billing_job_runs_invoice_id | invoice_id | False |

### `billing_periods`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | VARCHAR(36) | False | True | <function new_uuid_str at 0x7f1551c36ca0> |  |  |  |
| period_type | VARCHAR(7) | False | False |  |  |  | billing_period_type |
| start_at | DATETIME | False | False |  |  |  |  |
| end_at | DATETIME | False | False |  |  |  |  |
| tz | VARCHAR(64) | False | False |  |  |  |  |
| status | VARCHAR(9) | False | False | BillingPeriodStatus.OPEN | 'OPEN' |  | billing_period_status |
| finalized_at | DATETIME | True | False |  |  |  |  |
| locked_at | DATETIME | True | False |  |  |  |  |
| created_at | DATETIME | False | False |  | now() |  |  |
| updated_at | DATETIME | False | False |  | now() |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_billing_periods_start_at | start_at | False |
| ix_billing_periods_status | status | False |
| ix_billing_periods_type_start | period_type, start_at | False |

**Уникальные ограничения**
| Name | Columns |
| --- | --- |
| uq_billing_period_scope | period_type, start_at, end_at |

### `billing_reconciliation_items`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | VARCHAR(36) | False | True | <function BillingReconciliationItem.<lambda> at 0x7f1551985940> |  |  |  |
| run_id | VARCHAR(36) | False | False |  |  | billing_reconciliation_runs.id |  |
| invoice_id | VARCHAR(36) | False | False |  |  |  |  |
| client_id | VARCHAR(64) | False | False |  |  |  |  |
| currency | VARCHAR(3) | False | False |  |  |  |  |
| verdict | VARCHAR(14) | False | False | BillingReconciliationVerdict.OK |  |  |  |
| diff_json | JSON | True | False |  |  |  |  |
| created_at | DATETIME | False | False |  | now() |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_billing_reconciliation_items_run_id | run_id | False |

**Foreign Keys**
| Columns | References |
| --- | --- |
| run_id | billing_reconciliation_runs.id |

### `billing_reconciliation_runs`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | VARCHAR(36) | False | True | <function BillingReconciliationRun.<lambda> at 0x7f1551984220> |  |  |  |
| billing_period_id | VARCHAR(36) | False | False |  |  | billing_periods.id |  |
| status | VARCHAR(7) | False | False | BillingReconciliationStatus.OK |  |  |  |
| started_at | DATETIME | False | False |  | now() |  |  |
| finished_at | DATETIME | True | False |  |  |  |  |
| total_invoices | INTEGER | False | False | 0 |  |  |  |
| ok_count | INTEGER | False | False | 0 |  |  |  |
| mismatch_count | INTEGER | False | False | 0 |  |  |  |
| missing_ledger_count | INTEGER | False | False | 0 |  |  |  |
| created_at | DATETIME | False | False |  | now() |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_billing_reconciliation_runs_billing_period_id | billing_period_id | False |

**Foreign Keys**
| Columns | References |
| --- | --- |
| billing_period_id | billing_periods.id |

### `billing_summary`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | VARCHAR(36) | False | True | <function BillingSummary.<lambda> at 0x7f1551c16980> |  |  |  |
| billing_date | DATE | False | False |  |  |  |  |
| client_id | VARCHAR(64) | True | False |  |  |  |  |
| merchant_id | VARCHAR(64) | False | False |  |  |  |  |
| product_type | VARCHAR(6) | True | False |  |  |  |  |
| currency | VARCHAR(3) | True | False |  |  |  |  |
| total_amount | BIGINT | False | False | 0 |  |  |  |
| total_quantity | NUMERIC(18, 3) | True | False |  |  |  |  |
| operations_count | INTEGER | False | False | 0 |  |  |  |
| commission_amount | BIGINT | False | False | 0 |  |  |  |
| status | VARCHAR(9) | False | False | BillingSummaryStatus.PENDING | PENDING |  |  |
| generated_at | DATETIME | True | False |  | now() |  |  |
| finalized_at | DATETIME | True | False |  |  |  |  |
| hash | VARCHAR(128) | True | False |  |  |  |  |
| created_at | DATETIME | False | False |  | now() |  |  |
| updated_at | DATETIME | False | False |  | now() |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_billing_summary_billing_date | billing_date | False |
| ix_billing_summary_client_id | client_id | False |
| ix_billing_summary_currency | currency | False |
| ix_billing_summary_merchant_id | merchant_id | False |
| ix_billing_summary_product_type | product_type | False |
| ix_billing_summary_status | status | False |
| ix_billing_summary_status_billing_date | status, billing_date | False |

**Уникальные ограничения**
| Name | Columns |
| --- | --- |
| uq_billing_summary_unique_scope | billing_date, merchant_id, client_id, product_type, currency |

### `billing_task_links`
**Назначение:** Tracks Celery tasks associated with invoices for idempotency and audit.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | VARCHAR(36) | False | True | <function BillingTaskLink.<lambda> at 0x7f1551c5d940> |  |  |  |
| task_id | VARCHAR(128) | False | False |  |  |  |  |
| task_name | VARCHAR(128) | False | False |  |  |  |  |
| job_run_id | VARCHAR(36) | False | False |  |  | billing_job_runs.id |  |
| invoice_id | VARCHAR(36) | True | False |  |  |  |  |
| billing_period_id | VARCHAR(36) | True | False |  |  |  |  |
| task_type | VARCHAR(12) | False | False |  |  |  | billing_task_type |
| status | VARCHAR(7) | False | False |  |  |  | billing_task_status |
| created_at | DATETIME | False | False |  | now() |  |  |
| updated_at | DATETIME | False | False |  | now() |  |  |
| error | TEXT | True | False |  |  |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_billing_task_links_billing_period_id | billing_period_id | False |
| ix_billing_task_links_invoice_id | invoice_id | False |
| ix_billing_task_links_job_run_id | job_run_id | False |
| ix_billing_task_links_task_id | task_id | True |

**Foreign Keys**
| Columns | References |
| --- | --- |
| job_run_id | billing_job_runs.id |

### `card_group_members`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | INTEGER | False | True |  |  |  |  |
| card_group_id | INTEGER | False | False |  |  | card_groups.id |  |
| card_id | VARCHAR(64) | False | False |  |  |  |  |
| created_at | DATETIME | False | False |  | now() |  |  |

**Уникальные ограничения**
| Name | Columns |
| --- | --- |
| uq_card_group_member | card_group_id, card_id |

**Foreign Keys**
| Columns | References |
| --- | --- |
| card_group_id | card_groups.id |

### `card_groups`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | INTEGER | False | True |  |  |  |  |
| group_id | VARCHAR(64) | False | False |  |  |  |  |
| name | VARCHAR(128) | False | False |  |  |  |  |
| description | TEXT | True | False |  |  |  |  |
| created_at | DATETIME | False | False |  | now() |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_card_groups_group_id | group_id | True |

### `cards`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | VARCHAR(64) | False | True |  |  |  |  |
| client_id | VARCHAR(64) | False | False |  |  |  |  |
| status | VARCHAR(32) | False | False |  |  |  |  |
| pan_masked | VARCHAR(32) | True | False |  |  |  |  |
| expires_at | VARCHAR(16) | True | False |  |  |  |  |
| created_at | DATETIME | False | False |  | now() |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_cards_client_id | client_id | False |
| ix_cards_id | id | False |
| ix_cards_status | status | False |

### `clearing`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | VARCHAR(36) | False | True | <function Clearing.<lambda> at 0x7f1551c5f060> |  |  |  |
| batch_date | DATE | False | False |  |  |  |  |
| merchant_id | VARCHAR(64) | False | False |  |  |  |  |
| currency | VARCHAR(3) | False | False |  |  |  |  |
| total_amount | BIGINT | False | False |  |  |  |  |
| status | VARCHAR(7) | False | False |  | PENDING |  |  |
| details | JSON | True | False |  |  |  |  |
| created_at | DATETIME | False | False |  | now() |  |  |
| updated_at | DATETIME | False | False |  | now() |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_clearing_batch_date | batch_date | False |
| ix_clearing_currency | currency | False |
| ix_clearing_merchant_id | merchant_id | False |
| ix_clearing_status | status | False |

**Уникальные ограничения**
| Name | Columns |
| --- | --- |
| uq_clearing_date_merchant_currency | batch_date, merchant_id, currency |

### `clearing_batch`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | VARCHAR(36) | False | True | <function ClearingBatch.<lambda> at 0x7f1551acca40> |  |  |  |
| merchant_id | VARCHAR(64) | False | False |  |  |  |  |
| tenant_id | INTEGER | True | False |  |  |  |  |
| date_from | DATE | False | False |  |  |  |  |
| date_to | DATE | False | False |  |  |  |  |
| total_amount | INTEGER | False | False |  |  |  |  |
| total_qty | NUMERIC(18, 3) | True | False |  |  |  |  |
| operations_count | INTEGER | False | False | 0 |  |  |  |
| state | VARCHAR(6) | False | False |  | OPEN |  |  |
| status | VARCHAR(9) | False | False |  | PENDING |  |  |
| created_at | DATETIME | False | False |  | now() |  |  |
| closed_at | DATETIME | True | False |  |  |  |  |
| updated_at | DATETIME | False | False |  | now() |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_clearing_batch_date_from | date_from | False |
| ix_clearing_batch_date_to | date_to | False |
| ix_clearing_batch_merchant_id | merchant_id | False |
| ix_clearing_batch_state | state | False |
| ix_clearing_batch_status | status | False |
| ix_clearing_batch_tenant_id | tenant_id | False |

**Уникальные ограничения**
| Name | Columns |
| --- | --- |
| uq_clearing_batch_tenant_period | tenant_id, date_from, date_to |

### `clearing_batch_operation`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | VARCHAR(36) | False | True | <function ClearingBatchOperation.<lambda> at 0x7f1551ace7a0> |  |  |  |
| batch_id | VARCHAR(36) | False | False |  |  | clearing_batch.id |  |
| operation_id | VARCHAR(64) | False | False |  |  | operations.operation_id |  |
| amount | INTEGER | False | False |  |  |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_clearing_batch_operation_batch_id | batch_id | False |

**Foreign Keys**
| Columns | References |
| --- | --- |
| operation_id | operations.operation_id |
| batch_id | clearing_batch.id |

### `client_cards`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | BIGINT | False | True |  |  |  |  |
| client_id | UUID | False | False |  |  | clients.id |  |
| card_id | VARCHAR | False | False |  |  |  |  |
| pan_masked | VARCHAR | True | False |  |  |  |  |
| status | VARCHAR | False | False |  | ACTIVE |  |  |
| created_at | DATETIME | False | False |  | now() |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_client_cards_card_id | card_id | False |
| ix_client_cards_client_id | client_id | False |

**Foreign Keys**
| Columns | References |
| --- | --- |
| client_id | clients.id |

### `client_group_members`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | INTEGER | False | True |  |  |  |  |
| client_group_id | INTEGER | False | False |  |  | client_groups.id |  |
| client_id | VARCHAR(64) | False | False |  |  |  |  |
| created_at | DATETIME | False | False |  | now() |  |  |

**Уникальные ограничения**
| Name | Columns |
| --- | --- |
| uq_client_group_member | client_group_id, client_id |

**Foreign Keys**
| Columns | References |
| --- | --- |
| client_group_id | client_groups.id |

### `client_groups`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | INTEGER | False | True |  |  |  |  |
| group_id | VARCHAR(64) | False | False |  |  |  |  |
| name | VARCHAR(128) | False | False |  |  |  |  |
| description | TEXT | True | False |  |  |  |  |
| created_at | DATETIME | False | False |  | now() |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_client_groups_group_id | group_id | True |

### `client_limits`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | BIGINT | False | True |  |  |  |  |
| client_id | UUID | False | False |  |  | clients.id |  |
| limit_type | VARCHAR | False | False |  |  |  |  |
| amount | NUMERIC | False | False |  |  |  |  |
| currency | VARCHAR(3) | False | False |  | RUB |  |  |
| used_amount | NUMERIC | True | False |  | 0 |  |  |
| period_start | DATETIME | True | False |  |  |  |  |
| period_end | DATETIME | True | False |  |  |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_client_limits_client_id | client_id | False |

**Foreign Keys**
| Columns | References |
| --- | --- |
| client_id | clients.id |

### `client_operations`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | BIGINT | False | True |  |  |  |  |
| client_id | UUID | False | False |  |  | clients.id |  |
| card_id | VARCHAR | True | False |  |  |  |  |
| operation_type | VARCHAR | False | False |  |  |  |  |
| status | VARCHAR | False | False |  |  |  |  |
| amount | INTEGER | False | False |  |  |  |  |
| currency | VARCHAR(3) | False | False |  | RUB |  |  |
| performed_at | DATETIME | False | False |  | now() |  |  |
| fuel_type | VARCHAR | True | False |  |  |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_client_operations_card_id | card_id | False |
| ix_client_operations_client_id | client_id | False |
| ix_client_operations_operation_type | operation_type | False |
| ix_client_operations_status | status | False |

**Foreign Keys**
| Columns | References |
| --- | --- |
| client_id | clients.id |

### `client_tariffs`
**Назначение:** Assignment of tariff plans to clients with optional validity windows.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | INTEGER | False | True |  |  |  |  |
| client_id | VARCHAR(64) | False | False |  |  |  |  |
| tariff_id | VARCHAR(64) | False | False |  |  | tariff_plans.id |  |
| valid_from | DATETIME | True | False |  |  |  |  |
| valid_to | DATETIME | True | False |  |  |  |  |
| priority | INTEGER | False | False | 100 |  |  |  |
| created_at | DATETIME | False | False |  | now() |  |  |
| updated_at | DATETIME | False | False |  | now() |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_client_tariffs_client_id | client_id | False |
| ix_client_tariffs_priority | priority | False |
| ix_client_tariffs_tariff_id | tariff_id | False |
| ix_client_tariffs_valid_from | valid_from | False |
| ix_client_tariffs_valid_to | valid_to | False |

**Foreign Keys**
| Columns | References |
| --- | --- |
| tariff_id | tariff_plans.id |

### `clients`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | UUID | False | True | <function uuid4 at 0x7f1551d5d1c0> |  |  |  |
| name | VARCHAR | False | False |  |  |  |  |
| external_id | VARCHAR | True | False |  |  |  |  |
| inn | VARCHAR | True | False |  |  |  |  |
| email | VARCHAR | True | False |  |  |  |  |
| full_name | VARCHAR | True | False |  |  |  |  |
| tariff_plan | VARCHAR | True | False |  |  |  |  |
| account_manager | VARCHAR | True | False |  |  |  |  |
| status | VARCHAR | False | False |  | ACTIVE |  |  |
| created_at | DATETIME | False | False |  | now() |  |  |

**Уникальные ограничения**
| Name | Columns |
| --- | --- |
|  | external_id |
|  | email |

### `closing_packages`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | VARCHAR(36) | False | True | <function ClosingPackage.<lambda> at 0x7f15517c5da0> |  |  |  |
| tenant_id | INTEGER | False | False |  |  |  |  |
| client_id | VARCHAR(64) | False | False |  |  |  |  |
| period_from | DATE | False | False |  |  |  |  |
| period_to | DATE | False | False |  |  |  |  |
| status | VARCHAR(12) | False | False | ClosingPackageStatus.DRAFT |  |  | closing_package_status |
| version | INTEGER | False | False | 1 |  |  |  |
| invoice_document_id | VARCHAR(36) | True | False |  |  | documents.id |  |
| act_document_id | VARCHAR(36) | True | False |  |  | documents.id |  |
| recon_document_id | VARCHAR(36) | True | False |  |  | documents.id |  |
| created_at | DATETIME | False | False |  | now() |  |  |
| generated_at | DATETIME | True | False |  |  |  |  |
| sent_at | DATETIME | True | False |  |  |  |  |
| ack_at | DATETIME | True | False |  |  |  |  |
| meta | JSON | True | False |  |  |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_closing_packages_client_id | client_id | False |
| ix_closing_packages_period_from | period_from | False |
| ix_closing_packages_period_to | period_to | False |
| ix_closing_packages_status | status | False |
| ix_closing_packages_tenant_id | tenant_id | False |

**Уникальные ограничения**
| Name | Columns |
| --- | --- |
| uq_closing_packages_scope | tenant_id, client_id, period_from, period_to, version |

**Foreign Keys**
| Columns | References |
| --- | --- |
| act_document_id | documents.id |
| invoice_document_id | documents.id |
| recon_document_id | documents.id |

### `commission_rules`
**Назначение:** Commission overrides per tariff/partner/product.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | INTEGER | False | True |  |  |  |  |
| tariff_id | VARCHAR(64) | False | False |  |  | tariff_plans.id |  |
| product_id | VARCHAR(64) | True | False |  |  |  |  |
| partner_id | VARCHAR(64) | True | False |  |  |  |  |
| azs_id | VARCHAR(64) | True | False |  |  |  |  |
| platform_rate | NUMERIC(6, 4) | False | False |  |  |  |  |
| partner_rate | NUMERIC(6, 4) | True | False |  |  |  |  |
| promo_rate | NUMERIC(6, 4) | True | False |  |  |  |  |
| valid_from | DATETIME | True | False |  |  |  |  |
| valid_to | DATETIME | True | False |  |  |  |  |
| priority | INTEGER | False | False | 100 |  |  |  |
| created_at | DATETIME | False | False |  | now() |  |  |
| updated_at | DATETIME | False | False |  | now() |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_commission_rules_azs_id | azs_id | False |
| ix_commission_rules_partner_id | partner_id | False |
| ix_commission_rules_priority | priority | False |
| ix_commission_rules_product_id | product_id | False |
| ix_commission_rules_tariff_id | tariff_id | False |
| ix_commission_rules_valid_from | valid_from | False |
| ix_commission_rules_valid_to | valid_to | False |

**Foreign Keys**
| Columns | References |
| --- | --- |
| tariff_id | tariff_plans.id |

### `credit_notes`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | VARCHAR(36) | False | True |  |  |  |  |
| invoice_id | VARCHAR(36) | False | False |  |  | invoices.id |  |
| amount | BIGINT | False | False |  |  |  |  |
| currency | VARCHAR(3) | False | False |  |  |  |  |
| provider | VARCHAR(64) | True | False |  |  |  |  |
| external_ref | VARCHAR(128) | True | False |  |  |  |  |
| reason | VARCHAR(255) | True | False |  |  |  |  |
| idempotency_key | VARCHAR(128) | False | False |  |  |  |  |
| status | VARCHAR(8) | False | False | CreditNoteStatus.POSTED |  |  | credit_note_status |
| created_at | DATETIME | False | False |  | now() |  |  |
| updated_at | DATETIME | False | False |  | now() |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_credit_notes_external_ref | external_ref | False |
| ix_credit_notes_idempotency_key | idempotency_key | True |
| ix_credit_notes_invoice_id | invoice_id | False |

**Foreign Keys**
| Columns | References |
| --- | --- |
| invoice_id | invoices.id |

### `dispute_events`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | BIGINT | False | True |  |  |  |  |
| dispute_id | UUID | False | False |  |  | disputes.id |  |
| event_type | VARCHAR(15) | False | False |  |  |  |  |
| payload | JSON | True | False |  |  |  |  |
| actor | VARCHAR(128) | True | False |  |  |  |  |
| created_at | DATETIME | False | False |  | now() |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_dispute_events_created_at | created_at | False |
| ix_dispute_events_dispute_id | dispute_id | False |

**Foreign Keys**
| Columns | References |
| --- | --- |
| dispute_id | disputes.id |

### `disputes`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | UUID | False | True | <function uuid4 at 0x7f15518f9f80> |  |  |  |
| operation_id | UUID | False | False |  |  | operations.id |  |
| operation_business_id | VARCHAR(64) | False | False |  |  |  |  |
| disputed_amount | BIGINT | False | False |  |  |  |  |
| currency | VARCHAR(3) | False | False |  |  |  |  |
| fee_amount | BIGINT | False | False | 0 |  |  |  |
| status | VARCHAR(12) | False | False | DisputeStatus.OPEN |  |  |  |
| hold_placed | BOOLEAN | False | False | False |  |  |  |
| hold_posting_id | UUID | True | False |  |  |  |  |
| resolution_posting_id | UUID | True | False |  |  |  |  |
| initiator | VARCHAR(128) | True | False |  |  |  |  |
| created_at | DATETIME | False | False |  | now() |  |  |
| updated_at | DATETIME | False | False |  | now() |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_disputes_operation_business_id | operation_business_id | False |
| ix_disputes_operation_id | operation_id | False |
| ix_disputes_status | status | False |

**Foreign Keys**
| Columns | References |
| --- | --- |
| operation_id | operations.id |

### `document_acknowledgements`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | VARCHAR(36) | False | True | <function new_uuid_str at 0x7f1551916840> |  |  |  |
| tenant_id | INTEGER | False | False |  |  |  |  |
| client_id | VARCHAR(64) | False | False |  |  |  |  |
| document_type | VARCHAR(64) | False | False |  |  |  |  |
| document_id | VARCHAR(64) | False | False |  |  |  |  |
| document_object_key | TEXT | True | False |  |  |  |  |
| document_hash | VARCHAR(64) | True | False |  |  |  |  |
| ack_by_user_id | TEXT | True | False |  |  |  |  |
| ack_by_email | TEXT | True | False |  |  |  |  |
| ack_ip | TEXT | True | False |  |  |  |  |
| ack_user_agent | TEXT | True | False |  |  |  |  |
| ack_at | DATETIME | False | False |  | now() |  |  |
| ack_method | VARCHAR(32) | True | False |  |  |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_document_acknowledgements_ack_at | ack_at | False |
| ix_document_acknowledgements_client_id | client_id | False |
| ix_document_acknowledgements_tenant_id | tenant_id | False |

**Уникальные ограничения**
| Name | Columns |
| --- | --- |
| uq_document_acknowledgements_scope | client_id, document_type, document_id |

### `document_files`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | VARCHAR(36) | False | True | <function DocumentFile.<lambda> at 0x7f15517c4ae0> |  |  |  |
| document_id | VARCHAR(36) | False | False |  |  | documents.id |  |
| file_type | VARCHAR(4) | False | False |  |  |  | document_file_type |
| bucket | TEXT | False | False |  |  |  |  |
| object_key | TEXT | False | False |  |  |  |  |
| sha256 | VARCHAR(64) | False | False |  |  |  |  |
| size_bytes | BIGINT | False | False |  |  |  |  |
| content_type | TEXT | False | False |  |  |  |  |
| created_at | DATETIME | False | False |  | now() |  |  |
| meta | JSON | True | False |  |  |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_document_files_document_id | document_id | False |

**Уникальные ограничения**
| Name | Columns |
| --- | --- |
| uq_document_files_type | document_id, file_type |

**Foreign Keys**
| Columns | References |
| --- | --- |
| document_id | documents.id |

### `documents`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | VARCHAR(36) | False | True | <function Document.<lambda> at 0x7f1551986f20> |  |  |  |
| tenant_id | INTEGER | False | False |  |  |  |  |
| client_id | VARCHAR(64) | False | False |  |  |  |  |
| document_type | VARCHAR(18) | False | False |  |  |  | document_type |
| period_from | DATE | False | False |  |  |  |  |
| period_to | DATE | False | False |  |  |  |  |
| status | VARCHAR(12) | False | False | DocumentStatus.DRAFT |  |  | document_status |
| version | INTEGER | False | False | 1 |  |  |  |
| number | TEXT | True | False |  |  |  |  |
| source_entity_type | TEXT | True | False |  |  |  |  |
| source_entity_id | TEXT | True | False |  |  |  |  |
| created_at | DATETIME | False | False |  | now() |  |  |
| updated_at | DATETIME | False | False |  | now() |  |  |
| generated_at | DATETIME | True | False |  |  |  |  |
| sent_at | DATETIME | True | False |  |  |  |  |
| ack_at | DATETIME | True | False |  |  |  |  |
| cancelled_at | DATETIME | True | False |  |  |  |  |
| created_by_actor_type | VARCHAR(32) | True | False |  |  |  |  |
| created_by_actor_id | TEXT | True | False |  |  |  |  |
| created_by_email | TEXT | True | False |  |  |  |  |
| meta | JSON | True | False |  |  |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_documents_client_id | client_id | False |
| ix_documents_document_type | document_type | False |
| ix_documents_period_from | period_from | False |
| ix_documents_period_to | period_to | False |
| ix_documents_status | status | False |
| ix_documents_tenant_id | tenant_id | False |

**Уникальные ограничения**
| Name | Columns |
| --- | --- |
| uq_documents_scope | tenant_id, client_id, document_type, period_from, period_to, version |

### `external_request_logs`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | INTEGER | False | True |  |  |  |  |
| partner_id | VARCHAR(64) | False | False |  |  |  |  |
| azs_id | VARCHAR(64) | True | False |  |  |  |  |
| terminal_id | VARCHAR(64) | True | False |  |  |  |  |
| operation_id | VARCHAR(128) | True | False |  |  |  |  |
| request_type | VARCHAR(32) | False | False |  |  |  |  |
| amount | INTEGER | True | False |  |  |  |  |
| liters | FLOAT | True | False |  |  |  |  |
| currency | VARCHAR(8) | True | False |  |  |  |  |
| status | VARCHAR(32) | False | False |  |  |  |  |
| reason_category | VARCHAR(32) | True | False |  |  |  |  |
| risk_code | VARCHAR(64) | True | False |  |  |  |  |
| limit_code | VARCHAR(64) | True | False |  |  |  |  |
| latency_ms | FLOAT | True | False |  |  |  |  |
| created_at | DATETIME | True | False | <function ExternalRequestLog.<lambda> at 0x7f1551a360c0> |  |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_external_request_logs_azs_id | azs_id | False |
| ix_external_request_logs_created_at | created_at | False |
| ix_external_request_logs_id | id | False |
| ix_external_request_logs_partner_id | partner_id | False |
| ix_external_request_logs_reason_category | reason_category | False |
| ix_external_request_logs_status | status | False |

### `financial_adjustments`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | UUID | False | True | <function uuid4 at 0x7f1551959f80> |  |  |  |
| kind | VARCHAR(19) | False | False |  |  |  |  |
| related_entity_type | VARCHAR(14) | False | False |  |  |  |  |
| related_entity_id | UUID | False | False |  |  |  |  |
| operation_id | UUID | False | False |  |  | operations.id |  |
| amount | BIGINT | False | False |  |  |  |  |
| currency | VARCHAR(3) | False | False |  |  |  |  |
| status | VARCHAR(7) | False | False | FinancialAdjustmentStatus.PENDING |  |  |  |
| posting_id | UUID | True | False |  |  |  |  |
| effective_date | DATE | False | False |  |  |  |  |
| idempotency_key | VARCHAR(128) | False | False |  |  |  |  |
| created_at | DATETIME | False | False |  | now() |  |  |
| updated_at | DATETIME | False | False |  | now() |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_financial_adjustments_operation_id | operation_id | False |
| ix_financial_adjustments_status | status | False |

**Уникальные ограничения**
| Name | Columns |
| --- | --- |
|  | idempotency_key |

**Foreign Keys**
| Columns | References |
| --- | --- |
| operation_id | operations.id |

### `invoice_lines`
**Назначение:** Line item describing a single billed product or operation.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | VARCHAR(36) | False | True | <function InvoiceLine.<lambda> at 0x7f1551a7e980> |  |  |  |
| invoice_id | VARCHAR(36) | False | False |  |  | invoices.id |  |
| operation_id | VARCHAR(128) | False | False |  |  |  |  |
| card_id | VARCHAR(64) | True | False |  |  |  |  |
| product_id | VARCHAR(64) | False | False |  |  |  |  |
| liters | NUMERIC(18, 3) | True | False |  |  |  |  |
| unit_price | NUMERIC(18, 3) | True | False |  |  |  |  |
| line_amount | BIGINT | False | False |  |  |  |  |
| tax_amount | BIGINT | False | False | 0 |  |  |  |
| partner_id | VARCHAR(64) | True | False |  |  |  |  |
| azs_id | VARCHAR(64) | True | False |  |  |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_invoice_lines_invoice_id | invoice_id | False |

**Уникальные ограничения**
| Name | Columns |
| --- | --- |
| uq_invoice_line_operation_per_invoice | invoice_id, operation_id |

**Foreign Keys**
| Columns | References |
| --- | --- |
| invoice_id | invoices.id |

### `invoice_messages`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | VARCHAR(36) | False | True | <function new_uuid_str at 0x7f1551958d60> |  |  |  |
| thread_id | VARCHAR(36) | False | False |  |  | invoice_threads.id |  |
| sender_type | VARCHAR(7) | False | False |  |  |  | invoice_message_sender_type |
| sender_user_id | TEXT | True | False |  |  |  |  |
| sender_email | TEXT | True | False |  |  |  |  |
| message | TEXT | False | False |  |  |  |  |
| created_at | DATETIME | False | False |  | now() |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_invoice_messages_created_at | created_at | False |
| ix_invoice_messages_sender_type | sender_type | False |
| ix_invoice_messages_thread_id | thread_id | False |

**Foreign Keys**
| Columns | References |
| --- | --- |
| thread_id | invoice_threads.id |

### `invoice_payments`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | VARCHAR(36) | False | True |  |  |  |  |
| invoice_id | VARCHAR(36) | False | False |  |  | invoices.id |  |
| amount | BIGINT | False | False |  |  |  |  |
| currency | VARCHAR(3) | False | False |  |  |  |  |
| provider | VARCHAR(64) | True | False |  |  |  |  |
| external_ref | VARCHAR(128) | True | False |  |  |  |  |
| idempotency_key | VARCHAR(128) | False | False |  |  |  |  |
| status | VARCHAR(6) | False | False | PaymentStatus.POSTED |  |  | invoice_payment_status |
| created_at | DATETIME | False | False |  | now() |  |  |
| updated_at | DATETIME | False | False |  | now() |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_invoice_payments_external_ref | external_ref | False |
| ix_invoice_payments_idempotency_key | idempotency_key | True |
| ix_invoice_payments_invoice_id | invoice_id | False |
| uq_invoice_payments_provider_external_ref | provider, external_ref | True |

**Foreign Keys**
| Columns | References |
| --- | --- |
| invoice_id | invoices.id |

### `invoice_threads`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | VARCHAR(36) | False | True | <function new_uuid_str at 0x7f1551917a60> |  |  |  |
| invoice_id | VARCHAR(36) | False | False |  |  | invoices.id |  |
| client_id | VARCHAR(64) | False | False |  |  |  |  |
| status | VARCHAR(15) | False | False | InvoiceThreadStatus.OPEN |  |  | invoice_thread_status |
| created_at | DATETIME | False | False |  | now() |  |  |
| closed_at | DATETIME | True | False |  |  |  |  |
| last_message_at | DATETIME | True | False |  |  |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_invoice_threads_client_id | client_id | False |
| ix_invoice_threads_invoice_id | invoice_id | False |
| ix_invoice_threads_last_message_at | last_message_at | False |
| ix_invoice_threads_status | status | False |

**Уникальные ограничения**
| Name | Columns |
| --- | --- |
| uq_invoice_thread_invoice | invoice_id |

**Foreign Keys**
| Columns | References |
| --- | --- |
| invoice_id | invoices.id |

### `invoice_transition_logs`
**Назначение:** Audit log for every invoice lifecycle transition.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | VARCHAR(36) | False | True | <function uuid4 at 0x7f1551a7fce0> |  |  |  |
| invoice_id | VARCHAR(36) | False | False |  |  | invoices.id |  |
| from_status | VARCHAR(14) | False | False |  |  |  | invoicestatus |
| to_status | VARCHAR(14) | False | False |  |  |  | invoicestatus |
| actor | VARCHAR(64) | False | False |  |  |  |  |
| reason | TEXT | False | False |  |  |  |  |
| metadata | JSON | True | False |  |  |  |  |
| created_at | DATETIME | False | False |  | now() |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_invoice_transition_logs_invoice_id | invoice_id | False |

**Foreign Keys**
| Columns | References |
| --- | --- |
| invoice_id | invoices.id |

### `invoices`
**Назначение:** Client invoice aggregated for a billing period.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | VARCHAR(36) | False | True | <function Invoice.<lambda> at 0x7f1551a37880> |  |  |  |
| clearing_batch_id | VARCHAR(36) | True | False |  |  | clearing_batch.id |  |
| client_id | VARCHAR(64) | False | False |  |  |  |  |
| number | VARCHAR(64) | True | False |  |  |  |  |
| period_from | DATE | False | False |  |  |  |  |
| period_to | DATE | False | False |  |  |  |  |
| currency | VARCHAR(3) | False | False |  |  |  |  |
| billing_period_id | VARCHAR(36) | True | False |  |  | billing_periods.id |  |
| due_date | DATE | True | False |  |  |  |  |
| payment_terms_days | INTEGER | True | False |  |  |  |  |
| total_amount | BIGINT | False | False | 0 |  |  |  |
| tax_amount | BIGINT | False | False | 0 |  |  |  |
| total_with_tax | BIGINT | False | False | 0 |  |  |  |
| amount_paid | BIGINT | False | False | 0 |  |  |  |
| amount_due | BIGINT | False | False | 0 |  |  |  |
| amount_refunded | BIGINT | False | False | 0 |  |  |  |
| status | VARCHAR(14) | False | False | InvoiceStatus.DRAFT |  |  | invoicestatus |
| created_at | DATETIME | False | False |  | now() |  |  |
| issued_at | DATETIME | True | False |  |  |  |  |
| sent_at | DATETIME | True | False |  |  |  |  |
| delivered_at | DATETIME | True | False |  |  |  |  |
| paid_at | DATETIME | True | False |  |  |  |  |
| cancelled_at | DATETIME | True | False |  |  |  |  |
| closed_at | DATETIME | True | False |  |  |  |  |
| refunded_at | DATETIME | True | False |  |  |  |  |
| external_number | VARCHAR(64) | True | False |  |  |  |  |
| external_delivery_id | VARCHAR(128) | True | False |  |  |  |  |
| external_delivery_provider | VARCHAR(64) | True | False |  |  |  |  |
| payment_reference | VARCHAR(128) | True | False |  |  |  |  |
| pdf_url | VARCHAR(512) | True | False |  |  |  |  |
| pdf_status | VARCHAR(10) | False | False |  | NONE |  | invoice_pdf_status |
| pdf_object_key | VARCHAR(512) | True | False |  |  |  |  |
| pdf_generated_at | DATETIME | True | False |  |  |  |  |
| pdf_hash | VARCHAR(64) | True | False |  |  |  |  |
| pdf_version | INTEGER | False | False | 1 | 1 |  |  |
| pdf_error | TEXT | True | False |  |  |  |  |
| credited_amount | BIGINT | False | False | 0 |  |  |  |
| credited_at | DATETIME | True | False |  |  |  |  |
| accounting_exported_at | DATETIME | True | False |  |  |  |  |
| accounting_export_batch_id | VARCHAR(36) | True | False |  |  |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_invoices_billing_period_id | billing_period_id | False |
| ix_invoices_clearing_batch_id | clearing_batch_id | False |
| ix_invoices_client_id | client_id | False |
| ix_invoices_delivered_at | delivered_at | False |
| ix_invoices_due_date | due_date | False |
| ix_invoices_number | number | False |
| ix_invoices_paid_at | paid_at | False |
| ix_invoices_pdf_status | pdf_status | False |
| ix_invoices_period_from | period_from | False |
| ix_invoices_period_to | period_to | False |
| ix_invoices_sent_at | sent_at | False |
| ix_invoices_status | status | False |

**Уникальные ограничения**
| Name | Columns |
| --- | --- |
| uq_invoice_clearing_batch | clearing_batch_id |
| uq_invoice_scope | client_id, billing_period_id, currency |
| uq_invoice_number | number |

**Foreign Keys**
| Columns | References |
| --- | --- |
| clearing_batch_id | clearing_batch.id |
| billing_period_id | billing_periods.id |

### `ledger_entries`
**Назначение:** Represents a posted ledger movement for an account.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | BIGINT | False | True |  |  |  |  |
| entry_id | UUID | False | False |  |  |  |  |
| posting_id | UUID | False | False |  |  |  |  |
| account_id | BIGINT | False | False |  |  | accounts.id |  |
| operation_id | UUID | True | False |  |  | operations.id |  |
| direction | VARCHAR(6) | False | False |  |  |  |  |
| amount | NUMERIC(18, 4) | False | False |  |  |  |  |
| currency | VARCHAR(8) | False | False |  |  |  |  |
| balance_before | NUMERIC(18, 4) | True | False |  |  |  |  |
| balance_after | NUMERIC(18, 4) | True | False |  |  |  |  |
| posted_at | DATETIME | False | False |  | now() |  |  |
| value_date | DATE | True | False |  |  |  |  |
| metadata | JSON | True | False |  |  |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_ledger_entries_account_id | account_id | False |
| ix_ledger_entries_entry_id | entry_id | True |
| ix_ledger_entries_operation_id | operation_id | False |
| ix_ledger_entries_posted_at | posted_at | False |
| ix_ledger_entries_posting_id | posting_id | False |

**Foreign Keys**
| Columns | References |
| --- | --- |
| operation_id | operations.id |
| account_id | accounts.id |

### `limit_configs`
**Назначение:** Contractual limits applied per client/card/tariff independent from risk DSL.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | INTEGER | False | True |  |  |  |  |
| scope | VARCHAR(6) | False | False |  |  |  |  |
| subject_ref | VARCHAR(64) | False | False |  |  |  |  |
| limit_type | VARCHAR(14) | False | False |  |  |  |  |
| value | BIGINT | False | False |  |  |  |  |
| window | VARCHAR(7) | False | False | LimitWindow.PER_TX | PER_TX |  |  |
| enabled | BOOLEAN | False | False | True |  |  |  |
| tariff_plan_id | VARCHAR(64) | True | False |  |  | tariff_plans.id |  |
| description | TEXT | True | False |  |  |  |  |
| created_at | DATETIME | False | False |  | now() |  |  |
| updated_at | DATETIME | False | False |  | now() |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_limit_configs_enabled | enabled | False |
| ix_limit_configs_limit_type | limit_type | False |
| ix_limit_configs_scope | scope | False |
| ix_limit_configs_subject_ref | subject_ref | False |

**Foreign Keys**
| Columns | References |
| --- | --- |
| tariff_plan_id | tariff_plans.id |

### `limits_rules`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | BIGINT | False | True |  |  |  |  |
| phase | VARCHAR(16) | False | False | AUTH |  |  |  |
| entity_type | VARCHAR(8) | False | False | LimitEntityType.CLIENT |  |  |  |
| scope | VARCHAR(7) | False | False | LimitScope.PER_TX |  |  |  |
| product_type | VARCHAR(6) | True | False |  |  |  |  |
| client_id | VARCHAR(64) | True | False |  |  |  |  |
| card_id | VARCHAR(64) | True | False |  |  |  |  |
| merchant_id | VARCHAR(64) | True | False |  |  |  |  |
| terminal_id | VARCHAR(64) | True | False |  |  |  |  |
| client_group_id | VARCHAR(64) | True | False |  |  |  |  |
| card_group_id | VARCHAR(64) | True | False |  |  |  |  |
| product_category | VARCHAR(64) | True | False |  |  |  |  |
| mcc | VARCHAR(32) | True | False |  |  |  |  |
| tx_type | VARCHAR(32) | True | False |  |  |  |  |
| currency | VARCHAR(8) | False | False | RUB |  |  |  |
| max_amount | BIGINT | True | False |  |  |  |  |
| max_quantity | NUMERIC(18, 3) | True | False |  |  |  |  |
| daily_limit | BIGINT | True | False |  |  |  |  |
| limit_per_tx | BIGINT | True | False |  |  |  |  |
| active | BOOLEAN | False | False | True |  |  |  |
| created_at | DATETIME | False | False |  | now() |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_limits_rules_card_group_id | card_group_id | False |
| ix_limits_rules_card_id | card_id | False |
| ix_limits_rules_client_group_id | client_group_id | False |
| ix_limits_rules_client_id | client_id | False |
| ix_limits_rules_id | id | False |
| ix_limits_rules_mcc | mcc | False |
| ix_limits_rules_merchant_id | merchant_id | False |
| ix_limits_rules_product_category | product_category | False |
| ix_limits_rules_terminal_id | terminal_id | False |
| ix_limits_rules_tx_type | tx_type | False |

### `merchants`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | VARCHAR(64) | False | True |  |  |  |  |
| name | VARCHAR(255) | False | False |  |  |  |  |
| status | VARCHAR(32) | False | False |  |  |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_merchants_id | id | False |
| ix_merchants_status | status | False |

### `operations`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | UUID | False | True | <function uuid4 at 0x7f1551d5f600> |  |  |  |
| operation_id | VARCHAR(64) | False | False |  |  |  |  |
| created_at | DATETIME | False | False |  | now() |  |  |
| updated_at | DATETIME | False | False |  | now() |  |  |
| operation_type | VARCHAR(8) | False | False |  |  |  |  |
| status | VARCHAR(10) | False | False |  |  |  |  |
| merchant_id | VARCHAR(64) | False | False |  |  |  |  |
| terminal_id | VARCHAR(64) | False | False |  |  |  |  |
| client_id | VARCHAR(64) | False | False |  |  |  |  |
| card_id | VARCHAR(64) | False | False |  |  |  |  |
| tariff_id | VARCHAR(64) | True | False |  |  |  |  |
| product_id | VARCHAR(64) | True | False |  |  |  |  |
| amount | BIGINT | False | False |  |  |  |  |
| amount_settled | BIGINT | True | False | 0 |  |  |  |
| currency | VARCHAR(3) | False | False | RUB |  |  |  |
| product_type | VARCHAR(6) | True | False |  |  |  |  |
| quantity | NUMERIC(18, 3) | True | False |  |  |  |  |
| unit_price | NUMERIC(18, 3) | True | False |  |  |  |  |
| captured_amount | BIGINT | False | False | 0 |  |  |  |
| refunded_amount | BIGINT | False | False | 0 |  |  |  |
| daily_limit | BIGINT | True | False |  |  |  |  |
| limit_per_tx | BIGINT | True | False |  |  |  |  |
| used_today | BIGINT | True | False |  |  |  |  |
| new_used_today | BIGINT | True | False |  |  |  |  |
| limit_profile_id | VARCHAR(64) | True | False |  |  |  |  |
| limit_check_result | JSON | True | False |  |  |  |  |
| authorized | BOOLEAN | False | False | False |  |  |  |
| response_code | VARCHAR(8) | False | False | 00 |  |  |  |
| response_message | VARCHAR(255) | False | False | OK |  |  |  |
| auth_code | VARCHAR(32) | True | False |  |  |  |  |
| parent_operation_id | VARCHAR(64) | True | False |  |  |  |  |
| reason | VARCHAR(255) | True | False |  |  |  |  |
| mcc | VARCHAR(8) | True | False |  |  |  |  |
| product_code | VARCHAR(32) | True | False |  |  |  |  |
| product_category | VARCHAR(32) | True | False |  |  |  |  |
| tx_type | VARCHAR(16) | True | False |  |  |  |  |
| accounts | JSON | True | False |  |  |  |  |
| posting_result | JSON | True | False |  |  |  |  |
| risk_score | FLOAT | True | False |  |  |  |  |
| risk_result | VARCHAR(13) | True | False |  |  |  |  |
| risk_payload | JSON | True | False |  |  |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_operations_card_id | card_id | False |
| ix_operations_client_id | client_id | False |
| ix_operations_created_at | created_at | False |
| ix_operations_mcc | mcc | False |
| ix_operations_merchant_id | merchant_id | False |
| ix_operations_operation_type | operation_type | False |
| ix_operations_parent_operation_id | parent_operation_id | False |
| ix_operations_product_category | product_category | False |
| ix_operations_status | status | False |
| ix_operations_tariff_id | tariff_id | False |
| ix_operations_terminal_id | terminal_id | False |
| ix_operations_tx_type | tx_type | False |

**Уникальные ограничения**
| Name | Columns |
| --- | --- |
|  | operation_id |

### `partners`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | VARCHAR(64) | False | True |  |  |  |  |
| name | VARCHAR(255) | False | False |  |  |  |  |
| type | VARCHAR(32) | False | False |  |  |  |  |
| allowed_ips | JSON | True | False | <function list at 0x7f1551b7c0e0> |  |  |  |
| token | VARCHAR(255) | False | False |  |  |  |  |
| status | VARCHAR(32) | False | False | active |  |  |  |
| created_at | DATETIME | True | False | <function Partner.<lambda> at 0x7f1551b7c220> |  |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_partners_id | id | False |
| ix_partners_status | status | False |

### `payout_batches`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | VARCHAR(36) | False | True | <function PayoutBatch.<lambda> at 0x7f1551b2f100> |  |  |  |
| tenant_id | INTEGER | False | False |  |  |  |  |
| partner_id | VARCHAR(64) | False | False |  |  |  |  |
| date_from | DATE | False | False |  |  |  |  |
| date_to | DATE | False | False |  |  |  |  |
| state | VARCHAR(7) | False | False |  | DRAFT |  |  |
| total_amount | NUMERIC(18, 2) | False | False |  | 0 |  |  |
| total_qty | NUMERIC(18, 3) | False | False |  | 0 |  |  |
| operations_count | INTEGER | False | False |  | 0 |  |  |
| created_at | DATETIME | False | False |  | now() |  |  |
| sent_at | DATETIME | True | False |  |  |  |  |
| settled_at | DATETIME | True | False |  |  |  |  |
| provider | VARCHAR(64) | True | False |  |  |  |  |
| external_ref | VARCHAR(128) | True | False |  |  |  |  |
| meta | JSON | True | False |  |  |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_payout_batches_partner_id | partner_id | False |
| ix_payout_batches_state | state | False |
| ix_payout_batches_tenant_id | tenant_id | False |

### `payout_events`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | VARCHAR(36) | False | True | <function PayoutEvent.<lambda> at 0x7f1551b2df80> |  |  |  |
| payout_order_id | VARCHAR(36) | False | False |  |  | payout_orders.id |  |
| event_type | VARCHAR(64) | False | False |  |  |  |  |
| payload | JSON | True | False |  |  |  |  |
| created_at | DATETIME | False | False |  | now() |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_payout_events_payout_order_id | payout_order_id | False |

**Foreign Keys**
| Columns | References |
| --- | --- |
| payout_order_id | payout_orders.id |

### `payout_export_files`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | VARCHAR(36) | False | True | <function PayoutExportFile.<lambda> at 0x7f1551b56160> |  |  |  |
| batch_id | VARCHAR(36) | False | False |  |  | payout_batches.id |  |
| format | VARCHAR(4) | False | False |  |  |  |  |
| state | VARCHAR(9) | False | False |  |  |  |  |
| provider | VARCHAR(64) | True | False |  |  |  |  |
| external_ref | VARCHAR(128) | True | False |  |  |  |  |
| bank_format_code | VARCHAR(64) | True | False |  |  |  |  |
| object_key | VARCHAR(512) | False | False |  |  |  |  |
| bucket | VARCHAR(128) | False | False |  |  |  |  |
| sha256 | VARCHAR(64) | True | False |  |  |  |  |
| size_bytes | BIGINT | True | False |  |  |  |  |
| generated_at | DATETIME | True | False |  |  |  |  |
| uploaded_at | DATETIME | True | False |  |  |  |  |
| error_message | VARCHAR(512) | True | False |  |  |  |  |
| meta | JSON | True | False |  |  |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_payout_export_files_batch_id | batch_id | False |

**Foreign Keys**
| Columns | References |
| --- | --- |
| batch_id | payout_batches.id |

### `payout_items`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | VARCHAR(36) | False | True | <function PayoutItem.<lambda> at 0x7f1551b54d60> |  |  |  |
| batch_id | VARCHAR(36) | False | False |  |  | payout_batches.id |  |
| azs_id | VARCHAR(64) | True | False |  |  |  |  |
| product_id | VARCHAR(64) | True | False |  |  |  |  |
| amount_gross | NUMERIC(18, 2) | False | False |  |  |  |  |
| commission_amount | NUMERIC(18, 2) | False | False |  | 0 |  |  |
| amount_net | NUMERIC(18, 2) | False | False |  |  |  |  |
| qty | NUMERIC(18, 3) | False | False |  | 0 |  |  |
| operations_count | INTEGER | False | False |  | 0 |  |  |
| meta | JSON | True | False |  |  |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_payout_items_batch_id | batch_id | False |

**Foreign Keys**
| Columns | References |
| --- | --- |
| batch_id | payout_batches.id |

### `payout_orders`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | VARCHAR(36) | False | True | <function PayoutOrder.<lambda> at 0x7f1551b2c400> |  |  |  |
| settlement_id | VARCHAR(36) | False | False |  |  | settlements.id |  |
| partner_bank_details_ref | VARCHAR(255) | True | False |  |  |  |  |
| amount | BIGINT | False | False |  |  |  |  |
| currency | VARCHAR(8) | False | False |  |  |  |  |
| status | VARCHAR(9) | False | False |  | QUEUED |  |  |
| provider_ref | VARCHAR(128) | True | False |  |  |  |  |
| error | TEXT | True | False |  |  |  |  |
| created_at | DATETIME | False | False |  | now() |  |  |
| updated_at | DATETIME | False | False |  | now() |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_payout_orders_provider_ref | provider_ref | False |
| ix_payout_orders_settlement_id | settlement_id | False |
| ix_payout_orders_status | status | False |

**Foreign Keys**
| Columns | References |
| --- | --- |
| settlement_id | settlements.id |

### `posting_batches`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | UUID | False | True | <function uuid4 at 0x7f15519d5800> |  |  |  |
| operation_id | UUID | True | False |  |  |  |  |
| posting_type | VARCHAR(15) | False | False |  |  |  |  |
| status | VARCHAR(8) | False | False | PostingBatchStatus.APPLIED |  |  |  |
| idempotency_key | VARCHAR(255) | False | False |  |  |  |  |
| hash | VARCHAR(255) | True | False |  |  |  |  |
| created_at | DATETIME | False | False |  | now() |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_posting_batches_idempotency_key | idempotency_key | True |
| ix_posting_batches_operation_id | operation_id | False |

### `reconciliation_requests`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | VARCHAR(36) | False | True | <function new_uuid_str at 0x7f1551914ea0> |  |  |  |
| tenant_id | INTEGER | False | False |  |  |  |  |
| client_id | VARCHAR(64) | False | False |  |  |  |  |
| date_from | DATE | False | False |  |  |  |  |
| date_to | DATE | False | False |  |  |  |  |
| status | VARCHAR(12) | False | False | ReconciliationRequestStatus.REQUESTED |  |  | reconciliation_request_status |
| requested_by_user_id | TEXT | True | False |  |  |  |  |
| requested_by_email | TEXT | True | False |  |  |  |  |
| requested_at | DATETIME | False | False |  | now() |  |  |
| generated_at | DATETIME | True | False |  |  |  |  |
| sent_at | DATETIME | True | False |  |  |  |  |
| acknowledged_at | DATETIME | True | False |  |  |  |  |
| result_object_key | TEXT | True | False |  |  |  |  |
| result_bucket | TEXT | True | False |  |  |  |  |
| result_hash_sha256 | VARCHAR(64) | True | False |  |  |  |  |
| version | INTEGER | False | False | 1 | 1 |  |  |
| note_client | TEXT | True | False |  |  |  |  |
| note_ops | TEXT | True | False |  |  |  |  |
| meta | JSON | True | False |  |  |  |  |
| created_at | DATETIME | False | False |  | now() |  |  |
| updated_at | DATETIME | False | False |  | now() |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_reconciliation_requests_client_id | client_id | False |
| ix_reconciliation_requests_date_from | date_from | False |
| ix_reconciliation_requests_date_to | date_to | False |
| ix_reconciliation_requests_status | status | False |
| ix_reconciliation_requests_tenant_id | tenant_id | False |

### `refund_requests`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | UUID | False | True | <function uuid4 at 0x7f15518ce0c0> |  |  |  |
| operation_id | UUID | False | False |  |  | operations.id |  |
| operation_business_id | VARCHAR(64) | False | False |  |  |  |  |
| amount | BIGINT | False | False |  |  |  |  |
| currency | VARCHAR(3) | False | False |  |  |  |  |
| reason | TEXT | True | False |  |  |  |  |
| initiator | VARCHAR(128) | True | False |  |  |  |  |
| idempotency_key | VARCHAR(128) | False | False |  |  |  |  |
| status | VARCHAR(9) | False | False | RefundRequestStatus.REQUESTED |  |  |  |
| posted_posting_id | UUID | True | False |  |  |  |  |
| settlement_policy | VARCHAR(19) | False | False |  |  |  |  |
| created_at | DATETIME | False | False |  | now() |  |  |
| updated_at | DATETIME | False | False |  | now() |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_refund_requests_operation_business_id | operation_business_id | False |
| ix_refund_requests_operation_id | operation_id | False |
| ix_refund_requests_status | status | False |

**Уникальные ограничения**
| Name | Columns |
| --- | --- |
|  | idempotency_key |

**Foreign Keys**
| Columns | References |
| --- | --- |
| operation_id | operations.id |

### `reversals`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | UUID | False | True | <function uuid4 at 0x7f15518f8180> |  |  |  |
| operation_id | UUID | False | False |  |  | operations.id |  |
| operation_business_id | VARCHAR(64) | False | False |  |  |  |  |
| reason | TEXT | True | False |  |  |  |  |
| initiator | VARCHAR(128) | True | False |  |  |  |  |
| idempotency_key | VARCHAR(128) | False | False |  |  |  |  |
| status | VARCHAR(9) | False | False | ReversalStatus.REQUESTED |  |  |  |
| posted_posting_id | UUID | True | False |  |  |  |  |
| settlement_policy | VARCHAR(19) | False | False |  |  |  |  |
| created_at | DATETIME | False | False |  | now() |  |  |
| updated_at | DATETIME | False | False |  | now() |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_reversals_operation_business_id | operation_business_id | False |
| ix_reversals_operation_id | operation_id | False |
| ix_reversals_status | status | False |

**Уникальные ограничения**
| Name | Columns |
| --- | --- |
|  | idempotency_key |

**Foreign Keys**
| Columns | References |
| --- | --- |
| operation_id | operations.id |

### `risk_rule_audits`
**Назначение:** Audit trail entry for changes applied to risk rules.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | BIGINT | False | True |  |  |  |  |
| rule_id | BIGINT | False | False |  |  | risk_rules.id |  |
| action | VARCHAR(7) | False | False |  |  |  |  |
| old_value | JSON | True | False |  |  |  |  |
| new_value | JSON | True | False |  |  |  |  |
| performed_by | VARCHAR(256) | True | False |  |  |  |  |
| performed_at | DATETIME | False | False |  | now() |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_risk_rule_audits_action | action | False |
| ix_risk_rule_audits_performed_at | performed_at | False |
| ix_risk_rule_audits_rule_id | rule_id | False |

**Foreign Keys**
| Columns | References |
| --- | --- |
| rule_id | risk_rules.id |

### `risk_rule_versions`
**Назначение:** Historical version of a rule configuration.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | BIGINT | False | True |  |  |  |  |
| rule_id | BIGINT | False | False |  |  | risk_rules.id |  |
| version | INTEGER | False | False |  |  |  |  |
| dsl_payload | JSON | False | False |  |  |  |  |
| effective_from | DATETIME | True | False |  |  |  |  |
| created_at | DATETIME | False | False |  | now() |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_risk_rule_versions_rule_id | rule_id | False |

**Уникальные ограничения**
| Name | Columns |
| --- | --- |
| uq_risk_rule_version | rule_id, version |

**Foreign Keys**
| Columns | References |
| --- | --- |
| rule_id | risk_rules.id |

### `risk_rules`
**Назначение:** Persisted risk rule with raw DSL payload.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | BIGINT | False | True |  |  |  |  |
| name | VARCHAR(128) | False | False |  |  |  |  |
| description | TEXT | True | False |  |  |  |  |
| scope | VARCHAR(7) | False | False |  |  |  |  |
| subject_ref | VARCHAR(128) | True | False |  |  |  |  |
| action | VARCHAR(13) | False | False |  |  |  |  |
| enabled | BOOLEAN | False | False | True |  |  |  |
| priority | INTEGER | False | False | 100 |  |  |  |
| dsl_payload | JSON | False | False |  |  |  |  |
| created_at | DATETIME | False | False |  | now() |  |  |
| updated_at | DATETIME | False | False |  | now() |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_risk_rules_enabled | enabled | False |
| ix_risk_rules_id | id | False |
| ix_risk_rules_scope | scope | False |
| ix_risk_rules_subject_ref | subject_ref | False |

**Уникальные ограничения**
| Name | Columns |
| --- | --- |
|  | name |

### `settlements`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | VARCHAR(36) | False | True | <function Settlement.<lambda> at 0x7f1551afa8e0> |  |  |  |
| merchant_id | VARCHAR(64) | False | False |  |  |  |  |
| partner_id | VARCHAR(64) | True | False |  |  |  |  |
| period_from | DATE | False | False |  |  |  |  |
| period_to | DATE | False | False |  |  |  |  |
| currency | VARCHAR(8) | False | False |  |  |  |  |
| total_amount | BIGINT | False | False |  |  |  |  |
| commission_amount | BIGINT | False | False | 0 |  |  |  |
| status | VARCHAR(9) | False | False |  | DRAFT |  |  |
| created_at | DATETIME | False | False |  | now() |  |  |
| updated_at | DATETIME | False | False |  | now() |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_settlements_currency | currency | False |
| ix_settlements_merchant_id | merchant_id | False |
| ix_settlements_partner_id | partner_id | False |
| ix_settlements_period_from | period_from | False |
| ix_settlements_period_to | period_to | False |
| ix_settlements_status | status | False |

**Уникальные ограничения**
| Name | Columns |
| --- | --- |
| uq_settlement_scope | merchant_id, currency, period_from, period_to |

### `tariff_plans`
**Назначение:** Represents a financial tariff/plan with customizable parameters.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | VARCHAR(64) | False | True |  |  |  |  |
| name | VARCHAR(255) | False | False |  |  |  |  |
| params | JSON | True | False |  |  |  |  |
| created_at | DATETIME | False | False |  | now() |  |  |
| updated_at | DATETIME | False | False |  | now() |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_tariff_plans_name | name | True |

### `tariff_prices`
**Назначение:** Pricing rules for a tariff plan scoped by product and partner/azs.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | BIGINT | False | True |  |  |  |  |
| tariff_id | VARCHAR(64) | False | False |  |  | tariff_plans.id |  |
| product_id | VARCHAR(64) | False | False |  |  |  |  |
| partner_id | VARCHAR(64) | True | False |  |  |  |  |
| azs_id | VARCHAR(64) | True | False |  |  |  |  |
| price_per_liter | NUMERIC(18, 6) | False | False |  |  |  |  |
| cost_price_per_liter | NUMERIC(18, 6) | True | False |  |  |  |  |
| currency | VARCHAR(3) | False | False |  |  |  |  |
| valid_from | DATETIME | True | False |  |  |  |  |
| valid_to | DATETIME | True | False |  |  |  |  |
| priority | INTEGER | False | False | 100 |  |  |  |
| created_at | DATETIME | False | False |  | now() |  |  |
| updated_at | DATETIME | False | False |  | now() |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_tariff_prices_azs_id | azs_id | False |
| ix_tariff_prices_partner_id | partner_id | False |
| ix_tariff_prices_priority | priority | False |
| ix_tariff_prices_product_id | product_id | False |
| ix_tariff_prices_tariff_id | tariff_id | False |
| ix_tariff_prices_valid_from | valid_from | False |
| ix_tariff_prices_valid_to | valid_to | False |

**Foreign Keys**
| Columns | References |
| --- | --- |
| tariff_id | tariff_plans.id |

### `terminals`
**Назначение:** Docstring/назначение не найдено в моделях.

**Колонки**
| Column | Type | Nullable | PK | Default | Server Default | FK | Enum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | VARCHAR(64) | False | True |  |  |  |  |
| merchant_id | VARCHAR(64) | False | False |  |  | merchants.id |  |
| status | VARCHAR(32) | False | False |  |  |  |  |
| location | VARCHAR(255) | True | False |  |  |  |  |

**Индексы**
| Name | Columns | Unique |
| --- | --- | --- |
| ix_terminals_id | id | False |
| ix_terminals_merchant_id | merchant_id | False |
| ix_terminals_status | status | False |

**Foreign Keys**
| Columns | References |
| --- | --- |
| merchant_id | merchants.id |



### Таблицы auth-host (создаются при старте)

* `users` — id(UUID), email(unique), full_name, password_hash, is_active, created_at.
* `user_roles` — (user_id, role) с FK на users.

### Странности/несоответствия (по факту в коде)

* Auth-host создаёт таблицы напрямую при старте, без Alembic.
* В core-api часть статусных полей — обычные `VARCHAR` без PostgreSQL enum типов (например, `clearing.status`, `payout_orders.status`).

---

## 3.7 Alembic миграции

**Стратегия:**

* Только online миграции (`run_migrations_offline` запрещён).
* `transaction_per_migration=True`.
* Идемпотентность: таблицы/колонки/индексы/enum создаются с проверками (см. `app/alembic/README`).
* Enum policy: только через helper `ensure_pg_enum(...)` (никаких implicit `CREATE TYPE`).

**Список миграций (по цепочке)**

- 0039_billing_finance_idempotency.py
- 0039_clearing_job_type.py
- 0040_merge_heads.py
- 0041_invoice_lifecycle_hardening.py
- 0042_audit_log.py
- 0042_invoice_state_machine_v15.py
- 0043_client_actions_enterprise.py
- 0044_documents_registry.py
- 0044_invoice_payments_external_ref.py
- 0045_invoice_payments_provider.py
- 0046_invoice_payments_provider_external_ref_unique.py
- 0046_invoice_refunds.py
- 0047_merge_heads.py
- 20250210_0043_billing_invoice_clearing_batch_fields.py
- 20251112_0001_core.py
- 20251118_0002_operations_journal.py
- 20251120_0003_limits_rules_v2.py
- 20251121_0003a_extend_alembic_version_len.py
- 20251124_0003_merchants_terminals_cards.py
- 20251206_0004_operations_product_fields.py
- 20251208_0004a_bootstrap_clients_cards_partners.py
- 20251215_0005_add_created_at_to_cards.py
- 20251220_0006_auto_fix.py
- 20251230_0007_add_capture_refund_fields_to_operations.py
- 2025_11_01_init.py
- 20260101_0008_billing_summary.py
- 20260110_0009_billing_summary_extend.py
- 20260110_0009_create_clearing_table.py
- 20260110_0010_clearing.py
- 20260115_0011_operations_indexes.py
- 20261010_0012_client_ids_uuid.py
- 20261020_0013_operations_limits_alignment.py
- 20261020_0013a_operations_limits_alignment_alias.py
- 20261101_0014_billing_summary_alignment.py
- 20261120_0015_risk_rules.py
- 20261125_0016_risk_rule_audit.py
- 20261201_0017_accounts_and_ledger.py
- 20261205_0018_contract_limits.py
- 20270101_0019_external_request_logs.py
- 20270115_0020_invoices.py
- 20270201_0020_tariff_prices.py
- 20270215_0021_merge_heads.py
- 20270301_0022_extend_alembic_version_len.py
- 20270520_0023_billing_summary_status_enum_fix.py
- 20270601_0024_bootstrap_schema.py
- 20270620_0025_ledger_entries_operation_id_nullable.py
- 20270625_0026_add_accounts_to_operations.py
- 20270626_0027_add_posting_result_to_operations.py
- 20270710_0028_limit_config_scope_enum_fix.py
- 20270720_0029_cards_created_at.py
- 20270831_0030_billing_state_machine.py
- 20270901_0031_partner_settlements.py
- 20270901_0031_tariff_commission_rules.py
- 20271015_0032_operational_scenarios_v1.py
- 20271020_0033_billing_periods.py
- 20271030_0034_billing_hardening_v11.py
- 20271101_0035_billing_period_type_adhoc.py
- 20271120_0036_billing_job_runs_and_invoice_fields.py
- 20271205_0037_billing_pdf_and_tasks.py
- 20271220_0038_finance_invoice_extensions.py
- 20271230_0039_payout_batches.py
- 20280115_0040_payout_exports.py
- 20280301_0041_payout_exports_bank_format.py
- 20280315_0042_client_actions_v1.py
- 20280401_0043_invoice_settlement_allocations.py
- 20280415_0044_accounting_export_batches.py
- 20280420_0045_decision_results.py
- 20290501_0045_document_status_lifecycle.py
- 20290520_0046_risk_scores.py
- 20290601_0046a_documents_bootstrap.py
- 20290601_0047_document_chain_reconciliation.py
- 20290615_0048_merge_heads.py
- 20290620_0049_fix_settlement_period_id_type.py
- 20290625_0050_fix_invoices_reconciliation_request_id_type.py


**Особенности**

* Bootstrap schema (миграция `20270601_0024_bootstrap_schema.py`) создаёт schema и alembic_version.
* Есть защищённые revision id (`app/alembic/protected_revisions.txt`).
* Fix migrations появились из-за legacy varchar id vs uuid id: выравнивание типов и безопасные миграции для fresh installs.
* `20290501_0045_document_status_lifecycle.py` выполняет schema-aware пересоздание enum и миграцию статусов.

**Риски/уязвимые места**

* Множество idempotent миграций с кастомными helpers — сложность поддержки.
* Зависимость от `search_path` и корректной установки `NEFT_DB_SCHEMA`.

---

## 3.8 API слой (core-api)

**Wiring:**

* `app/main.py` подключает несколько наборов роутеров с разными prefix:
  * `app/api/routes` → `/api/v1` (legacy).
  * `app/api/v1/endpoints/*` → включены без prefix, но сами имеют `/api/v1/...`.
  * admin router `/v1/admin` → включается под `/api` и `/api/core`.
  * client router `/client/api/v1` → включается без prefix и под `/api/core`.
  * client_portal router `/v1/client` → включается под `/api` и `/api/core`.
  * client_documents router `/api/v1/client` → включается без prefix и под `/api/core`.

**Список роутеров (файлы)**

* `app/api/routes/*.py` — health, auth internal, clients, prices, rules, transactions, limits, merchants, terminals, cards.
* `app/api/v1/endpoints/*.py` — operations_read, transactions, reports_billing, intake, partners, billing_invoices, payouts, audit.
* `app/routers/admin/*.py` — billing, limits, merchants, clearing, disputes, refunds, reversals, finance, settlements, documents, client_actions, etc.
* `app/routers/client.py` — клиентские operations/limits/dashboard.
* `app/routers/client_portal.py` — клиентский портал (operations, invoices, cards, reconciliation requests, exports).
* `app/routers/client_documents.py` — documents/closing_package ack/download.

**Auth/permissions**

* Админские роуты `/v1/admin` используют `require_admin_user` (JWT с public key из auth-host).
* Клиентские/портальные роуты используют `client_portal_user` и валидацию JWT (см. `app/services/client_auth.py`).

**Endpoints (полный список по декораторам)**

| Method | Path (as declared) | Location |
| --- | --- | --- |
| GET | `(empty string path)` | `platform/processing-core/app/api/routes/cards.py:13` |
| GET | `(empty string path)` | `platform/processing-core/app/api/routes/clients.py:18` |
| GET | `(empty string path)` | `platform/processing-core/app/api/routes/health.py:43` |
| GET | `(empty string path)` | `platform/processing-core/app/api/routes/merchants.py:18` |
| GET | `(empty string path)` | `platform/processing-core/app/api/routes/terminals.py:19` |
| GET | `(empty string path)` | `platform/processing-core/app/api/v1/endpoints/operations_read.py:22` |
| GET | `(empty string path)` | `platform/processing-core/app/api/v1/endpoints/partners.py:13` |
| GET | `(empty string path)` | `platform/processing-core/app/api/v1/endpoints/transactions.py:153` |
| POST | `(empty string path)` | `platform/processing-core/app/api/routes/cards.py:25` |
| POST | `(empty string path)` | `platform/processing-core/app/api/routes/clients.py:12` |
| POST | `(empty string path)` | `platform/processing-core/app/api/routes/merchants.py:30` |
| POST | `(empty string path)` | `platform/processing-core/app/api/routes/terminals.py:31` |
| POST | `(empty string path)` | `platform/processing-core/app/api/v1/endpoints/partners.py:18` |
| POST | `(empty string path)` | `platform/processing-core/app/routers/admin/refunds.py:16` |
| POST | `(empty string path)` | `platform/processing-core/app/routers/admin/reversals.py:16` |
| GET | `/accounts` | `platform/processing-core/app/routers/admin/accounts.py:31` |
| GET | `/accounts/{account_id}/statement` | `platform/processing-core/app/routers/admin/accounts.py:58` |
| GET | `/active` | `platform/processing-core/app/api/routes/prices.py:9` |
| POST | `/adjustments` | `platform/processing-core/app/routers/admin/billing.py:132` |
| GET | `/audit/search` | `platform/processing-core/app/routers/client_portal.py:679` |
| POST | `/authorize` | `platform/processing-core/app/api/v1/endpoints/intake.py:21` |
| POST | `/authorize` | `platform/processing-core/app/api/v1/endpoints/transactions.py:59` |
| GET | `/balances` | `platform/processing-core/app/routers/client_portal.py:1276` |
| GET | `/batches` | `platform/processing-core/app/api/v1/endpoints/admin_clearing.py:21` |
| GET | `/batches` | `platform/processing-core/app/api/v1/endpoints/payouts.py:93` |
| GET | `/batches` | `platform/processing-core/app/routers/admin/clearing.py:28` |
| POST | `/batches/build` | `platform/processing-core/app/routers/admin/clearing.py:83` |
| GET | `/batches/{batch_id}` | `platform/processing-core/app/api/v1/endpoints/admin_clearing.py:44` |
| GET | `/batches/{batch_id}` | `platform/processing-core/app/api/v1/endpoints/payouts.py:116` |
| GET | `/batches/{batch_id}` | `platform/processing-core/app/routers/admin/clearing.py:46` |
| POST | `/batches/{batch_id}/export` | `platform/processing-core/app/api/v1/endpoints/payouts.py:228` |
| GET | `/batches/{batch_id}/exports` | `platform/processing-core/app/api/v1/endpoints/payouts.py:319` |
| POST | `/batches/{batch_id}/mark-confirmed` | `platform/processing-core/app/routers/admin/clearing.py:115` |
| POST | `/batches/{batch_id}/mark-failed` | `platform/processing-core/app/routers/admin/clearing.py:125` |
| POST | `/batches/{batch_id}/mark-sent` | `platform/processing-core/app/api/v1/endpoints/payouts.py:124` |
| POST | `/batches/{batch_id}/mark-sent` | `platform/processing-core/app/routers/admin/clearing.py:105` |
| POST | `/batches/{batch_id}/mark-settled` | `platform/processing-core/app/api/v1/endpoints/payouts.py:157` |
| GET | `/batches/{batch_id}/operations` | `platform/processing-core/app/routers/admin/clearing.py:56` |
| GET | `/batches/{batch_id}/reconcile` | `platform/processing-core/app/api/v1/endpoints/payouts.py:190` |
| POST | `/batches/{batch_id}/retry` | `platform/processing-core/app/routers/admin/clearing.py:135` |
| POST | `/billing/close-period` | `platform/processing-core/app/api/v1/endpoints/billing_invoices.py:43` |
| GET | `/billing/daily` | `platform/processing-core/app/api/v1/endpoints/reports_billing.py:56` |
| GET | `/billing/summary` | `platform/processing-core/app/api/v1/endpoints/reports_billing.py:123` |
| POST | `/billing/summary/rebuild` | `platform/processing-core/app/api/v1/endpoints/reports_billing.py:92` |
| POST | `/callback` | `platform/processing-core/app/api/v1/endpoints/intake.py:61` |
| GET | `/card-groups` | `platform/processing-core/app/routers/admin/groups_legacy.py:178` |
| GET | `/card-groups` | `platform/processing-core/app/routers/admin/limits.py:295` |
| POST | `/card-groups` | `platform/processing-core/app/routers/admin/groups_legacy.py:184` |
| POST | `/card-groups` | `platform/processing-core/app/routers/admin/limits.py:312` |
| DELETE | `/card-groups/{group_id}` | `platform/processing-core/app/routers/admin/groups_legacy.py:228` |
| DELETE | `/card-groups/{group_id}` | `platform/processing-core/app/routers/admin/limits.py:342` |
| GET | `/card-groups/{group_id}` | `platform/processing-core/app/routers/admin/groups_legacy.py:199` |
| GET | `/card-groups/{group_id}` | `platform/processing-core/app/routers/admin/limits.py:307` |
| PUT | `/card-groups/{group_id}` | `platform/processing-core/app/routers/admin/groups_legacy.py:205` |
| PUT | `/card-groups/{group_id}` | `platform/processing-core/app/routers/admin/limits.py:329` |
| GET | `/card-groups/{group_id}/members` | `platform/processing-core/app/routers/admin/limits.py:354` |
| POST | `/card-groups/{group_id}/members` | `platform/processing-core/app/routers/admin/groups_legacy.py:235` |
| POST | `/card-groups/{group_id}/members` | `platform/processing-core/app/routers/admin/limits.py:368` |
| DELETE | `/card-groups/{group_id}/members/{card_id}` | `platform/processing-core/app/routers/admin/groups_legacy.py:256` |
| DELETE | `/card-groups/{group_id}/members/{card_id}` | `platform/processing-core/app/routers/admin/limits.py:395` |
| GET | `/cards` | `platform/processing-core/app/routers/admin/dashboard.py:70` |
| GET | `/cards` | `platform/processing-core/app/routers/client_portal.py:311` |
| GET | `/cards/{card_id}` | `platform/processing-core/app/routers/client_portal.py:321` |
| POST | `/cards/{card_id}/block` | `platform/processing-core/app/routers/client_portal.py:340` |
| POST | `/cards/{card_id}/limits` | `platform/processing-core/app/routers/client_portal.py:384` |
| POST | `/cards/{card_id}/unblock` | `platform/processing-core/app/routers/client_portal.py:362` |
| GET | `/client-groups` | `platform/processing-core/app/routers/admin/groups_legacy.py:80` |
| GET | `/client-groups` | `platform/processing-core/app/routers/admin/limits.py:169` |
| POST | `/client-groups` | `platform/processing-core/app/routers/admin/groups_legacy.py:86` |
| POST | `/client-groups` | `platform/processing-core/app/routers/admin/limits.py:186` |
| DELETE | `/client-groups/{group_id}` | `platform/processing-core/app/routers/admin/groups_legacy.py:130` |
| DELETE | `/client-groups/{group_id}` | `platform/processing-core/app/routers/admin/limits.py:218` |
| GET | `/client-groups/{group_id}` | `platform/processing-core/app/routers/admin/groups_legacy.py:101` |
| GET | `/client-groups/{group_id}` | `platform/processing-core/app/routers/admin/limits.py:181` |
| PUT | `/client-groups/{group_id}` | `platform/processing-core/app/routers/admin/groups_legacy.py:107` |
| PUT | `/client-groups/{group_id}` | `platform/processing-core/app/routers/admin/limits.py:205` |
| GET | `/client-groups/{group_id}/members` | `platform/processing-core/app/routers/admin/limits.py:230` |
| POST | `/client-groups/{group_id}/members` | `platform/processing-core/app/routers/admin/groups_legacy.py:137` |
| POST | `/client-groups/{group_id}/members` | `platform/processing-core/app/routers/admin/limits.py:244` |
| DELETE | `/client-groups/{group_id}/members/{client_id}` | `platform/processing-core/app/routers/admin/groups_legacy.py:158` |
| DELETE | `/client-groups/{group_id}/members/{client_id}` | `platform/processing-core/app/routers/admin/limits.py:271` |
| GET | `/clients` | `platform/processing-core/app/routers/admin/dashboard.py:23` |
| GET | `/clients/{client_id}/balances` | `platform/processing-core/app/routers/admin/accounts.py:84` |
| POST | `/close-period` | `platform/processing-core/app/api/v1/endpoints/payouts.py:49` |
| POST | `/closing-packages/{package_id}/ack` | `platform/processing-core/app/routers/client_documents.py:254` |
| POST | `/commit` | `platform/processing-core/app/api/v1/endpoints/transactions.py:111` |
| POST | `/credit-notes` | `platform/processing-core/app/routers/admin/finance.py:50` |
| GET | `/dashboard` | `platform/processing-core/app/routers/client.py:107` |
| GET | `/documents` | `platform/processing-core/app/routers/client_documents.py:60` |
| POST | `/documents/{document_id}/ack` | `platform/processing-core/app/routers/client_documents.py:176` |
| GET | `/documents/{document_id}/download` | `platform/processing-core/app/routers/client_documents.py:130` |
| POST | `/documents/{document_type}/{document_id}/ack` | `platform/processing-core/app/routers/client_portal.py:948` |
| GET | `/enqueue` | `platform/processing-core/app/api/routes/health.py:49` |
| GET | `/entity/{entity_type}/{entity_id}` | `platform/processing-core/app/api/v1/endpoints/audit.py:94` |
| GET | `/export-formats` | `platform/processing-core/app/api/v1/endpoints/payouts.py:326` |
| GET | `/exports` | `platform/processing-core/app/routers/client_portal.py:1251` |
| GET | `/exports/{export_id}/download` | `platform/processing-core/app/api/v1/endpoints/payouts.py:331` |
| POST | `/finalize-day` | `platform/processing-core/app/routers/admin/billing.py:297` |
| POST | `/generate` | `platform/processing-core/app/routers/admin/closing_packages.py:15` |
| GET | `/integration/azs/heatmap` | `platform/processing-core/app/routers/admin/integration_monitoring.py:61` |
| GET | `/integration/declines/recent` | `platform/processing-core/app/routers/admin/integration_monitoring.py:71` |
| GET | `/integration/partners/status` | `platform/processing-core/app/routers/admin/integration_monitoring.py:55` |
| GET | `/integration/requests` | `platform/processing-core/app/routers/admin/integration_monitoring.py:28` |
| POST | `/internal/pricing/resolve` | `platform/processing-core/app/api/routes/auth.py:9` |
| POST | `/internal/rules/evaluate` | `platform/processing-core/app/api/routes/auth.py:22` |
| POST | `/invoice-threads/{thread_id}/close` | `platform/processing-core/app/routers/admin/client_actions.py:206` |
| GET | `/invoices` | `platform/processing-core/app/routers/admin/billing.py:376` |
| GET | `/invoices` | `platform/processing-core/app/routers/client_portal.py:478` |
| POST | `/invoices/generate` | `platform/processing-core/app/api/v1/endpoints/billing_invoices.py:64` |
| POST | `/invoices/generate` | `platform/processing-core/app/routers/admin/billing.py:410` |
| POST | `/invoices/run-monthly` | `platform/processing-core/app/routers/admin/billing.py:486` |
| GET | `/invoices/{invoice_id}` | `platform/processing-core/app/api/v1/endpoints/billing_invoices.py:104` |
| GET | `/invoices/{invoice_id}` | `platform/processing-core/app/routers/admin/billing.py:402` |
| GET | `/invoices/{invoice_id}` | `platform/processing-core/app/routers/client_portal.py:527` |
| GET | `/invoices/{invoice_id}/audit` | `platform/processing-core/app/routers/client_portal.py:607` |
| GET | `/invoices/{invoice_id}/messages` | `platform/processing-core/app/routers/client_portal.py:1155` |
| POST | `/invoices/{invoice_id}/messages` | `platform/processing-core/app/routers/admin/client_actions.py:145` |
| POST | `/invoices/{invoice_id}/messages` | `platform/processing-core/app/routers/client_portal.py:1058` |
| POST | `/invoices/{invoice_id}/payments` | `platform/processing-core/app/api/v1/endpoints/billing_invoices.py:123` |
| GET | `/invoices/{invoice_id}/pdf` | `platform/processing-core/app/api/v1/endpoints/billing_invoices.py:315` |
| GET | `/invoices/{invoice_id}/pdf` | `platform/processing-core/app/routers/admin/billing.py:604` |
| GET | `/invoices/{invoice_id}/pdf` | `platform/processing-core/app/routers/client_portal.py:1218` |
| POST | `/invoices/{invoice_id}/pdf` | `platform/processing-core/app/routers/admin/billing.py:528` |
| GET | `/invoices/{invoice_id}/refunds` | `platform/processing-core/app/api/v1/endpoints/billing_invoices.py:278` |
| POST | `/invoices/{invoice_id}/refunds` | `platform/processing-core/app/api/v1/endpoints/billing_invoices.py:205` |
| POST | `/invoices/{invoice_id}/status` | `platform/processing-core/app/routers/admin/billing.py:421` |
| POST | `/invoices/{invoice_id}/transition` | `platform/processing-core/app/routers/admin/billing.py:452` |
| GET | `/jobs` | `platform/processing-core/app/routers/admin/billing.py:633` |
| GET | `/limit-rules` | `platform/processing-core/app/routers/admin/groups_legacy.py:284` |
| POST | `/limit-rules` | `platform/processing-core/app/routers/admin/groups_legacy.py:294` |
| DELETE | `/limit-rules/{rule_id}` | `platform/processing-core/app/routers/admin/groups_legacy.py:350` |
| GET | `/limit-rules/{rule_id}` | `platform/processing-core/app/routers/admin/groups_legacy.py:316` |
| PUT | `/limit-rules/{rule_id}` | `platform/processing-core/app/routers/admin/groups_legacy.py:322` |
| GET | `/limits` | `platform/processing-core/app/routers/client.py:86` |
| GET | `/limits/rules` | `platform/processing-core/app/routers/admin/limits.py:55` |
| POST | `/limits/rules` | `platform/processing-core/app/routers/admin/limits.py:109` |
| DELETE | `/limits/rules/{rule_id}` | `platform/processing-core/app/routers/admin/limits.py:143` |
| GET | `/limits/rules/{rule_id}` | `platform/processing-core/app/routers/admin/limits.py:104` |
| PUT | `/limits/rules/{rule_id}` | `platform/processing-core/app/routers/admin/limits.py:124` |
| GET | `/log` | `platform/processing-core/app/api/routes/transactions_log.py:19` |
| GET | `/me` | `platform/processing-core/app/routers/client_portal.py:290` |
| GET | `/merchants` | `platform/processing-core/app/routers/admin/merchants.py:60` |
| POST | `/merchants` | `platform/processing-core/app/routers/admin/merchants.py:99` |
| DELETE | `/merchants/{merchant_id}` | `platform/processing-core/app/routers/admin/merchants.py:149` |
| GET | `/merchants/{merchant_id}` | `platform/processing-core/app/routers/admin/merchants.py:94` |
| PATCH | `/merchants/{merchant_id}` | `platform/processing-core/app/routers/admin/merchants.py:132` |
| PUT | `/merchants/{merchant_id}` | `platform/processing-core/app/routers/admin/merchants.py:116` |
| POST | `/open` | `platform/processing-core/app/routers/admin/disputes.py:30` |
| GET | `/operations` | `platform/processing-core/app/routers/admin/operations.py:80` |
| GET | `/operations` | `platform/processing-core/app/routers/client.py:25` |
| GET | `/operations` | `platform/processing-core/app/routers/client_portal.py:428` |
| GET | `/operations/{operation_id}` | `platform/processing-core/app/routers/admin/operations.py:260` |
| GET | `/operations/{operation_id}` | `platform/processing-core/app/routers/client_portal.py:459` |
| GET | `/operations/{operation_id}/children` | `platform/processing-core/app/routers/admin/operations.py:268` |
| GET | `/partners/{partner_id}/balance` | `platform/processing-core/app/routers/admin/settlements.py:60` |
| POST | `/payments` | `platform/processing-core/app/routers/admin/finance.py:18` |
| POST | `/payouts/{payout_id}/confirm` | `platform/processing-core/app/routers/admin/settlements.py:51` |
| POST | `/payouts/{payout_id}/send` | `platform/processing-core/app/routers/admin/settlements.py:42` |
| GET | `/periods` | `platform/processing-core/app/routers/admin/billing.py:69` |
| POST | `/periods/finalize` | `platform/processing-core/app/routers/admin/billing.py:98` |
| POST | `/periods/lock` | `platform/processing-core/app/routers/admin/billing.py:82` |
| POST | `/processing/terminal-auth` | `platform/processing-core/app/api/routes/transactions.py:323` |
| POST | `/recalc/{client_id}` | `platform/processing-core/app/api/routes/limits.py:90` |
| POST | `/reconcile` | `platform/processing-core/app/routers/admin/billing.py:114` |
| GET | `/reconciliation-requests` | `platform/processing-core/app/routers/client_portal.py:812` |
| POST | `/reconciliation-requests` | `platform/processing-core/app/routers/client_portal.py:752` |
| GET | `/reconciliation-requests/{request_id}` | `platform/processing-core/app/routers/client_portal.py:849` |
| POST | `/reconciliation-requests/{request_id}/ack` | `platform/processing-core/app/routers/client_portal.py:905` |
| POST | `/reconciliation-requests/{request_id}/attach-result` | `platform/processing-core/app/routers/admin/client_actions.py:87` |
| GET | `/reconciliation-requests/{request_id}/download` | `platform/processing-core/app/routers/client_portal.py:872` |
| POST | `/reconciliation-requests/{request_id}/mark-in-progress` | `platform/processing-core/app/routers/admin/client_actions.py:66` |
| POST | `/reconciliation-requests/{request_id}/mark-sent` | `platform/processing-core/app/routers/admin/client_actions.py:123` |
| POST | `/refund` | `platform/processing-core/app/api/v1/endpoints/intake.py:26` |
| POST | `/refund` | `platform/processing-core/app/api/v1/endpoints/transactions.py:135` |
| POST | `/reversal` | `platform/processing-core/app/api/v1/endpoints/intake.py:46` |
| POST | `/reverse` | `platform/processing-core/app/api/v1/endpoints/transactions.py:126` |
| GET | `/rules` | `platform/processing-core/app/routers/admin/risk_rules.py:89` |
| POST | `/rules` | `platform/processing-core/app/routers/admin/risk_rules.py:124` |
| GET | `/rules/{rule_id}` | `platform/processing-core/app/routers/admin/risk_rules.py:118` |
| PUT | `/rules/{rule_id}` | `platform/processing-core/app/routers/admin/risk_rules.py:144` |
| POST | `/rules/{rule_id}/disable` | `platform/processing-core/app/routers/admin/risk_rules.py:195` |
| POST | `/rules/{rule_id}/enable` | `platform/processing-core/app/routers/admin/risk_rules.py:170` |
| POST | `/run` | `platform/processing-core/app/api/v1/endpoints/admin_clearing.py:52` |
| POST | `/run` | `platform/processing-core/app/routers/admin/billing.py:195` |
| POST | `/run` | `platform/processing-core/app/routers/admin/clearing.py:95` |
| POST | `/run-daily` | `platform/processing-core/app/routers/admin/billing.py:287` |
| POST | `/run-daily` | `platform/processing-core/app/routers/admin/clearing.py:67` |
| GET | `/search` | `platform/processing-core/app/api/v1/endpoints/audit.py:42` |
| POST | `/seed` | `platform/processing-core/app/routers/admin/billing.py:171` |
| POST | `/settlements/generate` | `platform/processing-core/app/routers/admin/settlements.py:24` |
| POST | `/settlements/{settlement_id}/approve` | `platform/processing-core/app/routers/admin/settlements.py:33` |
| POST | `/simulate` | `platform/processing-core/app/api/routes/rules.py:15` |
| GET | `/statements` | `platform/processing-core/app/routers/client_portal.py:1302` |
| GET | `/summary` | `platform/processing-core/app/routers/admin/billing.py:238` |
| GET | `/summary/{summary_id}` | `platform/processing-core/app/routers/admin/billing.py:270` |
| POST | `/summary/{summary_id}/finalize` | `platform/processing-core/app/routers/admin/billing.py:278` |
| GET | `/tariffs` | `platform/processing-core/app/routers/admin/billing.py:311` |
| GET | `/tariffs/{tariff_id}` | `platform/processing-core/app/routers/admin/billing.py:323` |
| GET | `/tariffs/{tariff_id}/prices` | `platform/processing-core/app/routers/admin/billing.py:359` |
| POST | `/tariffs/{tariff_id}/prices` | `platform/processing-core/app/routers/admin/billing.py:338` |
| GET | `/terminals` | `platform/processing-core/app/routers/admin/merchants.py:168` |
| POST | `/terminals` | `platform/processing-core/app/routers/admin/merchants.py:216` |
| DELETE | `/terminals/{terminal_id}` | `platform/processing-core/app/routers/admin/merchants.py:275` |
| GET | `/terminals/{terminal_id}` | `platform/processing-core/app/routers/admin/merchants.py:211` |
| PATCH | `/terminals/{terminal_id}` | `platform/processing-core/app/routers/admin/merchants.py:255` |
| PUT | `/terminals/{terminal_id}` | `platform/processing-core/app/routers/admin/merchants.py:235` |
| GET | `/transactions` | `platform/processing-core/app/routers/admin/operations.py:190` |
| POST | `/transactions/{auth_operation_id}/capture` | `platform/processing-core/app/api/routes/transactions.py:347` |
| POST | `/transactions/{auth_operation_id}/capture` | `platform/processing-core/app/api/v1/endpoints/transactions.py:214` |
| POST | `/transactions/{auth_operation_id}/reverse` | `platform/processing-core/app/api/v1/endpoints/transactions.py:254` |
| POST | `/transactions/{capture_operation_id}/refund` | `platform/processing-core/app/api/routes/transactions.py:384` |
| POST | `/transactions/{capture_operation_id}/refund` | `platform/processing-core/app/api/v1/endpoints/transactions.py:232` |
| POST | `/transactions/{operation_id}/reversal` | `platform/processing-core/app/api/routes/transactions.py:414` |
| GET | `/turnover` | `platform/processing-core/app/api/v1/endpoints/reports_billing.py:30` |
| GET | `/turnover/export` | `platform/processing-core/app/api/v1/endpoints/reports_billing.py:154` |
| POST | `/verify` | `platform/processing-core/app/api/v1/endpoints/audit.py:122` |
| GET | `/{card_id}` | `platform/processing-core/app/api/routes/cards.py:40` |
| PATCH | `/{card_id}` | `platform/processing-core/app/api/routes/cards.py:48` |
| POST | `/{dispute_id}/accept` | `platform/processing-core/app/routers/admin/disputes.py:77` |
| POST | `/{dispute_id}/close` | `platform/processing-core/app/routers/admin/disputes.py:133` |
| POST | `/{dispute_id}/reject` | `platform/processing-core/app/routers/admin/disputes.py:107` |
| POST | `/{dispute_id}/review` | `platform/processing-core/app/routers/admin/disputes.py:58` |
| GET | `/{document_id}/download` | `platform/processing-core/app/routers/admin/documents.py:17` |
| DELETE | `/{merchant_id}` | `platform/processing-core/app/api/routes/merchants.py:67` |
| GET | `/{merchant_id}` | `platform/processing-core/app/api/routes/merchants.py:41` |
| PATCH | `/{merchant_id}` | `platform/processing-core/app/api/routes/merchants.py:49` |
| GET | `/{operation_id}` | `platform/processing-core/app/api/v1/endpoints/operations_read.py:86` |
| GET | `/{operation_id}/timeline` | `platform/processing-core/app/api/v1/endpoints/operations_read.py:99` |
| DELETE | `/{partner_id}` | `platform/processing-core/app/api/v1/endpoints/partners.py:60` |
| GET | `/{partner_id}` | `platform/processing-core/app/api/v1/endpoints/partners.py:37` |
| PUT | `/{partner_id}` | `platform/processing-core/app/api/v1/endpoints/partners.py:45` |
| DELETE | `/{terminal_id}` | `platform/processing-core/app/api/routes/terminals.py:83` |
| GET | `/{terminal_id}` | `platform/processing-core/app/api/routes/terminals.py:51` |
| PATCH | `/{terminal_id}` | `platform/processing-core/app/api/routes/terminals.py:59` |
| GET | `/{transaction_id}` | `platform/processing-core/app/api/v1/endpoints/transactions.py:184` |
| GET | `/{transaction_id}/timeline` | `platform/processing-core/app/api/v1/endpoints/transactions.py:199` |


---

## 3.9 Фоновые процессы (Celery/beat/workers)

**Workers (platform/billing-clearing):**

* `workers.ping` — тест задачи.
* `periodic.ping` — периодический лог.
* `limits.recalc_for_client`, `limits.recalc_all`, `limits.apply_daily_limits`, `limits.check_and_reserve`.
* `billing.build_daily_summaries` — агрегирует CAPTURE операции в billing_summary.
* `clearing.build_daily_batch` — создаёт clearing_batch + clearing_batch_operation.
* `clearing.finalize_billing` — финализирует billing_summary.
* `ai.score_transaction` — прокси к ai-service.

**Beat:**

* `periodic.ping` каждые 60 сек.
* `limits.apply_daily_limits` каждые 3600 сек.
* (но см. замечание про не подключенный `beat.py`).

**Core-api Celery tasks:**

* `billing.generate_monthly_invoices` (monthly run + PDF очередь).
* `billing.generate_invoice_pdf` (queue=pdf).
* `workers.ping` (health check).

---

## 3.10 Observability и метрики

**Gateway:** `/metrics` → `gateway_up 1`.

**Core-api:** `/metrics` и алиас `/api/v1/metrics` → Prometheus text format (billing, payouts, posting, intake, risk, audit).

**AI-service:** `/metrics` через `prometheus_client`.

**Auth-host:** метрики не реализованы, но Prometheus ожидает `/api/v1/metrics`.

**OTEL/Jaeger:** в infra есть OTEL collector + Jaeger, но явной инструментализации в коде не обнаружено.

---

## 3.11 Тесты (фактическое покрытие)

**Auth-host:**

* `platform/auth-host/app/tests/*` — auth, admin users, bootstrap, keys, processing.

**Core-api:**

* `platform/processing-core/app/tests/*` — billing pipeline, invoices, payments, refunds, state machine/invariants, migrations, limits, risk rules, payouts, settlements, metrics, api endpoints.
* `test_settlement_allocations.py`, `test_accounting_exports.py` — settlement_allocation + accounting_export_batch.
* `test_policy_engine.py` — RBAC/policy denials/allowances.
* `test_documents_lifecycle.py`, `test_immutability_enforcement.py` — document lifecycle + immutability.
* `test_decision_engine*.py` — decision engine determinism/integration.

**AI-service:**

* `platform/ai-services/risk-scorer/app/tests/*` — score + risk_score_v2 + train/update endpoints.

**Root tests:**

* `tests/test_gateway_routing_smoke.py`, `tests/test_smoke_gateway_routing.py`, `tests/test_alembic_single_head.py`, `tests/test_alembic_history.py`, `tests/test_minio_init.py`.

**Что покрыто хорошо:**

* Биллинг, инвойсы, state machine, миграции, payouts.

**Что не покрыто:**

* Реальные интеграции с внешними платёжными системами/CRM/логистикой.

---

## 3.12 Итоговая матрица готовности

| Модуль | Готовность | Почему |
| --- | --- | --- |
| Core operations | ✅ | CRUD и обработка транзакций есть, DB и API реализованы. |
| Billing | ✅ | Period lifecycle finalize/lock + hardening инварианты реализованы. |
| Invoices + PDF | ✅ | State machine, PDF generation и storage реализованы. |
| Finance (payments/credit notes/refunds) | ✅ | Idempotency, status transitions, settlement_allocation и аудит реализованы. |
| Settlement_allocation | ✅ | `invoice_settlement_allocations`, cross-period логика и summary отчёты есть. |
| Accounting export | ✅ | accounting_export_batch lifecycle, deterministic serializer, S3 upload/download/confirm. |
| RBAC/policies (finance) | ✅ | Policy engine защищает finalize/lock/payment/credit/export/payout. |
| Documents (legal finalization) | ✅ | ISSUED→ACKNOWLEDGED→FINALIZED, hash chain, immutability guards, closing_package. |
| Clearing | 🟡 | Batch/статусы/генерация есть, интеграции внешние отсутствуют. |
| Payouts/exports | 🟡 | Основные сущности и API есть, внешний провайдер не реализован. |
| Decision engine + risk scoring | ✅ | Decision engine deterministic + audit; ai-service risk-score v2 endpoints/tests есть (heuristic/stub). |
| Auth-host | 🟡 | Базовая auth + bootstrap, без миграций и расширенного RBAC. |
| Admin UI | 🟡 | SPA собран, но функционал зависит от backend. |
| Client portal | 🟡 | SPA собран, есть client endpoints. |
| Observability | 🟡 | Метрики есть, но auth-host metrics отсутствуют, traces не включены. |
| CRM/Logistics/Document services | ❌ | Только заглушки в compose. |

---

## 3.13 Следующие логичные шаги (основанные на gaps)

1. **Привести auth-host к миграционной стратегии**: добавить Alembic/DDL миграции для users/user_roles.
2. **Подключить beat расписания**: запускать `services.workers.app.beat` или импортировать `beat.py` в `celery_app`.
3. **Добавить метрики auth-host**: реализовать `/api/v1/metrics` для Prometheus.
4. **Стабилизировать API префиксы**: сократить дублирующиеся маршруты (/api, /api/core, /api/v1) и оставить единый prefix.
5. **Вынести integrations**: реализовать внешние интеграции для payouts/settlements.
6. **Добавить уведомления**: отправка email/webhook о статусах инвойса/оплат.
7. **Документооборот**: расширить `documents`/`closing_package` и добавить workflows/архив.
8. **Audit completeness**: покрыть аудитом ключевые операции (не все endpoints логируются).
9. **Стабилизация AI**: подключить реальные модели или сервис, задокументировать SLA.
10. **RBAC**: уточнить роли/permissions в auth-host и core-api.
11. **Monitoring dashboards**: привязать Grafana dashboards к метрикам core-api.
12. **Schema hardening**: завершить проверку FK/индексов для новых таблиц.
13. **Очистка legacy endpoints**: удалить или задокументировать legacy маршруты.
14. **Обработка ошибок**: унифицировать error responses в core-api и auth-host.
15. **Perf/Load testing**: добавить нагрузочные тесты для billing/transactions.
16. **CI миграции**: включить миграционные проверки для auth-host.
17. **Payout exports**: документировать форматы и добавить validation.
18. **Client actions**: завершить API для reconciliation/closing_package.
19. **MinIO policies**: формализовать S3 bucket naming и retention policies.
20. **Security**: ограничить CORS/headers в auth-host, добавить JWT rotation.

---

## Приложение: endpoints auth-host

| Method | Path (as declared) | Location |
| --- | --- | --- |
| GET | `(empty string path)` | `platform/auth-host/app/api/routes/admin_users.py:45` |
| POST | `(empty string path)` | `platform/auth-host/app/api/routes/admin_users.py:62` |
| POST | `/authorize` | `platform/auth-host/app/transactions.py:19` |
| POST | `/capture` | `platform/auth-host/app/transactions.py:85` |
| GET | `/health` | `platform/auth-host/app/api/routes/auth.py:71` |
| GET | `/health` | `platform/auth-host/app/api/routes/health.py:8` |
| POST | `/login` | `platform/auth-host/app/api/routes/auth.py:118` |
| GET | `/me` | `platform/auth-host/app/api/routes/auth.py:174` |
| GET | `/public-key` | `platform/auth-host/app/api/routes/auth.py:76` |
| POST | `/register` | `platform/auth-host/app/api/routes/auth.py:83` |
| POST | `/reverse` | `platform/auth-host/app/transactions.py:112` |
| POST | `/terminal-auth` | `platform/auth-host/app/api/routes/processing.py:19` |
| POST | `/terminal-capture` | `platform/auth-host/app/api/routes/processing.py:47` |
| PATCH | `/{user_id}` | `platform/auth-host/app/api/routes/admin_users.py:100` |


## Приложение: endpoints ai-service

| Method | Path (as declared) | Location |
| --- | --- | --- |
| POST | `/` | `platform/ai-services/risk-scorer/app/api/v1/score.py:15` |
| GET | `/health` | `platform/ai-services/risk-scorer/app/api/v1/health.py:6` |
| GET | `/live` | `platform/ai-services/risk-scorer/app/api/v1/health.py:11` |
| GET | `/ready` | `platform/ai-services/risk-scorer/app/api/v1/health.py:16` |

---

## Итоговая таблица статуса компонентов

| Component | Status | Notes | Ports |
| --- | --- | --- | --- |
| core-api | ✅ | Healthy, миграции стабилизированы, health/metrics доступны. | 8001→8000 |
| gateway | ✅ | Проксирование /api/core, /api/auth, /api/ai и SPA. | 80 |
| admin-web | ✅ | Build проходит, payouts выровнены. | 4173 |
| client-web | ✅ | Build проходит, TS guards добавлены. | 4174 |
| auth-host | 🟡 | Запускается, без Alembic миграций. | 8002→8000 |
| ai-service | 🟡 | Запускается, stub/риск-скоры. | 8003→8000 |
| workers / beat | 🟡 | Работают, расписание beat требует явного импорта. | — |
| flower | ✅ | UI мониторинга Celery доступен. | 5555 |
| postgres | ✅ | Основная БД. | 5432 |
| redis | ✅ | Брокер/кеш Celery. | 6379 |
| minio / minio-init | ✅ | S3-сторидж и инициализация бакетов. | 9000/9001 |
| prometheus | 🟡 | Scrape работает, auth-host metrics отсутствуют. | 9090 |
| grafana | 🟡 | Дашборды доступны, требуют настройки. | 3000 |
| jaeger / otel-collector | 🟡 | Инфра поднята, трассировки не везде включены. | 16686 / 4317 |
| crm-service / logistics-service / document-service | ❌ | Заглушки (alpine sleep). | — |
