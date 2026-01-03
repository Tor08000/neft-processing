NEFT Processing — локальная среда: Postgres, Redis, Core API, Auth Host, AI Service, Workers, Nginx.

## AS-IS документация

* Master doc: `docs/as-is/NEFT_PLATFORM_AS_IS_MASTER.md`

## Как поднять систему локально

1. Скопируйте переменные окружения:
   - Windows CMD: `if not exist .env copy .env.example .env`
   - Linux/macOS: `cp -n .env.example .env`
2. В файле `.env` замените плейсхолдеры `change-me` (например, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `NEFT_S3_ACCESS_KEY`, `NEFT_S3_SECRET_KEY`) на реальные значения.
3. Заполните доступы администратора в `.env` (значения хранятся только локально):
   - `AUTH_BOOTSTRAP_ENABLED=1`
   - `AUTH_BOOTSTRAP_ADMIN_EMAIL` (fallback: `ADMIN_EMAIL`, пример: `admin@example.com`)
   - `AUTH_BOOTSTRAP_ADMIN_PASSWORD` (fallback: `ADMIN_PASSWORD`, пример: `change-me`)
   - `AUTH_BOOTSTRAP_ADMIN_ROLES=ADMIN,PLATFORM_ADMIN,SUPERADMIN`
   Эти переменные используются для автоматического создания/обновления администратора при старте `auth-host` (идемпотентно, не затирает пароль существующего пользователя).
4. Соберите и поднимите сервисы: `docker compose up -d --build`.
5. Проверьте доступность сервисов через gateway и напрямую:
 - Gateway health: `http://localhost/health`
  - Core API напрямую: `http://localhost:8001/health`
  - Core API через gateway: `http://localhost/api/core/health`
 - Auth напрямую: `http://localhost:8002/health`
  - Auth через gateway: `http://localhost/api/auth/health`
  - AI напрямую: `http://localhost:8003/health`
  - AI через gateway: `http://localhost/api/ai/api/v1/health`
  - Admin UI: `http://localhost/admin/`
  - Client UI: `http://localhost/client/`
5. Для локальной наблюдаемости поднимите инструменты: `docker compose up -d otel-collector jaeger prometheus grafana` (Grafana: `http://localhost:3000`, логин/пароль `admin/admin`).
   - Проверка Prometheus targets из контейнера: `make prometheus-smoke`
   - Мини-проверка DOWN targets: `curl http://localhost:9090/api/v1/targets | findstr /C:"\"health\":\"down\""` (не должно быть вывода)
6. Для обычной остановки используйте `docker compose down` (без `-v`), чтобы сохранить тома `postgres-data`, `minio-data` и `auth-keys`. Полная очистка с `docker compose down -v` удалит данные БД, ключи и файлы из MinIO.

### Endpoints & Ports

* Gateway health: `GET http://localhost/health`
* Core через gateway: `GET http://localhost/api/core/health` (OpenAPI/Swagger: `http://localhost/api/core/docs`)
* Core KPI/Achievements через gateway:
  * `GET http://localhost/api/core/kpi/summary?window_days=7`
  * `GET http://localhost/api/core/achievements/summary?window_days=7`

Пример ответа KPI:

```json
{
  "window_days": 7,
  "as_of": "2026-01-01T00:00:00Z",
  "kpis": [
    {
      "key": "billing_errors",
      "title": "Billing errors",
      "value": 0,
      "unit": "count",
      "delta": -12.4,
      "good_when": "down",
      "target": 0,
      "progress": 1.0,
      "meta": { "source": "billing_job_runs" }
    }
  ]
}
```

Пример ответа Achievements:

```json
{
  "window_days": 7,
  "as_of": "2026-01-01T00:00:00Z",
  "badges": [
    {
      "key": "clean_billing",
      "title": "Чистый биллинг",
      "description": "0 критических ошибок за неделю",
      "status": "unlocked",
      "progress": 1.0,
      "how_to": "Держите billing_errors=0 за период",
      "meta": { "window_days": 7 }
    }
  ],
  "streak": {
    "key": "no_critical_errors",
    "title": "Серия без ошибок",
    "current": 7,
    "target": 7,
    "history": [true, true, true, true, true, true, true],
    "status": "unlocked",
    "how_to": "Ежедневно без критических ошибок"
  }
}
```
* Auth через gateway: `GET http://localhost/api/auth/health` (Swagger: `http://localhost/api/auth/docs`)
* AI через gateway: `GET http://localhost/api/ai/api/v1/health` (Swagger: `http://localhost/api/ai/api/v1/docs`)
* Сервисы напрямую (диагностика): core-api `http://localhost:8001/health`, auth-host `http://localhost:8002/health`, ai-service `http://localhost:8003/health`

### Хранение ключей и файлов

* Ключи RSA для `auth-host` сохраняются в volume `auth-keys` (`/data/keys`), поэтому перезапуск без `-v` не ломает уже выданные токены. После `docker compose down -v` ключи пересоздаются автоматически.
* Данные MinIO лежат в `minio-data`; бакеты создаются при старте `minio-init` (используются переменные `NEFT_S3_*` из `.env`, включена идемпотентная настройка версиирования и политик доступа). `minio-init` — одноразовый job: после сообщения `init complete` контейнер корректно завершается со статусом `Exited (0)`. Зелёный статус в `docker compose ps` важен для `minio-health` (который проверяет `http://minio:9000/minio/health/ready`); сам контейнер `minio` может быть без healthcheck, это нормально.

### Вход в админ-панель

- Откройте `http://localhost/admin/`.
- В форме логина используйте значения из `.env` (`ADMIN_EMAIL` и `ADMIN_PASSWORD`).
- После входа доступен журнал операций и остальные разделы админки.

### Работа со снапшотами

- Для фиксации состояния используйте `python docs/diag/inspect_neft_repo.py`.
- Отчёты сохраняются в `docs/diag/neft_state_YYYYMMDD_HHMM.txt` (пример: `docs/diag/neft_state_2025-12-02.txt`).
- Подробная инструкция: `docs/diag/README.md`.

### Админский токен для локальной разработки

1) Убедитесь, что в `.env` прописаны `ADMIN_EMAIL` и `ADMIN_PASSWORD` (например, `admin@example.com` / `change-me`).
2) Выполните в PowerShell/cmd: `scripts\get_admin_token.cmd`. Скрипт запросит `access_token` у auth-host через gateway (`/api/auth/api/v1/auth/login`), сохранит его в `.admin_token` и выведет команду `set TOKEN=...`.
3) Пример запроса к защищённой ручке через gateway:

```
call scripts\get_admin_token.cmd
curl -i "http://localhost/api/core/api/v1/admin/operations?limit=5" ^
  -H "Authorization: Bearer %TOKEN%"
```

### Admin Web — как зайти

* Запустить окружение:
  * `docker compose up -d --build`
* Открыть в браузере: `http://localhost/admin/` (или напрямую в контейнер admin-web: `http://localhost:4173/admin/`)
* В форме логина ввести:
  * Email: `admin@example.com`
  * Пароль: `change-me`
* После входа:
 * Отобразится журнал операций с пагинацией.
  * Все запросы идут через gateway:
    * `/api/auth/api/v1/auth/login`
    * `/api/core/api/v1/admin/operations`
* Клиент использует React Query для кэширования (операции: `staleTime=30s`, дашборд: `staleTime=5s`) и динамическую
  подгрузку страниц/тяжёлых компонентов через `React.lazy + Suspense`, чтобы ускорить initial load.

### Client Web — клиентский кабинет

* Запуск окружения с фронтом: `docker compose up -d --build gateway client-web` (или полный стек `docker compose up -d --build`).
* Открыть в браузере: `http://localhost/client/` (или напрямую через контейнер client-web: `http://localhost:4174/client/`).

### Клиентский кабинет (реальные данные)

* Доступ: `http://localhost/client/`.
* Демо-креды: `client@neft.local` / `change-me` (значения можно изменить в `.env`).
* Что внутри: операции, лимиты и дашборд читают реальные записи из БД (`client_operations`, `client_limits`, `client_cards`).
* Быстрый старт:
  1. `cp -n .env.example .env` и при необходимости скорректируйте `DEMO_CLIENT_*`.
  2. `docker compose up -d --build`.
  3. Откройте клиентский портал, авторизуйтесь демо-клиентом — увидите seeded-операции/лимиты из базы.
* Навигация включает "Дашборд", "Операции" и "Лимиты"; все запросы уходят на `/api/core/client/api/v1/...` через gateway.
* Для демо-доступа используется единый аккаунт клиента (по умолчанию `client@neft.local / change-me`). Креды можно переопределить через
  переменные окружения `DEMO_CLIENT_EMAIL` и `DEMO_CLIENT_PASSWORD` в `.env`.
* Авторизация клиентских API защищена JWT: логин по пути `/api/auth/api/v1/auth/login`, последующие запросы к `/api/core/client/api/v1/client/*`
  выполняются с заголовком `Authorization: Bearer <token>`; при 401/403 клиент сбрасывает токен и возвращает пользователя на экран логина.
* Базовый сценарий: форма логина → получение токена `auth-host` → загрузка дашборда и списков операций/лимитов по организации.

### Разделение публичного и admin API

* Gateway проксирует сервисы без перезаписи пути:
  * `/api/core/*` → core-api
  * `/api/auth/*` → auth-host
  * `/api/ai/*` → ai-service
* Админские и клиентские SPA остаются на путях `/admin/` и `/client/`, но их API-запросы идут через новые namespace'ы `/api/core/...` и `/api/auth/...`.
* Admin Web/Client Web собираются с `VITE_API_BASE_URL=http://gateway`, `VITE_CORE_API_BASE=/api/core`, `VITE_AUTH_API_BASE=/api/auth` и опираются на `BASE_URL` (`/admin/` и `/client/`) как единственный базовый путь SPA.

### Smoke-проверки (gateway, health, DB, merge markers)

Быстрый локальный прогон (Windows CMD):

```bat
docker compose up -d --build
pytest -q tests\test_no_merge_markers.py tests\test_smoke_gateway_routing.py
```
Запускайте `pytest` из корня репозитория, чтобы автоматически подхватывался `pytest.ini`.

KPI smoke (core-api напрямую):

```
make kpi-smoke
```

### Contract testing

* Политика контрактов и версионирования: `docs/ops/contract_testing.md`.
* Реестр событий: `docs/contracts/events/`.
* Запуск контрактных тестов:

```bash
pytest -m contracts
```

Полный smoke для биллинга/финансов (Windows CMD): `scripts\smoke_billing_v14.cmd` (логин → /auth/me → billing periods → billing run ADHOC → clearing → invoices/PDF → finance best-effort). Расширенный вариант с дополнительными шагами: `scripts\smoke_billing_finance.cmd`.

Docker smoke профайл (Linux/macOS): `docker compose -f docker-compose.yml -f docker-compose.smoke.yml --profile smoke up --build --abort-on-container-exit smoke-tests`.

Поиск маркеров конфликтов только в трекаемых файлах (без шума от `.venv` и прочего):

```
git grep -n "^\<\<\<\<\<\<\<\|^\=\=\=\=\=\=\=\|^\>\>\>\>\>\>\>" -- .
```

### Проверка миграций (single head)

Убедитесь, что у Alembic ровно один head (локально или в CI):

```
docker compose run --rm --entrypoint "" core-api sh -lc "alembic -c app/alembic.ini heads"
```
Ожидается ровно одна строка (единственный head).

### Проверка разделённых таблиц версий Alembic

Быстрый smoke для проверки того, что `core-api` и `auth-host` не делят историю:

```
make alembic-version-check
```

Ручной эквивалент:

```
docker compose exec -T postgres psql -U neft -d neft -c "select table_schema, table_name from information_schema.tables where table_name in ('alembic_version_core','alembic_version_auth') order by 1,2;"
docker compose exec -T postgres psql -U neft -d neft -c "select * from public.alembic_version_core;"
docker compose exec -T postgres psql -U neft -d neft -c "select * from public.alembic_version_auth;"
docker compose exec -T postgres psql -U neft -d neft -c "select version_num from public.alembic_version_core where version_num like '%auth%';"
docker compose exec -T postgres psql -U neft -d neft -c "select version_num from public.alembic_version_auth where version_num like '%core%';"
```

### Системный стенд-чеклист (Windows CMD)

Минимальный набор для фиксации статуса (запускать из корня репозитория):

```bat
docker compose up -d
docker compose ps

:: Health checks via gateway
curl http://localhost/api/core/health
curl http://localhost/metrics

:: Health checks (direct to core-api)
curl http://localhost:8001/api/core/health
curl http://localhost:8001/metrics

docker compose run --rm --entrypoint "" core-api sh -lc "alembic -c app/alembic.ini heads"
docker compose run --rm --entrypoint "" core-api sh -lc "alembic -c app/alembic.ini current"
docker compose run --rm --entrypoint "" core-api sh -lc "alembic -c app/alembic.ini history --verbose -r -50:"
docker compose exec -T postgres psql -U neft -d neft -c "select * from public.alembic_version_core;"
docker compose exec -T postgres psql -U neft -d neft -c "select * from public.alembic_version_auth;"
```

Gateway и direct ports отличаются. Используйте правильный URL для диагностики.

### Gateway (Nginx)

* Конфигурация: `gateway/nginx.conf` (прокси без rewrite для `/api/core/*`, `/api/auth/*`, `/api/ai/*`, статик `/admin/` и `/client/`, favicon и health).
* Dockerfile: `gateway/Dockerfile` (основан на `nginx:1.27-alpine`, копирует конфиг в контейнер и перенаправляет логи в stdout/stderr).
* Сборка и запуск:
  * `docker compose build gateway` — собрать образ с конфигом.
  * `docker compose up -d gateway` — поднять только gateway (или `docker compose up -d --build` для всей среды).
  * Альтернативно: `docker build -f services/gateway/Dockerfile -t neft-processing-gateway .`.

## Фоновые задачи и очереди (Celery / Redis / Flower)

* Workers и Beat запускаются через общий образ `services/workers` и точку входа `services/workers/entrypoint.sh`.
  * Очереди по умолчанию: `celery,default,limits,antifraud,reports` (список можно переопределить переменной `QUEUES`).
  * Лимиты надёжности: `worker_max_tasks_per_child=100`, `worker_prefetch_multiplier=1`, `task_soft_time_limit=240`, `task_time_limit=300`.
* Брокер и result backend разведены по разным Redis DB:
  * `CELERY_BROKER_URL=redis://redis:6379/0`
  * `CELERY_RESULT_BACKEND=redis://redis:6379/1`
  * Кэш/сессии сервисов используют `REDIS_URL=redis://redis:6379/2`, чтобы не конкурировать с очередями.
* Flower поднимается отдельным сервисом (`services/flower`) и теперь требует Basic Auth (`FLOWER_BASIC_AUTH`, по умолчанию `admin:change-me`). Порт наружу не публикуется, доступ возможен только из docker-сети (`http://flower:5555`); для внешнего доступа прокиньте порт вручную и задайте свои креды.

### Переменные окружения

* `CELERY_DEFAULT_QUEUE` — основная очередь (совпадает с exchange/routing key) по умолчанию `celery`.
* `CELERY_WORKER_MAX_TASKS_PER_CHILD` — сколько задач обрабатывает процесс worker перед перезапуском (борьба с утечками памяти).
* `CELERY_WORKER_PREFETCH_MULTIPLIER` — количество задач, которые воркер берёт наперёд (меньшее значение сглаживает нагрузку).
* `CELERY_TASK_SOFT_TIME_LIMIT` / `CELERY_TASK_TIME_LIMIT` — мягкий/жёсткий лимит времени на задачу (секунды).
* `FLOWER_BASIC_AUTH` — логин и пароль для Flower в формате `user:password`.
* `REDIS_URL` — URL Redis для кеша/сессий (не для Celery), по умолчанию выделенная DB `redis://redis:6379/2`.

### Отладка и диагностика Celery/Redis/Flower

* Быстрая проверка очереди: `curl http://localhost/api/core/health/celery` (ping через Celery) либо `docker compose exec workers python - <<'PY'
from services.workers.app.celery_app import celery_app
print(celery_app.send_task("workers.ping", kwargs={"x": 1}).get(timeout=5))
PY`.
* Перезапуск воркеров при росте памяти: `docker compose restart workers`; параметр `CELERY_WORKER_MAX_TASKS_PER_CHILD` автоматически перезапускает процессы после 100 задач, что помогает сбрасывать утечки.
* Доступ в Flower (внутри сети Docker): откройте `http://flower:5555` и используйте логин/пароль из `FLOWER_BASIC_AUTH`. Для смены пароля пропишите новое значение в `.env` и перезапустите `docker compose up -d flower`.

## Billing / Clearing / Invoicing (jobs)

Новые переменные окружения и флаги:

* `NEFT_COMMISSION_RATE` — ставка комиссии платформы (по умолчанию 0.01).
* `NEFT_BILLING_TZ` — часовой пояс биллинга (по умолчанию `UTC`).
* `NEFT_BILLING_DAILY_ENABLED` — включить дневную агрегацию биллинга.
* `NEFT_CLEARING_DAILY_ENABLED` — включить дневной клиринг.
* `NEFT_INVOICE_MONTHLY_ENABLED` — включить генерацию ежемесячных счетов.
* `NEFT_BILLING_FINALIZE_GRACE_HOURS` — сколько часов ожидать перед финализацией дня (late events), по умолчанию 12.
* `NEFT_BILLING_DAILY_AT` / `NEFT_CLEARING_DAILY_AT` / `NEFT_INVOICE_MONTHLY_AT` — время запуска крон-задач (формат `HH:MM`).

Ручные запуски (Windows CMD):

```cmd
docker compose up -d --build
curl -X POST "http://127.0.0.1/api/core/admin/billing/run-daily?date=2025-12-19"
curl -X POST "http://127.0.0.1/api/core/admin/billing/finalize-day?date=2025-12-19"
curl -X POST "http://127.0.0.1/api/core/admin/clearing/run-daily?date=2025-12-19"
curl -X POST "http://127.0.0.1/api/core/admin/billing/invoices/run-monthly?month=2025-12"
```
Ручной billing run (MVP) через admin API:

```bash
curl -X POST "http://localhost/api/core/api/v1/admin/billing/run" \
  -H "Content-Type: application/json" \
  -d '{"period_type":"ADHOC","start_at":"2025-12-01T00:00:00Z","end_at":"2025-12-31T23:59:59Z","tz":"UTC","client_id":null}'
```

Статусные заметки и контрольный список: `docs/status/STATUS_20251220.md`.

Smoke/тесты (Windows CMD):

```cmd
pytest -q
pytest -q -m smoke
python -m pytest -q tests\test_alembic_single_head.py
```

Интеграционные тесты (compose profile `test` + Postgres/Redis/MinIO/auth/core):

```cmd
docker compose -f docker-compose.yml -f docker-compose.test.yml --profile test up -d --build
RUN_INTEGRATION_TESTS=1 pytest -m integration platform/processing-core/app/tests
```

## Общий Python-пакет `neft_shared`

В каталоге `shared/python` расположен пакет с общими настройками и логированием.

### Локальная установка

Для разработки установите пакет в editable-режиме из корня репозитория:

```bash
pip install -e shared/python
```

### Использование в сервисах

Сервисы `core-api`, `auth-host`, `ai-service` и `workers` подключают пакет как локальную зависимость через `pyproject.toml` (запись `"neft_shared @ file:../../shared/python"`). При установке зависимостей сервисов из корня репозитория пакет будет подтянут автоматически, а импорты доступны в коде как `from neft_shared...`.

## Releases

- **[v0.1.3](docs/releases/v0.1.3.md)** — рекомендованный стабильный релиз для локального и demo-развёртывания: миграция всех FastAPI-сервисов на `lifespan`, аккуратное завершение ресурсов, обновлённые схемы/типы и оптимизированный admin-web.
- [v0.1.1](https://github.com/Tor08000/neft-processing/releases/tag/v0.1.1) — стабильный билд admin-web с валидацией TypeScript, синхронизированным OperationQuery, SPA-маршрутизацией `/admin/` и подтверждённым end-to-end циклом (Auth → Operations → Billing → Clearing). Точка безопасного отката; подробности в `docs/releases/v0.1.1.md`.
