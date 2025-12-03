# Changelog

# v0.1.4
- Added local observability stack (OTLP collector, Jaeger, Prometheus, Grafana) with provisioned dashboards.
- Introduced environment profile scaffolding (local/dev/staging) across Python services.
- Hardened gateway logging with JSON access logs including upstream timings.
- Added Alembic helper scripts for migration state safety checks.

## v0.1.3
- Migrated FastAPI services to the lifespan API, replacing deprecated `startup`/`shutdown` events while preserving initialization flows.
- Updated test clients to run application lifespan contexts reliably during API-level checks and tightened resource teardown across services.
- Cleaned up lingering FastAPI/Pydantic deprecations and refreshed documentation for the migration (core-api + auth-host/workers/ai-service shims).

## v0.1.2
- Admin schemas switched to Pydantic v2-style configuration with `ConfigDict` and `field_validator`, reducing deprecated warnings in tests and preparing the API for framework upgrades.
- Admin-web optimized with React Query caching, lazy routing, and bundle-size reductions aligned with updated Operation/Billing/Clearing types.

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
