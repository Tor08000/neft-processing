# MoR Policy (TO-BE)

## Policy flag

`payment_flow = PLATFORM_MOR` is the default and enforced policy for marketplace orders.
The client always pays NEFT; direct client → partner payments are not allowed.

## Settlement breakdown

Each order has a deterministic settlement breakdown:

- `gross_amount` — client payment to NEFT.  
- `platform_fee_amount` — fee retained by NEFT.  
- `platform_fee_basis` — PERCENT / FIXED / TIER.  
- `penalties_amount` — SLA penalties applied pre‑payout.  
- `partner_net_amount` — credited to partner ledger.  
- `currency`.

Invariant: `partner_net_amount = gross_amount - platform_fee_amount - penalties_amount`.

## Ledger & payout rules

1. **Order DONE → compute settlement breakdown.**  
2. **Apply SLA penalties** → update breakdown and ledger.  
3. **Post ledger entries**:
   - CREDIT EARNED = partner_net_amount  
   - DEBIT SLA_PENALTY  
   - DEBIT PAYOUT_PAID  
4. **Payout available** only after penalties are applied.

## Documents

- Client invoice is issued by NEFT for `gross_amount`.  
- Partner receives an NEFT act/registry for `partner_net_amount` (Option A).  
- Documents must reconcile with payouts and ledger.

## Revenue

Platform revenue is computed from `platform_fee_amount`.
Revenue dashboards must use fees (not gross) for MoR reporting.
