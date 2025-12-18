# Core API: руководство по миграциям БД

Все команды используют единый DSN из переменной окружения `DATABASE_URL`. В docker-compose для `core-api` он задан как `postgresql+psycopg://neft:neft@postgres:5432/neft` и совпадает с настройками приложения.

## Проверка текущей ревизии

```bash
docker compose exec core-api alembic -c app/alembic.ini current
```

## Применение всех миграций

```bash
docker compose exec core-api alembic -c app/alembic.ini upgrade head
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
