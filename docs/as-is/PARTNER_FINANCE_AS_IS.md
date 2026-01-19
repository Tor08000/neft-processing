# Partner Finance (AS-IS)

## Summary

Partner finance is modeled as a ledger-backed balance with explicit payout gating:

- **EARNED** credits are created from completed marketplace orders (partner_net).  
- **SLA_PENALTY** debits reduce the available balance before payout.  
- Payout requests are allowed only from `balance_available` and move balance into `balance_blocked` until paid.

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

- `GET /partner/orders/{order_id}/settlement` — settlement breakdown with fee formula, penalties and snapshot hash.  
- `GET /partner/ledger/{entry_id}/explain` — ledger entry explain with source type/id and formula (if available).  
- `GET /partner/payouts/{payout_id}/trace` — payout batch composition with order-level totals.  
- `POST /partner/exports/settlement-chain` — async export job for orders → settlements → payouts (CSV/ZIP).

All endpoints are ABAC-protected (`partner_org_id` must match the token org). Violations return **403** and emit audit events.

## Settlement breakdown

For each marketplace order, a settlement breakdown snapshot is stored and audited:

- `gross_amount` — client payment to NEFT.  
- `platform_fee_amount` — platform commission.  
- `penalties_amount` — SLA penalties.  
- `partner_net_amount` — credited to partner ledger.  
- `currency`, `platform_fee_basis`.

The partner portal displays this snapshot with a fee formula and penalty source references (audit/SLA event ids).

## Payout gating

- Partner payouts are derived from `balance_available` only.  
- Penalties are applied before payout, reducing available balance.  
- This ensures partner documents and payouts match the ledger and settlement breakdown.
