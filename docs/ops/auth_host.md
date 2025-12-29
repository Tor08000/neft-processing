# Auth-host operations

## Миграции

### Запуск миграций вручную

```bash
cd platform/auth-host
alembic -c alembic.ini upgrade head
```

### Проверка текущей версии

```bash
cd platform/auth-host
alembic -c alembic.ini current
alembic -c alembic.ini heads
```

### Проверка таблиц

```bash
psql "$DATABASE_URL" -c "SELECT to_regclass('public.users'), to_regclass('public.user_roles');"
```

## Метрики

### Проверка /metrics

```bash
curl -s http://localhost:8000/metrics | grep auth_host_up
```

### Ожидаемые метрики

- `auth_host_up`
- `auth_host_http_requests_total{method,path,status}`
- `auth_host_http_request_duration_seconds_bucket` (если включены buckets)

## Типовые ошибки

- `alembic.util.exc.CommandError`: проверьте переменную `DATABASE_URL`/`AUTH_DB_DSN` и доступность Postgres.
- `relation "users" does not exist`: не выполнены миграции (`alembic upgrade head`).
