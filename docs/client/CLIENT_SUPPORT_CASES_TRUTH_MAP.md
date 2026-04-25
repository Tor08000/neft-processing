# Client Support / Cases Truth Map

## Scope

This map freezes the mounted client support and case contour after the support/cases unification wave. It covers:

- client support tickets under `/client/support*`
- canonical cases under mounted `/cases*`
- marketplace order incident linkage from `/marketplace/orders/:id`

It does not re-open new public API families and it does not change the support/helpdesk money semantics.

## Owner map

| Surface | Runtime owner | Client portal state |
| --- | --- | --- |
| `/client/support*` | support ticket/helpdesk sidecar linked to canonical case | mounted and visible in navigation |
| `/cases*` | canonical `/api/core/cases*` | mounted as deep-link/read trail; intentionally hidden from navigation |
| `/marketplace/orders/:id` incidents tab | order-scoped canonical cases via `/api/v1/marketplace/client/orders/:id/incidents` | mounted and linked into `/cases/:id` |
| `/marketplace/orders/:id` credits and penalties tab | `/api/core/client/marketplace/orders/:id/consequences` | mounted read surface; returns `200` with an `items` list and honest empty state when there are no credits/penalties |
| `/support/requests*` | compatibility redirect tail | frozen redirect into `/client/support` |

## Mounted vs frozen decision

- `/client/support*` stays the visible client owner surface for creating and tracking helpdesk requests.
- `/cases*` stays mounted because support tickets and marketplace incidents need a canonical case trail, but it is not a top-level client navigation section.
- `/support/requests*` remains compatibility-only and must not grow new owner semantics.

## Visibility truth

- Client navigation exposes `Support` at `/client/support`.
- Client navigation must not expose a standalone `/cases` menu item.
- When a user lands on `/cases/:id`, the support navigation item remains the active shell anchor.

## Marketplace incident linkage

- Marketplace order incidents are read from `/api/v1/marketplace/client/orders/:id/incidents`.
- Each incident entry deep-links into `/cases/:id`.
- The marketplace order page does not invent a second incident owner or a separate client-only lifecycle.
- Marketplace credits and penalties stay in the same order detail shell, and `/api/core/client/marketplace/orders/:id/consequences` is mounted as a read owner over persisted SLA/consequence data.
- Missing SLA contract-link data must not downgrade an existing order into `order_not_found`; absence of consequences is an empty `items` list.

## Explicit tails

| Tail | State | Reason |
| --- | --- | --- |
| `/support/requests*` | frozen compatibility redirect | repo-visible consumer path still exists |
| hidden `/cases*` nav omission | deliberate freeze | canonical case trail is needed, but client IA stays support-first |
| `/api/core/client/marketplace/orders/:id/consequences` empty order result | mounted empty state | no persisted consequence row for the order |

## Verification anchors

- `frontends/client-portal/src/layout/ClientLayout.test.tsx`
- `frontends/client-portal/src/pages/CasesPage.test.tsx`
- `frontends/client-portal/src/pages/SupportTicketDetailsPage.test.tsx`
- `frontends/client-portal/src/pages/MarketplaceOrderDetailsPage.test.tsx`
- live evidence: `docs/diag/client-partner-support-marketplace-live-smoke.json`

## Live runtime freeze

- Live browser proof is anchored in `docs/diag/client-partner-support-marketplace-live-smoke.json`.
- Current verified runtime at `2026-04-25T12:14:00+03:00` shows:
  - `/client/marketplace/orders/:id` opens the incidents tab without auth/bootstrap bounce;
  - `/api/core/v1/marketplace/client/orders/:id/incidents` returns `200`;
  - incident rows deep-link into `/client/cases/:id`;
  - `/api/core/cases/:id` returns `200`;
  - `/api/core/client/marketplace/orders/:id/consequences` returns `200` with an `items` list, and the portal keeps empty consequences as explicit no-credits/no-penalties copy;
  - the visible shell anchor remains `/client/client/support`.
- The client live proof depends on a fresh canonical marketplace order/case seeded by `scripts/smoke_marketplace_order_loop.cmd`; the portal should not assume ambient historical demo data.
