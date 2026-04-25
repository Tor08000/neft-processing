# ADR-0005: Route topology freeze map

## Status
Accepted

## Context
`processing-core` still carries several route families at once:

- `/api/core/*` for the newer canonical namespace
- `/api/v1/*` for legacy/public compatibility families
- a reduced hidden `/v1/admin/*` root-alias family
- a few narrow redirect/projection tails under `/api/core/*`

Recent hardening waves already removed the most misleading hidden aliases and aligned several domain owners, but the remaining topology split was still implicit. That made it too easy to confuse:

- canonical owners
- compatibility-full public families
- hidden ballast
- intentional shadow/projection tails

This ADR freezes the current route-family truth so future cleanup can remove surfaces deliberately instead of rediscovering ownership each time.

## Decision
- `/api/core/*` is the canonical namespace for new and already-hardened cross-domain surfaces.
- `/api/v1/*` remains a live compatibility/public family where consumers still exist; it is not automatically the canonical owner.
- hidden `/v1/admin/*` routes are frozen compatibility ballast only. They must not be widened, and removals require explicit sentinel coverage plus consumer diagnosis.
- narrow redirect/projection tails under `/api/core/*` stay allowed only where they bridge an already-accepted ownership split.

## Frozen family map
### Canonical
- `/api/core/portal/*`
  `portal_me` is the canonical bootstrap/profile source of truth for client, partner, and admin surfaces.
- `/api/core/v1/admin/*`
  canonical admin namespace
- `/api/core/v1/admin/rules*`
  canonical unified-rules admin route family; it exists to serve admin clients that already build requests relative to `/api/core/v1/admin`
- `/api/core/client/documents*`
  canonical client general docflow surface
- `/api/core/client/v1/onboarding/*`, `/api/core/client/docflow/*`
  canonical onboarding-token document/signing surfaces; gateway pass-throughs intentionally bypass the regular client JWT `auth_request` because processing-core verifies the short-lived onboarding token on these routes.
- `/api/core/partner/finance/*`
  canonical partner finance namespace
- `/api/marketplace/client/recommendations`
- `/api/marketplace/client/events`
  canonical live client recommendations/events owners under the current absolute-prefix marketplace family
- `/api/core/v1/marketplace/client/recommendations`
- `/api/core/v1/marketplace/client/events`
  additive core-prefixed projections over the same marketplace owner; keep explicit because current gateway/docs/tests still exercise this namespace
- `/v1/marketplace/client/recommendations`
- `/v1/marketplace/client/events`
  app-mounted transport paths behind gateway `/api/v1/marketplace/client/*`; not separate product owners

### Compatibility-full or compatibility/public
- narrowed `/api/v1/admin/*`
  remaining live compatibility/public admin family after canonical handoff. It is schema-visible, but not canonical.
  Current processing-core family roots are:
  `accounting`, `accounts`, `api`, `bank_stub`, `bi`, `billing`, `bookings`, `card-groups`, `cards`, `cases`, `clearing`, `client-groups`, `clients`, `closing-packages`, `commercial`, `contracts`, `crm`, `decision-memory`, `disputes`, `documents`, `edo`, `entitlements`, `erp_stub`, `explain`, `exports`, `fleet`, `fleet-control`, `fleet-intelligence`, `fraud`, `fuel`, `integration`, `integrations`, `invoice-threads`, `invoices`, `ledger`, `legal`, `legal-graph`, `limits`, `logistics`, `me`, `merchants`, `notifications`, `operations`, `ops`, `partners`, `payouts`, `pricing`, `products`, `reconciliation-requests`, `refunds`, `revenue`, `reversals`, `risk`, `risk-v5`, `seed`, `settlement`, `settlements`, `terminals`, `transactions`, `what-if`.
  The `api` root is the inherited nested unified-rules tail (`/api/v1/admin/api/v1/admin/rules*`), not a new namespace for future routes. Canonical parity exists under `/api/core/v1/admin/rules*`; the nested tail remains frozen until a separate consumer migration/removal decision.
  Public/admin roster CRUD in auth-host remains under `/api/v1/admin/users*`.
  Further narrowing still requires explicit consumer diagnosis.
- `/api/v1/client/documents*`
  legacy closing-docs/ack/risk contour; compatibility only, not the canonical general documents API
- `/api/v1/client/closing-packages/{package_id}/ack`
  final compatibility tail for closing-package acknowledgement
- `/api/v1/reports/*`
  compatibility read/export family over billing-summary projections; see ADR-0004
- `/api/v1/partner/fuel/stations/*/prices*`
  partner-facing fuel price compatibility family; keep while partner fuel tooling and backend contract tests still depend on it
- `/api/client/invoices*`
  public client billing projection from `portal.py`; keep explicit while it still serves the legacy `Invoice`/`invoice_ref` contour. This is not route-parity with canonical `/api/core/client/invoices*`, which reads the subscription/billing-invoice contour from `client_portal_v1`.
- `/api/client/fleet*`
  public client fleet family; there is no mounted `/api/core/client/fleet*` parity in the current topology, so this remains a live public owner surface rather than a parity-ready tail.
- `/api/client/onboarding/state|step`
  commercial-layer compatibility state endpoints; keep explicit while docs/scenarios still reference them. They are not the primary authenticated onboarding owner.
- `/api/partner/acts`, `/api/partner/balance`, `/api/partner/invoices`, `/api/partner/ledger*`, `/api/partner/payouts*`
  public partner self-serve finance family. Canonical `/api/core/partner/*` parity exists for the main read surfaces, but repo-visible tests/docs/compatibility consumers still reference the public family, so route handoff is deferred.

### Hidden compatibility ballast
- `/v1/admin/*`
  reduced hidden admin family mounted only as compatibility ballast; every route under this prefix must stay `include_in_schema=False`.
  Current hidden family roots are:
  `accounting`, `accounts`, `api`, `bank_stub`, `bi`, `billing`, `bookings`, `card-groups`, `cards`, `cases`, `clearing`, `client-groups`, `clients`, `closing-packages`, `contracts`, `crm`, `decision-memory`, `disputes`, `documents`, `edo`, `entitlements`, `erp_stub`, `explain`, `exports`, `fleet`, `fleet-control`, `fleet-intelligence`, `fraud`, `fuel`, `integration`, `integrations`, `invoice-threads`, `invoices`, `ledger`, `legal`, `legal-graph`, `limits`, `logistics`, `notifications`, `operations`, `partners`, `payouts`, `pricing`, `products`, `reconciliation-requests`, `refunds`, `revenue`, `reversals`, `risk`, `risk-v5`, `seed`, `settlement`, `settlements`, `transactions`, `what-if`.
  The hidden `api` root is the same inherited nested unified-rules ballast and must not be widened. It does not imply root `/v1/admin/rules*` parity.
- removed hidden slices stay removed:
  - `/v1/admin/auth/verify`
  - `/v1/admin/runtime/summary`
  - `/v1/admin/merchants*`
  - `/v1/admin/terminals*`
  - `/v1/admin/billing/summary`
  - `/v1/admin/finance*`
  - `/v1/admin/commercial*`
  - `/v1/admin/clients/*/invitations*`
  - `/v1/admin/audit*`
  - `/v1/admin/legal/documents*`
  - `/v1/admin/legal/partners*`
  - `/v1/admin/me`
  - `/v1/admin/marketplace*`
  - `/v1/admin/money*`
  - `/v1/admin/ops*`
  - `/v1/admin/reconciliation*`

### Intentional redirect/projection tails under /api/core
- `/api/core/client/me`
  compatibility projection over canonical `/api/core/portal/me`
  keep while repo-visible smoke/contract consumers still depend on the client-focused wrapper shape
- `/api/core/admin/payouts*`
- `/api/core/admin/partner/{partner_id}/ledger`
- `/api/core/admin/partner/{partner_id}/settlement`
  schema-hidden admin finance bridge only; canonical operator finance owner remains `/api/core/v1/admin/finance/*`, and new consumers must not target these tails
- `/api/client/marketplace/recommendations`
- `/api/client/marketplace/events`
  compatibility/internal shadow routes; canonical live owners remain the dedicated `/api/marketplace/client/*` surfaces

Routes that are now part of the default mounted topology as read-only partner finance surfaces:

- `/api/core/partner/contracts`
- `/api/core/partner/settlements*`
- `/api/partner/contracts`
- `/api/partner/settlements*`

These are additive read APIs only. They must not be used to imply partner-side contract/settlement write or approval ownership.
The partner shell keeps `/contracts` and `/settlements*` finance-view-gated; `docs/diag/partner-finance-mounted-routes-live-smoke-20260425.json` records live proof that canonical and compatibility reads return `200` and that settlement confirm/write tails remain absent.

Removed hidden `/api/core/*` tails stay removed after consumer diagnosis:

- `/api/core/partner/dashboard`
- `/api/core/admin/me`
- `/api/core/admin/runtime/summary`
- `/api/core/admin/finance/overview`
- `/api/core/admin/legal/partners`
- `/api/core/admin/audit`

### Explicit `/api/core/admin/*` non-v1 visibility map

The default mounted topology still contains several `/api/core/admin/*` routes
that are not hidden aliases. These are schema-visible working contracts with
repo-visible consumers and must not be removed under the hidden-alias cleanup
rule:

- `/api/core/admin/auth/verify`
- `/api/core/admin/client-onboarding/{application_id}/approve`
- `/api/core/admin/clients/{client_id}/documents`
- `/api/core/admin/clients/{client_id}/subscription*`
- `/api/core/admin/documents/{document_id}/files`
- `/api/core/admin/partners*`
- `/api/core/admin/v1/onboarding/*`

The schema-hidden `/api/core/admin/*` family is limited to the finance bridge
listed above. Adding a new `/api/core/admin/*` route requires updating the
topology sentinel and this map with an owner classification.

### Dormant conditional code paths (not part of default mounted topology)
- `/api/core/partner/me`
  compatibility projection over canonical `/api/core/portal/me` exists in code but is not mounted in the default app topology while `API_PREFIX_CORE` stays at `/api/core`

## What this ADR does not approve
- broad removal of `/api/v1/*` families
- changing public gateway route families
- flipping compatibility consumers to canonical paths without read/action parity proof
- widening hidden `/v1/admin/*` coverage
- inventing new redirect tails

## Removed after consumer migration
- `/api/v1/admin/audit*`
- `/api/v1/admin/finance*`
- `/api/v1/admin/legal/documents*`
- `/api/v1/admin/marketplace*`
- `/api/v1/admin/money*`
- `/api/v1/admin/reconciliation*`

## Removal rule
Every remaining compatibility family or redirect tail must be treated as one of:

- canonical owner
- frozen compatibility tail
- frozen hidden ballast
- explicit shadow/internal compatibility route

If it does not fit one of those classes, it should be diagnosed for removal instead of silently surviving.
