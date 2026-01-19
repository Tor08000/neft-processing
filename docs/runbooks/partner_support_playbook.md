# Partner Support Playbook: Trust Layer

## Purpose

This playbook explains how to answer partner questions about payouts, penalties, and ledger entries
using the Partner Trust Layer endpoints and Partner Portal UI.

## Quick intake checklist

1. Identify the **partner org_id** and **order_id** from the partner request.
2. Confirm the partner is querying their own org (ABAC is enforced and forbidden access is audited).
3. Collect the relevant payout batch id (if the question is about a payout).

## Explain a settlement per order

Use the settlement breakdown endpoint (immutable snapshot only):

```
GET /api/core/partner/orders/{order_id}/settlement
```

What to highlight:

- **Gross / Fee / Penalties / Net** values are derived from the finalized snapshot.
- The **snapshot hash** is the immutable reference for audit.
- Penalty items include audit/SLA references for “why was it withheld”.

If the response returns `SETTLEMENT_NOT_FINALIZED`, explain that the settlement has not been finalized yet
and will appear after settlement processing completes.

## Explain a ledger entry

Use the ledger explain endpoint:

```
GET /api/core/partner/ledger/{entry_id}/explain
```

What to highlight:

- Source type + source id (order, payout, or manual adjustment).
- Snapshot hash and breakdown link when the entry is derived from a settlement snapshot.
- If the source is missing, the entry is a **manual adjustment** and the admin actor id is included.

## Trace a payout batch

Use the payout trace endpoint:

```
GET /api/core/partner/payouts/{payout_id}/trace
```

What to highlight:

- Included orders and their settlement totals.
- Summary totals: gross/fee/penalties/net.
- Each order links back to the settlement breakdown.

## Export the settlement chain

Partners can request a report via:

```
POST /api/core/partner/exports/settlement-chain
```

Payload:

```
{"from":"YYYY-MM-DD","to":"YYYY-MM-DD","format":"CSV|ZIP"}
```

The export contains order → settlement → payout mapping and the snapshot hash for audit.

## Common responses

| Question | Response checklist |
| --- | --- |
| “Why was my payout smaller?” | Confirm payout trace, review penalties + ledger explain. |
| “What is this ledger entry?” | Use ledger explain for source + snapshot hash. |
| “Why no settlement yet?” | Settlement not finalized; retry once settlement snapshot finalized. |

## Escalation

Escalate to finance ops if:

- Snapshot hash is missing for a completed order.
- Ledger entry lacks a source and admin actor id.
- Payout trace does not include expected orders.
