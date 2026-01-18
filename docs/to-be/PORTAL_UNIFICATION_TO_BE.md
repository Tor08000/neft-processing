# Portal Unification — TO-BE

## Goals

- Единый портал NEFT (Portal UI + Portal API).
- Один аккаунт, один SSO, единый SSoT `/portal/me`.
- Доступ строится на `org.roles`, `user.roles` и entitlements snapshot.

## Canonical Model

### Organization Roles

- `org.roles[]` содержит `CLIENT` и/или `PARTNER`.
- Роли изменяются через admin commercial ops API.

### Capabilities

- `capabilities[]` вычисляются из org roles + entitlements + billing policy.
- Примеры:
  - `CLIENT_CORE`, `CLIENT_BILLING`, `CLIENT_ANALYTICS`
  - `PARTNER_CORE`, `PARTNER_PRICING`, `PARTNER_SETTLEMENTS`
  - `MARKETPLACE`, `LOGISTICS`

### Billing Enforcement

- `OVERDUE/SUSPENDED` блокирует client capability с `billing_scoped=CLIENT`.
- Partner capabilities не блокируются, если явно не запрещены моделью.

## Portal SSoT Endpoint

`GET /api/core/portal/me` возвращает:

- `user`
- `org`
- `org_roles[]`
- `user_roles[]`
- `subscription` (если есть CLIENT роль)
- `entitlements_snapshot`
- `capabilities[]`
- `nav_sections[]` (optional)

Backwards compatible wrappers:

- `GET /api/core/client/me` — thin wrapper (subset).
- `GET /api/core/partner/me` — thin wrapper (subset).

## UI поведения

- Меню и разделы строятся из `capabilities[]`.
- Если capability нет — route показывает paywall/coming soon.
- Организации с CLIENT+PARTNER видят обе группы секций.

## Admin Ops

- `POST /api/core/v1/admin/commercial/orgs/{org_id}/roles/add`
- `POST /api/core/v1/admin/commercial/orgs/{org_id}/roles/remove`

После изменения:

- моментальный recompute entitlements snapshot
- audit event `org_role_changed`

