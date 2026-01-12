# Core API: руководство по миграциям БД

Все команды используют единый DSN из переменной окружения `DATABASE_URL`. В docker-compose для `core-api` он задан как `postgresql+psycopg://neft:neft@postgres:5432/neft` и совпадает с настройками приложения.

Если меняли Alembic-хелперы (например, `app/alembic/helpers.py`), обязательно пересоберите образ без кэша:

```bash
docker compose build --no-cache core-api
```

## Полный сценарий восстановления

1. Предзагрузить базовые образы, чтобы сборка не падала на `load metadata for ...`:

```bash
bash scripts/pull_base_images.sh
# или
make prepull-base-images
# или вручную:
docker pull python:3.11-slim
docker pull node:20-alpine
docker pull nginx:1.27-alpine
```

2. Пересоздать стенд с чистыми томами и пересборкой сервисов:

```bash
docker compose down -v
docker compose up -d --build
docker compose logs --tail=200 core-api
```

3. Убедиться, что схема и версии применены:

```bash
docker compose exec -T postgres psql -U neft -d neft -c "select table_name from information_schema.tables where table_schema='public' order by 1;"
docker compose exec -T postgres psql -U neft -d neft -c "select * from public.alembic_version_core;"
docker compose exec -T postgres psql -U neft -d neft -c "select * from public.alembic_version_auth;"
```

### Windows CMD

```cmd
docker-compose.exe pull python:3.11-slim
docker-compose.exe pull node:20-alpine
docker-compose.exe pull nginx:1.27-alpine
docker-compose.exe down -v
docker-compose.exe up -d --build
docker-compose.exe logs --tail=200 core-api
docker-compose.exe exec -T postgres psql -U neft -d neft -c "select table_name from information_schema.tables where table_schema='public' order by 1;"
docker-compose.exe exec -T postgres psql -U neft -d neft -c "select * from public.alembic_version_core;"
docker-compose.exe exec -T postgres psql -U neft -d neft -c "select * from public.alembic_version_auth;"
```

## Миграция существующей dev БД (после разделения alembic_version)

### Быстрый dev reset (данные не важны)

```bash
docker compose down -v
docker compose up -d postgres
docker compose up -d core-api auth-host
```

### Аккуратный переход без сброса данных

1. Проверить, что старая таблица не используется и есть ли в ней записи:

```bash
docker compose exec -T postgres psql -U neft -d neft -c "select table_schema, table_name from information_schema.tables where table_name='alembic_version' order by 1;"
docker compose exec -T postgres psql -U neft -d neft -c "select * from public.alembic_version;"
```

2. Создать/зафиксировать версии для core-api и auth-host через stamp:

```bash
docker compose exec core-api alembic -c app/alembic.ini stamp head
docker compose exec auth-host alembic -c /app/alembic.ini stamp head
```

3. Убедиться, что создались новые таблицы версий:

```bash
docker compose exec -T postgres psql -U neft -d neft -c "select table_schema, table_name from information_schema.tables where table_name in ('alembic_version_core','alembic_version_auth') order by 1,2;"
docker compose exec -T postgres psql -U neft -d neft -c "select * from public.alembic_version_core;"
docker compose exec -T postgres psql -U neft -d neft -c "select * from public.alembic_version_auth;"
```

4. (Опционально) Если `public.alembic_version` больше не нужен, можно удалить:

```bash
docker compose exec -T postgres psql -U neft -d neft -c "drop table if exists public.alembic_version;"
```

## Быстрый smoke-check разделённых таблиц версий

```bash
make alembic-version-check
```

Ручной эквивалент:

```bash
docker compose exec -T postgres psql -U neft -d neft -c "select table_schema, table_name from information_schema.tables where table_name in ('alembic_version_core','alembic_version_auth') order by 1,2;"
docker compose exec -T postgres psql -U neft -d neft -c "select * from public.alembic_version_core;"
docker compose exec -T postgres psql -U neft -d neft -c "select * from public.alembic_version_auth;"
docker compose exec -T postgres psql -U neft -d neft -c "select version_num from public.alembic_version_core where version_num like '%auth%';"
docker compose exec -T postgres psql -U neft -d neft -c "select version_num from public.alembic_version_auth where version_num like '%core%';"
```

## Проверка текущей ревизии

```bash
docker compose exec core-api alembic -c app/alembic.ini current
```

```bash
docker compose exec core-api alembic -c app/alembic.ini heads
docker compose exec core-api alembic -c app/alembic.ini history
```

## Применение всех миграций

```bash
docker compose exec core-api alembic -c app/alembic.ini upgrade head
```

Для диагностики без применения DDL можно сгенерировать SQL:

```bash
docker compose exec core-api alembic -c app/alembic.ini upgrade head --sql
```

Команды нужно выполнять из корня репозитория, при запущенных контейнерах docker compose.

## Подключение к базе через psql

### Linux/macOS (bash/zsh)

```bash
docker compose exec postgres psql -U neft -d neft
# пример разового запроса
docker compose exec postgres psql -U neft -d neft -c "SELECT * FROM operations LIMIT 5;"
```

### Windows CMD

```cmd
docker-compose.exe exec postgres psql -U neft -d neft
REM пример разового запроса
docker-compose.exe exec postgres psql -U neft -d neft -c "SELECT * FROM operations LIMIT 5;"
```

Быстрые проверки схемы:

```cmd
REM перечень таблиц
docker-compose.exe exec postgres psql -U neft -d neft -c "\\dt"
REM убедиться, что ключевые таблицы существуют
docker-compose.exe exec postgres psql -U neft -d neft -c "SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name IN ('operations','accounts','limit_configs','ledger_entries');"
```
