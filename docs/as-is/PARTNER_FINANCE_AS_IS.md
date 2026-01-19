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

## Settlement breakdown

For each marketplace order, a settlement breakdown snapshot is stored and audited:

- `gross_amount` — client payment to NEFT.  
- `platform_fee_amount` — platform commission.  
- `penalties_amount` — SLA penalties.  
- `partner_net_amount` — credited to partner ledger.  
- `currency`, `platform_fee_basis`.

## Payout gating

- Partner payouts are derived from `balance_available` only.  
- Penalties are applied before payout, reducing available balance.  
- This ensures partner documents and payouts match the ledger and settlement breakdown.
