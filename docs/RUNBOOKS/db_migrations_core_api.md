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
