# Core API: руководство по миграциям БД

Все команды используют единый DSN из переменной окружения `DATABASE_URL`. В docker-compose для `core-api` он задан как `postgresql+psycopg://neft:neft@postgres:5432/neft` и совпадает с настройками приложения.

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
