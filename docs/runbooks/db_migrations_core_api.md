# Core API DB migrations (repeatable flow)

Цель: сделать `alembic upgrade head` детерминированным как на чистой БД, так и при повторном запуске контейнера `core-api`.

## Контракты и переменные

- **DATABASE_URL** — единственный источник истины. Формат: `postgresql+psycopg://USER:PASSWORD@HOST:PORT/DB`.
- **NEFT_DB_SCHEMA** — опциональная схема (по умолчанию `public`). `entrypoint.sh` и `alembic/env.py` выставляют `search_path` только в эту схему и создают `alembic_version` там же (никаких fallback'ов).
- **ALEMBIC_CONFIG** — путь к конфигу (по умолчанию `app/alembic.ini` внутри контейнера).

## Команды (из корня репозитория)

```bash
# чистый старт с томов
docker compose down -v
docker compose up -d --build

# проверка состояния после старта
docker compose exec core-api alembic -c app/alembic.ini current
docker compose exec core-api alembic -c app/alembic.ini heads

# ручное применение (если нужно перезапустить без контейнера)
docker compose exec core-api alembic -c app/alembic.ini upgrade head
```

Windows CMD эквивалент: замените `docker compose` на `docker-compose.exe`.

## Smoke для схемы

```bash
docker compose exec -T postgres psql -U neft -d neft -c "select * from public.alembic_version;"
docker compose exec -T postgres psql -U neft -d neft -c "select to_regclass('public.operations');"
```

Если `NEFT_DB_SCHEMA` задан, меняем `public` на нужное значение.

## Проверка search_path/идемпотентности

```bash
# 1) захватить fingerprint
docker compose exec core-api python - <<'PY'
from app.diagnostics.db_state import log_fingerprint_from_url
log_fingerprint_from_url(label="pre-upgrade")
PY

# 2) повторный upgrade head (ожидаем "no changes")
docker compose exec core-api alembic -c app/alembic.ini upgrade head

# 3) убедиться, что revision не изменилась
docker compose exec core-api alembic -c app/alembic.ini current
```

## Типовые проблемы и решения

| Симптом | Причина | Действие |
| --- | --- | --- |
| `RuntimeError: DATABASE_URL is required` | env не передан в контейнер | Убедиться, что `.env` или compose содержит `DATABASE_URL` |
| `alembic_version` в `public`, а таблицы в другой схеме | `NEFT_DB_SCHEMA` отличен от search_path миграций | Запустить с корректным `NEFT_DB_SCHEMA`, проверить `log_fingerprint_from_url` |
| Несколько heads | Мерж-ревизии не объединены | Выполнить `alembic merge` (отдельная задача), до фикса не выпускать |

## Связанные файлы

- `platform/processing-core/app/alembic/env.py` — search_path + запрет offline.
- `platform/processing-core/entrypoint.sh` — порядок: resolve schema → wait-for-postgres → `alembic upgrade head` → `reset_engine()` → post-check на новом соединении (`operations` + `alembic_version` совпадает с head).
- `docs/audit/consistency_report.md` — актуальные несостыковки и фиксы.
