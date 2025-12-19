# Windows CMD quickstart (cold start / smoke)

Набор повторяемых команд для запуска и быстрой проверки NEFT Processing под Windows CMD. Предполагается установленный Docker Desktop (Compose V2 доступен как `docker compose` и `docker-compose.exe`).

## Поднять стенд “с нуля”

```cmd
REM 1) сбросить тома и контейнеры
docker compose down -v

REM 2) пересобрать и запустить
docker compose up -d --build

REM 3) убедиться, что сервисы запустились
docker compose ps
```

Если используется CLI v1, все команды выше можно выполнить как `docker-compose.exe ...`.

## Быстрая диагностика после старта

```cmd
REM Gateway и UI
curl -i http://localhost/health
curl -i http://localhost/admin/
curl -i http://localhost/client/

REM API через gateway
curl -i http://localhost/api/v1/health
curl -i http://localhost/admin/api/v1/health

REM Postgres список таблиц и версия Alembic
docker compose exec -T postgres psql -U neft -d neft -c "\dt"
docker compose exec -T postgres psql -U neft -d neft -c "select * from public.alembic_version;"
```

## Просмотр логов ключевых сервисов

```cmd
docker compose logs -f gateway
docker compose logs -f core-api
docker compose logs -f auth-host
docker compose logs -f admin-web
docker compose logs -f client-web
```

## Ручной прогон миграций (core-api)

```cmd
docker compose exec core-api alembic -c app/alembic.ini current
docker compose exec core-api alembic -c app/alembic.ini upgrade head
```

## Мини-smoke пакет (без pytest)

```cmd
REM ассеты админки
curl -I http://localhost/admin/
curl -I http://localhost/admin/assets/ -H "Accept: text/html"

REM health основных API
curl -i http://localhost/api/v1/health
curl -i http://localhost/admin/api/v1/health

REM Celery Flower
curl -i http://localhost:5555/api/workers
```

## Сброс данных

```cmd
docker compose down -v
```

Эти команды совпадают с секциями Definition of Done: cold start, UI доступность, миграции, healthchecks.
