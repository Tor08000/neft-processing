# Changelog

## v0.1.3
- Migrated all FastAPI services to the lifespan API, replacing deprecated `startup`/`shutdown` events and preserving existing
  initialization flows.
- Updated test clients to run application lifespan contexts reliably during API-level checks.
- Cleaned up lingering FastAPI/Pydantic deprecations and refreshed documentation for the migration.

## v0.1.2
- Admin schemas switched to Pydantic v2-style configuration with `ConfigDict` and `field_validator`, reducing deprecated warnings in tests and preparing the API for framework upgrades.

## v0.1.1
- Milestone v0.1.1 — Admin UI stable, TS filters synced, gateway stabilized.
- Admin UI builds cleanly with TypeScript validation and synced OperationQuery interface (including date aliases).
- Gateway `/admin/` routing stabilized for SPA behavior; backend operations, billing, and clearing endpoints aligned with admin-web expectations.
- End-to-end flow verified (Auth → Capture → Billing summary → Clearing batches); diagnostic snapshot tooling extended.
- Annotated tag `v0.1.1` created; see `docs/releases/v0.1.1.md` for full release notes.

## v0.1.0-admin-ui-online
- Поднята локальная среда со всеми сервисами (Postgres, Redis, Core API, Auth Host, AI Service, Workers, Nginx/Gateway).
- Админ-панель доступна по `http://localhost/admin/`, авторизация через переменные `ADMIN_EMAIL` и `ADMIN_PASSWORD`.
- API проходит базовые health-check проверки, стабильная работа подтверждена.
- Добавлен обновлённый набор диагностик и пример снапшота в `docs/diag/`.
- README дополнен инструкциями по локальному запуску, входу в админку и съёму снапшотов.
