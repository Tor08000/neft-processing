# Client Portal menu policy (SSoT-driven)

Menu visibility and disabled state must be derived from `GET /api/core/portal/me` fields: `capabilities`, `entitlements_snapshot.modules`, and role checks, with disabled items showing CTA instead of 404. The current navigation uses module/capability checks + role gating in `Layout.tsx`.【F:frontends/client-portal/src/components/Layout.tsx†L25-L140】

## Source of truth
- **Capabilities:** `portal/me.capabilities`.
- **Modules:** `portal/me.entitlements_snapshot.modules`.
- **Roles:** `portal/me.user_roles` and `portal/me.org_roles`.

## Policy table (as-is)

| Nav item | Route | Module gate | Capability gate | Role gate | Disabled reason shown |
| --- | --- | --- | --- | --- | --- |
| Vehicles | `/vehicles` | `FLEET` | `CLIENT_CORE` | none | "Недоступно по подписке" when module/capability missing.【F:frontends/client-portal/src/components/Layout.tsx†L58-L140】 |
| Cards | `/cards` | none | `CLIENT_CORE` | none | same as above.【F:frontends/client-portal/src/components/Layout.tsx†L58-L140】 |
| Limit Templates | `/limits/templates` | none | `CLIENT_CORE` | none | same as above.【F:frontends/client-portal/src/components/Layout.tsx†L58-L140】 |
| Orders | `/orders` | `MARKETPLACE` | `MARKETPLACE` | none | same as above.【F:frontends/client-portal/src/components/Layout.tsx†L58-L140】 |
| Billing | `/billing` | `DOCS` | `CLIENT_BILLING` | none | same as above.【F:frontends/client-portal/src/components/Layout.tsx†L58-L140】 |
| Notifications | `/client/notifications` | none | `CLIENT_CORE` | none | same as above.【F:frontends/client-portal/src/components/Layout.tsx†L58-L140】 |
| Support | `/client/support` | none | `CLIENT_CORE` | none | same as above.【F:frontends/client-portal/src/components/Layout.tsx†L58-L140】 |
| Audit | `/audit` | none | `CLIENT_CORE` | none | same as above.【F:frontends/client-portal/src/components/Layout.tsx†L58-L140】 |
| Analytics | `/client/analytics` | `ANALYTICS` | `CLIENT_ANALYTICS` | OWNER/ADMIN/ACCOUNTANT/FLEET_MANAGER | "Нужна роль" or subscription gating.【F:frontends/client-portal/src/components/Layout.tsx†L69-L140】 |
| Reports | `/client/reports` | none | `CLIENT_CORE` | OWNER/ADMIN/ACCOUNTANT/FLEET_MANAGER | "Нужна роль" or subscription gating.【F:frontends/client-portal/src/components/Layout.tsx†L69-L140】 |
| Exports | `/client/exports` | none | `CLIENT_CORE` | OWNER/ADMIN/ACCOUNTANT/FLEET_MANAGER | same as above.【F:frontends/client-portal/src/components/Layout.tsx†L69-L140】 |
| SLO / SLA | `/client/slo` | none | `CLIENT_CORE` | OWNER/ADMIN | "Нужна роль" or subscription gating.【F:frontends/client-portal/src/components/Layout.tsx†L69-L140】 |
| Marketplace | `/marketplace` | `MARKETPLACE` | `MARKETPLACE` | none | "Недоступно по подписке" when disabled.【F:frontends/client-portal/src/components/Layout.tsx†L58-L140】 |
| Legal | `/legal` | none | none | none | always visible; sole menu item during legal block.【F:frontends/client-portal/src/components/Layout.tsx†L105-L138】 |

## AccessState alignment
- **Module disabled:** use `entitlements_snapshot.modules.<module>.enabled=false` → `MODULE_DISABLED` access state, not 404. The access resolver already checks `modules` for disabled/absent entries.【F:frontends/client-portal/src/access/accessState.ts†L64-L117】
- **Missing capability:** when module is enabled but capability missing, return `MISSING_CAPABILITY` state.【F:frontends/client-portal/src/access/accessState.ts†L83-L117】
- **Role forbidden:** if role gate fails, return `FORBIDDEN_ROLE` state with explicit CTA.【F:frontends/client-portal/src/access/accessState.ts†L72-L92】

## TODO
- Convert disabled menu items to show upgrade CTA (plan selection or contact manager), driven by SSoT `features.onboarding_enabled` and subscription status.
