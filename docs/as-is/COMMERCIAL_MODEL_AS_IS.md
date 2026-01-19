# Commercial Model (AS-IS)

## Merchant of Record (MoR)

The platform operates as **Merchant of Record**:

1. The **client pays NEFT** (gross amount).  
2. NEFT retains the **platform fee**.  
3. The partner receives **partner_net** (gross minus fee and penalties).

No flow exists where the client pays the partner directly.

## Fee model

The platform fee is derived from the commission rules and recorded per order:

- **PERCENT** — fee is a percentage of gross.  
- **FIXED** — fee is a fixed amount.  
- **TIER** — fee is calculated by tiered rules.

The fee basis is stored as part of the settlement breakdown for auditability.

## Revenue accounting

Platform revenue is tracked as **platform_fee_amount** per order/period.
Dashboards should use platform fee totals, **not gross**, to represent revenue.
