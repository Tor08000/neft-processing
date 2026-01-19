# MoR Runtime Invariants (Sprint G1 — FINAL)

This document captures the **runtime-enforced** invariants for the Marketplace MoR
(Merchant of Record) flow. These rules are enforced by application guards and
cannot be bypassed without explicit admin override + audit.

## Required invariants (must hold in production)

| Invariant | Guardrail / Enforcement | Audit + Metric |
| --- | --- | --- |
| Settlement snapshot is immutable after `finalized_at` | `MarketplaceSettlementService._upsert_snapshot` blocks mutations unless override | Audit: `SETTLEMENT_IMMUTABLE_VIOLATION`, Metric: `core_api_mor_settlement_immutable_violation_total` |
| Payout is allowed **only** from `balance_available` | `PartnerFinanceService.evaluate_payout_blockers` checks available balance before payout batch | Audit: `MARKETPLACE_PAYOUT_BLOCKED`, Metric: `core_api_mor_payout_blocked_total{reason=...}` |
| Penalty applied **before payout** | `MarketplaceSettlementService.update_penalty_for_order` updates settlement snapshot + ledger before payout batch build | Audit: `MARKETPLACE_PENALTY_CLAWBACK_REQUIRED` (if needed) |
| Refund → clawback | `MarketplaceSettlementService.update_penalty_for_order` emits clawback required when net negative | Audit: `MARKETPLACE_PENALTY_CLAWBACK_REQUIRED`, Metric: `core_api_mor_clawback_required_total` |
| Admin override is always audited | `MarketplaceSettlementService.override_settlement_snapshot` requires reason | Audit: `SETTLEMENT_OVERRIDE`, Metric: `core_api_mor_admin_override_total` |

## I1 — Settlement snapshot is the single source of truth

All money movements must be backed by a settlement snapshot:

- partner ledger entries
- platform revenue entries
- payout batches
- partner invoices/acts

**Forbidden**

- Recalculate gross/fee/net after `finalized_at` without override
- Create payout items without snapshot references

## I2 — No snapshot → no money

While a settlement snapshot is not finalized, the system **blocks** payout creation
and prevents revenue recognition or partner documents without snapshot linkage.

## I3 — Access ≠ money

Access is restored **only** when all are true:

- `invoice.status == PAID`
- `subscription.status == ACTIVE`
- `entitlements.allow == true`

Payment events alone never grant access.

## I4 — No silent fixes

Any manual override, skip, or force operation must emit an **audit** event and
is time-limited. Overrides are visible in the settlement snapshot and partner UI.

## Trust visibility endpoints

Operators can validate partner-visible transparency via the Partner Trust Layer endpoints:

- `/api/core/partner/orders/{order_id}/settlement`
- `/api/core/partner/ledger/{entry_id}/explain`
- `/api/core/partner/payouts/{payout_id}/trace`
- `/api/core/partner/exports/settlement-chain`

These endpoints should always reflect the immutable settlement snapshot and enforce ABAC checks.

## Runtime guardrail reasons (payout)

Payout creation and payout requests are blocked with explicit reasons, for example:

- `MIN_THRESHOLD`
- `HOLD_ACTIVE`
- `SCHEDULE_LOCK`
- `LEGAL_PENDING`
- `DISPUTES_OPEN`
- `NEGATIVE_NET`
- `NO_SNAPSHOT`

Each block is audited and counted in MoR runtime metrics.
