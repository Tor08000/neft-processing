# Partner Portal Truth Map

## Overall state

Partner portal is no longer treated as one shared shell for every external partner. The canonical shell now composes routes and navigation from:

- `GET /api/core/portal/me`
- `partner.kind`
- `partner.partner_roles`
- `partner.workspaces`
- `capabilities[]`

The portal is intentionally segmented into partner-facing workspaces rather than broad generic sections.

Dashboard composition now follows the same truth:

- dashboard focus block must point to the partner's real workspace default route
- finance overview appears only when the finance workspace is mounted for that partner
- if finance is not mounted, the dashboard must render an explicit access-limited state rather than a fake balance/settlement preview
- workflow cards must lead directly into mounted workspace routes, not into broad generic sections
- when `portal/me` returns `partner_onboarding`, the shell must redirect into mounted `/onboarding` instead of bouncing pending partners into active-only profile routes

State-quality truth for high-traffic partner pages:

- support list pages must distinguish first-use empty from filtered empty and offer a clear next step
- service/order/finance lists should keep canonical owner routes visible in empty/error states instead of bouncing users into generic sections
- partner pages may stay workflow-heavy, but they should not collapse into raw “no rows / error string” surfaces
- orders list must distinguish working-queue empty from filtered-empty and keep pagination/counts inside the same table shell
- services catalog must keep filtered-empty, retry, count footer, and import refresh inside the same workflow contour
- finance workspace must render honest ledger/export empty states and retry paths instead of reloading the entire portal shell
- support request detail must distinguish:
  - request load failure with retry
  - request not found
  - empty timeline after request creation
  - canonical case trail (`/cases/:id`, queue, source, SLA timers) without pretending that partner support is a separate backend owner
  instead of reusing the same generic empty copy for every state
- marketplace order detail must expose order-linked incidents through canonical `cases` rather than treating support as a detached modal-only side surface
- order detail must treat proofs, settlement penalties, and settlement snapshot as explicit owner-backed states:
  - absent proofs are not a blank section
  - absent penalties are not raw muted text
  - missing snapshot is an explicit payout-chain state, not silent omission
  - `409 SETTLEMENT_NOT_FINALIZED` on the order settlement read is an explicit readiness state, not a generic error card
- service detail subreads (locations, schedule, preview) must surface retryable load errors instead of console-only failures or silently empty tabs
- payout request flow must distinguish:
  - preview check/loading
  - blocked legal state
  - read-only finance analyst mode
  - first-use payout history empty
  - retryable history load failure

## Portal composition map

Canonical partner shell composition is now workspace-first:

- `dashboard` -> action-oriented overview, not a dumping ground
- `finance` -> balance / ledger / payouts / exports only for finance-capable partners
- `marketplace` -> products / offers / orders only for marketplace-capable partners
- `services` -> catalog / execution only for service partners
- `support` -> canonical partner case/request inbox for all mounted partner shells
- `profile` -> legal / locations / users / terms according to role and capability

No partner kind should see wrong-workspace tabs or dead menu items “just in case”.

Visual system owner is shared with the other portals:

- canonical visual foundation: `frontends/shared/brand`
- partner shell consumes shared `BrandSidebar`, `BrandHeader`, and `brand.css`
- reference doc: [NEFT Visual System](../architecture/NEFT_VISUAL_SYSTEM.md)

## Partner kind / capability map

| Kind | Primary workspaces | Typical capabilities |
| --- | --- | --- |
| `FINANCE_PARTNER` | `finance`, `support`, `profile` | `PARTNER_FINANCE_VIEW`, `PARTNER_PAYOUT_REQUEST`, `PARTNER_SETTLEMENTS`, `PARTNER_DOCUMENTS_LIST` |
| `MARKETPLACE_PARTNER` | `marketplace`, `support`, `profile` | `PARTNER_CATALOG`, `PARTNER_PRICING`, `PARTNER_ORDERS`, `PARTNER_ANALYTICS` |
| `SERVICE_PARTNER` | `services`, `support`, `profile` | `PARTNER_CORE` |
| `FUEL_PARTNER` | `profile` plus additive finance/support only when explicitly granted | no dedicated fuel shell is mounted in this contour |
| `LOGISTICS_PARTNER` | `profile` plus additive finance/support only when explicitly granted | no dedicated logistics shell is mounted in this contour |
| `GENERAL_PARTNER` | `support`, `profile` plus additive workspaces from capabilities | fallback compatibility kind |

`kind` gives the base workspace composition. `capabilities` further narrow read/operate access inside those workspaces.

## Partner sub-role map

Current shell-level partner roles are normalized from repo-truth into:

- `OWNER`
- `FINANCE_MANAGER`
- `MANAGER`
- `OPERATOR`
- `ANALYST`

Current explicit read-only rule in the shell:

- finance analysts remain read-only for payout actions
- contracts and settlement registers are mounted as read-only finance surfaces
- settlement write/approval actions remain admin-owned; partner confirm/approve tails are still absent

This is additive UI gating over existing backend capability/owner checks. It does not change billing, ledger, or settlement semantics.

### Profile workspace access map

| Surface | Read | Manage |
| --- | --- | --- |
| Partner profile (`/partner/profile`) | any linked partner user in the `profile` workspace | `OWNER`, `MANAGER`, `FINANCE_MANAGER` |
| Partner locations (`/partner/locations`) | any linked partner user in the `profile` workspace | `OWNER`, `MANAGER` |
| Partner users (`/partner/users`) | any linked partner user in the `profile` workspace | `OWNER` only |
| Partner terms (`/partner/terms`) | any linked partner user in the `profile` workspace | read-only surface |

These rules now match both:

- portal UI visibility and write affordances
- backend owner guards in `partner_management`

## Contour-by-contour owner map

| Contour | Canonical owner | Partner shell status |
| --- | --- | --- |
| Onboarding / activation | `/api/core/partner/onboarding*` plus partner/admin legal owners | mounted; pending partners are redirected into `/onboarding`, not fake-routed into active-only profile pages |
| Bootstrap / segmentation | `/api/core/portal/me` | canonical |
| Finance dashboard / balance / ledger / payouts / documents | `/api/core/partner/finance/dashboard`, `/api/core/partner/balance`, `/api/core/partner/ledger`, `/api/core/partner/payouts*`, `/api/core/partner/invoices`, `/api/core/partner/acts` | mounted for finance-capable partners only; dashboard summary and document lists are visible only inside that workspace |
| Contracts / settlements | `/api/core/partner/contracts*`, `/api/core/partner/settlements*` plus compatibility `/api/partner/contracts*`, `/api/partner/settlements*` reads | mounted read-only for finance-capable partners; empty state is allowed, fake rows and partner write actions are not |
| Marketplace products / offers | `/api/core/partner/products*`, `/api/core/partner/offers*` | mounted for marketplace partners only |
| Marketplace orders | `/api/core/v1/marketplace/partner/orders*` | mounted for marketplace partners only |
| Services catalog / execution | `/api/core/partner/catalog*`, `/api/core/partner/services*`, `/api/core/partner/service-locations*` | mounted for service partners only |
| Support / incidents | canonical `/api/core/cases*` via partner UX `/support/requests*`, mounted `/cases*` shell alias for the case trail, and order-scoped `/api/core/v1/marketplace/partner/orders/:id/incidents` read projection | mounted for all partner shells |
| Profile / legal / team / locations | `/api/core/partner/self-profile`, `/api/core/partner/legal/*`, `/api/core/partner/locations*`, `/api/core/partner/users*`, `/api/core/partner/terms` | mounted in profile workspace |

Profile workspace pages now include direct support entrypoints and create partner cases against canonical `/api/core/cases*` rather than a separate partner-helpdesk owner.

## Marketplace incident linkage

- Partner order detail now reads order-linked incidents from `/api/core/v1/marketplace/partner/orders/:id/incidents`.
- This route is a read-only projection over canonical `cases`; it does not introduce a separate marketplace incident owner.
- Incident rows deep-link into mounted `/cases/:id`, which stays inside the support workspace contour.
- Settlement penalty source links remain frozen to the broader support inbox when only audit/SLA ids exist and no direct case id is available.

## Live visibility / runtime evidence

- Live browser proof is anchored in `docs/diag/client-partner-support-marketplace-live-smoke.json`.
- Current verified runtime at `2026-04-23T20:00:11.983Z` shows:
  - `partner@neft.local` opens `/partner/orders/:id` after canonical reseed and stays inside the mounted marketplace workspace;
  - `/api/core/v1/marketplace/partner/orders/:id/incidents` returns `200`;
  - incident rows deep-link into `/partner/cases/:id`;
  - `/api/core/cases/:id` returns `200`;
  - the sidebar support anchor `/partner/support/requests` stays active on the canonical case trail.
- This live matrix depends on repo-truth reseed before browser proof:
  - `scripts/seed_partner_money_e2e.cmd` promotes the demo partner to canonical finance + marketplace capabilities/workspaces;
  - `scripts/smoke_marketplace_order_loop.cmd` seeds a fresh shared marketplace order and canonical case.
- The same seeded loop now verifies settlement-readiness truth explicitly:
  - `/api/core/v1/marketplace/partner/orders/:id/settlement` returns `409 SETTLEMENT_NOT_FINALIZED` until the settlement snapshot is finalized;
  - after admin finalization the same partner read returns `200` with snapshot hash, finalized timestamp, penalties, and net amount;
  - partner order detail keeps pending and finalized responses inside the mounted settlement-readiness state instead of rendering generic load failures.
- The default unseeded demo tenant must not be treated as implicit marketplace evidence.

## Removed or frozen partner shell ballast

These surfaces are no longer mounted in the canonical partner shell:

- `/stations*`
- `/transactions*`
- `/refunds*`
- `/integrations`
- `/settings`
- `/prices*`
- `/documents/:id`
- payout-batch / trace helper pages without mounted shell entrypoints

`/contracts` and `/settlements*` are no longer frozen ballast. They are mounted read-only finance registers behind `PARTNER_FINANCE_VIEW`; wrong-kind partners are routed back to their default workspace, and `PARTNER_SETTLEMENTS` alone still does not imply write authority. Dead payout-batch / trace helper pages without mounted shell entrypoints were removed from the repo in this wave instead of lingering as fake-parity residue.

Frozen/removed UI tails must stay explicit in docs because the shell intentionally avoids route handoff theater:

- no fake settlement write/approval owner in navigation
- no generic “all partners see all finance tabs” behavior
- no broad generic sections standing in for missing mounted owners

## Remaining compatibility tails

These tails were re-diagnosed in this wave and remain frozen because repo-visible consumers still exist:

| Tail | State | Why not removed |
| --- | --- | --- |
| `/api/core/partner/me` | compatibility projection over `portal/me` | still referenced by smoke scripts, tests, and contract docs |
| `/api/partner/dashboard` | compatibility redirect tail | still referenced by route topology sentinels and consumer docs |
| `/api/partner/acts`, `/api/partner/balance`, `/api/partner/invoices`, `/api/partner/ledger*`, `/api/partner/payouts*`, `/api/partner/contracts*`, `/api/partner/settlements*` | public parity-adjacent partner finance family | additive `/api/core/partner/*` parity exists for the main read surfaces, but repo-visible backend tests, docs, and compatibility consumers still reference the public family |
| `/api/v1/partner/fuel/stations/*/prices*` | public compatibility family | still used by partner fuel price tooling and backend tests |

No narrow partner tail removal was safe in this wave because canonical parity alone was not enough; repo-visible consumers still remain.

## Finance contracts / settlements read-only owner

The default backend app topology now mounts read-only finance registers:

- `/api/core/partner/contracts`
- `/api/core/partner/settlements*`
- `/api/partner/contracts`
- `/api/partner/settlements*`

The partner shell exposes these workflows from finance navigation and dashboard cards only for finance-view partners. Empty lists are honest launch states. Partner write/approval tails remain absent; for example settlement confirm returns `404`.

## Partner finance write exclusions

The partner shell still excludes these actions from launch:

- contract create/edit/approval
- settlement confirmation/approval/override
- payout batch/export operator actions outside existing payout request flow

What the user sees today:

- read-only contracts and settlements pages stay mounted behind `PARTNER_FINANCE_VIEW`
- wrong-kind partners do not see the finance surface
- navigation and dashboard cards present read-only registers, not write workflows
- runtime evidence is anchored in the mounted finance dashboard / ledger / payout request / admin approve contour plus contract/settlement read smokes

What re-opens them:

- a later admin/finance owner wave for write/approval semantics, not a partner shell shortcut

## Finance partner truth

`FINANCE_PARTNER` is treated as an external actor over existing finance owners. It:

- can read balance, ledger, payouts, invoices and acts through mounted finance owner routes
- can read contracts and settlement registers through mounted read-only owner routes
- can request payouts only where the existing owner workflow already supports it
- cannot change formulas, ledger semantics, settlement policy, or pricing logic

Current runtime evidence for this contour is no longer hypothetical:

- after canonical `scripts/seed_partner_money_e2e.cmd`, seeded `partner@neft.local` resolves finance-capable `portal/me` truth without hidden demo fallback
- mounted finance dashboard / ledger / payout preview / payout request flow is runtime-verified by `scripts/smoke_partner_money_e2e.cmd`
- mounted contracts/settlements route truth is runtime-verified by `scripts/smoke_partner_settlement_e2e.cmd`: finance partners receive read-only `200` responses from canonical and compatibility aliases, service partners redirect away in UI regression coverage, and settlement confirm/write tails stay `404`
- admin approve plus canonical audit correlation read are part of the same smoke, so the contour no longer stops at a read-only shell
- `/contracts` and `/settlements*` are dashboard/navigation read surfaces now; write actions remain explicit exclusions

No new money owner was introduced. Finance partner remains a consumer/operator over processing-core finance truth.
