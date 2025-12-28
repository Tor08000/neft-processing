# Unified Explain v1

## Overview
Unified Explain provides a single admin endpoint that aggregates explainability signals across fuel, logistics, limits, risk, money, and document domains. The response is structured for fleet managers (behavior/route/risk) and accountants (limits/money/documents) using a view parameter.

## Endpoint
`GET /api/v1/admin/explain`

### Query parameters
- `fuel_tx_id`: Fuel transaction id.
- `order_id`: Logistics order id.
- `invoice_id`: Invoice id.
- `view`: `FLEET | ACCOUNTANT | FULL` (default `FULL`).
- `depth`: Graph trace depth (default `3`).
- `snapshot`: `true | false` (default `false`).

Exactly one of `fuel_tx_id`, `order_id`, or `invoice_id` must be provided.

## Response shape
```json
{
  "subject": {
    "type": "FUEL_TX",
    "id": "...",
    "ts": "...",
    "client_id": "...",
    "vehicle_id": "...",
    "driver_id": "..."
  },
  "result": {
    "status": "DECLINED",
    "primary_reason": "LIMIT_EXCEEDED",
    "decline_code": "LIMIT_EXCEEDED_AMOUNT"
  },
  "sections": {
    "limits": { },
    "risk": { },
    "logistics": { },
    "navigator": { },
    "money": { },
    "documents": { },
    "graph": { }
  },
  "ids": {
    "risk_decision_id": "...",
    "ledger_transaction_id": "...",
    "invoice_id": "...",
    "document_ids": ["..."],
    "money_flow_event_ids": ["..."],
    "snapshot_id": "...",
    "snapshot_hash": "..."
  },
  "recommendations": ["..."]
}
```

## Snapshot behavior
When `snapshot=true`, the service stores a deterministic, canonical JSON snapshot and returns `snapshot_id` and `snapshot_hash`.

## Views
- `FLEET`: prioritizes logistics, navigator, risk, limits, money.
- `ACCOUNTANT`: prioritizes money, limits, documents, risk.
- `FULL`: returns all available sections.
