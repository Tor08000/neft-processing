# Runbook: миграции БД для core-api (NEFT Processing)

## 1. Назначение документа

Этот документ описывает, **как управлять миграциями базы данных** для сервиса `core-api`:

- как посмотреть текущую ревизию,
- как применить миграции,
- что делать при ошибках,
- минимальные проверки после изменений.

Сервис: **core-api**  
БД: **PostgreSQL** (контейнер `postgres` из `docker-compose.yml`)  
Миграции: **Alembic** (конфиг внутри `services/core-api/app`)

---

## 2. Где лежит Alembic

Каталог core-api:

```text
services/core-api/app/
    alembic.ini          # основной конфиг Alembic
    alembic/
        env.py           # точка входа для Alembic
        versions/
            2025_11_01_init.py
            20251112_0001_core.py
            ...

Alembic запускается из контейнера `core-api`. Конфиг `alembic.ini` в контейнере
лежит по пути `/app/app/alembic.ini` (мы передаём его через `-c app/alembic.ini`).

---

## 3. Подготовка окружения

1. Соберите и поднимите docker-compose (Postgres нужен здоровым):

   ```bash
   docker compose up -d
   ```

2. **DSN для БД**: Alembic использует переменную `DATABASE_URL`, а её значение по
   умолчанию берётся из `app.db` (тот же URL, что и у приложения). Мы также
   пробрасываем `DATABASE_URL` в `docker-compose.yml`, поэтому внутри контейнера
   уже будет строка вида `postgresql+psycopg://neft:neft@postgres:5432/neft`.

---

## 4. Базовые команды

Все команды выполняются из корня репозитория.

- Проверить текущую ревизию:

  ```bash
  docker compose exec core-api alembic -c app/alembic.ini current
  ```

- Применить миграции до последней версии:

  ```bash
  docker compose exec core-api alembic -c app/alembic.ini upgrade head
  ```

---

## 5. Развёртывание на чистой базе

Init-скрипты из `db/init/*.sql` теперь считаются **легаси**: базовая схема
разворачивается через Alembic. Для нового стенда достаточно иметь пустую БД и
выполнить:

```bash
docker compose exec core-api alembic -c app/alembic.ini upgrade head
```

После этого таблицы `operations`, `limits_rules`, `merchants`, `terminals`,
`billing_summary` и прочие будут созданы автоматически.

---

## 6. Проверки после миграций

1. Убедиться, что Alembic показывает актуальную ревизию (например,
   `20260101_0008_billing_summary`).
2. Быстро проверить API-здоровье:

   ```bash
   curl "http://localhost:8001/api/v1/health"
   ```
3. При необходимости выполнить smoke-тесты выборки:

   ```bash
   curl "http://localhost:8001/api/v1/cards?limit=5"
   curl "http://localhost:8001/api/v1/operations?limit=5"
   ```
