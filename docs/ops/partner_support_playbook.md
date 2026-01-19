# Partner Support Playbook — Finance & Trust Layer

## Scope

This runbook explains how to answer partner questions about settlements, penalties and payouts using the Partner Trust Layer endpoints.

## Quick checks

1. Verify partner org context (token org matches request).
2. Use the order settlement breakdown endpoint to show the fee formula, penalties and snapshot hash.
3. Use the ledger explain endpoint to reference the source object (order/payout) and formula.
4. Use the payout trace endpoint to list orders included in the payout batch.

## Order settlement breakdown

**Endpoint**

`GET /api/core/partner/orders/{order_id}/settlement`

**What to tell the partner**

- Gross is the client-facing total (no invoice line disclosure).
- Platform fee includes basis + rate (no tier rules).
- Penalties include SLA breach reason + source references.
- Net = gross − fee − penalties.
- Snapshot hash ties the breakdown to the finalized settlement snapshot.

## Ledger entry explain

**Endpoint**

`GET /api/core/partner/ledger/{entry_id}/explain`

**What to tell the partner**

- Operation type (EARNED / SLA_PENALTY / PAYOUT_*).
- Source object (order / payout request).
- Formula if available (gross − fee − penalties).

## Payout trace (batch composition)

**Endpoint**

`GET /api/core/partner/payouts/{payout_id}/trace`

**What to tell the partner**

- Which orders/settlements were included in the batch.
- Totals and penalties withheld.
- Payout period and state.

## Export settlements

**Endpoint**

`POST /api/core/partner/exports/settlement-chain`

Payload:

```
{
  "from": "2026-03-01",
  "to": "2026-03-31",
  "format": "CSV" | "ZIP"
}
```

Use `/api/core/partner/exports/jobs` to check status and `/download` when the job is complete.
