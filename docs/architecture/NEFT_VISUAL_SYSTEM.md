# NEFT Visual System

## Canonical owner

The canonical code owner for the cross-portal visual system is:

- `frontends/shared/brand`

Current repo-truth implementation layers:

1. `frontends/shared/brand/v1/neft/colors/tokens.css`
2. `frontends/shared/brand/brand.css`
3. portal-specific shell adapters:
   - `frontends/admin-ui`
   - `frontends/partner-portal`
   - `frontends/client-portal`
4. client compatibility token bridge:
   - `brand/v1/neft-client/tokens.client.css`

There is no separate runtime `packages/ui` package in current repo-truth. Shared visual ownership currently lives in `frontends/shared/brand`.

## Visual direction

- dark-first
- premium fintech
- enterprise minimal
- data-first

Primary rules:

- numbers outrank prose
- status outranks decoration
- one surface language across admin, partner, and client
- portal differences are density/composition differences, not separate brands

## Foundation tokens

Canonical dark-first palette:

- canvas: `#0B1020`
- surface: `#11182A`
- surface-2: `#151E33`
- elevated: `#1A2440`
- text primary: `#F5F7FB`
- text secondary: `#A8B3CF`
- text muted: `#74809D`
- brand primary: `#E3AC21`
- brand accent: `#2F6BFF`
- gold: `#E3AC21`
- danger: `#F04D4D`
- success: `#16C784`
- warning: `#F5B942`
- info: `#38BDF8`

Dark NEFT Premium direction is now fixed as:

- graphite / black shell
- white typography
- gold as the primary brand tone from the NEFT droplet
- restrained blue only for CTA/data accents
- red only for danger/error semantics

Canonical type hierarchy:

- page title: `heading.lg`
- KPI / money / balances: `metric.*`
- table content: `body.md` / `body.sm`
- labels/status support copy: `label.*`

Canonical layout rules:

- sidebar `240px`
- collapsed sidebar `80px`
- content max `1440px`
- page padding `24px`
- 4px spacing grid

## Portal adaptations

### Client portal

- lighter density
- onboarding-first
- more helper copy
- more empty-state guidance
- dashboard composition must stay role-aware and recommendation-like only when grounded by role/workspace truth, not by fake “AI” cards
- still uses the same shell tokens and button / card / table language

### Partner portal

- workflow-heavy
- table/status/action oriented
- moderate density
- dashboard sections should collapse into next actions and capability-aware summaries, not generic “all sections for everyone”
- same shell tokens, stronger list/detail rhythm

### Admin portal

- strictest density
- data-first
- action-first
- stronger triage / inspection / audit framing
- no playful gamification, no streak/achievement language, no fake widgets on runtime/operator dashboards

## Shared shell components

Current shared shell components in repo-truth:

- `AppLogo`
- `BrandSidebar`
- `BrandHeader`
- `PageShell`
- `EmptyState`
- `StatusPill`
- `BrandIcon`

These are the canonical entrypoint for shared shell branding and must be preferred over portal-local copies.

## Generic screen patterns

Canonical reusable patterns already enforced by shared CSS:

- dashboard
- list/detail
- finance summary
- review / approval
- support/case timeline
- KPI cards
- table surfaces
- empty/error/loading states

Shared generic class ownership now includes:

- `card`
- `card__header`
- `card__section`
- `stack`
- `stack-inline`
- `stats-grid`
- `kpi-grid`
- `finance-summary-grid`
- `finance-summary-card`
- `metric-card`
- `stat`
- `table-shell`
- `table-toolbar`
- `table-toolbar__content`
- `table-footer`
- `table-footer__content`
- `surface-toolbar`
- `toolbar-actions`
- `table-row-actions`
- `table-container`
- `table-scroll`
- `filters`
- `filter`
- `quick-filters`
- `dashboard-grid`
- `dashboard-widget`
- `dashboard-list`
- `dashboard-health`
- `dashboard-actions`
- `modal`
- `modal-card`
- `timeline`
- `timeline-list`
- `timeline-item`
- `detail-panel`
- `detail-panel__sheet`
- `detail-panel__split`
- `detail-panel__card`
- `page-header`
- `section-title`

Portals should not redefine these with different semantics unless there is a scoped product reason.

Shared component ownership for interactive data surfaces now also includes:

- `EmptyState` for cross-portal empty-state composition
- `FinanceOverview` for finance summary cards in client / partner / admin
- `DetailPanel` for review-side panels and detail drawers
- reusable table shells as the owner of filter / error / empty / footer composition, not only page wrappers

Dashboard/state composition rules for the current repo-truth:

- client dashboards may use role-aware spotlight / next-step framing, but only from real role/workspace truth
- partner dashboards must show capability-aware workspace actions and finance visibility only where the finance owner is mounted
- admin dashboards must stay operator-first: priority routes, queue/runtime summaries, capability visibility, no synthetic KPI theater
- high-traffic dashboard sections should prefer `EmptyState` over raw `Нет данных` / plain text empties
- access-limited and first-use states must be explicit and must not pretend that a hidden owner surface exists
- high-traffic list/detail pages must expose state transitions the same way:
  - `loading` explains what contour is being loaded
  - `error` offers retry or a real fallback route
  - `empty` distinguishes first-use from filtered-empty
  - detail tabs must not show blank tables when files/history are truly absent
- document, support, case, queue, and logistics inspection pages should prefer explicit next steps over silent zero-data placeholders
- finance queue/detail surfaces should keep retry, filtered-empty, and count/footer semantics inside the table/detail owner rather than scattering them into page-local cards
- client support and finance detail pages should expose honest missing-history / missing-payment / missing-refund states instead of raw text or blank sections
- partner orders/services/finance lists should treat first-use, filtered-empty, retry, and count footer as part of the shared list language
- support-create flows should honor known deep-link topics and prefill contour context instead of opening as blank generic forms
- export/order/payout detail pages should prefer explicit section empties over muted one-line placeholders for proofs, reconciliation, penalties, snapshot, trace, and audit-chain gaps
- list/detail finance-support pages should also keep form-level honesty:
  - access-limited actions should render as explicit states instead of disabled pseudo-forms
  - unavailable subreads should not masquerade as genuine empty history
  - modal action failures should stay inside the same operator/user contour with a readable next step

## Client bridge

`client-portal` still has historical `neftc-*` runtime classes and token names. Current safe alignment model is:

- client tokens mirror the canonical NEFT palette and spacing
- client tokens export a bridge back into `--neft-*`
- `client-portal` imports `@shared/brand/brand.css` after client-local CSS so canonical shared styling becomes the final owner for overlapping generic classes

This is an intentional compatibility bridge, not a second design-system owner.

## Client CSS owner map

`frontends/client-portal/src/index.css` is no longer a dead-residue bucket. Current repo-truth shows four live owner families:

- structural bridge:
  - `card`
  - `stack`
  - `card__header`
  - `card__section`
  - `section-title`
  - `card-grid`
  - `pagination`
  - `label`
  - `meta-grid`
- form bridge:
  - `checkbox-row`
  - `checkbox-grid`
- feature-owned dynamic:
  - `achievement-badge*`
  - owner: `frontends/client-portal/src/features/achievements/components/AchievementBadge.tsx`
- feature-owned analytics:
  - `attention-list*`
  - owner: `frontends/client-portal/src/components/analytics/AttentionList.tsx`

Route/page-owner-aware migration rules:

- no selector removal while a family still has mounted consumers
- do not hide bridge selectors by moving them into shared brand CSS without a page-owner handoff
- migrate self-contained feature families first
- structural bridge families move only as part of a route/page-owner migration per slice
- page-scoped CSS owners already exist and should be preferred for future slice migrations:
  - `frontends/client-portal/src/layout/client-layout.css`
  - `frontends/client-portal/src/pages/DashboardPage.tsx`
  - `frontends/client-portal/src/pages/dashboard/DashboardRenderer.tsx`
  - `frontends/client-portal/src/pages/stations/stations-map.css`

## Figma truth

Target Figma structure remains:

- `00 Foundations`
- `01 Tokens`
- `02 Components`
- `03 Patterns`
- `04 Client Portal`
- `05 Partner Portal`
- `06 Admin Portal`
- `07 Prototypes`
- `08 Archive`

Repo does not store Figma files, but runtime docs and code must keep the same ownership model.

## Rollout rules

When changing UI across portals:

1. prefer updating `frontends/shared/brand` first
2. use portal-local CSS only for density/workflow adaptations
3. do not introduce a new visual token family per portal
4. do not keep duplicate button/card/table semantics alive in parallel
5. remove or freeze legacy visual layers only after shared parity exists

## Known residue

- `frontends/client-portal/src/styles/neft-client-brand.css` still contains historical client-local styling beyond the shared shell layer
- some portal pages still have page-local CSS for legacy widgets and complex workflows
- no dedicated runtime `packages/ui` workspace exists yet

These are compatibility / rollout residue, not canonical visual ownership.
