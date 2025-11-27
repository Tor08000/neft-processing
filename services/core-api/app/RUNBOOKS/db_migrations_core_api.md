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
