# ADR-0011: Admin Portal Owner And Access Truth

## Status

Accepted

## Context

Repo-truth already had one canonical operator surface:

- frontend: `frontends/admin-ui`
- backend: `/api/core/v1/admin/*`

But the admin contour still behaved as if:

- `admin = everything`
- coarse role buckets were enough
- fake dashboard/widgets could stand in for missing operator workflows
- legacy `/api/core/admin/*` and removed `/v1/admin/*` aliases were interchangeable with canonical owners

That created three kinds of drift:

1. domain-limited admins such as support, finance, ops, legal, and commercial could exist in repo, but the default admin envelope still blocked them or flattened them;
2. admin-ui navigation and route gating did not line up with backend owner truth;
3. weak pages and placeholder drilldowns looked actionable even when there was no canonical operator owner behind them.

## Decision

### Canonical admin owner

The canonical operator surface is:

- frontend: `frontends/admin-ui`
- backend routes: `/api/core/v1/admin/*`

### Access model

Admin access is capability-based over the existing JWT/admin token model.

Explicit role levels:

- `superadmin`
- `platform_admin`
- `finance_admin`
- `support_admin`
- `operator`
- `commercial_admin`
- `legal_admin`
- `observer`

Explicit capability keys:

- `access`
- `ops`
- `runtime`
- `finance`
- `cases`
- `commercial`
- `crm`
- `marketplace`
- `legal`
- `onboarding`
- `audit`

Explicit actions:

- `read`
- `operate`
- `approve`
- `override`
- `manage`

`write` is a derived compatibility flag, not a first-class policy input.

### Operator surface truth

Canonical admin UI must link only to grounded operator pages:

- admin roster / role management
- cases/support inbox
- finance
- commercial
- CRM
- marketplace moderation
- onboarding invitations
- ops overview, escalations, KPI
- logistics inspection
- runtime
- legal documents and partner review
- audit

Synthetic home widgets and placeholder drilldowns are not canonical owners.

Admin roster management is an explicit owner split:

- processing-core `/api/core/v1/admin/me` owns capability resolution for the admin shell;
- auth-host `/api/auth/v1/admin/users*` remains the CRUD owner for platform/admin user roles, with `/api/v1/admin/users*` kept as the live public compatibility family.
- admin roster mutations must emit canonical audit records into processing-core audit feed with operator-provided `reason` and `correlation_id`; auth-host is not a second audit owner.

### Route topology

- canonical: `/api/core/v1/admin/*`
- removed hidden `/api/core/admin/*` tails: `/api/core/admin/me`, `/api/core/admin/runtime/summary`
- removed hidden `/api/core/admin/*` tails:
  - `/api/core/admin/finance/overview`
  - `/api/core/admin/legal/partners`
  - `/api/core/admin/audit`
- frozen hidden `/api/core/admin/*` finance bridge:
  - `/api/core/admin/payouts*`
  - `/api/core/admin/partner/{partner_id}/ledger`
  - `/api/core/admin/partner/{partner_id}/settlement`
  - these routes stay mounted for compatibility but are schema-hidden; canonical finance remains `/api/core/v1/admin/finance/*`
- removed hidden aliases: root `/v1/admin/*` shortcuts that duplicated canonical owners

Compatibility tails must stay explicit and hidden if they still exist.

## Consequences

- Domain-limited admins are now first-class admin users instead of accidental non-admins.
- Admin UI navigation and route guards must read the same capability map as backend owners.
- Weak/fake admin pages should be removed or frozen instead of left clickable.
- Any new admin capability should land on canonical `/api/core/v1/admin/*` owners first, and only then consider compatibility tails.
- Narrow public admin-tail removal is allowed only after canonical parity plus repo consumer migration. This wave removed `/api/v1/admin/audit*`, `/api/v1/admin/finance*`, `/api/v1/admin/legal/documents*`, `/api/v1/admin/marketplace*`, `/api/v1/admin/money*`, and `/api/v1/admin/reconciliation*`; surviving `/api/v1/admin/*` families remain explicit compatibility/public surfaces.
