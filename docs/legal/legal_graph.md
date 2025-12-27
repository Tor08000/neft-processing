# Legal Graph v1

## Overview

Legal Graph stores auditable relationships between legal artifacts (documents, invoices, payments, exports, billing periods, closing packages) and produces immutable snapshots on finalize/lock events.

## Node types

| Type | Description |
| --- | --- |
| DOCUMENT | Document record (invoice/act/reconciliation/offer) |
| DOCUMENT_FILE | Document file artifact (PDF/XLSX/SIG/etc.) |
| DOCUMENT_ACK | Document acknowledgement record |
| CLOSING_PACKAGE | Closing package that groups documents |
| BILLING_PERIOD | Billing period | 
| INVOICE | Invoice |
| PAYMENT | Invoice payment |
| CREDIT_NOTE | Credit note |
| REFUND | Refund request |
| SETTLEMENT_ALLOCATION | Settlement allocation |
| ACCOUNTING_EXPORT_BATCH | Accounting export batch |
| RISK_DECISION | Risk decision record |
| OFFER | Offer document |

## Edge types

| Type | Meaning |
| --- | --- |
| GENERATED_FROM | Document generated from invoice/period/export |
| CONFIRMS | Document confirms settlement/export |
| CLOSES | Closing package closes billing period |
| INCLUDES | Closing package includes document |
| RELATES_TO | Generic relation (allocations to invoices, payments, periods) |
| SIGNED_BY | Document signed/acknowledged by actor/ack record |
| GATED_BY_RISK | Risk decision gates target action |
| SETTLES | Payment settles invoice |
| EXPORTS | Export batch exports docs/allocations/period |
| REPLACES | New document version replaces old |
| ALLOCATES | Settlement allocation applies to invoice |
| OVERRIDDEN_BY | Risk decision override relation |

## Snapshot rules

Snapshots are created for:

- `DOCUMENT` when finalized (depth=3)
- `CLOSING_PACKAGE` when finalized (depth=4)
- `BILLING_PERIOD` when locked (depth=3)

Snapshots are canonical JSON:

- Nodes sorted by `(node_type, ref_id)`
- Edges sorted by `(edge_type, src, dst)`
- `meta` serialized with stable key order

`snapshot_hash = sha256(canonical_json)`

## Trace queries

Example trace for a document:

```
GET /v1/admin/legal-graph/trace/DOCUMENT/{document_id}?depth=3
```

Example trace payload (trimmed):

```json
{
  "nodes": [
    {"node_type": "DOCUMENT", "ref_id": "doc-1"},
    {"node_type": "INVOICE", "ref_id": "inv-1"}
  ],
  "edges": [
    {
      "edge_type": "GENERATED_FROM",
      "src": {"node_type": "DOCUMENT", "ref_id": "doc-1"},
      "dst": {"node_type": "INVOICE", "ref_id": "inv-1"},
      "meta": null
    }
  ],
  "layers": [
    [{"node_type": "DOCUMENT", "ref_id": "doc-1"}],
    [{"node_type": "INVOICE", "ref_id": "inv-1"}]
  ]
}
```

Example node lookup:

```
GET /v1/admin/legal-graph/nodes/DOCUMENT/{document_id}
```

## Completeness checks

Billing period completeness requires:

- Invoice document present
- Act document present
- Reconciliation document present
- Closing package present
- Documents finalized or acknowledged
- Closing package finalized or acknowledged
- Confirmed accounting export (if exports exist for the period)

Endpoint:

```
GET /v1/admin/legal-graph/completeness/billing-period/{period_id}
```

## Snapshot example

```
GET /v1/admin/legal-graph/snapshot/BILLING_PERIOD/{period_id}
```

Response contains:

- `snapshot_hash`
- `nodes_count`, `edges_count`
- `snapshot_json` (canonical graph payload)
