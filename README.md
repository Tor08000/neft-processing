NEFT Processing — локальная среда: Postgres, Redis, Core API, Auth Host, AI Service, Workers, Nginx.

## Как поднять систему локально

1. Скопируйте переменные окружения: `cp -n .env.example .env`.
2. Заполните доступы администратора в `.env` (значения хранятся только локально):
   - `ADMIN_EMAIL`
   - `ADMIN_PASSWORD`
3. Соберите и поднимите сервисы: `docker compose up -d --build`.
4. Проверьте доступность сервисов:
 - Core API напрямую: `http://localhost:8001/api/v1/health`
  - Через gateway: `http://localhost/api/core/api/v1/health`
  - Admin UI: `http://localhost/admin/`
  - Client UI: `http://localhost/client/`
5. Для локальной наблюдаемости поднимите инструменты: `docker compose up -d otel-collector jaeger prometheus grafana` (Grafana: `http://localhost:3000`, логин/пароль `admin/admin`).

### Вход в админ-панель

- Откройте `http://localhost/admin/`.
- В форме логина используйте значения из `.env` (`ADMIN_EMAIL` и `ADMIN_PASSWORD`).
- После входа доступен журнал операций и остальные разделы админки.

### Работа со снапшотами

- Для фиксации состояния используйте `python docs/diag/inspect_neft_repo.py`.
- Отчёты сохраняются в `docs/diag/neft_state_YYYYMMDD_HHMM.txt` (пример: `docs/diag/neft_state_2025-12-02.txt`).
- Подробная инструкция: `docs/diag/README.md`.

### Админский токен для локальной разработки

1) Убедитесь, что в `.env` прописаны `ADMIN_EMAIL` и `ADMIN_PASSWORD` (по умолчанию `admin@example.com` / `admin123`).
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
  * Пароль: `admin`
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
* Демо-креды: `client@neft.local` / `client` (значения можно изменить в `.env`).
* Что внутри: операции, лимиты и дашборд читают реальные записи из БД (`client_operations`, `client_limits`, `client_cards`).
* Быстрый старт:
  1. `cp -n .env.example .env` и при необходимости скорректируйте `DEMO_CLIENT_*`.
  2. `docker compose up -d --build`.
  3. Откройте клиентский портал, авторизуйтесь демо-клиентом — увидите seeded-операции/лимиты из базы.
* Навигация включает "Дашборд", "Операции" и "Лимиты"; все запросы уходят на `/client/api/v1/...` через gateway.
* Для демо-доступа используется единый аккаунт клиента (по умолчанию `client@neft.local / client`). Креды можно переопределить через
  переменные окружения `DEMO_CLIENT_EMAIL` и `DEMO_CLIENT_PASSWORD` в `.env`.
* Авторизация клиентских API защищена JWT: логин по пути `/client/api/v1/auth/login`, последующие запросы к `/client/api/v1/client/*`
  выполняются с заголовком `Authorization: Bearer <token>`; при 401/403 клиент сбрасывает токен и возвращает пользователя на экран логина.
* Базовый сценарий: форма логина → получение токена `auth-host` → загрузка дашборда и списков операций/лимитов по организации.

### Разделение публичного и admin API

* Публичные ручки Core API остаются в пространстве `/api/core/api/v1/*`.
* Все административные операции теперь живут под префиксом `/api/core/api/v1/admin/*` и требуют admin JWT.
* Admin Web клиент обновлён на использование нового префикса, поэтому старая схема путей `/api/core/api/v1/admin/...` остаётся единственной точкой входа.

### Gateway (Nginx)

* Конфигурация: `services/gateway/nginx.conf` (прокси для `/admin/`, `/api/auth/`, `/api/core/`, `/api/ai/`, favicon и health).
* Dockerfile: `services/gateway/Dockerfile` (основан на `nginx:1.27-alpine`, копирует конфиг в контейнер и перенаправляет логи в stdout/stderr).
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

* Быстрая проверка очереди: `curl http://localhost:8001/api/v1/health/celery` (ping через Celery) либо `docker compose exec workers python - <<'PY'
from services.workers.app.celery_app import celery_app
print(celery_app.send_task("workers.ping", kwargs={"x": 1}).get(timeout=5))
PY`.
* Перезапуск воркеров при росте памяти: `docker compose restart workers`; параметр `CELERY_WORKER_MAX_TASKS_PER_CHILD` автоматически перезапускает процессы после 100 задач, что помогает сбрасывать утечки.
* Доступ в Flower (внутри сети Docker): откройте `http://flower:5555` и используйте логин/пароль из `FLOWER_BASIC_AUTH`. Для смены пароля пропишите новое значение в `.env` и перезапустите `docker compose up -d flower`.

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
