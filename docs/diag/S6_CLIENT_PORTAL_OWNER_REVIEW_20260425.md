# S6 Client Portal Owner Review Closeout - 2026-04-25

## Scope

This review covers S6 from `docs/diag/RELEASE_PATCH_SLICES_20260425.md`:

- `frontends/client-portal/**`
- adjacent docs corrections in `docs/client-portal.md` and `docs/architecture/NEFT_VISUAL_SYSTEM.md`

No staging, commits, branch split, patch bundle generation, public API changes, money semantic changes, auth semantic changes, or route-family removals were performed.

## S6 Client Portal

Review-visible S6 scope:

| Status | Count |
| --- | ---: |
| `M` | 120 |
| `D` | 8 |
| `??` | 26 |
| Total | 154 |

Primary owner areas:

- canonical `src/App.tsx` route map and workspace/onboarding gates
- client bootstrap over `/api/core/portal/me`
- client-kind segmentation for personal vs business workspaces
- dashboard over `/api/core/client/dashboard`
- canonical documents routing under `/client/documents*` with legacy `/documents/:id` compatibility
- support/cases, finance read pages, exports, subscriptions, and marketplace order detail states
- client logistics trip create and fuel-consumption analytics reads
- shared brand shell/layout adoption and state-quality tests

## Deletion Review

Deleted files under S6:

- `frontends/client-portal/src/components/__snapshots__/EmptyState.test.tsx.snap`
- `frontends/client-portal/src/components/overview/HeroSummaryCard.tsx`
- `frontends/client-portal/src/components/overview/OperationRow.tsx`
- `frontends/client-portal/src/components/overview/OverviewEmptyState.tsx`
- `frontends/client-portal/src/components/overview/VehicleCard.tsx`
- `frontends/client-portal/src/pages/ConnectFlowPage.tsx`
- `frontends/client-portal/src/pages/OverviewPage.tsx`
- `frontends/client-portal/src/pages/overview.css`

Deletion decision:

| Deleted family | Replacement / freeze evidence |
| --- | --- |
| old overview component subtree and `OverviewPage` | replaced by canonical `pages/DashboardPage.tsx`, `pages/dashboard/DashboardRenderer.tsx`, `layout/ClientLayout.tsx`, shared brand dashboard/list classes, and dashboard state tests |
| `overview.css` | retired with the old overview route; current styling owners are `layout/client-layout.css`, `src/index.css` bridge classes, shared `frontends/shared/brand`, and page-local owners such as `stations-map.css` |
| `ConnectFlowPage` | frozen as compatibility redirects from `/connect*` to canonical `/onboarding*`; locked by `pages/ConnectFlowPage.test.tsx` and `App.onboarding-routing.test.tsx` |
| `EmptyState` snapshot | replaced by explicit DOM assertions in `components/EmptyState.test.tsx`; the shared state component is tested by rendered copy/roles rather than a stale snapshot file |

These deletions are not accepted globally by this document. They are eligible for S6 owner staging only with this evidence, the route/state sentinels, and the passing build/test gate below.

## Reference Scan

Deleted S6 paths were scanned across `docs` and `frontends/client-portal`.

Live code does not import the deleted `ConnectFlowPage`, `OverviewPage`, overview components, or `overview.css`. Remaining matches are limited to hygiene/freeze docs that intentionally list the deletion candidates.

Two stale docs references to `frontends/client-portal/src/pages/overview.css` were corrected:

- `docs/client-portal.md`
- `docs/architecture/NEFT_VISUAL_SYSTEM.md`

Those docs now point to the current dashboard/layout ownership instead of the retired overview CSS tail.

## Checks

| Check | Result |
| --- | --- |
| deleted-path reference scan over `docs frontends/client-portal` | PASS; no live imports or smoke consumers |
| `npx.cmd vitest run` in `frontends/client-portal` | PASS, `79` files / `245` tests |
| `npm.cmd run build` in `frontends/client-portal` | PASS; brand/shared import checks, `tsc`, and Vite production build passed |

## Review Decision

S6 is reviewable as a client-portal owner slice. Deleted client files have replacement or freeze evidence, compatibility redirects stay locked by sentinels, and the portal build/test gate is green.

Final packaging still must use explicit S6 pathspecs. Do not stage generated browser results, unrelated docs/evidence, or root helper deletions with this slice.
