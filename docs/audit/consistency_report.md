# Consistency report (NEFT Processing)

Артефакт первого прохода инвентаризации. Фиксирует карту сервисов и выявленные несостыковки, которые нужно закрыть, чтобы cold start был детерминированным.

## Карта сервисов (docker-compose.yml)

| Сервис | Порт(ы) | Зависимости | Точка входа / важные параметры |
| --- | --- | --- | --- |
| postgres | 5432 | — | `POSTGRES_*`, том `postgres-data`, healthcheck `pg_isready` |
| redis | 6379 | — | `redis-server --appendonly yes --databases 4`, healthcheck `redis-cli ping` |
| minio | 9000/9001 | — | healthcheck `curl /minio/health/live` |
| core-api | 8001 -> 8000 | postgres, redis | `entrypoint.sh` → wait-for-psql → `alembic upgrade head` → uvicorn; health `/health` |
| auth-host | 8002 -> 8000 | postgres, redis | uvicorn on 8000, health `/api/v1/health` |
| ai-service | 8003 -> 8000 | redis | health `/api/v1/health` |
| workers | — | core-api (healthy), redis | Celery worker (no DB_URL), shared image с beat |
| beat | — | core-api (healthy), redis | Celery beat (`CELERY_BEAT=true`) |
| flower | 5555 | redis | `celery flower` with basic auth; health via `/api/workers` |
| admin-web | 4173 -> 80 | — | Nginx serving Vite bundle; health `/health` |
| client-web | 4174 -> 80 | — | Nginx serving Vite bundle; health `/health` |
| gateway | 80 | core-api, auth-host, ai-service | Nginx, health `/health`, metrics `/metrics` |
| otel-collector | 4317 | — | loads `/etc/otel-collector-config.yaml` |
| jaeger | 16686/14250 | otel-collector | health `/` |
| prometheus | 9090 | gateway | health `/-/healthy` |
| grafana | 3000 | prometheus | health `/health` |
| crm/logistics/document | — | — | alpine placeholder, health `echo ok` |

## Несостыковки и дыры

| Проблема | Где | Симптом | Причина | Фикс | Тест |
| --- | --- | --- | --- | --- | --- |
| Нет прокси для большинства admin API | `gateway/nginx.conf` | Любой запрос к `/admin/api/v1/...` (кроме `auth`/`admin` блочного) уходит в статику `admin-web` → 404/SPA вместо JSON | Есть правила только для `/admin/api/v1/auth` и `/admin/api/v1/admin`, остальные пути матчятся `location /admin/` | Добавить явное правило `location /admin/api/v1/ { proxy_pass http://core_api/; }` + перенести auth/admin правила выше fallback | `curl -i http://localhost/admin/api/v1/health` → 200 JSON |
| Фронты не получают VITE_API_BASE_URL | `docker-compose.yml`, `frontends/*/src/api*.ts` | Сборка берёт `http://localhost` как базу API и склеивает с `/admin`/`/client`; при нестандартном хосте/HTTP(S) получаем CORS/404, а базовая переменная в Compose (`VITE_CORE_API_URL`) не используется кодом | В коде фронтов используется только `VITE_API_BASE_URL`, но Compose передаёт другие имена (`VITE_CORE_API_URL`, `VITE_AUTH_HOST_URL`, `VITE_AI_SERVICE_URL`) | Прописать `VITE_API_BASE_URL=http://gateway` (или `${PUBLIC_GATEWAY_ORIGIN}`) для обоих фронтов и удалить неиспользуемые `VITE_*_URL`, либо адаптер в коде | Проверить `npm run build` → `dist/assets/index-*.js` содержит правильный `BASE_URL`, затем `curl -I http://localhost/admin/api/v1/health` отдаёт JSON без CORS |
| Дубли/дрейф путей API | `gateway/nginx.conf`, `auth-host/app/settings.py` | Разные сервисы ожидают разные базовые URL: `CORE_API_URL` в auth-host по умолчанию `.../api/v1`, gateway проксирует `/api/v1/` и `/api/core/`, фронт склеивает `/admin/api/v1` | Отсутствует единый контракт (prefix `/api/v1` через gateway) | Зафиксировать договор: gateway принимает `/api/v1/*` и `/auth/api/v1/*`, фронты ходят в `/admin/api/v1`/`/client/api/v1` (через прокси к core/auth), переменные `CORE_API_URL`/`VITE_API_BASE_URL` указывают на gateway-URL без лишних сегментов | `docker compose up -d`, `curl -i http://localhost/api/v1/health` → 200; `curl -i http://localhost/admin/api/v1/health` → 200 (через gateway → core-api) |
| Нет smoke-пакета на целостность после cold start | tests отсутствуют вне core-api | После `docker compose up -d --build` нет автоматической проверки доступности gateway/UI/миграций; баги ловятся вручную | Тесты разбросаны, нет набора `smoke` в корне | Добавить `tests/smoke/test_bootstrap.py` с проверками: `/health`, `/admin/`, `/admin/assets/...`, `/api/v1/health`, alembic `upgrade --sql` idempotent | `pytest tests/smoke -q` под контейнером или локально с `DOCKER_HOST` |

## Следующие шаги (минимум)

1. Исправить `gateway/nginx.conf` и переменные фронтов (см. таблицу выше).
2. Добавить smoke-тесты, чтобы DoD A/B/C/D можно было прогонять одной командой.
3. Пересобрать runbook-ы: единственный список команд для Windows CMD, отдельная инструкция по UI debug, обновить миграции core-api с фокусом на `NEFT_DB_SCHEMA`.
