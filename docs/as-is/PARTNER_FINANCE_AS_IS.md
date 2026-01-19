# Partner Finance (AS-IS)

## Summary

Partner finance is modeled as a ledger-backed balance with explicit payout gating:

- **EARNED** credits are created from completed marketplace orders (partner_net).  
- **SLA_PENALTY** debits reduce the available balance before payout.  
- Payout requests are allowed only from `balance_available` and move balance into `balance_blocked` until paid.
- Ledger entries reference settlement snapshots to preserve MoR traceability.

## Ledger semantics

| Entry type | Direction | Meaning |
| --- | --- | --- |
| EARNED | CREDIT | Partner net earnings (`gross - fee - penalties`). |
| SLA_PENALTY | DEBIT | SLA penalty applied before payout. |
| PAYOUT_REQUESTED | DEBIT | Requested payout locks funds. |
| PAYOUT_APPROVED | CREDIT | Approval event (no balance delta). |
| PAYOUT_PAID | DEBIT | Final payout. |

Gross client amounts **never** appear in the partner ledger.

## Partner Trust Layer (Sprint E2)

Partner portal exposes explainability endpoints on `/api/core/partner`:

- `GET /partner/orders/{order_id}/settlement` — settlement breakdown from immutable snapshot (gross/fee/penalties/net + hash).  
- `GET /partner/ledger/{entry_id}/explain` — ledger entry explain with source type/id, snapshot hash and breakdown link (if available).  
- `GET /partner/payouts/{payout_id}/trace` — payout batch composition with order-level totals and summary.  
- `POST /partner/exports/settlement-chain` — async export job for orders → settlements → payouts (CSV/ZIP).

All endpoints are ABAC-protected (`partner_org_id` must match the token org). Violations return **403** and emit audit events (`partner_trust_forbidden`).

## Settlement breakdown

For each marketplace order, a settlement breakdown snapshot is stored and audited:

- `gross_amount` — client payment to NEFT.  
- `platform_fee_amount` — platform commission.  
- `penalties_amount` — SLA penalties.  
- `partner_net_amount` — credited to partner ledger.  
- `currency`, `platform_fee_basis`.

The partner portal displays this snapshot with a fee formula and penalty source references (audit/SLA event ids),
including the immutable snapshot hash and finalized timestamp.

## Settlement chain export

CSV rows include:

- `order_id`
- `finalized_at`
- `gross`
- `fee`
- `penalties`
- `net`
- `payout_id`
- `payout_status`
- `snapshot_hash`

## Trust metrics

The following counters are emitted from `/api/core/metrics`:

- `partner_trust_settlement_breakdown_requests_total`
- `partner_trust_ledger_explain_requests_total`
- `partner_trust_payout_trace_requests_total`
- `partner_trust_exports_created_total`

## Payout gating

- Partner payouts are derived from `balance_available` only.  
- Penalties are applied before payout, reducing available balance.  
- This ensures partner documents and payouts match the ledger and settlement breakdown.
- Runtime blockers expose explicit reasons (threshold, legal status, disputes) in the partner portal.
