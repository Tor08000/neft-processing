# ADR-0007 — Money Owner Truth

## Status

Accepted

## Decision

- Canonical admin billing control-plane owner is `processing-core` under `/api/core/v1/admin/billing/*`.
- Canonical admin operator-finance queue/read-action owner is `processing-core` under `/api/core/v1/admin/finance/*`.
- Canonical money diagnostics/explain/replay owner is `processing-core` under `/api/core/v1/admin/money/*`.
- Canonical partner self-serve finance owner is `processing-core` under `/api/core/partner/finance/*`.
- `reports_billing` remains a frozen compatibility read/export family under `/api/v1/reports/*`; see ADR-0004.
- `/api/v1/admin/*` remains a live compatibility/public family and must not be treated as the canonical owner by default.
- Hidden `/api/core/admin/*` finance aliases remain compatibility ballast only and must stay schema-hidden.

## Owner map

### Canonical owners
- `admin/billing`
  - billing summary read/control
  - billing periods / billing runs
  - tariff admin surface
  - canonical invoice list/detail/generate/status/PDF surface
- `admin/billing_flows`
  - explicit invoice / payment / refund action flow owner over `billing_flows` storage
- `admin/finance`
  - operator overview
  - payment-intake review/confirm
  - reflected invoice queue and payout queue actions
  - partner payout policy / partner ledger seeding
- `admin/money_flow`
  - money explain / health / CFO explain / replay diagnostics
- `admin/clearing`, `admin/reconciliation`, `admin/revenue`, `admin/refunds`, `admin/reversals`, `admin/disputes`, `admin/settlements`
  - keep their domain-specific admin ownership
- `partner_finance`
  - partner dashboard / ledger / payouts / finance docs / export jobs

### Compatibility or bridge surfaces
- `/api/v1/reports/*`
  - billing-summary and turnover compatibility projections over canonical storage
- `/api/v1/admin/*`
  - compatibility/public admin namespace; route presence does not make it the owner
- `admin_core_finance`
  - hidden `/api/core/admin/*` bridge over canonical `/api/core/v1/admin/finance/*`
  - remaining tails: `/api/core/admin/payouts*`, `/api/core/admin/partner/{partner_id}/ledger`, `/api/core/admin/partner/{partner_id}/settlement`
- `partner_finance_legacy`
  - redirect-only compatibility tail

### Active public families that are not removal candidates yet
- `/api/v1/invoices/*`
  - active batch invoice/payment/refund family with repo-visible tests and docs
- `/api/v1/payouts/*`
  - active payout batch/export family with repo-visible tests and docs

## Why

- `billing`, `finance`, `reports_billing`, `partner_finance`, and API-v1 money routes all coexist in `processing-core`.
- Before this decision, route presence made it too easy to confuse:
  - canonical owner
  - operator queue/read surface
  - compatibility projection
  - hidden bridge
- `frontends/admin-ui` consumes both canonical admin billing and operator finance surfaces.
- `client-portal` and partner payout/export scenarios still rely on API-v1 invoice/payout families, so they are not safe removal candidates without separate consumer diagnosis.

## Unresolved but explicit weak zones

- `admin/finance` is still partly reflection-backed over shared money tables. It is an operator surface, not the product owner for billing summary truth.
- `frontends/admin-ui` billing/reconciliation screens still expose explicit `unavailable` states for some flow endpoints. That is underpowered compatibility behavior, not proof that those APIs are fake or removable.
- `reports_billing` access posture stays compatibility-only but public-facing until live consumer evidence says otherwise.

## What this ADR does not approve

- changing billing formulas
- changing clearing / settlement / payout semantics
- removing `/api/v1/invoices/*` or `/api/v1/payouts/*`
- flipping `/api/v1/admin/*` consumers to canonical routes without parity proof
- destructive money-schema changes
