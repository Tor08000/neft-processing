# Accounting Exports Contract (v1)

## Overview
This document defines the export contract for accounting integrations with 1C (CSV) and SAP/middleware (JSON).

Exports are generated **only** for finalized/locked billing periods. Once generated, the payload is deterministic and
idempotent: identical input produces identical bytes and the same SHA-256 checksum.

## Canonical model: `AccountingEntry`
Source of truth for all formats: `platform/processing-core/app/services/accounting_export/canonical.py`.

Fields:
- `entry_id` — deterministic SHA-256 id (see rules below)
- `batch_id`, `export_type` (`CHARGES`, `SETTLEMENT`)
- `tenant_id`, `client_id`, `currency`
- `posting_date`, `period_from`, `period_to`
- `document_type`, `document_id`, `document_number`
- `amount_gross`, `vat_rate`, `vat_amount`, `amount_net` (minor units)
- `counterparty_ref`, `contract_ref`, `cost_center`
- `source_type`, `source_id`, `external_ref`, `provider`
- `meta`

### `entry_id` rules
`entry_id` is computed as SHA-256 of a canonical JSON payload of stable fields:
- document identifiers, dates, amounts, source identifiers
- counterparty/contract references, `meta`

Same input → same `entry_id`.

## Export types
- **CHARGES** — invoices for billing period → accounting “Accrual” document
- **SETTLEMENT** — payments/credits/refunds for settlement period → “Receipt/Adjustment” document

## CSV format (1C)
Delimiter: `;`

Encoding: UTF-8

Minor units: integer values, `minor_units=2` indicated in preamble.

### CSV preamble
First line (preamble):
```
# minor_units=2
```

### CHARGES columns
```
batch_id;entry_id;tenant_id;client_id;posting_date;period_from;period_to;document_type;document_id;document_number;currency;amount_gross;vat_amount;amount_net;contract_ref;counterparty_ref
```

### SETTLEMENT columns
```
batch_id;entry_id;tenant_id;client_id;posting_date;document_id;document_number;source_type;source_id;provider;external_ref;currency;amount_gross;charge_period_from;charge_period_to;contract_ref;counterparty_ref
```

### CSV example (CHARGES)
```
# minor_units=2
batch_id;entry_id;tenant_id;client_id;posting_date;period_from;period_to;document_type;document_id;document_number;currency;amount_gross;vat_amount;amount_net;contract_ref;counterparty_ref
9cce...;9baf...;1;client-1;2024-01-31;2024-01-01;2024-01-31;INVOICE;inv-1;INV-001;RUB;120000;20000;100000;;
```

## JSON format (SAP / middleware)
```
{
  "meta": {
    "batch_id": "...",
    "export_type": "CHARGES",
    "format": "JSON",
    "generated_at": "2024-01-31T00:00:00+00:00",
    "records_count": 123,
    "sha256": "<sha256 of canonical entries>"
  },
  "entries": [
    {
      "entry_id": "...",
      "batch_id": "...",
      "export_type": "CHARGES",
      "tenant_id": 1,
      "client_id": "client-1",
      "currency": "RUB",
      "posting_date": "2024-01-31",
      "period_from": "2024-01-01",
      "period_to": "2024-01-31",
      "document_type": "INVOICE",
      "document_id": "inv-1",
      "document_number": "INV-001",
      "amount_gross": 120000,
      "vat_rate": null,
      "vat_amount": 20000,
      "amount_net": 100000,
      "counterparty_ref": null,
      "contract_ref": null,
      "cost_center": null,
      "source_type": null,
      "source_id": null,
      "external_ref": null,
      "provider": null,
      "meta": {}
    }
  ]
}
```

## Metadata file (`metadata.json`)
For every export file, a companion metadata object is generated and uploaded to S3:

```
{
  "schema_version": "1.0",
  "batch_id": "...",
  "period_id": "...",
  "export_type": "CHARGES",
  "format": "CSV",
  "records_count": 123,
  "object_key": "...",
  "object_key_metadata": "...",
  "sha256": "<sha256 of export file>",
  "sha256_metadata": "<sha256 of metadata payload without sha256_metadata>",
  "generated_at": "...",
  "timestamps": {
    "created_at": "...",
    "generated_at": "...",
    "uploaded_at": "..."
  },
  "minor_units": 2
}
```

## Idempotency rules
- `create` with the same `(period_id, export_type, format, version)` returns the same batch.
- Re-generating with the same input produces identical bytes and identical SHA-256 checksum.

## ERP confirmation (ACK/CONFIRM)
Admin endpoint:
```
POST /v1/admin/accounting/exports/{batch_id}/confirm
```
Payload:
```
{
  "erp_system": "1C",
  "erp_import_id": "import-123",
  "status": "CONFIRMED",
  "message": "optional",
  "processed_at": "2024-01-31T12:00:00+00:00"
}
```

Rules:
- `CONFIRMED` sets batch state to `CONFIRMED`.
- `REJECTED` sets batch state to `FAILED` and stores `error_message`.
- Repeating the same `erp_import_id` is idempotent.
- Different `erp_import_id` for an already confirmed batch returns 409.
