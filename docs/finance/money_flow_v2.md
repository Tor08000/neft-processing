# Money Flow v2 (Core)

## Overview
Money Flow v2 provides a canonical state machine for all monetary operations (fuel, subscriptions, invoices, refunds, payouts).
It stores a deterministic audit trail in `money_flow_events` and powers admin explain/health endpoints.

## Canonical states
- `DRAFT`
- `AUTHORIZED`
- `PENDING_SETTLEMENT`
- `SETTLED`
- `REVERSED`
- `DISPUTED`
- `FAILED`
- `CANCELLED`

## Canonical event types
- `AUTHORIZE`
- `SETTLE`
- `REVERSE`
- `DISPUTE_OPEN`
- `DISPUTE_RESOLVE`
- `FAIL`
- `CANCEL`

## Money flow types
- `FUEL_TX`
- `SUBSCRIPTION_CHARGE`
- `INVOICE_PAYMENT`
- `REFUND`
- `PAYOUT`

## money_flow_events
Each event captures:
- `flow_type` + `flow_ref_id`
- `state_from` → `state_to`
- `event_type`
- `ledger_transaction_id` and `risk_decision_id` (optional)
- `explain_snapshot` (canonical JSON with hash)

## Explain snapshot
Use `app.services.money_flow.explain.build_explain_snapshot` to create a deterministic payload:
```
{
  "hash": "<sha256>",
  "payload": { ... }
}
```

## Admin endpoints
- `GET /api/core/v1/admin/money/explain?flow_type=...&flow_ref_id=...`
- `GET /api/core/v1/admin/money/health`
