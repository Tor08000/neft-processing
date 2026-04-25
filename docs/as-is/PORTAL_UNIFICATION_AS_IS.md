# Portal Unification — AS-IS

## Summary

- Client Portal и Partner Portal — отдельные фронтенды, но оба используют общий bootstrap `GET /api/core/portal/me`.
- `/api/core/portal/me` возвращает `actor_type`, `org_roles`, `capabilities`, `subscription`, `scopes`, `flags` и snapshot entitlements; используется как базовый источник прав в UI.
- `org_roles` и `capabilities` формируются из entitlements snapshot (если есть) с fallback на роли в токене.
- Для CLIENT orgs `portal/me` включает `org.org_type`; client shell derives `INDIVIDUAL` vs `BUSINESS` composition from that bootstrap field instead of inventing a second client-kind source.
- Billing enforcement по-прежнему применяется в клиентских потоках, partner-capabilities не блокируются billing policy.
- Для PARTNER orgs `portal/me` включает `partner.profile`/`partner.status` и partner-capabilities (`PARTNER_CORE`, `PARTNER_CATALOG`, `PARTNER_ORDERS`, `PARTNER_ANALYTICS`).

## Current Entry Points

- Canonical bootstrap SSoT: `GET /api/core/portal/me`.
- Compatibility-full wrapper: `GET /api/core/client/me` (совместимый слой с полным `PortalMeResponse` поверх `portal/me`; не второй canonical endpoint).
- Compatibility projection: `GET /api/core/partner/me` (совместимый слой поверх `portal/me` с урезанным partner payload; не SSoT для `access_state`/UI gating).
- Canonical client business namespace: `GET /api/core/client/*`.
- Partner core business namespace: `GET /api/core/partner/*` (profile/offers/orders/analytics).
- Canonical authenticated client onboarding: frontend `/onboarding*` + backend `/api/core/client/onboarding/*`; legacy `/connect*` stays redirect-only.
- Legacy non-bootstrap profile endpoint: `GET /api/v1/client/me`.
- Legacy business portal surfaces: `/api/client/*` и `/api/partner/*` из `portal.py`.
  Client diagnosis status in the current repo:
  - `/api/client/invoices*` stays explicit because it still serves the legacy `invoice_ref`/`Invoice` contour, not the canonical subscription invoice owner.
  - `/api/client/fleet*` stays explicit because it is still the mounted fleet owner surface in the current topology; repo-visible fleet tests/scenarios confirm it is not parity-ready for a core-prefixed handoff yet.
  - `/api/client/onboarding/state|step` stays explicit as commercial-layer compatibility state endpoints, not the primary onboarding owner.
- SPA entrypoints остаются отдельными (`/client/*`, `/partner/*`).
## Access Model

- `org_roles` и `capabilities` приходят из entitlements snapshot и используются для построения секций меню.
- Навигационные секции рассчитываются по capabilities (`CLIENT_*`, `PARTNER_*`).
- При отсутствии snapshot используется fallback на роли из токена (CLIENT/PARTNER).

## UX последствия

- Навигация и bootstrap gating должны строиться из единого ответа `portal/me`; compatibility-вью `/client/me` и `/partner/me` не должны восприниматься как равноправные bootstrap контракты.
- Frontend-оболочки остаются разными, поэтому единый entrypoint `/portal/` ещё не включён.
