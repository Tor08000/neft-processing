# MoR Runtime Invariants (Sprint F2)

This document captures the **runtime-enforced** invariants for the Marketplace MoR
(Merchant of Record) flow. These rules are enforced by application guards and
cannot be bypassed without explicit admin override + audit.

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
