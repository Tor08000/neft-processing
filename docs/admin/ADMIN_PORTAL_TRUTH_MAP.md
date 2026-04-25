# Admin Portal Truth Map

Current source of truth:

- ADR: [ADR-0011](../architecture/adr/ADR-0011-admin-portal-owner-and-access-truth.md)
- frontend owner: `frontends/admin-ui`
- backend owner: `/api/core/v1/admin/*`
- visual foundation owner: `frontends/shared/brand`
- visual system reference: [NEFT Visual System](../architecture/NEFT_VISUAL_SYSTEM.md)

## Overall state

Admin portal is the canonical operator surface for platform operations. It is no longer treated as a generic “superadmin shell”; access is capability-based and domain-limited admins are first-class users.

Home/runtime dashboard composition is now explicitly strict:

- home (`/`) is a capability/visibility/operator-route summary, not a fake KPI dashboard
- runtime (`/runtime`) is a grounded operator overview over probe-backed service/observability health, queue pressure, violations and critical events
- queue / violation / event sections must render honest empty states and direct drilldowns into mounted operator owners
- playful achievement/streak patterns are not part of admin runtime truth
- runtime health cards must be backed by real internal probes or explicit degraded/down evidence, never synthetic all-green defaults

State-quality truth for operator pages:

- cases list pages must keep filters, error states, empty states, and pagination inside one operator shell instead of scattering them across generic cards
- logistics inspection must distinguish first-use (`order_id` not selected), loading, runtime error, and genuine “no route / no snapshot / no explain” states
- finance/case/logistics operator pages should always prefer honest retry / drilldown actions over blank cards or generic “not available” text
- finance queue pages must keep filters, empty states, counts, and pagination inside the shared table shell
- payment intake and invoice detail pages must render explicit empty timeline / explain states instead of inline technical placeholders
- filtered finance queues should behave like scoped operator inboxes, not like generic null-result cards without next actions
- finance overview must render retryable summary and honest blocker-empty states instead of raw loading/error strings
- payout review/detail must distinguish:
  - missing payout
  - payout load failure
  - missing audit chain
  - missing settlement snapshot
  - missing ledger / trace / correlation chain
  as separate operator states rather than one generic red text block
- billing payment detail must distinguish:
  - owner route unavailable in the current environment
  - payment not found
  - retryable payment load failure
  - refunds unavailable vs genuine empty refunds history
  - refund action failure inside the modal
  instead of raw `Loading...` / `endpoint unavailable` / generic error cards

## Portal composition / visibility map

Admin UI composition is capability-first and contour-specific:

- `/` -> access/capability summary and operator route map
- `/runtime` -> service/runtime overview with drilldowns only into mounted owners
- `/cases` -> support/case triage inbox
- `/finance*` -> finance queues, review/detail, explain, billing-linked operator inspection
- `/finance/revenue` -> revenue and overdue aging read surface, exposed only through the narrower `revenue.read` capability
- `/commercial*`, `/crm*`, `/marketplace/moderation*`, `/legal/*`, `/audit*`, `/ops*`, `/logistics/inspection` -> only when the capability envelope exposes those contours

The shell must not show broad generic operator actions to admins who only have read or domain-limited access.

## Role / access map

| Level | Typical raw roles | Primary capabilities |
| --- | --- | --- |
| `superadmin` | `ADMIN`, `NEFT_ADMIN`, `NEFT_SUPERADMIN`, `SUPERADMIN` | full read/operate/approve/override/manage across all admin capabilities |
| `platform_admin` | `PLATFORM_ADMIN` | broad cross-domain read/operate/approve/manage, targeted override in finance/commercial/legal; revenue is intentionally not inherited |
| `finance_admin` | `NEFT_FINANCE`, `FINANCE`, `ADMIN_FINANCE` | finance operator surface plus `revenue.read`, read-only access to runtime/cases/commercial/audit |
| `support_admin` | `NEFT_SUPPORT`, `SUPPORT` | cases/support triage, onboarding invitation operations, read access to adjacent contours |
| `operator` | `NEFT_OPS`, `OPS`, `OPERATIONS` | ops surface, runtime/read inspection of adjacent admin contours |
| `commercial_admin` | `NEFT_SALES`, `SALES`, `CRM`, `ADMIN_CRM` | commercial management, CRM read/write, onboarding read/operate, `revenue.read` for commercial finance context |
| `legal_admin` | `NEFT_LEGAL`, `LEGAL` | legal review/approval, read access to audit/cases/runtime |
| `observer` | `AUDITOR`, `ANALYST`, `OBSERVER`, `READ_ONLY_ANALYST`, `NEFT_OBSERVER` | read-only runtime/finance/cases/commercial/crm/marketplace/legal/audit |

## Contour map

| Contour | Canonical backend owner | Canonical admin UI surface | Notes |
| --- | --- | --- | --- |
| Home | `/api/core/v1/admin/me` | `/` | grounded access/capability summary only; no synthetic KPI owner |
| Admin access / roster | `auth-host /api/auth/v1/admin/users*` and `/api/v1/admin/users*` + `/api/core/v1/admin/me` capability envelope | `/admins*` | auth-host remains CRUD owner; processing-core admin profile owns capability gating only; create/update flows emit canonical audit records into processing-core |
| Cases / support inbox | `/api/core/cases*` for list/detail, `/api/core/v1/admin/cases*` for admin event/audit actions | `/cases` | canonical operator inbox; admin read surface is not a separate shadow list owner |
| Finance / billing | `/api/core/v1/admin/finance*`, `/api/core/v1/admin/billing*` | `/finance*` | admin inspection + non-destructive operator actions |
| Revenue | `/api/core/v1/admin/revenue*` | `/finance/revenue`, gated by `revenue` capability | narrower than broad `finance.read`; exposed to superadmin, finance and commercial/sales roles only; platform/support/ops/observer roles do not see it |
| Commercial | `/api/core/v1/admin/commercial*` | `/commercial*` | canonical commercial owner |
| CRM | `/api/core/v1/admin/crm*` | `/crm*` | canonical CRM operator surface; router access follows admin capability envelope (`crm.read` for reads, `crm.operate` for writes) with legacy `admin:contracts:*` preserved |
| Marketplace moderation | `/api/core/v1/admin/marketplace*` | `/marketplace/moderation*` | canonical moderation read owner; approve/reject requires `marketplace.approve`; hidden helper families stay backend-gated and unmounted |
| Onboarding invitations | `/api/core/v1/admin/clients/invitations*` | `/invitations` | global admin invitation inbox |
| Ops | `/api/core/v1/admin/ops*` and domain-owned admin reads | `/ops*` | canonical operator workflows now include escalations and KPI |
| Logistics inspection | `/api/core/v1/admin/logistics*` | `/logistics/inspection` | grounded order / route / ETA / explain inspection on ops capability |
| Runtime | `/api/core/v1/admin/runtime*` | `/runtime` | diagnostics, degraded evidence, and drilldowns into owned operator pages |
| Legal | `/api/core/v1/admin/legal*` | `/legal/documents`, `/legal/partners` | documents registry and partner review share the same canonical legal owner |
| Audit | `/api/core/v1/admin/audit*` | `/audit*` | canonical audit feed |
| Unified rules | `/api/core/v1/admin/rules*`, `/api/core/rules/sandbox:evaluate` | `admin-ui:/rules/sandbox`, gated by `ops` capability | legacy nested `/api/v1/admin/api/v1/admin/rules*` is compatibility only; admin sandbox now exposes loading/error/empty states for pinned versions |
| Risk rules | `/api/core/v1/admin/risk/rules*` | `/risk/rules*`, gated by `ops` capability | previously hidden page surface is now mounted; list uses backend-supported `subject_ref` and local-only reason filtering instead of sending unsupported query params |
| Policy center | `/api/core/v1/admin/policies*` | `/policies*`, gated by `ops` capability | mounted as an operator policy registry for fleet and finance policies only; marketplace policy UI remains frozen until backend owner exists |

## Live rules sandbox evidence

Verified on 2026-04-23 against local Docker stack through the real gateway entrypoint:

- stack: `core-api`, `admin-web`, `gateway`, and `auth-host` were running; `core-api`, `gateway`, and `auth-host` were healthy.
- tokens: one-off RS256 dev JWTs were issued inside `auth-host` for role probes only; no user/role DB mutation was made.
- backend check: `GET /api/core/v1/admin/rules/versions?scope=FLEET` with `NEFT_OPS` returned `200 []`, so the sandbox rendered the honest empty version state.

| Role | `/api/core/v1/admin/me` result | Browser route evidence | Screenshot |
| --- | --- | --- | --- |
| `NEFT_OPS` | `primary=operator`, `ops.read=true` | `/admin/rules/sandbox` renders `Rules sandbox`; sidebar includes `Rules Sandbox`; page shows empty pinned-version state with active-by-scope still available | [admin-rules-sandbox-ops.png](../diag/screenshots/admin-rules-sandbox-ops.png) |
| `NEFT_SUPPORT` | `primary=support_admin`, `ops.read=false` | `/admin/` sidebar does not include `Rules Sandbox`; direct `/admin/rules/sandbox` resolves to `FORBIDDEN_ROLE` | [admin-rules-sandbox-support-nav.png](../diag/screenshots/admin-rules-sandbox-support-nav.png) |
| `OBSERVER` | `primary=observer`, `ops.read=false` | `/admin/` sidebar does not include `Rules Sandbox`; direct `/admin/rules/sandbox` resolves to `FORBIDDEN_ROLE` | [admin-rules-sandbox-observer-nav.png](../diag/screenshots/admin-rules-sandbox-observer-nav.png) |

## Live revenue evidence

Verified on 2026-04-23 against local Docker stack through the real gateway entrypoint. Re-verified after full `core-api` image rebuilds at `2026-04-23T14:35:57Z` and `2026-04-23T15:09:06Z`.

Evidence artifact: [admin-revenue-live-smoke.json](../diag/admin-revenue-live-smoke.json).

- stack: `core-api`, `admin-web`, `gateway`, and `auth-host` were running; `core-api`, `gateway`, and `auth-host` were healthy.
- tokens: one-off RS256 dev JWTs were issued inside `auth-host` for role probes only; no user/role DB mutation was made.
- backend truth: direct probes confirmed `/api/core/v1/admin/me` role levels and `/api/core/v1/admin/revenue/summary|overdue` status codes.
- browser truth: headless Chromium opened `/admin/finance/revenue`; allowed roles rendered the page and forbidden roles did not issue revenue API calls.
- image truth: `docker compose up -d --build core-api` completed successfully before the final live smoke, so the runtime proof is image-backed rather than hot-patched-container proof.

| Role | `/api/core/v1/admin/me` result | API status | Browser route evidence | Screenshot |
| --- | --- | --- | --- | --- |
| `NEFT_FINANCE` | `primary=finance_admin`, `revenue.read=true` | `summary=200`, `overdue=200` | `/admin/finance/revenue` renders `Revenue`; sidebar includes `Revenue`; no console/page errors | [admin-revenue-finance.png](../diag/screenshots/admin-revenue-finance.png) |
| `NEFT_SALES` | `primary=commercial_admin`, `revenue.read=true` | `summary=200`, `overdue=200` | `/admin/finance/revenue` renders `Revenue`; sidebar includes `Revenue`; no console/page errors | [admin-revenue-sales.png](../diag/screenshots/admin-revenue-sales.png) |
| `PLATFORM_ADMIN` | `primary=platform_admin`, `revenue.read=false` | `summary=403`, `overdue=403` | direct `/admin/finance/revenue` resolves to `FORBIDDEN_ROLE`; sidebar does not include `Revenue`; browser issued no revenue API requests | [admin-revenue-platform-forbidden.png](../diag/screenshots/admin-revenue-platform-forbidden.png) |
| `NEFT_SUPPORT` | `primary=support_admin`, `revenue.read=false` | `summary=403`, `overdue=403` | direct `/admin/finance/revenue` resolves to `FORBIDDEN_ROLE`; sidebar does not include `Revenue`; browser issued no revenue API requests | [admin-revenue-support-forbidden.png](../diag/screenshots/admin-revenue-support-forbidden.png) |

## Live dashboard / shell evidence

Verified on 2026-04-23 against local Docker stack through the real gateway entrypoint after full `admin-web` and `core-api` image rebuilds. Re-verified after the support/marketplace wave at `2026-04-23T15:37:14Z`.

Evidence artifact: [admin-dashboard-live-smoke.json](../diag/admin-dashboard-live-smoke.json).

- stack: `admin-web`, `core-api`, `gateway`, and `auth-host` were running; `core-api`, `gateway`, and `auth-host` were healthy.
- shell truth: `AdminShell` active headers match owner prefixes for `/finance/revenue`, `/crm*`, and `/legal*` instead of the first broad sidebar prefix.
- dashboard truth: role-visible dashboard links contain only mounted canonical admin routes; stale `/billing`, `/money`, `/fleet`, `/subscriptions`, `/operations`, and `/explain` links were absent.
- CRM capability truth: `NEFT_SALES` can open `/admin/crm/tariffs` without backend 403 or console noise after CRM admin router moved from coarse `admin:contracts:*` gate to `crm.read`/`crm.operate` capability checks; observer-style CRM read remains read-only at the router dependency layer.

| Role | Browser route evidence | Screenshot |
| --- | --- | --- |
| `NEFT_OPS` | `/admin/` renders mounted ops subtools: `Rules Sandbox`, `Risk Rules`, `Policy Center`, `Geo Analytics`, and `Ops KPI`; `Revenue` is absent | [admin-dashboard-ops.png](../diag/screenshots/admin-dashboard-ops.png) |
| `NEFT_FINANCE` | `/admin/` renders `Finance` and `Revenue`; ops-only rule/policy links are absent | [admin-dashboard-finance.png](../diag/screenshots/admin-dashboard-finance.png) |
| `NEFT_SUPPORT` | `/admin/` renders support/onboarding entrypoints; revenue and ops-only rule/policy links are absent | [admin-dashboard-support.png](../diag/screenshots/admin-dashboard-support.png) |
| `NEFT_SALES` | `/admin/crm/tariffs` renders with active `CRM` shell header, `CRM` and `Revenue` links visible, no console/page errors | [admin-shell-crm-tariffs.png](../diag/screenshots/admin-shell-crm-tariffs.png) |
| `NEFT_LEGAL` | `/admin/legal/partners` renders with active `Legal` shell header and no revenue/ops-only links | [admin-shell-legal-partners.png](../diag/screenshots/admin-shell-legal-partners.png) |

## Live support / marketplace evidence

Verified on 2026-04-23 against local Docker stack through the real gateway entrypoint after full `admin-web` and `core-api` image rebuilds. Re-verified after the final `admin-web` image rebuild at `2026-04-23T15:54:14Z`.

Evidence artifact: [admin-support-marketplace-live-smoke.json](../diag/admin-support-marketplace-live-smoke.json).

- stack: `admin-web`, `core-api`, `gateway`, and `auth-host` were running; `core-api`, `gateway`, and `auth-host` were healthy.
- browser truth: `NEFT_SUPPORT` can open canonical cases and marketplace moderation read surfaces; `NEFT_FINANCE` can read cases but cannot see or open marketplace moderation.
- action truth: finance read access to cases does not expose case operation calls; support read access to marketplace detail does not expose approve/reject moderation actions.
- direct API truth: hidden marketplace helper read families return `403` to `NEFT_FINANCE`, and hidden marketplace helper write families return `403` to `NEFT_SUPPORT` through the gateway.
- detail error truth: the moderation detail smoke uses a valid missing product UUID and records the expected product `404`, proving the page keeps a real error state while still hiding read-only approve/reject actions.
- helper truth: admin marketplace order inspection remains backend-only for order settlement and SLA helper reads; the canonical mounted admin surface is still moderation plus finance payout/revenue work, not a new marketplace order settlement page.
- seeded helper proof: `scripts/smoke_marketplace_order_loop.cmd` verifies that `/api/core/v1/admin/marketplace/orders/:id/settlement-snapshot` and `/consequences` are readable for admin order inspection and return mounted `200` helper payloads.

| Role | Browser/API evidence | Screenshot |
| --- | --- | --- |
| `NEFT_SUPPORT` | `/admin/cases?queue=SUPPORT` renders the support/case inbox; sidebar includes `Cases`, `Marketplace`, and `Onboarding`; `Revenue` and ops-only tools are absent | [admin-cases-support.png](../diag/screenshots/admin-cases-support.png) |
| `NEFT_FINANCE` | `/admin/cases?queue=SUPPORT` renders the cases read surface; sidebar includes `Finance` and `Revenue`; marketplace and ops-only tools are absent; case operation buttons stay disabled by capability | [admin-cases-finance-readonly.png](../diag/screenshots/admin-cases-finance-readonly.png) |
| `NEFT_SUPPORT` | `/admin/marketplace/moderation` renders the moderation queue over `/api/core/v1/admin/marketplace/moderation/queue` | [admin-marketplace-support-read.png](../diag/screenshots/admin-marketplace-support-read.png) |
| `NEFT_FINANCE` | direct `/admin/marketplace/moderation` resolves to `FORBIDDEN_ROLE`; sidebar does not include `Marketplace`; no moderation API request is issued | [admin-marketplace-finance-forbidden.png](../diag/screenshots/admin-marketplace-finance-forbidden.png) |
| `NEFT_SUPPORT` | `/admin/marketplace/moderation/product/00000000-0000-0000-0000-000000000999` renders read-only moderation state, hides `Approve` and `Reject`, and records the expected product `404` | [admin-marketplace-support-detail-readonly.png](../diag/screenshots/admin-marketplace-support-detail-readonly.png) |

Hidden helper families frozen out of admin UI routes and gated by backend capability:

- `GET /api/core/v1/admin/products` -> requires marketplace admin capability
- `GET /api/core/v1/admin/marketplace/orders` -> requires marketplace admin capability
- `GET /api/core/v1/admin/marketplace/orders/{order_id}/settlement-snapshot` -> backend-only admin helper; read-visible for admin order inspection, unmounted in admin UI
- `GET /api/core/v1/admin/marketplace/orders/{order_id}/sla` -> backend-only SLA helper; remains unmounted in admin UI
- `GET /api/core/v1/admin/marketplace/orders/{order_id}/consequences` -> backend-only consequence helper; mounted as a `200` read helper with an `items` list
- `GET /api/core/v1/admin/marketplace/sponsored/campaigns` -> requires marketplace admin capability
- `POST /api/core/v1/admin/partners/{partner_id}/verify` -> requires marketplace approve capability
- `POST /api/core/v1/admin/marketplace/orders/{order_id}/settlement-override` -> requires marketplace override capability
- `PATCH /api/core/v1/admin/marketplace/sponsored/campaigns/{campaign_id}/status` -> requires marketplace operate capability

## Frozen / compatibility tails

- remaining live public `/api/v1/admin/*` tails stay explicit compatibility/public surfaces:
  - `processing-core` currently exposes 60 schema-visible family roots under this compatibility namespace:
    `accounting`, `accounts`, `api`, `bank_stub`, `bi`, `billing`, `bookings`, `card-groups`, `cards`, `cases`, `clearing`, `client-groups`, `clients`, `closing-packages`, `commercial`, `contracts`, `crm`, `decision-memory`, `disputes`, `documents`, `edo`, `entitlements`, `erp_stub`, `explain`, `exports`, `fleet`, `fleet-control`, `fleet-intelligence`, `fraud`, `fuel`, `integration`, `integrations`, `invoice-threads`, `invoices`, `ledger`, `legal`, `legal-graph`, `limits`, `logistics`, `me`, `merchants`, `notifications`, `operations`, `ops`, `partners`, `payouts`, `pricing`, `products`, `reconciliation-requests`, `refunds`, `revenue`, `reversals`, `risk`, `risk-v5`, `seed`, `settlement`, `settlements`, `terminals`, `transactions`, `what-if`
  - `api` means the inherited nested unified-rules tail (`/api/v1/admin/api/v1/admin/rules*`), not a new namespace for future admin routes; canonical parity is `/api/core/v1/admin/rules*`
  - `auth-host` admin roster CRUD under `/api/v1/admin/users*`
- removed public compatibility tails after canonical parity + repo consumer migration:
  - `/api/v1/admin/audit*`
  - `/api/v1/admin/finance*`
  - `/api/v1/admin/legal/documents*`
  - `/api/v1/admin/marketplace*`
  - `/api/v1/admin/money*`
  - `/api/v1/admin/reconciliation*`
- remaining repo-visible public consumers still exist for:
  - `platform/auth-host/app/tests/*` (`/api/v1/admin/users*`)
  - `scripts/selftest.sh`
  - checked-in route maps/docs around surviving `me`, `clients`, `billing`, `revenue`, and auth-host admin roster tails

- removed hidden `/api/core/admin/*` tails stay removed:
  - `/api/core/admin/me`
  - `/api/core/admin/runtime/summary`
  - `/api/core/admin/finance/overview`
  - `/api/core/admin/legal/partners`
  - `/api/core/admin/audit`
- frozen hidden `/api/core/admin/*` finance bridge stays mounted but schema-hidden:
  - `/api/core/admin/payouts*`
  - `/api/core/admin/partner/{partner_id}/ledger`
  - `/api/core/admin/partner/{partner_id}/settlement`
  - canonical finance UI and new consumers must use `/api/core/v1/admin/finance*`
- schema-visible `/api/core/admin/*` non-v1 contracts are explicitly limited to auth verify, client onboarding/documents, client subscription assignment, partner management, and onboarding review. New routes in this namespace require route-topology sentinel and owner-map updates.
- removed root aliases must stay removed:
  - `/v1/admin/me`
  - `/v1/admin/runtime/summary`
  - `/v1/admin/audit*`
  - `/v1/admin/finance*`
  - `/v1/admin/legal/documents*`
  - `/v1/admin/ops*`
  - `/v1/admin/legal/partners*`
  - `/v1/admin/marketplace*`
  - `/v1/admin/money*`
  - `/v1/admin/reconciliation*`
  - `/v1/admin/billing/summary`
  - `/v1/admin/commercial*`
  - `/v1/admin/clients/*/invitations*`
- remaining root `/v1/admin/*` ballast is schema-hidden and limited to 55 family roots:
  `accounting`, `accounts`, `api`, `bank_stub`, `bi`, `billing`, `bookings`, `card-groups`, `cards`, `cases`, `clearing`, `client-groups`, `clients`, `closing-packages`, `contracts`, `crm`, `decision-memory`, `disputes`, `documents`, `edo`, `entitlements`, `erp_stub`, `explain`, `exports`, `fleet`, `fleet-control`, `fleet-intelligence`, `fraud`, `fuel`, `integration`, `integrations`, `invoice-threads`, `invoices`, `ledger`, `legal`, `legal-graph`, `limits`, `logistics`, `notifications`, `operations`, `partners`, `payouts`, `pricing`, `products`, `reconciliation-requests`, `refunds`, `revenue`, `reversals`, `risk`, `risk-v5`, `seed`, `settlement`, `settlements`, `transactions`, `what-if`
- removed shadow residue:
  - unmounted `frontends/admin-ui/src/router/index.tsx`
  - old mock-first `frontends/admin-ui/src/pages/DashboardPage.tsx`
  - old `BillingDashboardPage` and its private KPI/achievements subtree

Removed/frozen UI tails stay part of truth-map ownership:

- they may remain in repo history or compatibility docs
- they must not regain navigation entrypoints
- they must not be presented as active operator capabilities in dashboard or sidebar composition

## Admin page inventory freeze

Verified on 2026-04-23 for `frontends/admin-ui/src/pages` against `src/App.tsx` and `AdminShell`:

- activated hidden but real ops surfaces:
  - `RiskRulesListPage` / `RiskRuleDetailsPage` -> `/risk/rules*`
  - `PolicyCenterPage` / `PolicyCenterDetailPage` -> `/policies*`
- activated hidden but real finance/commercial read surface:
  - `finance/RevenuePage` -> `/finance/revenue`, gated by the explicit `revenue.read` capability and canonical `/api/core/v1/admin/revenue*`
- tightened mounted support/marketplace operator truth:
  - `cases/CasesListPage` and `cases/CaseDetailsPage` keep finance/observer-style case read access visible while disabling mutation calls unless `cases.operate` is present
  - `marketplace/MarketplaceModerationDetailPage` renders approve/reject only for `marketplace.approve`; read-only marketplace roles see an explicit read-only moderation state
  - hidden marketplace helper API families for products, marketplace orders, sponsored campaigns, partner verification, settlement override, and campaign operations remain backend-gated and are not mounted as admin UI routes
- shared status-state truth:
  - legacy `ForbiddenPage` remains as a compatibility import for older helper pages, but now delegates to canonical `AdminForbiddenPage` so mounted `/policies*` and frozen helpers show the same `FORBIDDEN_ROLE` state and home route
- shell/navigation truth:
  - `AdminShell` uses explicit active prefixes for grouped mounted sections (`/finance/revenue`, `/crm*`, `/legal*`, `/marketplace*`, `/rules*`, `/risk/rules*`, `/policies*`) so the operator header follows the real owner instead of the first broad prefix match
- dashboard route truth:
  - `AdminDashboardPage` exposes the mounted ops subtools (`/geo`, `/rules/sandbox`, `/risk/rules`, `/policies`) as explicit operator cards with distinct labels, and the dashboard sentinel rejects stale `/billing`, `/money`, `/fleet`, `/subscriptions`, `/operations`, and `/explain` links
- explicitly frozen neighboring helpers that must not regain routes without owner-map and state-quality updates:
  - `RiskAnalyticsPage`: risk analytics remains split between mounted `/risk/rules*`, `/policies*`, ops KPI and backend audit/risk traces until a dedicated risk analytics owner exists
  - `OperationsListPage`, `OperationDetailsPage`: raw operation journal routes remain frozen behind `/ops*` and mounted finance/cases/logistics drilldowns
  - `ExplainPage`, `UnifiedExplainPage`: generic explain workbench remains frozen; mounted explain consumers stay domain-owned (`/crm/subscriptions/:id/cfo-explain`, finance/detail explain, logistics explain evidence)
  - root billing/clearing/account pages replaced by canonical `/finance*`
  - `pages/billing/*` legacy billing console pages replaced by canonical `/finance*`
  - `finance/PayoutsList` and `finance/PayoutBatchDetail` duplicate payout helpers replaced by mounted `/finance/payouts*`
  - `pages/fleet/*` direct fleet admin pages until fleet/admin ownership is re-cut against current backend truth
  - `pages/subscriptions/*` and root `TariffsPage` until CRM/commercial subscription ownership explicitly mounts them
  - `pages/reconciliation/*` until finance reconciliation owner decides whether those are import fixtures or operator pages
  - `pages/money/*` except mounted finance/CRM explain routes
  - `pages/partners/PartnerLegalPage` until partner legal review is intentionally merged into canonical `/legal/partners` or a partner-specific legal owner is created
  - `pages/ops/Ops*Panel` modules remain internal composition helpers for `/ops`, not direct routes

Sentinel coverage: `frontends/admin-ui/src/App.entrypoint.test.tsx` now asserts the mounted rules/policies/revenue routes and freezes the closest neighboring helpers plus duplicate finance/billing/money, fleet, legacy subscription/tariff, partner-legal, and marketplace helper admin page families from accidental route re-entry.

## Pre-external optional diagnostics

Admin runtime readiness now follows strict exclusions semantics:

- probe-backed `/runtime` cards for gateway/core/auth/integration/ai plus Prometheus/Grafana/Loki/OTel remain required `VERIFIED_RUNTIME` operator evidence
- worker-only/exporter-only signals without stable proof are optional diagnostics, not required gate-green
- ungrounded diagnostics sidecars must not reappear as dashboard cards or acceptance wording

Current implication:

- the internal gate is anchored in canonical runtime summary plus observability smoke
- thinner worker/exporter tails may remain degraded or not configured without invalidating the admin operator contour

## Explicitly removed weak surfaces

- fake support pages duplicated by canonical cases
- placeholder ops drilldown page without a real owner
- empty admin home/dashboard pretending to be a workflow owner
- legacy mock dashboard subtree that was no longer mounted by `src/App.tsx`
- unmounted `HealthPage` and `IntegrationMonitoringPage` sidecars that competed with canonical `/runtime`
- achievement/streak-style admin dashboard language pretending the operator console is a gamified product surface

## Current admin workflow truth

- support triage and reassignment: canonical via cases
- administrator roster and role management: canonical via `/admins*` over auth-host `admin/users`
- onboarding/admin invitation operations: canonical via `/clients/invitations*`
- finance detail/explain: canonical via `/finance*`
- revenue and overdue aging: canonical via `/finance/revenue` over `/api/core/v1/admin/revenue*`, with `revenue.read` separated from generic `finance.read`
- marketplace moderation: canonical via moderation queue/detail pages; read-only roles may inspect, while approve/reject actions require `marketplace.approve`
- commercial management: canonical via `/commercial*`
- legal documents review: canonical via `/legal/documents`
- ops escalation inbox: canonical via `/ops/escalations`
- ops KPI: canonical via `/ops/kpi`
- logistics inspection: canonical via `/logistics/inspection`
- runtime/ops links must resolve to grounded operator pages only
