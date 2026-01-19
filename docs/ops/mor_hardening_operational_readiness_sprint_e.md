# MoR Hardening & Operational Readiness — Sprint E (P0/P1)

> Scope definition + Definition of Done (DoD) for MoR hardening, operational readiness,
> and partner trust layer. This is a single reference checklist for product/engineering/ops.

## 1) P0 — Single Source of Truth (SSoT) for money

**Goal:** eliminate discrepancies between order, settlement, partner ledger, platform revenue,
invoice, and partner act.

### Requirements
- Introduce **immutable settlement snapshot**:
  - `settlement_id`
  - `gross`
  - `platform_fee`
  - `penalties`
  - `partner_net`
  - `currency`
  - `finalized_at`
- All downstream operations (ledger, payout, revenue, invoices) reference **only** the snapshot
  (no re-calculation downstream).

### DoD
- After `finalized_at`, settlement values cannot be changed without **explicit admin override + audit event**.
- Reconciliation reports show no drift between snapshot, ledger, revenue, and invoices.

## 2) P0 — Payout Safety & Thresholds

**Goal:** prevent “small/unsafe” payouts and operational mistakes.

### Requirements
- Add partner payout settings:
  - `min_payout_amount`
  - `payout_hold_days`
  - `payout_schedule` (`WEEKLY` / `BIWEEKLY` / `MONTHLY`)
- Auto-aggregate earnings until the threshold is met.
- Explicit balance states in UI/API:
  - `balance_available`
  - `balance_pending`
  - `balance_blocked`

### DoD
- Payout cannot be requested or approved below the threshold.
- Partner can see **why** payout is unavailable (threshold/hold/schedule).

## 3) P0 — Finance Ops Panel (Admin)

**Goal:** finance/sales/superadmin can operate MoR without engineering.

### Minimum UI/Reports
- Settlement batches list.
- Partner balances.
- Payout queue.
- SLA penalties overview.
- MoR overrides (read-only + action log).

### DoD
- All MoR key numbers are accessible from admin UI.
- Any manual action creates an **audit event** (who/when/why).

## 4) P1 — Partner Trust Layer

**Goal:** partner can verify payout independently and trust calculations.

### Requirements (Partner Portal)
- Settlement breakdown per order.
- Transparent fee formula.
- SLA penalties with links to originating events.

### Export
- CSV/ZIP export chain: **orders → settlements → payouts**.

### DoD
- Partner can verify any payout without support escalation.

## 5) P1 — Legal / Docs Consistency

**Goal:** legal/accounting have a single, consistent document chain.

### Requirements
- Hard-link:
  - settlement ↔ partner act
  - invoice ↔ gross amount
- Auto package:
  - client invoice
  - partner act
  - settlement appendix

### DoD
- One order yields one consistent document package.
- Document chain reconciles with ledger and settlement snapshot.

## 6) P0 — Negative Scenarios (Runtime)

**Goal:** predictable behavior under failures/edge cases.

### Mandatory scenarios
- Client refund → partner clawback.
- SLA penalty > fee.
- Order dispute after payout.
- Partner suspended (legal/tax).

### DoD
- Scenarios are described in runbook.
- Admin actions exist for resolution.
- No silent failures (all exceptions → audit + alert).

> **Runbook:** see `docs/ops/finance_negative_scenarios.md` for deterministic steps and
> integration coverage of refund/SLA penalty scenarios.

## 7) P0 — Extended E2E Smoke

**Scenario A — Happy path**
1. Client pays.
2. Order done.
3. Settlement finalized.
4. Payout requested.
5. Payout approved.
6. Partner balance = 0.
7. Platform revenue = fee.

**Scenario B — Penalty path**
1. SLA breach.
2. Partner net reduced.
3. Payout reflects penalty.

### DoD
- Both scenarios added to E2E smoke pipeline.
- Assertions check settlement snapshot, ledger, payout, and revenue consistency.

---

## Acceptance checklist
- [ ] Settlement snapshot stored + immutable after `finalized_at` without admin override.
- [ ] Payout thresholds enforced and visible to partner.
- [ ] Admin panel exposes settlement batches, balances, payout queue, SLA penalties, and overrides.
- [ ] Partner portal exposes settlement breakdown, fee formula, SLA penalty sources.
- [ ] Export chain orders → settlements → payouts available.
- [ ] Document package auto-generated (invoice, act, appendix).
- [ ] Negative scenarios documented with admin actions and alerting.
- [ ] Extended E2E smoke scenarios verified.
