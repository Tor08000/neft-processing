# Portal Unification — AS-IS

## Summary

- Client Portal и Partner Portal — отдельные фронтенды, но оба используют общий bootstrap `GET /api/core/portal/me`.
- `/api/core/portal/me` возвращает `org_roles`, `capabilities`, `subscription` и snapshot entitlements; используется как базовый источник прав в UI.
- `org_roles` и `capabilities` формируются из entitlements snapshot (если есть) с fallback на роли в токене.
- Billing enforcement по-прежнему применяется в клиентских потоках, partner-capabilities не блокируются billing policy.

## Current Entry Points

- Unified bootstrap: `GET /api/core/portal/me`.
- Client legacy: `GET /api/core/client/me` (совместимый слой поверх `portal/me`).
- Partner legacy: `GET /api/core/partner/me` (совместимый слой поверх `portal/me`).
- SPA entrypoints остаются отдельными (`/client/*`, `/partner/*`).

## Access Model

- `org_roles` и `capabilities` приходят из entitlements snapshot и используются для построения секций меню.
- Навигационные секции рассчитываются по capabilities (`CLIENT_*`, `PARTNER_*`).
- При отсутствии snapshot используется fallback на роли из токена (CLIENT/PARTNER).

## UX последствия

- Навигация может быть построена из единого ответа `portal/me`, без отдельных `/client/me` или `/partner/me` вызовов.
- Frontend-оболочки остаются разными, поэтому единый entrypoint `/portal/` ещё не включён.
